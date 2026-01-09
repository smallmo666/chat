import uuid
from typing import List, Optional
from openai import OpenAI
from pymilvus import MilvusClient, DataType
from sqlmodel import select

from src.core.config import settings
from src.core.database import get_app_db
from src.core.models import Knowledge

class KnowledgeRetriever:
    """
    通用知识库检索器 (基于 Milvus 向量检索)。
    用于存储和检索业务知识、公式等 (从 MySQL 同步)。
    """
    def __init__(self, project_id: int = None):
        self.project_id = project_id
        self.client = None
        self.openai_client = None
        # Collection name based on project or common
        self.collection_name = f"knowledge_base_{self.project_id}" if self.project_id else "knowledge_base_common"
        
        self._init_clients()
        # 实际生产中应避免每次初始化都全量同步，这里为了演示简化，
        # 或者可以设计一个标志位/后台任务。此处我们在初始化时尝试同步一次。
        self._sync_from_db()

    def _init_clients(self):
        """初始化 OpenAI 和 Milvus 客户端"""
        try:
            self.openai_client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE
            )
        except Exception as e:
            print(f"Warning: Failed to initialize OpenAI client for Knowledge: {e}")

        try:
            uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
            print(f"KnowledgeRetriever: Connecting to Milvus at {uri}...")
            self.client = MilvusClient(
                uri=uri,
                token=settings.MILVUS_TOKEN,
                db_name=settings.MILVUS_DB_NAME
            )
        except Exception as e:
            print(f"Warning: Failed to initialize Milvus for Knowledge: {e}")
            self.client = None

    def _embed(self, text: str) -> List[float]:
        """生成 Embedding"""
        if not self.openai_client:
            return []
        try:
            resp = self.openai_client.embeddings.create(
                input=[text],
                model=settings.EMBEDDING_MODEL
            )
            return resp.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding for knowledge: {e}")
            return []

    def _sync_from_db(self):
        """从 MySQL 同步 Knowledge 表到 Milvus"""
        if not self.client:
            return

        # Check if collection exists
        if not self.client.has_collection(self.collection_name):
            print(f"Creating Knowledge collection: {self.collection_name}")
            schema = MilvusClient.create_schema(
                auto_id=False,
                enable_dynamic_field=True,
            )
            # Fields
            schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=128, is_primary=True)
            schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=settings.EMBEDDING_DIM)
            schema.add_field(field_name="term", datatype=DataType.VARCHAR, max_length=256)
            schema.add_field(field_name="definition", datatype=DataType.VARCHAR, max_length=4096)
            schema.add_field(field_name="formula", datatype=DataType.VARCHAR, max_length=1024)
            schema.add_field(field_name="db_id", datatype=DataType.INT64) # MySQL ID reference

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
            
            # Initial Sync
            self._perform_full_sync()
        else:
            self.client.load_collection(self.collection_name)
            # Optional: Check if count matches or force sync
            # For this demo, we'll do a quick check or just skip if collection exists
            # To ensure data freshness, let's do a sync if collection is empty
            res = self.client.query(collection_name=self.collection_name, filter="", output_fields=["count(*)"])
            if not res:
                self._perform_full_sync()

    def _perform_full_sync(self):
        """执行全量同步"""
        try:
            app_db = get_app_db()
            with app_db.get_session() as session:
                # Filter by project/org if needed, currently assuming global or mapped via project_id
                # In models.py, Knowledge has organization_id. 
                # For this demo, we sync all or filter by org if project_id is linked to org.
                # Simplification: Sync all Knowledge items for now.
                items = session.exec(select(Knowledge)).all()
                
            if not items:
                return

            print(f"Syncing {len(items)} knowledge items to Milvus...")
            insert_data = []
            for k in items:
                # Combine term + definition + formula
                text_to_embed = f"{k.term} {k.definition} {k.formula or ''}"
                vector = self._embed(text_to_embed)
                if vector:
                    insert_data.append({
                        "id": str(uuid.uuid4()), # Vector DB ID
                        "vector": vector,
                        "term": k.term,
                        "definition": k.definition,
                        "formula": k.formula or "",
                        "db_id": k.id
                    })
            
            if insert_data:
                self.client.insert(collection_name=self.collection_name, data=insert_data)
                print("Knowledge synced successfully.")
                
        except Exception as e:
            print(f"Failed to sync knowledge from DB: {e}")

    def retrieve(self, query: str, k: int = 3) -> str:
        """
        根据查询检索相关的知识。
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
                output_fields=["term", "definition", "formula"],
                search_params={"metric_type": "COSINE"}
            )

            if not results or not results[0]:
                return ""

            matched_items = []
            for match in results[0]:
                # Score filter
                # if match['distance'] < 0.3: continue
                
                entity = match['entity']
                term = entity.get("term")
                definition = entity.get("definition")
                formula = entity.get("formula")
                
                item_str = f"- **{term}**: {definition}"
                if formula:
                    item_str += f" (公式: `{formula}`)"
                matched_items.append(item_str)

            if not matched_items:
                return ""

            return "### 相关业务知识 (Knowledge Base):\n" + "\n".join(matched_items)

        except Exception as e:
            print(f"Knowledge retrieval failed: {e}")
            return ""

# 单例模式 (按 Project 缓存)
_retrievers = {}

def get_knowledge_retriever(project_id: int = None) -> KnowledgeRetriever:
    global _retrievers
    key = project_id or "default"
    if key not in _retrievers:
        _retrievers[key] = KnowledgeRetriever(project_id)
    return _retrievers[key]
