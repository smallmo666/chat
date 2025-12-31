import chromadb
import uuid
import threading
from typing import List, Dict, Any

class FewShotRetriever:
    """
    基于 ChromaDB 的 Few-Shot 样本检索器。
    用于存储和检索 {Question, DSL, SQL} 三元组，实现动态上下文学习。
    """
    def __init__(self, project_id: int = None):
        self.project_id = project_id
        self._chroma_client = None
        self._collection = None
        self._init_vector_db()

    def _init_vector_db(self):
        try:
            # 使用持久化客户端，与 ValueSearcher 保持一致
            self._chroma_client = chromadb.PersistentClient(path="./chroma_db_fewshot")
            # 每个项目使用独立的 Collection，或者是全局共享的 "common_examples"
            collection_name = f"few_shot_examples_{self.project_id}" if self.project_id else "few_shot_examples_common"
            self._collection = self._chroma_client.get_or_create_collection(name=collection_name)
            print(f"FewShotRetriever initialized for collection: {collection_name}")
        except Exception as e:
            print(f"Failed to init FewShotRetriever: {e}")

    def add_example(self, question: str, dsl: str, sql: str, metadata: Dict[str, Any] = None):
        """
        添加一个新的样本。
        """
        if not self._collection:
            return

        try:
            # ID: uuid
            doc_id = str(uuid.uuid4())
            
            # Metadata
            meta = {
                "question": question,
                "dsl": dsl, # 存储 DSL 以供参考
                "sql": sql  # 存储 SQL 以供参考
            }
            if metadata:
                meta.update(metadata)
                
            self._collection.add(
                ids=[doc_id],
                documents=[question], # 我们对问题进行 Embed
                metadatas=[meta]
            )
            print(f"Added few-shot example: {question[:30]}...")
        except Exception as e:
            print(f"Failed to add example: {e}")

    def retrieve(self, query: str, k: int = 3) -> str:
        """
        检索 Top-K 相似样本，并格式化为 Prompt 字符串。
        """
        if not self._collection:
            return ""
            
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=k
            )
            
            if not results['ids'] or len(results['ids'][0]) == 0:
                return ""
            
            examples_str = "**参考案例 (Few-Shot Examples):**\n"
            
            for i, doc in enumerate(results['documents'][0]):
                meta = results['metadatas'][0][i]
                question = meta.get("question", "")
                dsl = meta.get("dsl", "")
                
                # 格式化为一个清晰的 Example Block
                examples_str += (
                    f"Example {i+1}:\n"
                    f"User: {question}\n"
                    f"DSL: {dsl}\n\n"
                )
                
            return examples_str
            
        except Exception as e:
            print(f"Few-shot retrieval failed: {e}")
            return ""

# 全局缓存
_retrievers = {}
_retriever_lock = threading.Lock()

def get_few_shot_retriever(project_id: int = None):
    global _retrievers
    key = project_id or "default"
    if key not in _retrievers:
        with _retriever_lock:
            if key not in _retrievers:
                _retrievers[key] = FewShotRetriever(project_id)
    return _retrievers[key]
