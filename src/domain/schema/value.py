import chromadb
from typing import List, Dict, Any
from sqlalchemy import text
from src.core.database import get_query_db
import asyncio
import threading
import re
from src.core.config import settings

def validate_identifier(name: str):
    """
    Validates that a SQL identifier (table name, column name) contains only safe characters.
    Prevents SQL injection via identifier names.
    """
    if not name:
        return False
    # Only allow alphanumeric, underscore, and dot (for schema.table)
    if not re.match(r'^[a-zA-Z0-9_.]+$', name):
        return False
    return True

class ValueSearcher:
    """
    负责对数据库中的文本列值进行索引和检索，解决实体链接问题。
    例如：用户输入 "iPhone"，数据库存储 "Apple iPhone 15"。
    """
    def __init__(self, project_id: int = None):
        self.project_id = project_id
        self._chroma_client = None
        self._collection = None
        self._init_vector_db()

    def _init_vector_db(self):
        try:
            # 远端优先（HTTP-only）
            if settings.CHROMA_USE_REMOTE:
                try:
                    self._chroma_client = chromadb.HttpClient(
                        host=settings.CHROMA_SERVER_HOST,
                        port=settings.CHROMA_SERVER_PORT
                    )
                    self._chroma_client.heartbeat()
                except Exception as e:
                    print(f"Warning: Remote ChromaDB unavailable ({e}), falling back to EphemeralClient.")
                    self._chroma_client = chromadb.EphemeralClient()
            else:
                # 持久化客户端，不可用则降级内存
                try:
                    self._chroma_client = chromadb.PersistentClient(path="./chroma_db")
                except Exception as e:
                    print(f"Warning: PersistentClient failed ({e}), falling back to EphemeralClient (In-Memory).")
                    self._chroma_client = chromadb.EphemeralClient()
            collection_name = f"db_values_{self.project_id}" if self.project_id else "db_values_default"
            try:
                self._collection = self._chroma_client.get_or_create_collection(name=collection_name)
            except Exception:
                self._chroma_client = chromadb.EphemeralClient()
                self._collection = self._chroma_client.get_or_create_collection(name=collection_name)
        except Exception as e:
            print(f"Failed to init ValueSearcher vector db: {e}")

    async def index_values(self, tables: List[str] = None, limit_per_column: int = 1000):
        """
        扫描数据库中的文本列，构建值索引。
        :param tables: 指定要扫描的表名列表，如果为 None 则扫描所有表。
        :param limit_per_column: 每列采样的最大唯一值数量。
        """
        if not self._collection:
            return

        try:
            query_db = get_query_db(self.project_id)
            # 获取所有表结构
            # 简化起见，这里假设我们能获取所有表名
            # 在实际生产中，应从 SchemaSearcher 或元数据中获取
            # 使用同步的 _get_sync_engine 或 inspect_schema
            # 这里的 inspect_schema 已经是同步包装了，可以直接用
            
            # 由于 inspect_schema 内部创建了临时 engine，我们应该尽量减少调用次数
            # 或者将其重构为异步 (目前数据库层只有 inspect_schema 是 sync 的)
            # 为了不阻塞，我们在 thread 中运行 inspect_schema
            inspector_json = await asyncio.to_thread(query_db.inspect_schema)
            import json
            schema = json.loads(inspector_json)
            
            target_tables = tables if tables else schema.keys()
            
            ids = []
            documents = []
            metadatas = []
            
            # 使用异步连接
            async with query_db.async_engine.connect() as conn:
                for table_full_name in target_tables:
                    # schema keys are "db.table"
                    if table_full_name not in schema: continue
                    
                    # 提取纯表名用于 SQL (假设在同一个库或已处理上下文)
                    # 注意：schema key 是 "db.table"，SQL 需要根据情况处理
                    # 这里简化处理，直接使用 full name 或者 split
                    # async_engine 连接的是特定库，如果跨库会比较麻烦
                    # 假设 target_tables 都在当前连接的库中
                    
                    # 尝试从 full name 解析
                    if "." in table_full_name:
                        _, table_name = table_full_name.split(".", 1)
                    else:
                        table_name = table_full_name
                        
                    # Security Check
                    if not validate_identifier(table_name):
                        print(f"Skipping potentially unsafe table name: {table_name}")
                        continue

                    # 获取该表的文本列
                    columns = schema[table_full_name]
                    if isinstance(columns, dict): columns = columns.get("columns", [])
                    
                    text_columns = [col['name'] for col in columns if 'char' in col['type'].lower() or 'text' in col['type'].lower()]
                    
                    for col in text_columns:
                        # Security Check
                        if not validate_identifier(col):
                            print(f"Skipping potentially unsafe column name: {col}")
                            continue
                            
                        print(f"Indexing values for {table_full_name}.{col}...")
                        # 查询去重值
                        try:
                            # 简单的 SQL 防注入处理：使用 text()
                            # 加上表名引用
                            # SQL Injection Protection: Validated identifiers above.
                            # Using f-string here is safer now because we validated the identifiers against a whitelist regex.
                            sql = text(f"SELECT DISTINCT {col} FROM {table_name} WHERE {col} IS NOT NULL LIMIT {limit_per_column}")
                            result = await conn.execute(sql)
                            rows = result.fetchall()
                            values = [str(row[0]) for row in rows]
                            
                            for val in values:
                                if len(val) < 2 or len(val) > 100: continue # 过滤过短或过长的值
                                
                                # ID: table.col.hash(val)
                                doc_id = f"{table_full_name}.{col}.{hash(val)}"
                                
                                ids.append(doc_id)
                                documents.append(val)
                                metadatas.append({"table": table_full_name, "column": col, "value": val})
                                
                        except Exception as e:
                            print(f"Error indexing {table_full_name}.{col}: {e}")

            if ids:
                print(f"Adding {len(ids)} values to vector index...")
                batch_size = 500
                
                def _add_batch(batch_ids, batch_docs, batch_metas):
                     self._collection.add(
                        ids=batch_ids,
                        documents=batch_docs,
                        metadatas=batch_metas
                    )

                for i in range(0, len(ids), batch_size):
                    # 使用 to_thread 异步执行同步的 collection.add
                    await asyncio.to_thread(
                        _add_batch,
                        ids[i:i+batch_size],
                        documents[i:i+batch_size],
                        metadatas[i:i+batch_size]
                    )
                print("Value indexing complete.")
                
        except Exception as e:
            print(f"Value indexing failed: {e}")

    def search_similar_values(self, query_value: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        搜索与 query_value 最相似的数据库真实值。
        """
        if not self._collection:
            return []
            
        try:
            results = self._collection.query(
                query_texts=[query_value],
                n_results=limit
            )
            
            matches = []
            if results['ids'] and len(results['ids']) > 0:
                for i, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][i]
                    matches.append({
                        "value": meta["value"],
                        "table": meta["table"],
                        "column": meta["column"],
                        "score": results['distances'][0][i] # Smaller is better for L2
                    })
            return matches
        except Exception as e:
            print(f"Value search failed: {e}")
            return []

# 全局缓存
_value_searchers = {}
_value_searcher_lock = threading.Lock() # 全局锁

def get_value_searcher(project_id: int = None):
    global _value_searchers
    key = project_id or "default"
    # Double-checked locking
    if key not in _value_searchers:
        with _value_searcher_lock:
            if key not in _value_searchers:
                _value_searchers[key] = ValueSearcher(project_id)
    return _value_searchers[key]
