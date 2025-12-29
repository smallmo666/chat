import os
import random
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlmodel import SQLModel, create_engine as create_sqlmodel_engine, Session, select
from dotenv import load_dotenv
import json
import re
from src.models import DataSource, Project, AuditLog

load_dotenv()

class QueryDatabase:
    """
    Query Database Instance.
    Instantiated per-request or per-context based on DataSource configuration.
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
            raise ValueError("DataSource configuration is required. Default fallback is disabled.")
        
        # Construct connection string based on type
        if self.type == "postgresql":
            self.connection_string = f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}?client_encoding=utf8"
        elif self.type == "mysql":
            self.connection_string = f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"
        else:
            # Default to postgres
            self.connection_string = f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}?client_encoding=utf8"
        
        try:
            self.engine = create_engine(self.connection_string)
            print(f"Connected to Query Database: {self.host}:{self.port}/{self.dbname}")
        except Exception as e:
            print(f"Query Database Connection Failed: {e}")
            raise e

    def _get_databases(self):
        """Helper to get list of available databases"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT datname FROM pg_database WHERE datistemplate = false AND datname != 'postgres'"))
                databases = [row[0] for row in result]
                # Filter system/hidden dbs
                return [db for db in databases if not db.startswith('.') and not db.startswith('pg_')]
        except Exception as e:
            print(f"Error listing databases: {e}")
            return []

    def inspect_schema(self, scope_config: dict = None) -> str:
        """
        Inspect table structures.
        If scope_config is provided, only inspect specified tables/schemas.
        """
        schema_info = {}
        
        # Logic to determine target databases/schemas
        target_dbs = []
        target_tables = None
        
        if scope_config:
            # Example scope_config: {"databases": ["db1"], "tables": ["db1.t1"]}
            if "databases" in scope_config:
                target_dbs = scope_config["databases"]
            if "tables" in scope_config:
                target_tables = set(scope_config["tables"])
        
        if not target_dbs:
            # Fallback to auto-discovery if no specific scope
            target_dbs = self._get_databases()
            # Prioritize interesting domains for demo stability if list is huge
            priority_dbs = ['households', 'virtual_idol', 'sports_events', 'solar_panel', 'transportation']
            final_dbs = [db for db in target_dbs if db in priority_dbs]
            if not final_dbs and target_dbs:
                final_dbs = target_dbs[:5]
            target_dbs = final_dbs

        print(f"QueryDB: Inspecting databases: {target_dbs}")

        # 遍历每个数据库并获取表结构
        for db_name in target_dbs:
            try:
                # 动态构建连接字符串
                if self.type == "postgresql":
                    db_connection_str = f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{db_name}?client_encoding=utf8"
                else:
                    db_connection_str = self.connection_string # MySQL usually has 1 DB context
                    
                db_engine = create_engine(db_connection_str)
                inspector = inspect(db_engine)
                
                # 假设每个数据库主要使用 public schema
                tables = inspector.get_table_names(schema='public')
                
                for table_name in tables:
                    # 使用 "dbname.tablename" 格式
                    full_table_name = f"{db_name}.{table_name}"
                    
                    # Filter by scope if defined
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
                print(f"Error inspecting database {db_name}: {e}")
            
        return json.dumps(schema_info, ensure_ascii=False)

    def run_query(self, query: str) -> dict:
        """
        在 querydb 上执行 SQL 查询。
        自动检测是否需要切换数据库上下文。
        返回字典: {"markdown": str, "json": str, "error": str}
        """
        try:
            target_db = None
            modified_query = query
            
            # Pattern: FROM/JOIN "db"."table" or db.table
            match = re.search(r'(?:FROM|JOIN)\s+(?:["`]?([\w]+)["`]?\.)["`]?([\w]+)["`]?', query, re.IGNORECASE)
            if match:
                potential_db = match.group(1)
                # Check if this potential_db is actually a valid database
                # Optimistically assume yes for Postgres cross-db query simulation
                target_db = potential_db
                print(f"QueryDB: Switching context to database '{target_db}'")
                # Robust replacement: replace `potential_db.` with empty string
                modified_query = re.sub(rf'\b{re.escape(potential_db)}\.', '', query)
            
            # Determine engine to use
            if target_db and self.type == "postgresql":
                db_connection_str = f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{target_db}?client_encoding=utf8"
                engine_to_use = create_engine(db_connection_str)
            else:
                engine_to_use = self.engine

            # 使用显式连接管理，确保事务边界
            with engine_to_use.connect() as conn:
                try:
                    df = pd.read_sql(modified_query, conn)
                    if target_db:
                        engine_to_use.dispose()
                        
                    if df.empty:
                        return {
                            "markdown": "查询执行成功，但结果为空。",
                            "json": "[]",
                            "error": None
                        }
                    return {
                        "markdown": df.to_markdown(index=False),
                        "json": df.to_json(orient='records', force_ascii=False),
                        "error": None
                    }
                except Exception as query_error:
                    conn.rollback()
                    if target_db:
                        engine_to_use.dispose()
                    error_msg = f"执行查询时出错: {query_error}"
                    return {
                        "markdown": error_msg,
                        "json": None,
                        "error": error_msg
                    }
        except Exception as e:
            error_msg = f"数据库连接错误: {e}"
            return {
                "markdown": error_msg,
                "json": None,
                "error": error_msg
            }


class AppDatabase:
    """
    Application Database.
    Manages Metadata (DataSources, Projects, AuditLogs) via SQLModel.
    Supports PostgreSQL and MySQL based on configuration.
    """
    def __init__(self):
        self.host = os.getenv("APP_DB_HOST")
        self.port = int(os.getenv("APP_DB_PORT", "5432"))
        self.user = os.getenv("APP_DB_USER")
        self.password = os.getenv("APP_DB_PASSWORD")
        self.dbname = os.getenv("APP_DB_NAME")
        
        # Determine DB type and construct connection string
        if self.port == 3306:
            # MySQL
            self.connection_string = f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"
        else:
            # Default to PostgreSQL
            self.connection_string = f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"
        
        try:
            # create_engine args: pool_recycle is good for MySQL to prevent connection timeout
            connect_args = {}
            if self.port == 3306:
                connect_args["charset"] = "utf8mb4"
                
            self.engine = create_sqlmodel_engine(
                self.connection_string, 
                pool_pre_ping=True, # Auto-reconnect
                pool_recycle=3600
            )
            print(f"Connected to App Database: {self.host}:{self.port}/{self.dbname}")
            self.init_metadata_tables()
        except Exception as e:
            print(f"App Database Connection Failed: {e}")
            raise e

    def init_metadata_tables(self):
        """
        Initialize SQLModel tables.
        """
        try:
            SQLModel.metadata.create_all(self.engine)
            print("AppDB: Metadata tables initialized.")
        except Exception as e:
            print(f"AppDB: Failed to init metadata tables: {e}")

    def get_session(self):
        return Session(self.engine)

    # --- Legacy methods for backward compatibility (can be refactored later) ---
    def save_schema_info(self, schema_content: str):
        # We might not need this anymore if we persist schema in Project scope or cache
        pass

    def get_stored_schema_info(self) -> str:
        # Should return default or project specific schema
        return "{}"


class DatabaseProvider:
    """
    Database Provider for Dependency Injection.
    """
    def __init__(self):
        self._app_db = None
    
    def get_app_db(self) -> AppDatabase:
        if not self._app_db:
            self._app_db = AppDatabase()
        return self._app_db
    
    def get_query_db(self, project_id: int = None) -> QueryDatabase:
        """
        Get QueryDatabase instance.
        If project_id is provided, load config from AppDB.
        Otherwise, use default env config.
        """
        if project_id:
            app_db = self.get_app_db()
            with app_db.get_session() as session:
                project = session.get(Project, project_id)
                if project:
                    datasource = session.get(DataSource, project.data_source_id)
                    if datasource:
                        return QueryDatabase(datasource)
        
        # Default / Fallback
        return QueryDatabase()

# Global instance
_db_provider = DatabaseProvider()

def get_db_provider() -> DatabaseProvider:
    return _db_provider

def get_app_db() -> AppDatabase:
    return get_db_provider().get_app_db()

def get_query_db(project_id: int = None) -> QueryDatabase:
    return get_db_provider().get_query_db(project_id)
