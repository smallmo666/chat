import asyncio
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
from typing import List, Optional

from src.workflow.state import AgentState
from src.core.llm import get_llm
from src.domain.memory.few_shot import get_few_shot_retriever

class DetectiveResponse(BaseModel):
    is_complex: bool = Field(..., description="Query whether it is complex and needs to be split")
    hypotheses: List[str] = Field(default=[], description="List of hypotheses or sub-questions for complex queries")
    reasoning: str = Field(..., description="Reasoning behind the decision")

DETECTIVE_PROMPT = """
你是一个高级数据侦探 (Data Detective)。
你的任务是分析用户的查询，判断其是否是一个复杂的分析问题（例如涉及归因分析、异常检测、预测或多步推理）。

用户查询: {query}

### 任务指南:
1. **简单查询**: 如果用户只是查询事实（如 "上周销售额是多少"、"查询 iPhone 的库存"），标记为 `is_complex=False`。
2. **复杂查询**: 如果用户询问 "为什么" (Why)、"如何" (How)、"预测" (Predict) 或暗示了需要深入挖掘（如 "分析销售额下降的原因"），标记为 `is_complex=True`。
3. **假设生成**: 对于复杂查询，请提出 3-5 个可能的假设或拆解后的子问题。例如：
   - 用户: "为什么上周销售额下降？"
   - 假设: ["检查是否有缺货情况", "分析主要竞品是否降价", "查看特定地区或渠道的销售表现"]

### 参考案例 (Few-Shot):
{few_shot_context}

请输出 JSON 格式的分析结果。
"""

async def data_detective_node(state: AgentState, config: dict = None) -> dict:
    """
    数据侦探节点。
    在 Planner 之前运行，负责识别复杂问题并生成分析假设。
    """
    print("DEBUG: Entering data_detective_node")
    
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="DataDetective", project_id=project_id)
    
    # 获取用户最新查询
    messages = state.get("messages", [])
    last_query = ""
    for msg in reversed(messages):
        if msg.type == "human":
            last_query = msg.content
            break
            
    if not last_query:
        return {"next": "Planner"}

    # 获取 Few-Shot 上下文 (可选)
    few_shot_context = ""
    try:
        retriever = get_few_shot_retriever(project_id)
        # 尝试检索类似的复杂案例
        few_shot_context = await asyncio.to_thread(retriever.retrieve, last_query)
    except Exception as e:
        print(f"Detective: Failed to retrieve few-shot examples: {e}")

    prompt = ChatPromptTemplate.from_template(DETECTIVE_PROMPT)
    chain = prompt | llm.with_structured_output(DetectiveResponse)
    
    try:
        result = await chain.ainvoke({
            "query": last_query,
            "few_shot_context": few_shot_context
        })
        
        print(f"DEBUG: Detective Analysis: Complex={result.is_complex}, Hypotheses={result.hypotheses}")
        
        if result.is_complex and result.hypotheses:
            # 将假设注入到状态中，供 Planner 使用
            # 并生成一条 AIMessage 告知用户正在进行深度分析
            notification = f"🕵️‍♂️ 这是一个值得深入分析的问题。我将从以下几个角度入手：\n" + "\n".join([f"- {h}" for h in result.hypotheses])
            return {
                "hypotheses": result.hypotheses,
                "analysis_depth": "deep",
                "messages": [AIMessage(content=notification)]
            }
        else:
            return {
                "analysis_depth": "simple",
                "hypotheses": []
            }
            
    except Exception as e:
        print(f"Detective failed: {e}")
        return {"analysis_depth": "simple"} # Fallback
