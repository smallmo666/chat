from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Literal

from src.workflow.state import AgentState
from src.core.llm import get_llm

llm = None # 将在节点内部初始化

class PlanStep(BaseModel):
    node: Literal["ClarifyIntent", "SelectTables", "GenerateDSL", "DSLtoSQL", "ExecuteSQL", "Visualization", "TableQA", "PythonAnalysis"] = Field(
        ..., description="要执行的节点名称"
    )
    desc: str = Field(..., description="步骤描述")

class PlannerResponse(BaseModel):
    plan: List[PlanStep] = Field(..., description="执行计划")

BASE_SYSTEM_PROMPT = """
你是一个高级 Text2SQL 智能体的规划师。
你的任务是根据用户的输入、对话历史以及【数据侦探】提供的分析假设，制定一个独立可行的执行计划。

### 上下文信息:
- 用户意图: {user_query}
- 侦探假设 (Hypotheses):
{hypotheses_context}

### 可用节点：
- ClarifyIntent: 当用户意图不明确，需要反问澄清时使用。
- SelectTables: 当需要从数据库查询数据，且尚未选择表时使用。
- GenerateDSL: 已有表信息，需要生成中间 DSL。
- DSLtoSQL: 已有 DSL，需要转换为 SQL。
- ExecuteSQL: 已有 SQL，需要执行查询。
- Visualization: (ECharts 可视化) 已有查询结果，需要生成图表时使用。
- PythonAnalysis: (高级分析) 当用户需要复杂的统计计算、预测、高级数据清洗时使用。使用 Pandas 执行 Python 代码。
- TableQA: 当用户询问数据库表结构、字段含义等元数据问题时使用（不需要生成 SQL）。

### 典型场景：
1. **简单查询**: SelectTables -> GenerateDSL -> DSLtoSQL -> ExecuteSQL -> Visualization
2. **复杂分析 (涉及预测/归因)**: SelectTables -> GenerateDSL -> DSLtoSQL -> ExecuteSQL -> PythonAnalysis
3. **意图不明**: ClarifyIntent
4. **元数据询问**: TableQA

### 规划策略:
- 如果侦探提供了假设（例如"检查库存"），请确保生成的 SQL 或 Python 分析步骤能够验证这些假设。
- 如果需要多步验证（例如先查销量，再查库存），请在描述中注明。
- 优先使用 SQL 解决数据获取问题，使用 PythonAnalysis 解决计算和逻辑问题。

请制定执行计划，包含一系列步骤（node 和 desc），并以 JSON 格式输出。
"""

REWRITE_SYSTEM_PROMPT = """
你是一个对话上下文重写专家。你的任务是将用户的最新回复，结合之前的对话历史，重写为一个完整、独立的查询语句。
如果用户的最新回复依赖于上文（例如包含'它'、'这个'、'按地区呢'等），请补全上下文。
如果用户的最新回复是独立的，请保持原样。
只输出重写后的查询，不要输出其他内容。
"""

async def planner_node(state: AgentState, config: dict = None) -> dict:
    """
    规划器节点。
    """
    print("DEBUG: Entering planner_node")
    
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="Planner", project_id=project_id)
    
    messages = state.get("messages", [])
    hypotheses = state.get("hypotheses", [])
    
    # 截断历史记录以避免 Token 溢出
    # 保留最后 10 条消息应该足够用于规划
    if len(messages) > 10:
        messages = messages[-10:]
        
    # --- 查询重写 (上下文解析) ---
    rewritten_query = state.get("rewritten_query") # 优先使用已存在的重写查询
    if not rewritten_query:
        if len(messages) > 1:
            print("DEBUG: Planner - Detecting multi-turn context, attempting rewrite...")
            rewrite_prompt = ChatPromptTemplate.from_messages([
                ("system", REWRITE_SYSTEM_PROMPT),
                ("placeholder", "{messages}")
            ])
            rewrite_chain = rewrite_prompt | llm
            try:
                # 异步调用重写
                rewrite_res = await rewrite_chain.ainvoke({"messages": messages})
                rewritten_query = rewrite_res.content.strip()
                print(f"DEBUG: Planner - Rewritten Query: {rewritten_query}")
            except Exception as e:
                print(f"DEBUG: Planner - Rewrite failed: {e}")
        else:
            # 单轮对话，直接取最后一条消息
            for msg in reversed(messages):
                if msg.type == "human":
                    rewritten_query = msg.content
                    break

    # --------------------------------------------
    
    # 构建假设上下文
    hypotheses_context = "无"
    if hypotheses:
        hypotheses_context = "\n".join([f"- {h}" for h in hypotheses])
        print(f"DEBUG: Planner using hypotheses: {hypotheses}")

    prompt = ChatPromptTemplate.from_messages([
        ("system", BASE_SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ]).partial(
        user_query=rewritten_query or "Unknown Query",
        hypotheses_context=hypotheses_context
    )
    
    chain = prompt | llm.with_structured_output(PlannerResponse)
    
    # 异步调用规划
    result = await chain.ainvoke({"messages": messages})
    
    # 将 Pydantic 模型转换为字典以用于状态
    plan = [{"node": step.node, "desc": step.desc, "status": "wait"} for step in result.plan]
    
    return {
        "plan": plan, 
        "current_step_index": 0,
        "intent_clear": True,
        "rewritten_query": rewritten_query # 保存到 State 供后续节点使用
    }
