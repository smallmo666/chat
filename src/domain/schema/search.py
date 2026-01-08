import json
import threading
import hashlib
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
from src.core.database import get_query_db
from src.core.config import settings

class SchemaSearcher:
    """
    Schema 搜索器。
    使用 FAISS 向量数据库和 BM25 关键词检索进行混合搜索。
    支持自动检测 Schema 变更并刷新索引。
    """
    def __init__(self, project_id: int = None):
        self.project_id = project_id
        self.adjacency_list = {} # 表邻接图 {table_name: [neighbor_table_names]}
        self.all_table_metadata = {} # 缓存所有表的元数据 {table_name: info_dict}
        self.vectorstore = None
        self.bm25 = None # BM25 对象
        self.documents_cache = [] # 缓存 Document 对象用于 BM25
        self.last_checksum = None # Schema 指纹
        self.lock = threading.Lock()
        self._last_index_time = 0
        self._min_rebuild_interval = 60
        
        # 懒加载：首次查询时再触发索引构建

    def _calculate_checksum(self, schema_dict: dict) -> str:
        """
        计算 Schema 的校验和 (Checksum)。
        用于检测 Schema 是否发生变化。
        """
        # 提取关键信息用于 hash：表名、列名、列类型
        # 为了保证确定性，需要排序
        canonical_str = ""
        sorted_tables = sorted(schema_dict.keys())
        for table in sorted_tables:
            info = schema_dict[table]
            canonical_str += f"Table:{table}|"
            sorted_cols = sorted(info['columns'], key=lambda x: x['name'])
            for col in sorted_cols:
                canonical_str += f"{col['name']}:{col['type']}|"
        
        if not canonical_str:
            return None
        return hashlib.md5(canonical_str.encode('utf-8')).hexdigest()

    def index_schema(self, force: bool = False):
        """
        从数据库 Schema 构建 FAISS 索引和 BM25 索引。
        
        Args:
            force (bool): 是否强制重建索引。如果为 False，则只在 Checksum 变化时重建。
        """
        with self.lock:
            try:
                db = get_query_db(self.project_id)
                schema_json = db.inspect_schema(project_id=self.project_id)
                schema_dict = json.loads(schema_json)
                
                # 检查变更
                current_checksum = self._calculate_checksum(schema_dict)
                import time as _time
                now = int(_time.time())
                if current_checksum is None:
                    self.vectorstore = None
                    self.bm25 = None
                    self.documents_cache = []
                    self.last_checksum = None
                    self._last_index_time = now
                    print("DEBUG: Empty schema, skipping index rebuild.")
                    return
                if not force:
                    if current_checksum == self.last_checksum and self.vectorstore is not None:
                        print("DEBUG: Schema unchanged, skipping index rebuild.")
                        return
                    if self._last_index_time and (now - self._last_index_time) < self._min_rebuild_interval:
                        print("DEBUG: Rebuild throttled, skipping due to interval.")
                        return

                print(f"DEBUG: Schema change detected (Checksum: {current_checksum}), rebuilding index...")
                
                # 更新元数据缓存
                self.all_table_metadata = schema_dict
                self.adjacency_list = {} # Reset graph
                
                documents = []
                tokenized_corpus = [] # For BM25
                
                for table_name, info in schema_dict.items():
                    # 初始化邻接列表
                    if table_name not in self.adjacency_list:
                        self.adjacency_list[table_name] = set()

                    # 为每个表创建一个文档
                    columns_str = ", ".join([f"{col['name']} ({col.get('comment', '')})" for col in info['columns']])
                    
                    relationships_str = ""
                    if "foreign_keys" in info:
                        relationships_str = "\nForeign Keys: " + ", ".join([f"{fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}" for fk in info['foreign_keys']])
                        
                        # 构建邻接图
                        for fk in info['foreign_keys']:
                            ref_table = fk['referred_table']
                            self.adjacency_list[table_name].add(ref_table)
                            if ref_table not in self.adjacency_list:
                                self.adjacency_list[ref_table] = set()
                            self.adjacency_list[ref_table].add(table_name)
                    
                    # Content for Vector Search (Semantic)
                    content = f"Table: {table_name}\nComment: {info.get('comment', '')}\nColumns: {columns_str}{relationships_str}"
                    
                    # Content for BM25 (Keyword heavy)
                    # Include table name multiple times to boost weight
                    bm25_content = f"{table_name} {table_name} {table_name} {info.get('comment', '')} {columns_str}"
                    tokenized_corpus.append(bm25_content.lower().split())
                    
                    doc = Document(
                        page_content=content,
                        metadata={"table_name": table_name, "full_info": json.dumps(info, ensure_ascii=False)}
                    )
                    documents.append(doc)

                if not documents:
                    self.vectorstore = None
                    self.bm25 = None
                    self.documents_cache = []
                    return
                
                # 1. Build Vector Store
                print(f"DEBUG: SchemaSearcher using Embedding Model: {settings.EMBEDDING_MODEL}")
                embeddings = OpenAIEmbeddings(
                    model=settings.EMBEDDING_MODEL, 
                    openai_api_key=settings.OPENAI_API_KEY,
                    openai_api_base=settings.OPENAI_API_BASE,
                    check_embedding_ctx_length=False,
                    chunk_size=10
                )
                self.vectorstore = FAISS.from_documents(documents, embeddings)
                
                # 2. Build BM25 Index
                self.bm25 = BM25Okapi(tokenized_corpus)
                self.documents_cache = documents
                
                self.last_checksum = current_checksum
                self._last_index_time = now
                print("DEBUG: Schema index rebuild completed (Vector + BM25).")
                
            except Exception as e:
                print(f"ERROR: Failed to index schema: {e}")

    def _get_schema(self) -> dict:
        """
        获取全量 Schema 元数据。
        如果尚未索引，则触发索引构建。
        """
        if not self.all_table_metadata:
            self.index_schema(force=False)
        return self.all_table_metadata

    def search_candidate_tables(self, query: str, limit: int = 5) -> list[dict]:
        """
        根据查询返回候选表列表（结构化数据）。
        采用混合检索策略 (Hybrid Search): Vector (Semantic) + BM25 (Keyword) + RRF Fusion
        """
        if not self.vectorstore or not self.bm25:
            try:
                self.index_schema(force=False)
            except Exception as _:
                return []
            if not self.vectorstore or not self.bm25:
                return []
            
        # 1. 向量检索 (Vector Recall)
        vector_limit = limit * 2
        vector_results = self.vectorstore.similarity_search_with_score(query, k=vector_limit)
        # normalize vector scores (L2 distance, lower is better. Convert to similarity 0-1 if possible, or just rank)
        # Here we just use rank for RRF
        
        # 2. BM25 检索 (Keyword Recall)
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        # Get top indices
        top_n = min(len(bm25_scores), limit * 2)
        # argsort returns indices of sorted array. We want descending.
        bm25_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:top_n]
        
        # 3. RRF Fusion (Reciprocal Rank Fusion)
        # RRF_score = 1 / (k + rank)
        k = 60
        rrf_scores = {} # {table_name: score}
        
        # Process Vector Results
        for rank, (doc, score) in enumerate(vector_results):
            table_name = doc.metadata["table_name"]
            rrf_scores[table_name] = rrf_scores.get(table_name, 0) + (1 / (k + rank + 1))
            
        # Process BM25 Results
        for rank, idx in enumerate(bm25_indices):
            doc = self.documents_cache[idx]
            table_name = doc.metadata["table_name"]
            rrf_scores[table_name] = rrf_scores.get(table_name, 0) + (1 / (k + rank + 1))
            
        # Keyword boosting for commerce domains
        commerce_tokens = {"sales", "order", "orders", "transaction", "transactions", "amount", "price", "value", "revenue", "gmv"}
        qt = set(tokenized_query)
        if qt & commerce_tokens:
            for doc, _ in vector_results:
                info = json.loads(doc.metadata["full_info"])
                table_name = doc.metadata["table_name"].lower()
                boost = 0
                if any(tok in table_name for tok in commerce_tokens):
                    boost += 1.5
                for col in info.get("columns", []):
                    cn = col.get("name", "").lower()
                    if cn in commerce_tokens:
                        boost += 0.2
                if boost > 0:
                    rrf_scores[doc.metadata["table_name"]] = rrf_scores.get(doc.metadata["table_name"], 0) + boost
        
        # Sort by RRF score
        sorted_tables = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        top_table_names = [t[0] for t in sorted_tables[:limit]]
        
        print(f"DEBUG: Hybrid Search Top Tables: {top_table_names}")
        
        # 4. 图谱扩展 (Graph Expansion)
        expanded_names = set(top_table_names)
        for name in top_table_names:
            neighbors = self.adjacency_list.get(name, set())
            for neighbor in neighbors:
                if neighbor not in expanded_names:
                    expanded_names.add(neighbor)
                    # print(f"DEBUG: Graph Expansion added neighbor: {neighbor} (via {name})")
        
        # 5. 构造结果
        results = []
        for name in expanded_names:
            if name in self.all_table_metadata:
                info = self.all_table_metadata[name]
                results.append({
                    "table_name": name,
                    "comment": info.get("comment", ""),
                    "full_info": info
                })
            else:
                # Should not happen if sync is correct
                results.append({
                    "table_name": name,
                    "comment": "",
                    "full_info": {"columns": []}
                })
        
        return results

    def get_pruned_schema(self, table_names: list[str], query: str, top_k_columns: int = 10) -> str:
        """
        根据查询生成精简的 Schema 描述 (Column-Level Pruning)。
        只保留 Top-K 相关列 + 主键 + 外键。
        """
        if not self.vectorstore or not self.all_table_metadata:
            return ""
            
        result_str = ""
        query_tokens = set(query.lower().split())
        
        # 预先构建列嵌入索引 (Ideal: Cache this, but for now we do simple keyword/rule matching + lightweight ranking)
        # 由于实时构建列级向量索引太慢，我们采用规则 + 关键词匹配的启发式剪枝
        
        for table_name in table_names:
            if table_name not in self.all_table_metadata:
                continue
                
            info = self.all_table_metadata[table_name]
            columns = info.get('columns', [])
            pks = info.get('primary_key', [])
            fks = info.get('foreign_keys', [])
            
            # 收集必须保留的列 (PKs + FKs)
            kept_columns = set()
            for pk in pks:
                kept_columns.add(pk)
            
            fk_cols = set()
            for fk in fks:
                for col in fk['constrained_columns']:
                    kept_columns.add(col)
                    fk_cols.add(col)
            
            # 对剩余列进行评分
            scored_cols = []
            for col in columns:
                col_name = col['name']
                if col_name in kept_columns:
                    continue
                
                score = 0
                # 规则 1: 精确匹配
                if col_name.lower() in query_tokens:
                    score += 10
                # 规则 2: 部分匹配
                elif col_name.lower() in query.lower():
                    score += 5
                # 规则 3: 注释匹配
                elif col.get('comment') and any(token in col['comment'] for token in query_tokens):
                    score += 3
                
                scored_cols.append((col, score))
            
            # 排序并取 Top-K
            scored_cols.sort(key=lambda x: x[1], reverse=True)
            top_cols = [x[0] for x in scored_cols[:top_k_columns]]
            
            # 合并结果
            final_cols = []
            # 先加 PK/FK
            for col in columns:
                if col['name'] in kept_columns:
                    final_cols.append(col)
            
            # 再加 Top-K
            for col in top_cols:
                final_cols.append(col)
                
            # 标记是否有省略
            omitted_count = len(columns) - len(final_cols)
            
            # 生成 Markdown
            result_str += f"### Table: {table_name}\n"
            if info.get("comment"):
                result_str += f"Comment: {info['comment']}\n"
            
            result_str += "| Column | Type | Comment |\n|---|---|---|\n"
            for col in final_cols:
                pk_mark = " (PK)" if col['name'] in pks else ""
                fk_mark = " (FK)" if col['name'] in fk_cols else ""
                result_str += f"| {col['name']} | {col['type']} | {col.get('comment', '')}{pk_mark}{fk_mark} |\n"
            
            if omitted_count > 0:
                result_str += f"... ({omitted_count} other columns omitted)\n"
            result_str += "\n"
            
        return result_str

    def search_relevant_tables(self, query: str, limit: int = 5) -> str:
        """
        根据自然语言查询搜索最相关的表。
        采用混合检索策略：向量检索 + 关键词匹配
        返回相关表的 Markdown 格式 Schema 描述。
        """
        if not self.vectorstore:
            return "No schema information available."
            
        # 1. 向量检索 (Semantic Search)
        # 稍微放宽 limit 以便混合
        semantic_docs = self.vectorstore.similarity_search(query, k=limit * 2)
        
        # 2. 关键词检索 (Keyword Search - 简单的 BM25 模拟)
        # 如果 query 中包含表名或字段名，显著增加其权重
        keyword_docs = []
        # 获取所有文档（这里假设内存中有副本，或者从 vectorstore 的 docstore 获取）
        # FAISS 默认不暴露 docstore 的全部遍历，但我们构建时有 documents 列表。
        # 由于 _build_index 没保存 documents 到 self，我们需要简单 hack 一下或者重新遍历
        # 为了性能，这里我们只对 semantic_docs 进行重排序，或者如果我们能访问 raw documents
        
        # 更好的做法：在 _build_index 时保存 self.documents
        # 但为了不破坏现有结构太大，我们这里只做简单的重排序优化：
        
        # 简单 Keyword Matching: 检查 query 中的 token 是否匹配表名
        query_tokens = set(query.lower().split())
        
        scored_results = {} # {table_name: score}
        
        # 初始分：向量检索的排名倒数
        for i, doc in enumerate(semantic_docs):
            score = 1.0 / (i + 1)
            scored_results[doc.metadata["table_name"]] = score
            
        # 关键词加权
        # 注意：这需要我们能访问所有表名。
        # 我们可以从 semantic_docs 的 metadata 中获取一部分，但如果关键词匹配的表没在向量 Top-K 里怎么办？
        # 这是一个局限。为了解决这个问题，我们需要在 init 时保存一份 table_names 列表。
        
        # 让我们修改一下 __init__ 来保存 table_metadata
        
        final_docs = semantic_docs[:limit] # 默认回退
        
        # 如果我们无法访问全量表，就只能对召回结果重排序
        for doc in semantic_docs:
            table_name = doc.metadata["table_name"]
            # 如果表名直接出现在 query 中，给极高权重
            if table_name.lower() in query.lower():
                scored_results[table_name] = scored_results.get(table_name, 0) + 2.0
                
            # 检查列名匹配
            info = json.loads(doc.metadata["full_info"])
            for col in info['columns']:
                if col['name'].lower() in query_tokens:
                     scored_results[table_name] = scored_results.get(table_name, 0) + 0.5
        
        # 排序
        sorted_tables = sorted(scored_results.items(), key=lambda x: x[1], reverse=True)
        top_tables = [t[0] for t in sorted_tables[:limit]]
        
        # 过滤 docs
        final_docs = [doc for doc in semantic_docs if doc.metadata["table_name"] in top_tables]
        
        # 如果 keyword matching 没找到什么，可能 final_docs 会变少，所以要补齐
        if len(final_docs) < limit:
            existing_names = set(d.metadata["table_name"] for d in final_docs)
            for doc in semantic_docs:
                if doc.metadata["table_name"] not in existing_names:
                    final_docs.append(doc)
                    existing_names.add(doc.metadata["table_name"])
                    if len(final_docs) >= limit:
                        break
        
        result_str = ""
        for doc in final_docs:
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
