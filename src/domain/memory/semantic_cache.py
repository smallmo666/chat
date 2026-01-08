import hashlib
import threading
from typing import Optional, List
from openai import OpenAI
from pymilvus import MilvusClient, DataType
from src.core.config import settings

class SemanticCache:
    """
    基于向量相似度的语义缓存。
    使用 Milvus 存储 (Question Vector, SQL)。
    """
    
    def __init__(self, project_id: int = None):
        self.project_id = project_id or "default"
        self.enabled = settings.ENABLE_SEMANTIC_CACHE
        self.client = None
        self.collection_name = f"sql_cache_project_{self.project_id}"
        self.openai_client = None
        
        if not self.enabled:
            print("Info: Semantic Cache is disabled.")
            return

        # 初始化 OpenAI 客户端 (用于 Embedding)
        try:
            self.openai_client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE
            )
        except Exception as e:
            print(f"Warning: Failed to initialize OpenAI client for SemanticCache: {e}")
            self.enabled = False
            return

        # 初始化 Milvus 客户端
        try:
            uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
            print(f"Connecting to Milvus at {uri}...")
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
                # 使用 MD5(query) 作为 ID
                schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=128, is_primary=True)
                schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=settings.EMBEDDING_DIM)
                schema.add_field(field_name="sql", datatype=DataType.VARCHAR, max_length=65535)
                schema.add_field(field_name="query", datatype=DataType.VARCHAR, max_length=65535)
                
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
            print("SemanticCache initialized successfully.")
            
        except Exception as e:
            print(f"Warning: Failed to initialize Milvus for SemanticCache: {e}")
            self.enabled = False
            self.client = None
        
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

    def check(self, query: str, threshold: float = 0.9) -> Optional[str]:
        """
        检查缓存。如果存在相似度 > threshold 的查询，返回对应的 SQL。
        """
        if not self.enabled or not self.client:
            return None

        query_embedding = self._embed(query)
        if not query_embedding:
            return None
        
        try:
            results = self.client.search(
                collection_name=self.collection_name,
                data=[query_embedding],
                limit=1,
                output_fields=["sql", "query"],
                search_params={"metric_type": "COSINE"}
            )
            
            if not results or not results[0]:
                return None
                
            match = results[0][0]
            distance = match['distance'] # COSINE similarity
            
            # Milvus COSINE: range [-1, 1], larger is better
            if distance >= threshold:
                sql = match['entity'].get('sql')
                print(f"Semantic Cache Hit! Similarity: {distance:.4f}")
                return sql
                
        except Exception as e:
            print(f"Error checking semantic cache: {e}")
            
        return None

    def add(self, query: str, sql: str):
        """
        添加缓存条目。
        """
        if not self.enabled or not self.client:
            return

        try:
            query_embedding = self._embed(query)
            if not query_embedding:
                return

            id = hashlib.md5(query.encode()).hexdigest()
            
            data = [{
                "id": id,
                "vector": query_embedding,
                "sql": sql,
                "query": query
            }]
            
            self.client.upsert(
                collection_name=self.collection_name,
                data=data
            )
        except Exception as e:
            print(f"Error adding to semantic cache: {e}")

    def delete(self, query: str, threshold: float = 0.95):
        """
        删除与 query 相似的缓存条目（用于负反馈处理）。
        """
        if not self.enabled or not self.client:
            return

        try:
            query_embedding = self._embed(query)
            if not query_embedding:
                return
            
            # 查找非常相似的记录
            results = self.client.search(
                collection_name=self.collection_name,
                data=[query_embedding],
                limit=1,
                output_fields=["id"],
                search_params={"metric_type": "COSINE"}
            )
            
            if not results or not results[0]:
                return
                
            match = results[0][0]
            distance = match['distance']
            
            if distance >= threshold:
                target_id = match['id']
                print(f"Removing semantic cache entry {target_id} due to negative feedback. Similarity: {distance}")
                self.client.delete(
                    collection_name=self.collection_name,
                    ids=[target_id]
                )
        except Exception as e:
            print(f"Error deleting from semantic cache: {e}")

# Factory/Singleton
_cache_instances = {}
_cache_lock = threading.Lock()

def get_semantic_cache(project_id: int = None) -> SemanticCache:
    key = str(project_id)
    if key not in _cache_instances:
        with _cache_lock:
            if key not in _cache_instances:
                _cache_instances[key] = SemanticCache(project_id)
    return _cache_instances[key]
