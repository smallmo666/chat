import chromadb
from typing import List, Dict, Any
from sqlalchemy import text
from src.core.database import get_query_db

class ValueSearcher:
    """
    负责对数据库中的文本列值进行索引和检索，解决实体链接问题。
    例如：用户输入 "iPhone"，数据库存储 "Apple iPhone 15"。
    """
    def __init__(self, project_id: int = None):
        self.project_id = project_id
        self._chroma_client = None
        self._collection = None
        self._init_vector_db()

    def _init_vector_db(self):
        try:
            self._chroma_client = chromadb.Client()
            collection_name = f"db_values_{self.project_id}" if self.project_id else "db_values_default"
            self._collection = self._chroma_client.create_collection(name=collection_name, get_or_create=True)
        except Exception as e:
            print(f"Failed to init ValueSearcher vector db: {e}")

    def index_values(self, tables: List[str] = None, limit_per_column: int = 1000):
        """
        扫描数据库中的文本列，构建值索引。
        :param tables: 指定要扫描的表名列表，如果为 None 则扫描所有表。
        :param limit_per_column: 每列采样的最大唯一值数量。
        """
        if not self._collection:
            return

        try:
            query_db = get_query_db(self.project_id)
            # 获取所有表结构
            # 简化起见，这里假设我们能获取所有表名
            # 在实际生产中，应从 SchemaSearcher 或元数据中获取
            inspector = query_db.inspect_schema() # 返回 JSON 字符串
            import json
            schema = json.loads(inspector)
            
            target_tables = tables if tables else schema.keys()
            
            ids = []
            documents = []
            metadatas = []
            
            with query_db.engine.connect() as conn:
                for table in target_tables:
                    if table not in schema: continue
                    
                    # 获取该表的文本列
                    columns = schema[table]
                    if isinstance(columns, dict): columns = columns.get("columns", [])
                    
                    text_columns = [col['name'] for col in columns if 'char' in col['type'].lower() or 'text' in col['type'].lower()]
                    
                    for col in text_columns:
                        print(f"Indexing values for {table}.{col}...")
                        # 查询去重值
                        try:
                            # 简单的 SQL 防注入处理：使用 text()
                            sql = text(f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL LIMIT {limit_per_column}")
                            result = conn.execute(sql)
                            values = [str(row[0]) for row in result]
                            
                            for val in values:
                                if len(val) < 2 or len(val) > 100: continue # 过滤过短或过长的值
                                
                                # ID: table.col.hash(val)
                                doc_id = f"{table}.{col}.{hash(val)}"
                                
                                ids.append(doc_id)
                                documents.append(val)
                                metadatas.append({"table": table, "column": col, "value": val})
                                
                        except Exception as e:
                            print(f"Error indexing {table}.{col}: {e}")

            if ids:
                print(f"Adding {len(ids)} values to vector index...")
                batch_size = 500
                for i in range(0, len(ids), batch_size):
                    self._collection.add(
                        ids=ids[i:i+batch_size],
                        documents=documents[i:i+batch_size],
                        metadatas=metadatas[i:i+batch_size]
                    )
                print("Value indexing complete.")
                
        except Exception as e:
            print(f"Value indexing failed: {e}")

    def search_similar_values(self, query_value: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        搜索与 query_value 最相似的数据库真实值。
        """
        if not self._collection:
            return []
            
        try:
            results = self._collection.query(
                query_texts=[query_value],
                n_results=limit
            )
            
            matches = []
            if results['ids'] and len(results['ids']) > 0:
                for i, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][i]
                    matches.append({
                        "value": meta["value"],
                        "table": meta["table"],
                        "column": meta["column"],
                        "score": results['distances'][0][i] # Smaller is better for L2
                    })
            return matches
        except Exception as e:
            print(f"Value search failed: {e}")
            return []

# 全局缓存
_value_searchers = {}

def get_value_searcher(project_id: int = None):
    global _value_searchers
    key = project_id or "default"
    if key not in _value_searchers:
        _value_searchers[key] = ValueSearcher(project_id)
    return _value_searchers[key]
