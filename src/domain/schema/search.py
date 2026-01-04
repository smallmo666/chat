import json
import threading
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from src.core.database import get_query_db
from src.core.config import settings

class SchemaSearcher:
    """
    Schema 搜索器。
    使用 FAISS 向量数据库和 OpenAI Embeddings 来搜索相关的表结构。
    """
    def __init__(self, project_id: int = None):
        self.project_id = project_id
        # 为了演示，我们每次都重新构建索引。
        # 在生产环境中，应该持久化向量存储并在元数据更改时更新。
        self.vectorstore = self._build_index()

    def _build_index(self):
        """
        从数据库 Schema 构建 FAISS 索引。
        """
        db = get_query_db(self.project_id)
        
        # 获取 Schema (JSON 字符串)
        # TODO: 从 Project 配置中获取 scope_config
        schema_json = db.inspect_schema()
        schema_dict = json.loads(schema_json)
        
        documents = []
        for table_name, info in schema_dict.items():
            # 为每个表创建一个文档
            # 内容是表名、注释和列定义的混合
            columns_str = ", ".join([f"{col['name']} ({col.get('comment', '')})" for col in info['columns']])
            content = f"Table: {table_name}\nComment: {info.get('comment', '')}\nColumns: {columns_str}"
            
            doc = Document(
                page_content=content,
                metadata={"table_name": table_name, "full_info": json.dumps(info, ensure_ascii=False)}
            )
            documents.append(doc)
            
        if not documents:
            return None
        
        # 使用 settings 中的配置，支持未来切换模型
        embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL, 
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_API_BASE,
            check_embedding_ctx_length=False
        )
        return FAISS.from_documents(documents, embeddings)

    def search_relevant_tables(self, query: str, limit: int = 5) -> str:
        """
        根据自然语言查询搜索最相关的表。
        返回相关表的 Markdown 格式 Schema 描述。
        """
        if not self.vectorstore:
            return "No schema information available."
            
        docs = self.vectorstore.similarity_search(query, k=limit)
        
        result_str = ""
        for doc in docs:
            table_name = doc.metadata["table_name"]
            info = json.loads(doc.metadata["full_info"])
            
            result_str += f"### Table: {table_name}\n"
            if info.get("comment"):
                result_str += f"Comment: {info['comment']}\n"
            
            result_str += "| Column | Type | Comment |\n|---|---|---|\n"
            for col in info['columns']:
                result_str += f"| {col['name']} | {col['type']} | {col.get('comment', '')} |\n"
            result_str += "\n"
            
        return result_str

# 缓存实例以避免重建
_searchers = {}
_searcher_lock = threading.Lock() # 添加全局锁

def get_schema_searcher(project_id: int = None) -> SchemaSearcher:
    key = str(project_id)
    # Double-checked locking 模式
    if key not in _searchers:
        with _searcher_lock:
            if key not in _searchers:
                _searchers[key] = SchemaSearcher(project_id)
    return _searchers[key]
