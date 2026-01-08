import uuid
import threading
from typing import Dict, Any, List
from openai import OpenAI
from pymilvus import MilvusClient, DataType

from src.core.config import settings

class FewShotRetriever:
    """
    基于 Milvus 的 Few-Shot 样本检索器。
    用于存储和检索 {Question, DSL, SQL} 三元组，实现动态上下文学习。
    """
    def __init__(self, project_id: int = None):
        self.project_id = project_id
        self.client = None
        self.openai_client = None
        self.collection_name = f"few_shot_examples_{self.project_id}" if self.project_id else "few_shot_examples_common"
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
                print(f"Warning: Failed to initialize OpenAI client for FewShotRetriever: {e}")
                return

            # 初始化 Milvus 客户端
            try:
                uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
                print(f"FewShotRetriever: Connecting to Milvus at {uri}...")
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
                    schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=128, is_primary=True)
                    schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=settings.EMBEDDING_DIM)
                    schema.add_field(field_name="question", datatype=DataType.VARCHAR, max_length=65535)
                    schema.add_field(field_name="dsl", datatype=DataType.VARCHAR, max_length=65535)
                    schema.add_field(field_name="sql", datatype=DataType.VARCHAR, max_length=65535)
                    
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
                print(f"FewShotRetriever initialized for collection: {self.collection_name}")
                
            except Exception as e:
                print(f"Warning: Failed to initialize Milvus for FewShotRetriever: {e}")
                self.client = None
                
        except Exception as e:
            print(f"Failed to init FewShotRetriever: {e}")

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

    def add_example(self, question: str, dsl: str, sql: str, metadata: Dict[str, Any] = None):
        """
        添加一个新的样本。
        """
        if not self.client:
            return

        try:
            vector = self._embed(question)
            if not vector:
                return

            # ID: uuid
            doc_id = str(uuid.uuid4())
            
            data = [{
                "id": doc_id,
                "vector": vector,
                "question": question,
                "dsl": dsl,
                "sql": sql,
                **(metadata or {})
            }]
                
            self.client.upsert(
                collection_name=self.collection_name,
                data=data
            )
            print(f"Added few-shot example: {question[:30]}...")
        except Exception as e:
            print(f"Failed to add example: {e}")

    def retrieve(self, query: str, k: int = 3) -> str:
        """
        检索 Top-K 相似样本，并格式化为 Prompt 字符串。
        """
        if not self.client:
            return ""
            
        try:
            vector = self._embed(query)
            if not vector:
                return ""

            results = self.client.search(
                collection_name=self.collection_name,
                data=[vector],
                limit=k,
                output_fields=["question", "dsl", "sql"],
                search_params={"metric_type": "COSINE"}
            )
            
            if not results or not results[0]:
                return ""
            
            examples_str = "**参考案例 (Few-Shot Examples):**\n"
            
            for i, match in enumerate(results[0]):
                entity = match['entity']
                question = entity.get("question", "")
                dsl = entity.get("dsl", "")
                
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
