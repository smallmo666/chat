import os
import threading
from src.core.config import settings

# 禁用 Mem0 遥测 (PostHog)，防止退出时报错
os.environ["MEM0_TELEMETRY"] = "False"

from mem0 import Memory

class LongTermMemory:
    """
    长期记忆管理类，使用 Mem0 + Milvus。
    """
    def __init__(self):
        
        # 基础配置
        config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": settings.OPENAI_MODEL_NAME,
                    "temperature": 0,
                    "openai_base_url": settings.OPENAI_API_BASE,
                    "api_key": settings.OPENAI_API_KEY,
                }
            },
            # 使用 OpenAI 兼容的 Embedding
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": settings.EMBEDDING_MODEL,
                    "openai_base_url": settings.OPENAI_API_BASE,
                    "api_key": settings.OPENAI_API_KEY,
                }
            },
            # Vector Store 配置 (Milvus)
            "vector_store": {
                "provider": "milvus",
                "config": {
                    "collection_name": "text2sql_memory",
                    "embedding_model_dims": settings.EMBEDDING_DIM,
                    "url": f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}",
                    "token": settings.MILVUS_TOKEN,
                    "db_name": settings.MILVUS_DB_NAME,
                }
            }
        }

        print(f"LongTermMemory: Connecting to Milvus at {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
        
        try:
            self.memory = Memory.from_config(config)
            print("LongTermMemory: Initialized successfully.")
        except Exception as e:
            print(f"LongTermMemory initialization failed: {e}")
            self.memory = None

    def add(self, user_id: str, text: str) -> bool:
        """添加记忆"""
        if self.memory:
            try:
                self.memory.add(text, user_id=user_id)
                return True
            except Exception as e:
                # 捕获可能的只读错误或连接错误，防止影响主流程
                if "read only" in str(e).lower():
                    print(f"添加记忆失败: 存储后端处于只读模式")
                else:
                    print(f"添加记忆失败: {e}")
                return False
        return False

    def search(self, user_id: str, query: str, limit: int = 3):
        """搜索记忆"""
        if self.memory:
            try:
                results = self.memory.search(query, user_id=user_id, limit=limit)
                return results
            except Exception as e:
                print(f"搜索记忆失败: {e}")
                return []
        return []
    
    def get_all(self, user_id: str):
        """获取所有记忆"""
        if self.memory:
            try:
                return self.memory.get_all(user_id=user_id)
            except Exception as e:
                print(f"获取所有记忆失败: {e}")
                return []
        return []

# 全局单例
memory_instance = None
memory_lock = threading.Lock()

def get_memory():
    global memory_instance
    if memory_instance is None:
        with memory_lock:
            if memory_instance is None:
                memory_instance = LongTermMemory()
    return memory_instance
