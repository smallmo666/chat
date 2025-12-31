from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Literal

from src.workflow.state import AgentState
from src.core.llm import get_llm

llm = None # Will be initialized in node

class PlanStep(BaseModel):
    node: Literal["ClarifyIntent", "SelectTables", "GenerateDSL", "DSLtoSQL", "ExecuteSQL", "DataAnalysis", "Visualization", "AnalysisViz", "TableQA", "PythonAnalysis"] = Field(
        ..., description="The node to execute"
    )
    desc: str = Field(..., description="Description of the step")

class PlannerResponse(BaseModel):
    plan: List[PlanStep] = Field(..., description="The execution plan")

BASE_SYSTEM_PROMPT = """
你是一个高级 Text2SQL 智能体的规划师。
你的任务是根据用户的输入和对话历史，制定一个独立可行的执行计划。
你需要判断用户的意图，并选择合适的节点序列。

可用节点：
- ClarifyIntent: 当用户意图不明确，需要反问澄清时使用。
- SelectTables: 当需要从数据库查询数据，且尚未选择表时使用。
- GenerateDSL: 已有表信息，需要生成中间 DSL。
- DSLtoSQL: 已有 DSL，需要转换为 SQL。
- ExecuteSQL: 已有 SQL，需要执行查询。
- AnalysisViz: (并行节点) 已有查询结果，同时进行数据分析和可视化生成。适用于常规分析。
- PythonAnalysis: (高级分析) 当用户需要复杂的统计计算、预测、高级数据清洗时使用。使用 Pandas 执行 Python 代码。
- TableQA: 当用户询问数据库表结构、字段含义等元数据问题时使用（不需要生成 SQL）。

典型场景：
1. 常规查询与分析：SelectTables -> GenerateDSL -> DSLtoSQL -> ExecuteSQL -> AnalysisViz
2. 复杂统计/预测/高级计算：SelectTables -> GenerateDSL -> DSLtoSQL -> ExecuteSQL -> PythonAnalysis
3. 仅查询数据：SelectTables -> GenerateDSL -> DSLtoSQL -> ExecuteSQL
4. 询问表信息：TableQA
5. 意图不明：ClarifyIntent
6. 对已有数据做预测/复杂处理：PythonAnalysis

注意：
- 如果用户提到“预测”、“线性回归”、“相关性”、“复杂清洗”，请务必使用 **PythonAnalysis**。
- 常规的“绘制”、“画图”、“可视化”使用 AnalysisViz 即可。
- 只有明确询问“数据库里有什么表”、“表的结构是什么”时，才使用 TableQA。

请制定执行计划，包含一系列步骤（node 和 desc），并以 JSON 格式输出。
输出格式示例：
{{
  "plan": [
    {{"node": "SelectTables", "desc": "选择相关表"}},
    {{"node": "GenerateDSL", "desc": "生成查询 DSL"}}
  ]
}}
"""

async def planner_node(state: AgentState, config: dict = None) -> dict:
    """
    规划器节点。
    """
    print("DEBUG: Entering planner_node")
    
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="Planner", project_id=project_id)
    
    # 检查我们是否已经有计划并且正在执行中
    # 但是等等，Planner 通常是入口点或澄清后的重新入口
    # 为了简单起见，如果计划为空或我们刚刚完成 ClarifyIntent，我们会重新生成计划
    
    messages = state.get("messages", [])
    
    # 截断历史记录以避免 Token 溢出
    # 保留最后 10 条消息应该足够用于规划
    if len(messages) > 10:
        messages = messages[-10:]
        
    # --- Query Rewriting (Context Resolution) ---
    # 如果对话历史超过 1 条（即不仅仅是当前用户输入），尝试重写查询
    # 我们检查是否有上一轮的对话
    rewritten_query = None
    if len(messages) > 1:
        print("DEBUG: Planner - Detecting multi-turn context, attempting rewrite...")
        rewrite_prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个对话上下文重写专家。你的任务是将用户的最新回复，结合之前的对话历史，重写为一个完整、独立的查询语句。\n"
                       "如果用户的最新回复依赖于上文（例如包含'它'、'这个'、'按地区呢'等），请补全上下文。\n"
                       "如果用户的最新回复是独立的，请保持原样。\n"
                       "只输出重写后的查询，不要输出其他内容。"),
            ("placeholder", "{messages}")
        ])
        rewrite_chain = rewrite_prompt | llm
        try:
            # Async invoke for rewrite
            rewrite_res = await rewrite_chain.ainvoke({"messages": messages})
            rewritten_query = rewrite_res.content.strip()
            print(f"DEBUG: Planner - Rewritten Query: {rewritten_query}")
        except Exception as e:
            print(f"DEBUG: Planner - Rewrite failed: {e}")

    # 将 rewritten_query 放入 state (虽然 planner_node 返回的是 dict update，我们需要确保 graph update logic 能处理)
    # LangGraph 的 update 是 merge，所以我们在 return 中包含它即可
    # 但是，Prompt 需要知道最新的意图，所以我们将 rewritten_query 附加到 prompt 或者 messages 中
    # 这里我们选择更新 messages 的最后一条，或者在 State 中增加字段
    # 为了不破坏原始 messages，我们在 State 中增加 'rewritten_query' 字段
    # --------------------------------------------
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", BASE_SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ])
    
    # 如果有重写后的查询，我们可以临时构造一个 prompt input，或者让 Planner 自己也看 history (它已经看了)
    # 实际上，如果 Planner 看到了完整的 history，它应该能理解上下文。
    # 但是显式的 Rewrite 有助于下游节点 (SelectTables, GenerateDSL) 直接使用明确的 Query，
    # 而不需要每个节点都去理解复杂的 history。
    
    chain = prompt | llm.with_structured_output(PlannerResponse)
    
    # Async invoke for planning
    result = await chain.ainvoke({"messages": messages})
    
    # 将 Pydantic 模型转换为字典以用于状态
    plan = [{"node": step.node, "desc": step.desc, "status": "wait"} for step in result.plan]
    
    return {
        "plan": plan, 
        "current_step_index": 0,
        "intent_clear": True,
        "rewritten_query": rewritten_query # 保存到 State 供后续节点使用
    }
