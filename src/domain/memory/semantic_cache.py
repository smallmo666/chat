import os
import hashlib
from typing import Optional, List
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
import json

class SemanticCache:
    """
    基于向量相似度的语义缓存。
    使用 ChromaDB 存储 (Question Vector, SQL)。
    """
    
    def __init__(self, project_id: int = None):
        self.project_id = project_id or "default"
        # 使用本地持久化
        self.client = chromadb.PersistentClient(path="./chroma_db")
        
        # 每个 Project 一个 Collection
        collection_name = f"sql_cache_project_{self.project_id}"
        self.collection = self.client.get_or_create_collection(name=collection_name)
        
        # 加载 Embedding 模型 (第一次运行会下载，建议生产环境预下载或使用 API)
        # 使用轻量级模型以保证速度
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        
    def _embed(self, text: str) -> List[float]:
        return self.encoder.encode(text).tolist()

    def check(self, query: str, threshold: float = 0.9) -> Optional[str]:
        """
        检查缓存。如果存在相似度 > threshold 的查询，返回对应的 SQL。
        """
        query_embedding = self._embed(query)
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=1,
            include=["metadatas", "distances"]
        )
        
        if not results["ids"][0]:
            return None
            
        # Cosine Distance: 0 = identical, 1 = opposite (roughly)
        # Chroma returns distance. For cosine, similarity = 1 - distance (if normalized)
        # Default metric is L2 usually, let's assume we can calibrate.
        # Actually for 'all-MiniLM-L6-v2' and default chroma (L2), lower is better.
        # Let's verify similarity.
        
        distance = results["distances"][0][0]
        
        # Empirical threshold for L2 with normalized vectors (MiniLM produces normalized)
        # 0.2 distance is roughly 0.8 similarity
        if distance < (1 - threshold): 
            sql = results["metadatas"][0][0].get("sql")
            return sql
            
        return None

    def add(self, query: str, sql: str):
        """
        添加缓存条目。
        """
        # 生成 ID
        id = hashlib.md5(query.encode()).hexdigest()
        
        self.collection.upsert(
            ids=[id],
            embeddings=[self._embed(query)],
            metadatas=[{"sql": sql, "query": query}]
        )

# Factory/Singleton
_cache_instances = {}

def get_semantic_cache(project_id: int = None) -> SemanticCache:
    key = str(project_id)
    if key not in _cache_instances:
        _cache_instances[key] = SemanticCache(project_id)
    return _cache_instances[key]
