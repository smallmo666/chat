import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 禁用 Mem0 遥测 (PostHog)，防止退出时报错
os.environ["MEM0_TELEMETRY"] = "False"

from mem0 import Memory

class LongTermMemory:
    """
    长期记忆管理类，使用 Mem0 + ChromaDB。
    """
    def __init__(self):
        chroma_host = os.getenv("CHROMA_HOST", "localhost")
        chroma_port = int(os.getenv("CHROMA_PORT", 8000))
        
        config = {
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "text2sql_memory",
                    "host": chroma_host,
                    "port": chroma_port,
                }
            },
            # 使用 OpenAI 兼容的 Embedding 和 LLM 配置
            "llm": {
                "provider": "openai",
                "config": {
                    "model": os.getenv("MODEL_NAME", "qwen-max"),
                    "temperature": 0,
                    "openai_base_url": os.getenv("OPENAI_API_BASE"),
                    "api_key": os.getenv("OPENAI_API_KEY"),
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-v2",
                    "openai_base_url": os.getenv("OPENAI_API_BASE"),
                    "api_key": os.getenv("OPENAI_API_KEY"),
                }
            },
            # 注意：Mem0 默认使用 OpenAIEmbedding，如果使用兼容接口可能需要配置 embedder
            # 这里假设环境中的 OPENAI_API_BASE 支持 embedding 或者 Mem0 能正确处理
            # 如果使用的是阿里云百炼，可能需要确认 embedding 模型支持情况
        }
        
        try:
            self.memory = Memory.from_config(config)
            print(f"成功连接到长期记忆存储 (ChromaDB @ {chroma_host}:{chroma_port})")
        except Exception as e:
            print(f"长期记忆初始化失败: {e}")
            self.memory = None

    def add(self, user_id: str, text: str) -> bool:
        """添加记忆"""
        if self.memory:
            try:
                self.memory.add(text, user_id=user_id)
                return True
            except Exception as e:
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

def get_memory():
    global memory_instance
    if memory_instance is None:
        memory_instance = LongTermMemory()
    return memory_instance
