from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from typing import List, Literal

from src.state.state import AgentState
from src.utils.llm import get_llm

llm = get_llm()

class PlanStep(BaseModel):
    node: Literal["ClarifyIntent", "SelectTables", "GenerateDSL", "DSLtoSQL", "ExecuteSQL", "DataAnalysis", "Visualization", "TableQA"] = Field(
        ..., description="The node to execute"
    )
    desc: str = Field(..., description="Description of the step")

class PlannerResponse(BaseModel):
    plan: List[PlanStep] = Field(..., description="The execution plan")

system_prompt = (
    "你是一个高级 Text2SQL 智能体的规划师。\n"
    "你的任务是根据用户的输入和对话历史，制定一个独立可行的执行计划。\n"
    "你需要判断用户的意图，并选择合适的节点序列。\n\n"
    "可用节点：\n"
    "- ClarifyIntent: 当用户意图不明确，需要反问澄清时使用。\n"
    "- SelectTables: 当需要从数据库查询数据，且尚未选择表时使用。\n"
    "- GenerateDSL: 已有表信息，需要生成中间 DSL。\n"
    "- DSLtoSQL: 已有 DSL，需要转换为 SQL。\n"
    "- ExecuteSQL: 已有 SQL，需要执行查询。\n"
    "- DataAnalysis: 已有查询结果，需要进行数据解读、洞察分析时使用。\n"
    "- Visualization: 已有查询结果，需要生成图表时使用。\n"
    "- TableQA: 当用户询问数据库表结构、字段含义等元数据问题时使用（不需要生成 SQL）。\n\n"
    "典型场景：\n"
    "1. 数据查询与分析：SelectTables -> GenerateDSL -> DSLtoSQL -> ExecuteSQL -> DataAnalysis -> Visualization\n"
    "2. 仅查询数据：SelectTables -> GenerateDSL -> DSLtoSQL -> ExecuteSQL\n"
    "3. 询问表信息：TableQA\n"
    "4. 意图不明：ClarifyIntent\n"
    "5. 后续深入分析（已有结果）：DataAnalysis -> Visualization\n\n"
    "请生成一个 JSON 列表，包含步骤的 node 和 desc。"
)

def planner_node(state: AgentState) -> dict:
    # Check if we already have a plan and are in the middle of it
    # But wait, Planner is usually the entry point or re-entry after clarification
    # For simplicity, we regenerate plan if it's empty or if we just finished ClarifyIntent
    
    messages = state.get("messages", [])
    
    # Truncate history to avoid token overflow
    # Keep last 10 messages should be enough for planning
    if len(messages) > 10:
        messages = messages[-10:]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ])
    
    chain = prompt | llm.with_structured_output(PlannerResponse)
    result = chain.invoke({"messages": messages})
    
    # Convert Pydantic models to dicts for state
    plan = [{"node": step.node, "desc": step.desc, "status": "wait"} for step in result.plan]
    
    return {
        "plan": plan, 
        "current_step_index": 0,
        "intent_clear": True # Assuming planner handles clarity check via ClarifyIntent node
    }
