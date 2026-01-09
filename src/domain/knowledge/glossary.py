import yaml
import os
import uuid
from typing import List, Dict, Any
from openai import OpenAI
from pymilvus import MilvusClient, DataType
from src.core.config import settings

class GlossaryRetriever:
    """
    业务术语检索器 (基于 Milvus 向量检索)。
    用于管理和检索业务定义（如 GMV, 活跃用户等）。
    支持语义召回。
    """
    def __init__(self, project_id: int = None, glossary_path: str = "config/glossary.yaml"):
        self.project_id = project_id
        self.glossary_path = glossary_path
        self.client = None
        self.openai_client = None
        # Collection name based on project or common
        self.collection_name = f"glossary_{self.project_id}" if self.project_id else "glossary_common"
        
        self._init_clients()
        self._sync_glossary()

    def _init_clients(self):
        """初始化 OpenAI 和 Milvus 客户端"""
        try:
            # Init OpenAI for Embeddings
            self.openai_client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE
            )
        except Exception as e:
            print(f"Warning: Failed to initialize OpenAI client for Glossary: {e}")

        try:
            # Init Milvus
            uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
            print(f"GlossaryRetriever: Connecting to Milvus at {uri}...")
            self.client = MilvusClient(
                uri=uri,
                token=settings.MILVUS_TOKEN,
                db_name=settings.MILVUS_DB_NAME
            )
        except Exception as e:
            print(f"Warning: Failed to initialize Milvus for Glossary: {e}")
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
            print(f"Error generating embedding for glossary: {e}")
            return []

    def _sync_glossary(self):
        """同步 YAML 文件到 Milvus"""
        if not self.client:
            return

        # Check if collection exists
        if not self.client.has_collection(self.collection_name):
            print(f"Creating Glossary collection: {self.collection_name}")
            schema = MilvusClient.create_schema(
                auto_id=False,
                enable_dynamic_field=True,
            )
            # Fields
            schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=128, is_primary=True)
            schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=settings.EMBEDDING_DIM)
            schema.add_field(field_name="term", datatype=DataType.VARCHAR, max_length=256)
            schema.add_field(field_name="definition", datatype=DataType.VARCHAR, max_length=2048)
            schema.add_field(field_name="keywords", datatype=DataType.VARCHAR, max_length=1024)

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
            
            # Load from YAML and insert
            self._load_and_insert_yaml()
        else:
            self.client.load_collection(self.collection_name)
            # Optional: Check if empty, if so, reload
            res = self.client.query(collection_name=self.collection_name, filter="", output_fields=["count(*)"])
            # Milvus query count is tricky, simpler to just rely on existence or force reload flag.
            # For this demo, we assume if collection exists, it's fine. 
            # Ideally we should version check or hash check.
            pass

    def _load_and_insert_yaml(self):
        """读取 YAML 并插入 Milvus"""
        if not os.path.exists(self.glossary_path):
            self._create_default_yaml()
            
        try:
            with open(self.glossary_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {"terms": []}
            
            terms = data.get("terms", [])
            if not terms:
                return

            print(f"Syncing {len(terms)} glossary terms to Milvus...")
            insert_data = []
            for t in terms:
                # Combine term + keywords + definition for embedding context
                text_to_embed = f"{t['name']} {' '.join(t.get('keywords', []))} {t['definition']}"
                vector = self._embed(text_to_embed)
                if vector:
                    insert_data.append({
                        "id": str(uuid.uuid4()),
                        "vector": vector,
                        "term": t['name'],
                        "definition": t['definition'],
                        "keywords": ",".join(t.get('keywords', []))
                    })
            
            if insert_data:
                self.client.insert(collection_name=self.collection_name, data=insert_data)
                print("Glossary synced successfully.")
                
        except Exception as e:
            print(f"Failed to sync glossary yaml: {e}")

    def _create_default_yaml(self):
        """创建默认 YAML"""
        os.makedirs(os.path.dirname(self.glossary_path), exist_ok=True)
        default_glossary = {
            "terms": [
                {
                    "name": "高价值用户",
                    "definition": "总消费金额 (total_amount) 大于 1000 的用户",
                    "keywords": ["高价值", "VIP", "重要客户"]
                },
                {
                    "name": "活跃用户",
                    "definition": "最近 30 天内有登录记录 (last_login > now() - interval 30 day) 的用户",
                    "keywords": ["活跃", "Active"]
                },
                {
                    "name": "GMV",
                    "definition": "商品交易总额，计算方式为 sum(order_amount) WHERE status = 'paid'",
                    "keywords": ["GMV", "成交额", "流水"]
                }
            ]
        }
        with open(self.glossary_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_glossary, f, allow_unicode=True)

    def retrieve(self, query: str, k: int = 3) -> str:
        """
        根据查询检索相关的业务术语定义 (Vector Search)。
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
                output_fields=["term", "definition"],
                search_params={"metric_type": "COSINE"}
            )

            if not results or not results[0]:
                return ""

            matched_terms = []
            for match in results[0]:
                # Score filter (optional)
                # if match['distance'] < 0.3: continue 
                
                entity = match['entity']
                term = entity.get("term")
                definition = entity.get("definition")
                matched_terms.append(f"- **{term}**: {definition}")

            if not matched_terms:
                return ""

            return "### 业务术语定义 (Business Glossary - Semantic Search):\n" + "\n".join(matched_terms)

        except Exception as e:
            print(f"Glossary retrieval failed: {e}")
            return ""

# 单例模式
_glossary_retriever = None

def get_glossary_retriever(project_id: int = None) -> GlossaryRetriever:
    global _glossary_retriever
    if _glossary_retriever is None:
        # 这里为了演示简单，忽略 project_id，实际可以按 project 加载不同的 yaml
        _glossary_retriever = GlossaryRetriever()
    return _glossary_retriever
