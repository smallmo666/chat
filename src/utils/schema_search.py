import json
import chromadb
from typing import List, Dict, Any
from src.utils.db import get_app_db
from src.utils.llm import get_llm
from langchain_core.prompts import ChatPromptTemplate

class SchemaSearcher:
    """
    负责从大规模 Schema 中检索相关表的工具。
    使用混合检索策略：关键词匹配 + ChromaDB 向量语义检索 + LLM 精选。
    """
    def __init__(self):
        self.app_db = get_app_db()
        self.llm = get_llm()
        self._schema_cache = None
        self._chroma_client = None
        self._collection = None
        self._init_vector_db()

    def _get_schema(self) -> Dict[str, Any]:
        """获取并缓存 Schema 数据"""
        if self._schema_cache is None:
            schema_json = self.app_db.get_stored_schema_info()
            try:
                self._schema_cache = json.loads(schema_json)
            except:
                self._schema_cache = {}
        return self._schema_cache

    def _init_vector_db(self):
        """初始化 ChromaDB 并索引表信息"""
        try:
            self._chroma_client = chromadb.Client()
            # 每次重启重建索引，保证最新。生产环境应持久化。
            self._collection = self._chroma_client.create_collection(name="db_tables", get_or_create=True)
            
            # 如果集合为空，进行索引
            if self._collection.count() == 0:
                print("Indexing tables for vector search...")
                full_schema = self._get_schema()
                
                ids = []
                documents = []
                metadatas = []
                
                for table_name, info in full_schema.items():
                    comment = ""
                    columns_text = ""
                    
                    if isinstance(info, dict):
                        comment = info.get("comment", "")
                        columns = info.get("columns", [])
                        # 将列名和列注释也加入索引，增强语义匹配
                        col_descs = [f"{c['name']} {c.get('comment', '')}" for c in columns]
                        columns_text = " ".join(col_descs)
                    elif isinstance(info, list): # Legacy format
                        columns = info
                        col_descs = [f"{c['name']} {c.get('comment', '')}" for c in columns]
                        columns_text = " ".join(col_descs)
                        
                    # 构造语义丰富的描述文档
                    # 格式：Table: [name] Comment: [comment] Columns: [col1, col2...]
                    doc_text = f"Table: {table_name}. Comment: {comment}. Columns: {columns_text}"
                    
                    ids.append(table_name)
                    documents.append(doc_text)
                    metadatas.append({"name": table_name, "comment": comment})
                
                if ids:
                    # 批量添加
                    batch_size = 100
                    for i in range(0, len(ids), batch_size):
                        self._collection.add(
                            ids=ids[i:i+batch_size],
                            documents=documents[i:i+batch_size],
                            metadatas=metadatas[i:i+batch_size]
                        )
                print(f"Indexed {len(ids)} tables in ChromaDB.")
                
        except Exception as e:
            print(f"Failed to initialize Vector DB: {e}")
            self._collection = None

    def search_relevant_tables(self, query: str, limit: int = 10) -> str:
        """
        根据用户查询检索最相关的表结构。
        采用三阶段混合检索：
        1. 向量检索 (Vector) + 关键词粗筛 (Keyword) -> 混合候选集
        2. LLM 精选 (LLM Selection)
        """
        full_schema = self._get_schema()
        all_tables = []
        
        # 解析 Schema
        for table_name, info in full_schema.items():
            comment = ""
            if isinstance(info, dict):
                comment = info.get("comment", "")
            all_tables.append({"name": table_name, "comment": comment})
            
        if not all_tables:
            return "No schema available."

        # --- 1. 混合检索阶段 ---
        candidates_map = {} # map table_name -> {'score': float, 'source': str, 'info': dict}

        # A. 向量检索 (Semantic Search)
        # 确保 Vector DB 已初始化
        if not self._collection:
             try:
                 self._init_vector_db()
             except Exception as e:
                 print(f"Lazy init vector db failed: {e}")

        if self._collection:
            try:
                # 查询 top-20 语义相关表
                vector_results = self._collection.query(
                    query_texts=[query],
                    n_results=min(20, len(all_tables))
                )
                
                if vector_results['ids'] and len(vector_results['ids']) > 0:
                    found_ids = vector_results['ids'][0]
                    distances = vector_results['distances'][0] # smaller is better
                    
                    for i, table_name in enumerate(found_ids):
                        # 转换距离为相似度分数 (approx inverted)
                        dist = distances[i]
                        score = 1.0 / (1.0 + dist) * 100 # Scale to roughly 0-100
                        
                        # Find table info
                        table_info = next((t for t in all_tables if t['name'] == table_name), None)
                        if table_info:
                            candidates_map[table_name] = {
                                'score': score, 
                                'source': 'vector', 
                                'info': table_info
                            }
            except Exception as e:
                print(f"Vector search failed: {e}")

        # B. 关键词检索 (Keyword Heuristic) - 作为补充和增强
        query_lower = query.lower()
        for t in all_tables:
            score = 0
            t_name = t["name"].lower()
            t_comment = t["comment"].lower() if t["comment"] else ""
            
            # 1. 完整包含 (High score)
            if t_name in query_lower: score += 50 # Keyword match should be strong
            if t_comment and t_comment in query_lower: score += 50
            
            # 2. 关键词重叠
            if "user" in t_name and "用户" in query_lower: score += 20
            if "order" in t_name and "订单" in query_lower: score += 20
            if "log" in t_name and "日志" in query_lower: score += 20
            
            # 3. 基础相关性
            parts = t_name.split('_')
            for part in parts:
                if len(part) > 2 and part in query_lower:
                    score += 10
            
            if score > 0:
                if t['name'] in candidates_map:
                    # Boost existing vector score
                    candidates_map[t['name']]['score'] += score
                    candidates_map[t['name']]['source'] = 'hybrid'
                else:
                    candidates_map[t['name']] = {
                        'score': score,
                        'source': 'keyword',
                        'info': t
                    }

        # C. 融合与排序
        scored_candidates = list(candidates_map.values())
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # 选取前 30 个混合候选表
        final_candidates = [c['info'] for c in scored_candidates[:30]]
        
        # 保底逻辑：如果候选太少，补充核心表
        core_tables = ["users", "products", "orders", "order_items"]
        for core in core_tables:
            if not any(c["name"] == core for c in final_candidates) and core in full_schema:
                info = full_schema[core]
                comment = info.get("comment", "") if isinstance(info, dict) else ""
                final_candidates.append({"name": core, "comment": comment})

        # --- 2. LLM 精选阶段 ---
        candidate_list_str = "\n".join([f"{t['name']} ({t['comment']})" for t in final_candidates])
        
        system_prompt = (
            "你是一个数据库专家。请根据用户的查询，从以下候选表中筛选出最相关的表。\n"
            "候选表格式为：表名 (中文注释)\n"
            "只返回最相关的表名列表，用逗号分隔，不要有其他废话。\n"
            "如果无法确定，请返回可能相关的核心表（如 users, orders 等）。\n"
            "最多选择 {limit} 张表。\n\n"
            "候选表列表:\n{candidate_list}"
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{query}")
        ]).partial(limit=str(limit), candidate_list=candidate_list_str)
        
        chain = prompt | self.llm
        try:
            result = chain.invoke({"query": query})
            selected_tables_str = result.content.strip()
            selected_tables_str = selected_tables_str.replace("`", "").replace("\n", " ")
            selected_tables = [t.strip() for t in selected_tables_str.split(",") if t.strip()]
        except Exception as e:
            print(f"Schema search error: {e}")
            selected_tables = ["users", "orders", "products"]

        # 3. 获取详细 Schema
        relevant_schema_info = []
        total_chars = 0
        MAX_SCHEMA_CHARS = 10000 
        
        for table in selected_tables:
            if table in full_schema:
                info = full_schema[table]
                if isinstance(info, dict):
                    columns = info.get("columns", [])
                    t_comment = info.get("comment", "")
                else:
                    columns = info
                    t_comment = ""
                    
                col_strings = [f"{col['name']} ({col['type']})" + (f" - {col.get('comment')}" if isinstance(col, dict) and col.get('comment') else "") for col in columns]
                
                header = f"表名: {table}"
                if t_comment:
                    header += f" ({t_comment})"
                
                table_schema_str = f"{header}\n列: {', '.join(col_strings)}"
                
                if total_chars + len(table_schema_str) > MAX_SCHEMA_CHARS:
                    print(f"Warning: Schema truncation hit at {total_chars} chars.")
                    break
                    
                relevant_schema_info.append(table_schema_str)
                total_chars += len(table_schema_str)
        
        if not relevant_schema_info:
            return "No relevant tables found."
            
        return "\n\n".join(relevant_schema_info)

# 全局实例
_searcher = None
def get_schema_searcher():
    global _searcher
    if _searcher is None:
        _searcher = SchemaSearcher()
    return _searcher
