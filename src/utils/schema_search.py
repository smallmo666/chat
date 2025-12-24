import json
from typing import List, Dict, Any
from src.utils.db import get_app_db
from src.utils.llm import get_llm
from langchain_core.prompts import ChatPromptTemplate

class SchemaSearcher:
    """
    负责从大规模 Schema 中检索相关表的工具。
    使用简单的关键词匹配 + LLM 语义辅助。
    """
    def __init__(self):
        self.app_db = get_app_db()
        self.llm = get_llm()
        self._schema_cache = None

    def _get_schema(self) -> Dict[str, Any]:
        """获取并缓存 Schema 数据"""
        if self._schema_cache is None:
            schema_json = self.app_db.get_stored_schema_info()
            try:
                self._schema_cache = json.loads(schema_json)
            except:
                self._schema_cache = {}
        return self._schema_cache

    def search_relevant_tables(self, query: str, limit: int = 10) -> str:
        """
        根据用户查询检索最相关的表结构。
        采用两阶段检索：关键词/语义粗筛 -> LLM 精选。
        """
        full_schema = self._get_schema()
        all_tables = []
        
        # 解析 Schema，提取表名和注释用于检索
        for table_name, info in full_schema.items():
            comment = ""
            if isinstance(info, dict):
                comment = info.get("comment", "")
            all_tables.append({"name": table_name, "comment": comment})
            
        if not all_tables:
            return "No schema available."

        # 1. 第一阶段：基于关键词的启发式粗筛
        # 将查询分词（简单的按空格或字切分，对于中文最好有分词，这里简化处理）
        # 我们简单地把查询字符串当作一个整体，或者简单的字符匹配
        # 更优做法：计算 Query 与 TableName/Comment 的重叠度
        
        # 简单评分逻辑
        scored_tables = []
        query_lower = query.lower()
        
        for t in all_tables:
            score = 0
            t_name = t["name"].lower()
            t_comment = t["comment"].lower() if t["comment"] else ""
            
            # 1. 完整包含 (High score)
            if t_name in query_lower: score += 10
            if t_comment and t_comment in query_lower: score += 10
            
            # 2. 关键词重叠 (这里简单模拟，真实环境可用 Jieba 分词)
            # 检查常见的业务词汇是否匹配
            # 将 query 拆分为 2-gram 或 3-gram 也许更好，但这里简化：
            # 只要 query 中包含表名的一部分（比如 log, user, order）
            if "user" in t_name and "用户" in query_lower: score += 5
            if "order" in t_name and "订单" in query_lower: score += 5
            if "log" in t_name and "日志" in query_lower: score += 5
            if "dept" in t_name and "部门" in query_lower: score += 5
            if "emp" in t_name and "员工" in query_lower: score += 5
            
            # 3. 基础相关性：如果表名出现在 query 中
            # 拆解表名下划线
            parts = t_name.split('_')
            for part in parts:
                if len(part) > 2 and part in query_lower:
                    score += 2
                    
            scored_tables.append((score, t))
            
        # 按分数排序
        scored_tables.sort(key=lambda x: x[0], reverse=True)
        
        # 选取前 50 个候选表（避免 Context Window 爆炸）
        # 如果分数都为0（无明确匹配），则保留核心表和部分随机表
        # Strict limit to 30 to be safer
        candidates = [t[1] for t in scored_tables[:30]]
        
        # 如果候选太少，补充一些核心表
        core_tables = ["users", "products", "orders", "order_items"]
        for core in core_tables:
            # 检查是否已在候选列表中
            if not any(c["name"] == core for c in candidates) and core in full_schema:
                # 找到 core table 的 info
                info = full_schema[core]
                comment = info.get("comment", "") if isinstance(info, dict) else ""
                candidates.append({"name": core, "comment": comment})

        # 构造候选列表字符串给 LLM
        candidate_list_str = "\n".join([f"{t['name']} ({t['comment']})" for t in candidates])
        
        # 2. 第二阶段：LLM 精选
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
            # 清理可能的 markdown
            selected_tables_str = selected_tables_str.replace("`", "").replace("\n", " ")
            selected_tables = [t.strip() for t in selected_tables_str.split(",") if t.strip()]
        except Exception as e:
            print(f"Schema search error: {e}")
            # Fallback to core tables
            selected_tables = ["users", "orders", "products"]

        # 3. 获取详细 Schema
        relevant_schema_info = []
        total_chars = 0
        MAX_SCHEMA_CHARS = 10000 # Limit to ~10k chars to leave room for history and output
        
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
