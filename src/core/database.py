import pandas as pd
import hashlib
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.pool import  AsyncAdaptedQueuePool
from sqlmodel import SQLModel, create_engine as create_sqlmodel_engine, Session
from dotenv import load_dotenv
import json
import re
import sqlglot
from src.core.models import DataSource, Project
from src.core.config import settings
from src.core.redis_client import get_redis_client
from src.core.metrics import QueryMetrics
import time

load_dotenv()

class QueryDatabase:
    """
    查询数据库实例。
    主要支持异步 (Async) 执行。保留有限的同步方法用于 Schema 检查 (inspector 尚不支持完全异步)。
    """
    def __init__(self, datasource: DataSource = None):
        if datasource:
            self.host = datasource.host
            self.port = datasource.port
            self.user = datasource.user
            self.password = datasource.password
            self.dbname = datasource.dbname
            self.type = datasource.type
        else:
            raise ValueError("必须提供 DataSource 配置。默认回退已禁用。")
        
        # 根据类型构建连接字符串
        # 如果 dbname 为空，使用默认维护库
        self.effective_dbname = self.dbname or ("postgres" if self.type == "postgresql" else "mysql")
        
        if self.type == "postgresql":
            # 异步
            self.async_connection_string = f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.effective_dbname}"
            # 同步 (仅用于 Schema Inspector)
            self._sync_conn_str = f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.effective_dbname}?client_encoding=utf8"
        elif self.type == "mysql":
            self.async_connection_string = f"mysql+aiomysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.effective_dbname}"
            self._sync_conn_str = f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.effective_dbname}"
        else:
            # 默认为 postgres
            self.async_connection_string = f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.effective_dbname}"
            self._sync_conn_str = f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.effective_dbname}?client_encoding=utf8"
        
        try:
            # 异步引擎 (用于高性能查询执行)
            # 生产环境配置: 使用连接池
            self.async_engine = create_async_engine(
                self.async_connection_string, 
                pool_pre_ping=True,
                poolclass=AsyncAdaptedQueuePool,
                pool_size=settings.QUERY_POOL_SIZE,
                max_overflow=settings.QUERY_MAX_OVERFLOW,
                pool_recycle=settings.QUERY_POOL_RECYCLE
            )
            
            # 多数据库支持：缓存不同数据库的 Engine
            # 如果 dbname 指定了，默认 engine 就是它；如果没指定，default engine 是 postgres/mysql 维护库
            self._db_engines = {"default": self.async_engine}
            if self.dbname:
                self._db_engines[self.dbname] = self.async_engine
            
            print(f"已连接到查询数据库 (Async): {self.host}:{self.port}/{self.effective_dbname}")
        except Exception as e:
            print(f"查询数据库连接失败: {e}")
            raise e

    def _get_engine_for_db(self, db_name: str) -> AsyncEngine:
        """
        获取或创建指定数据库的 AsyncEngine。
        """
        if db_name in self._db_engines:
            return self._db_engines[db_name]
            
        print(f"QueryDatabase: Initializing engine for target database: {db_name}")
        
        # 构建新的连接字符串 (复用 host, user, password, port)
        if self.type == "postgresql":
            conn_str = f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{db_name}"
        elif self.type == "mysql":
            conn_str = f"mysql+aiomysql://{self.user}:{self.password}@{self.host}:{self.port}/{db_name}"
        else:
            raise ValueError(f"Unsupported database type for routing: {self.type}")
            
        try:
            engine = create_async_engine(
                conn_str,
                pool_pre_ping=True,
                poolclass=AsyncAdaptedQueuePool,
                pool_size=settings.ROUTE_POOL_SIZE,
                max_overflow=settings.ROUTE_MAX_OVERFLOW,
                pool_recycle=settings.QUERY_POOL_RECYCLE
            )
            self._db_engines[db_name] = engine
            return engine
        except Exception as e:
            print(f"Failed to connect to target database {db_name}: {e}")
            raise e

    def _get_sync_engine(self):
        """辅助方法：按需创建临时同步引擎（仅用于 Inspector）"""
        from sqlalchemy import create_engine
        return create_engine(self._sync_conn_str)

    def _get_databases(self):
        """辅助方法：获取可用数据库列表 (同步)"""
        engine = self._get_sync_engine()
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT datname FROM pg_database WHERE datistemplate = false AND datname != 'postgres'"))
                databases = [row[0] for row in result]
                # 过滤系统/隐藏数据库
                return [db for db in databases if not db.startswith('.') and not db.startswith('pg_')]
        except Exception as e:
            print(f"获取数据库列表出错: {e}")
            return []
        finally:
            engine.dispose()

    def inspect_schema(self, scope_config: dict = None, project_id: int = None) -> str:
        """
        检查表结构。
        使用临时同步连接，因为 SQLAlchemy Inspector 目前主要支持同步 API。
        支持 Redis 缓存。
        """
        # Try to retrieve from Redis cache if project_id is provided
        cache_key = None
        redis_client = None
        if project_id:
            try:
                redis_client = get_redis_client()
                # Create a unique hash for the scope config
                scope_str = json.dumps(scope_config, sort_keys=True) if scope_config else "full"
                scope_hash = hashlib.md5(scope_str.encode()).hexdigest()
                cache_key = f"t2s:v1:schema:{project_id}:{scope_hash}"
                
                cached_schema = redis_client.get(cache_key)
                if cached_schema:
                    print(f"QueryDB: Schema cache hit for {cache_key}")
                    return cached_schema
            except Exception as e:
                print(f"Redis cache error: {e}")

        schema_info = {}
        
        # 确定目标数据库/Schema 的逻辑
        target_dbs = []
        target_tables = None
        
        if scope_config:
            if "databases" in scope_config:
                target_dbs = scope_config["databases"]
            if "tables" in scope_config:
                target_tables = set(scope_config["tables"])
        
        if not target_dbs:
            # 如果配置中未指定，或者 dbname 为空，尝试获取所有数据库
            # 注意：如果 dbname 有值，我们通常只 inspect 该库，除非 scope_config 明确扩大了范围
            # 但这里为了向后兼容，如果 scope_config 没填，我们之前的行为是 inspect 所有库 (通过 priority list)
            # 现在的逻辑：
            # 1. 如果 scope_config 有 databases，用它。
            # 2. 否则，如果 dbname 有值，只 inspect dbname。
            # 3. 如果 dbname 为空，inspect 所有库 (filtered)。
            
            if self.dbname:
                target_dbs = [self.dbname]
            else:
                target_dbs = self._get_databases()
                # 移除过滤策略，全量返回所有非系统库
                # priority_dbs = ['households', 'virtual_idol', 'sports_events', 'solar_panel', 'transportation']
                # final_dbs = [db for db in target_dbs if db in priority_dbs]
                # if not final_dbs and target_dbs:
                #     final_dbs = target_dbs[:5]
                # target_dbs = final_dbs

        print(f"QueryDB: 正在检查数据库: {target_dbs}")

        # 遍历每个数据库并获取表结构
        from sqlalchemy import create_engine
        
        for db_name in target_dbs:
            try:
                # 动态构建连接字符串
                if self.type == "postgresql":
                    # 使用 psycopg2 进行同步连接，确保 client_encoding=utf8
                    # 关键修改：默认不指定 dbname 连接到 postgres 库，以便跨库查询
                    # 但 inspect 通常需要连接到具体库。如果 target_dbs 包含多个库，我们需要循环连接。
                    # 这里 logic 是：外层 loop 遍历 db_name，所以这里连接到 db_name 是对的。
                    db_connection_str = f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{db_name}?client_encoding=utf8"
                else:
                    db_connection_str = self._sync_conn_str # MySQL 通常只有一个 DB 上下文
                    
                db_engine = create_engine(db_connection_str)
                inspector = inspect(db_engine)
                
                # 假设每个数据库主要使用 public schema
                tables = inspector.get_table_names(schema='public')
                
                for table_name in tables:
                    full_table_name = f"{db_name}.{table_name}"
                    
                    if target_tables and full_table_name not in target_tables:
                        continue
                    
                    columns = inspector.get_columns(table_name, schema='public')
                    
                    try:
                        table_comment = inspector.get_table_comment(table_name, schema='public')
                        comment_text = table_comment.get('text', '') if table_comment else ""
                    except:
                        comment_text = ""
                        
                    schema_info[full_table_name] = {
                        "columns": [{"name": col["name"], "type": str(col["type"]), "comment": col.get("comment", "")} for col in columns],
                        "comment": comment_text
                    }
                
                db_engine.dispose()
                
            except Exception as e:
                print(f"检查数据库 {db_name} 时出错: {e}")
            
        result_json = json.dumps(schema_info, ensure_ascii=False)
        
        # Save to Redis cache
        if cache_key and redis_client:
            try:
                redis_client.setex(cache_key, settings.REDIS_SCHEMA_TTL, result_json)
                print(f"QueryDB: Schema cached to Redis: {cache_key}")
            except Exception as e:
                print(f"Failed to save schema to Redis: {e}")
                
        return result_json

    async def run_query_async(self, query: str, project_id: int = None) -> dict:
        """
        使用 AsyncEngine 异步执行 SQL 查询。
        支持简单的多数据库路由 (基于 'dbname.table' 命名约定)。
        支持 SQL 结果缓存。
        """
        if settings.ENV == "development":
            print(f"DEBUG: QueryDatabase.run_query_async - Executing: {query}")
        
        # Check Query Cache
        cache_key = None
        redis_client = None
        if project_id:
            try:
                redis_client = get_redis_client()
                query_hash = hashlib.md5(query.strip().lower().encode()).hexdigest()
                cache_key = f"t2s:v1:sql:{project_id}:{query_hash}"
                
                cached_result = redis_client.get(cache_key)
                if cached_result:
                    print(f"DEBUG: SQL Cache Hit for {cache_key}")
                    return json.loads(cached_result)
            except Exception as e:
                print(f"Redis cache check error: {e}")
                
        try:
            modified_query = query
            target_engine = self.async_engine
            qm = QueryMetrics()
            t0 = time.time()

            try:
                ast = sqlglot.parse_one(query)
                db_name = None
                for table in ast.find_all(sqlglot.exp.Table):
                    qualifiers = table.parts
                    if len(qualifiers) >= 2:
                        candidate = qualifiers[-2]
                        if candidate.lower() != "public":
                            db_name = candidate
                            break
                if db_name:
                    print(f"DEBUG: Routing(sqlglot) - Target database: {db_name}")
                    target_engine = self._get_engine_for_db(db_name)
                    def strip_db(sql: str, db: str) -> str:
                        pattern = rf'\b{re.escape(db)}\.'
                        return re.sub(pattern, '', sql)
                    modified_query = strip_db(query, db_name)
            except Exception as e:
                print(f"sqlglot parse failed, fallback to default routing: {e}")

            if "limit" not in modified_query.lower() and "count(" not in modified_query.lower():
                modified_query = modified_query.strip().rstrip(';') + f" LIMIT {settings.DEFAULT_ROW_LIMIT}"
                print(f"DEBUG: Auto LIMIT applied in run_query_async: {modified_query}")

            print(f"DEBUG: QueryDatabase.run_query_async - Connecting...")
            async with target_engine.connect() as conn:
                print("DEBUG: QueryDatabase.run_query_async - Connected. Executing...")
                # 异步执行
                result = await conn.execute(text(modified_query))
                print("DEBUG: QueryDatabase.run_query_async - Executed. Fetching results...")
                
                rows = result.mappings().all()
                data = [dict(row) for row in rows]
                print(f"DEBUG: QueryDatabase.run_query_async - Fetched {len(data)} rows.")
                duration_ms = (time.time() - t0) * 1000.0
                try:
                    qm.record(project_id, len(data), duration_ms)
                except Exception as _:
                    pass
                
                if not data:
                    res = {
                        "markdown": "查询执行成功，但结果为空。",
                        "json": "[]",
                        "error": None
                    }
                else:
                    # 使用 pandas 进行简单的格式化 (在内存中)
                    df = pd.DataFrame(data)
                    res = {
                        "markdown": df.to_markdown(index=False),
                        "json": df.to_json(orient='records', force_ascii=False),
                        "error": None
                    }
                
                # Save to Cache
                if cache_key and redis_client:
                    try:
                        redis_client.setex(cache_key, settings.REDIS_SQL_TTL, json.dumps(res))
                    except Exception as e:
                        print(f"Failed to cache SQL result: {e}")
                
                return res
        except Exception as query_error:
            import traceback
            traceback.print_exc()
            error_msg = f"执行查询时出错: {query_error}"
            print(f"DEBUG: QueryDatabase.run_query_async - Error: {error_msg}")
            return {
                "markdown": error_msg,
                "json": None,
                "error": error_msg
            }


class AppDatabase:
    """
    应用程序数据库。
    """
    def __init__(self):
        # Use settings instead of os.getenv
        self.connection_string = settings.APP_DB_URL
        if not self.connection_string:
             # Fallback logic if needed, but settings should handle it
             pass
             
        try:
            self.engine = create_sqlmodel_engine(
                self.connection_string, 
                pool_pre_ping=True,
                pool_recycle=3600
            )
            print(f"已连接到应用数据库: {self.connection_string.split('@')[-1]}") # Hide credentials
            self.init_metadata_tables()
        except Exception as e:
            print(f"应用数据库连接失败: {e}")
            raise e

    def init_metadata_tables(self):
        try:
            SQLModel.metadata.create_all(self.engine)
            print("AppDB: 元数据表已初始化。")
        except Exception as e:
            print(f"AppDB: 初始化元数据表失败: {e}")

    def get_session(self):
        return Session(self.engine)


class DatabaseProvider:
    """
    用于依赖注入的数据库提供者。
    """
    def __init__(self):
        self._app_db = None
        self._query_engines = {} 
        # 元数据缓存：project_id -> ds_key
        # 避免每次获取 query_db 时都查询 AppDB
        self._project_ds_cache = {}
    
    def get_app_db(self) -> AppDatabase:
        if not self._app_db:
            self._app_db = AppDatabase()
        return self._app_db
    
    def get_query_db(self, project_id: int = None) -> QueryDatabase:
        """
        获取项目对应的查询数据库连接。
        必须提供 project_id。
        """
        ds_key = "default"
        
        # 1. 尝试从缓存获取 ds_key
        if project_id and project_id in self._project_ds_cache:
            ds_key = self._project_ds_cache[project_id]
            # 确认该 key 对应的 engine 是否存在
            if ds_key in self._query_engines:
                return self._query_engines[ds_key]
        
        # 2. 如果没有缓存或 Engine 不存在，查询数据库
        datasource = None
        if project_id:
            try:
                app_db = self.get_app_db()
                with app_db.get_session() as session:
                    project = session.get(Project, project_id)
                    if project:
                        datasource = session.get(DataSource, project.data_source_id)
                        if datasource:
                            ds_key = f"ds_{datasource.id}"
                            # 更新缓存
                            self._project_ds_cache[project_id] = ds_key
            except Exception as e:
                print(f"获取项目 {project_id} 的数据源出错: {e}")
        
        if not datasource:
            # 回退检查
            if ds_key != "default" and ds_key in self._query_engines:
                 # 缓存命中了 Key 但 Engine 还在
                 pass
            else:
                # 严格禁止自动回退到测试库或默认环境
                # 如果没有有效的 Project ID 或 DataSource，必须报错
                raise ValueError("无法获取查询数据库：未提供有效的 Project ID 或未找到对应的数据源配置。")

        # 3. 初始化 Engine 并缓存
        if ds_key not in self._query_engines:
             self._query_engines[ds_key] = QueryDatabase(datasource)
        
        return self._query_engines[ds_key]

    def get_test_query_db(self) -> QueryDatabase:
        """
        专门用于获取测试评估用的数据库连接。
        仅供 Evaluator 使用，严禁在生产路径调用。
        """
        ds_key = "test_eval_db"
        
        if ds_key not in self._query_engines:
             print("⚠️ 正在初始化测试查询数据库 (Test Query DB)...")
             datasource = DataSource(
                 name="test_eval_db",
                 type="postgresql", 
                 host=settings.TEST_QUERY_DB_HOST,
                 port=settings.TEST_QUERY_DB_PORT,
                 user=settings.TEST_QUERY_DB_USER,
                 password=settings.TEST_QUERY_DB_PASSWORD,
                 dbname=settings.TEST_QUERY_DB_NAME
             )
             self._query_engines[ds_key] = QueryDatabase(datasource)
             
        return self._query_engines[ds_key]

_db_provider = DatabaseProvider()

def get_db_provider() -> DatabaseProvider:
    return _db_provider

def get_app_db() -> AppDatabase:
    return get_db_provider().get_app_db()

def get_query_db(project_id: int = None) -> QueryDatabase:
    return get_db_provider().get_query_db(project_id)

def get_test_query_db() -> QueryDatabase:
    return get_db_provider().get_test_query_db()
