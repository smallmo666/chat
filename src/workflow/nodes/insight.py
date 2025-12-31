import json
from typing import List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from src.workflow.state import AgentState
from src.core.llm import get_llm

class InsightResponse(BaseModel):
    insights: List[str] = Field(default=[], description="List of discovered insights. Empty if nothing interesting.")

INSIGHT_PROMPT = """
你是一个高级数据洞察专家 (Data Insight Miner)。
你的任务是基于用户的查询和 SQL 执行结果，主动挖掘数据中隐藏的**有价值的洞察**。

用户查询: {query}
SQL: {sql}
结果数据 (前 {sample_size} 条):
{data_sample}

### 任务指南:
1. **寻找惊喜**: 不要仅仅复述结果（例如"结果显示A是100"），而是寻找**异常值 (Outliers)**、**显著趋势 (Trends)**、**极值 (Extremes)** 或 **反直觉的现象**。
2. **讲故事**: 将洞察转化为简短的业务故事。例如："虽然整体销售额下降，但 iPhone 15 的销量反而逆势增长了 20%。"
3. **保持克制**: 如果数据平平无奇，不要强行编造洞察，返回空列表即可。
4. **数量限制**: 最多返回 3 条最关键的洞察。

请输出 JSON 格式的洞察列表。
"""

async def insight_miner_node(state: AgentState, config: dict = None) -> dict:
    """
    主动洞察挖掘节点。
    在 SQL 执行成功后，针对复杂查询 (deep mode) 运行。
    """
    print("DEBUG: Entering insight_miner_node")
    
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="InsightMiner", project_id=project_id)
    
    # 获取上下文
    query = ""
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            query = msg.content
            break
            
    sql = state.get("sql", "")
    results_str = state.get("results", "[]")
    
    try:
        results = json.loads(results_str)
        if not isinstance(results, list) or not results:
            print("InsightMiner: Results empty or invalid, skipping.")
            return {"insights": []}
            
        # 采样数据，避免 Token 爆炸
        sample_size = 20
        data_sample = json.dumps(results[:sample_size], ensure_ascii=False)
        
        prompt = ChatPromptTemplate.from_template(INSIGHT_PROMPT)
        chain = prompt | llm.with_structured_output(InsightResponse)
        
        response = await chain.ainvoke({
            "query": query,
            "sql": sql,
            "data_sample": data_sample,
            "sample_size": sample_size
        })
        
        print(f"DEBUG: InsightMiner found {len(response.insights)} insights: {response.insights}")
        
        if response.insights:
            # 生成一条 AIMessage 通知用户
            # 但为了不打断主流程的可视化展示，我们这里只更新 State，
            # 让前端通过 'insight_mined' 事件来独立展示，或者由 Supervisor 决定是否发消息。
            # 这里我们选择只更新 State，把展示权交给前端事件流。
            return {"insights": response.insights}
            
        return {"insights": []}

    except Exception as e:
        print(f"InsightMiner failed: {e}")
        return {"insights": []}
