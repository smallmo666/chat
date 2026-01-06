import yaml
import os

class GlossaryRetriever:
    """
    业务术语检索器。
    用于管理和检索业务定义（如 GMV, 活跃用户等）。
    目前支持简单的关键词匹配，未来可升级为向量检索。
    """
    def __init__(self, glossary_path: str = "config/glossary.yaml"):
        self.glossary = {}
        self.glossary_path = glossary_path
        self._load_glossary()

    def _load_glossary(self):
        """加载术语表"""
        # 如果文件不存在，创建一个默认的
        if not os.path.exists(self.glossary_path):
            # 确保目录存在
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
            try:
                with open(self.glossary_path, 'w', encoding='utf-8') as f:
                    yaml.dump(default_glossary, f, allow_unicode=True)
                self.glossary = default_glossary
            except Exception as e:
                print(f"Warning: Failed to create default glossary: {e}")
        else:
            try:
                with open(self.glossary_path, 'r', encoding='utf-8') as f:
                    self.glossary = yaml.safe_load(f) or {"terms": []}
            except Exception as e:
                print(f"Warning: Failed to load glossary: {e}")
                self.glossary = {"terms": []}

    def retrieve(self, query: str) -> str:
        """
        根据查询检索相关的业务术语定义。
        返回格式化的字符串。
        """
        if not self.glossary or "terms" not in self.glossary:
            return ""

        query_lower = query.lower()
        matched_terms = []

        for term in self.glossary["terms"]:
            # 检查关键词是否出现在查询中
            is_match = False
            # 检查 name
            if term["name"].lower() in query_lower:
                is_match = True
            
            # 检查 keywords
            if not is_match and "keywords" in term:
                for kw in term["keywords"]:
                    if kw.lower() in query_lower:
                        is_match = True
                        break
            
            if is_match:
                matched_terms.append(f"- **{term['name']}**: {term['definition']}")

        if not matched_terms:
            return ""

        return "### 业务术语定义 (Business Glossary):\n" + "\n".join(matched_terms)

# 单例模式
_glossary_retriever = None

def get_glossary_retriever(project_id: int = None) -> GlossaryRetriever:
    global _glossary_retriever
    if _glossary_retriever is None:
        # 这里为了演示简单，忽略 project_id，实际可以按 project 加载不同的 yaml
        _glossary_retriever = GlossaryRetriever()
    return _glossary_retriever
