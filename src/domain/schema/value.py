from typing import List, Dict, Any
from sqlalchemy import text
from src.core.database import get_query_db
import asyncio
import threading
import re
from openai import OpenAI
from pymilvus import MilvusClient, DataType

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
    基于 Milvus 实现。
    """
    def __init__(self, project_id: int = None):
        self.project_id = project_id
        self.client = None
        self.openai_client = None
        self.collection_name = f"db_values_{self.project_id}" if self.project_id else "db_values_default"
        self._init_vector_db()

    def _init_vector_db(self):
        try:
            # 初始化 OpenAI 客户端 (用于 Embedding)
            try:
                self.openai_client = OpenAI(
                    api_key=settings.OPENAI_API_KEY,
                    base_url=settings.OPENAI_API_BASE
                )
            except Exception as e:
                print(f"Warning: Failed to initialize OpenAI client for ValueSearcher: {e}")
                return

            # 初始化 Milvus 客户端
            try:
                uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
                print(f"ValueSearcher: Connecting to Milvus at {uri}...")
                self.client = MilvusClient(
                    uri=uri,
                    token=settings.MILVUS_TOKEN,
                    db_name=settings.MILVUS_DB_NAME
                )
                
                # 检查并创建集合
                if not self.client.has_collection(self.collection_name):
                    print(f"Creating Milvus collection: {self.collection_name}")
                    # 定义 Schema
                    schema = MilvusClient.create_schema(
                        auto_id=False,
                        enable_dynamic_field=True,
                    )
                    # 字段定义
                    # ID 格式: table.col.hash(val) (string)
                    schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=512, is_primary=True)
                    schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=settings.EMBEDDING_DIM)
                    schema.add_field(field_name="value", datatype=DataType.VARCHAR, max_length=65535)
                    schema.add_field(field_name="table", datatype=DataType.VARCHAR, max_length=256)
                    schema.add_field(field_name="column", datatype=DataType.VARCHAR, max_length=256)
                    
                    # 索引参数
                    index_params = self.client.prepare_index_params()
                    index_params.add_index(
                        field_name="vector",
                        index_type="AUTOINDEX",
                        metric_type="COSINE" 
                    )
                    
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        schema=schema,
                        index_params=index_params
                    )
                    print(f"Milvus collection {self.collection_name} created successfully.")
                
                self.client.load_collection(self.collection_name)
                print(f"ValueSearcher initialized for collection: {self.collection_name}")
                
            except Exception as e:
                print(f"Warning: Failed to initialize Milvus for ValueSearcher: {e}")
                self.client = None
                
        except Exception as e:
            print(f"Failed to init ValueSearcher vector db: {e}")

    def _embed(self, text: str) -> List[float]:
        if not self.openai_client:
            return []
        try:
            resp = self.openai_client.embeddings.create(
                input=[text],
                model=settings.EMBEDDING_MODEL
            )
            return resp.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return []

    async def index_values(self, tables: List[str] = None, limit_per_column: int = 1000):
        """
        扫描数据库中的文本列，构建值索引。
        :param tables: 指定要扫描的表名列表，如果为 None 则扫描所有表。
        :param limit_per_column: 每列采样的最大唯一值数量。
        """
        if not self.client:
            return

        try:
            query_db = get_query_db(self.project_id)
            # 获取所有表结构
            inspector_json = await asyncio.to_thread(query_db.inspect_schema)
            import json
            schema = json.loads(inspector_json)
            
            target_tables = tables if tables else schema.keys()
            
            # 批量收集数据
            batch_data = []
            
            # 使用异步连接
            async with query_db.async_engine.connect() as conn:
                for table_full_name in target_tables:
                    # schema keys are "db.table"
                    if table_full_name not in schema: continue
                    
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
                            sql = text(f"SELECT DISTINCT {col} FROM {table_name} WHERE {col} IS NOT NULL LIMIT {limit_per_column}")
                            result = await conn.execute(sql)
                            rows = result.fetchall()
                            values = [str(row[0]) for row in rows]
                            
                            for val in values:
                                if len(val) < 2 or len(val) > 100: continue # 过滤过短或过长的值
                                
                                vector = self._embed(val)
                                if not vector: continue

                                # ID: table.col.hash(val)
                                doc_id = f"{table_full_name}.{col}.{hash(val)}"
                                
                                batch_data.append({
                                    "id": doc_id,
                                    "vector": vector,
                                    "value": val,
                                    "table": table_full_name,
                                    "column": col
                                })
                                
                        except Exception as e:
                            print(f"Error indexing {table_full_name}.{col}: {e}")

            if batch_data:
                print(f"Adding {len(batch_data)} values to vector index...")
                batch_size = 500
                
                for i in range(0, len(batch_data), batch_size):
                    batch = batch_data[i:i+batch_size]
                    self.client.upsert(
                        collection_name=self.collection_name,
                        data=batch
                    )
                print("Value indexing complete.")
                
        except Exception as e:
            print(f"Value indexing failed: {e}")

    def search_similar_values(self, query_value: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        搜索与 query_value 最相似的数据库真实值。
        """
        if not self.client:
            return []
            
        try:
            vector = self._embed(query_value)
            if not vector:
                return []

            results = self.client.search(
                collection_name=self.collection_name,
                data=[vector],
                limit=limit,
                output_fields=["value", "table", "column"],
                search_params={"metric_type": "COSINE"}
            )
            
            matches = []
            if results and results[0]:
                for match in results[0]:
                    entity = match['entity']
                    matches.append({
                        "value": entity["value"],
                        "table": entity["table"],
                        "column": entity["column"],
                        "score": match['distance'] # COSINE similarity
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
