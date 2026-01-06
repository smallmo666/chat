import os
from dotenv import load_dotenv
import threading

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
        # 优先使用本地持久化路径，与项目其他组件保持一致
        chroma_path = "./chroma_db"
        chroma_host = os.getenv("CHROMA_HOST")
        chroma_port = int(os.getenv("CHROMA_PORT", 8000))
        
        # 基础配置
        config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": os.getenv("MODEL_NAME", "gpt-4o"), # 优先使用环境变量
                    "temperature": 0,
                    "openai_base_url": os.getenv("OPENAI_API_BASE"),
                    "api_key": os.getenv("OPENAI_API_KEY"),
                }
            },
            # 使用 OpenAI 兼容的 Embedding
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
                    "openai_base_url": os.getenv("OPENAI_API_BASE"),
                    "api_key": os.getenv("OPENAI_API_KEY"),
                }
            }
        }

        # Vector Store 配置：优先本地，其次 Host/Port
        if not chroma_host:
             # 使用本地持久化客户端
             config["vector_store"] = {
                "provider": "chroma",
                "config": {
                    "collection_name": "text2sql_memory",
                    "path": chroma_path,
                }
            }
             print(f"LongTermMemory: Using local ChromaDB at {chroma_path}")
        else:
            # 使用 HTTP 客户端
            config["vector_store"] = {
                "provider": "chroma",
                "config": {
                    "collection_name": "text2sql_memory",
                    "host": chroma_host,
                    "port": chroma_port,
                }
            }
            print(f"LongTermMemory: Using remote ChromaDB at {chroma_host}:{chroma_port}")
        
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
