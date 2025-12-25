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
    "5. 后续深入分析（已有结果）：DataAnalysis -> Visualization\n"
    "6. 询问表结构/有哪些表：TableQA\n"
    "7. 对当前数据进行绘图/可视化：Visualization\n\n"
    "注意：\n"
    "- 如果用户要求“绘制”、“画图”、“可视化”且上下文中有查询结果，请直接使用 Visualization，不要使用 TableQA。\n"
    "- “清单表”通常指的是之前的查询结果，如果用户说“绘制清单表”，意图是 Visualization。\n"
    "- 只有明确询问“数据库里有什么表”、“表的结构是什么”时，才使用 TableQA。\n\n"
    "请生成一个 JSON 列表，包含步骤的 node 和 desc。"
)

def planner_node(state: AgentState) -> dict:
    # 检查我们是否已经有计划并且正在执行中
    # 但是等等，Planner 通常是入口点或澄清后的重新入口
    # 为了简单起见，如果计划为空或我们刚刚完成 ClarifyIntent，我们会重新生成计划
    
    messages = state.get("messages", [])
    
    # 截断历史记录以避免 Token 溢出
    # 保留最后 10 条消息应该足够用于规划
    if len(messages) > 10:
        messages = messages[-10:]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ])
    
    chain = prompt | llm.with_structured_output(PlannerResponse)
    result = chain.invoke({"messages": messages})
    
    # 将 Pydantic 模型转换为字典以用于状态
    plan = [{"node": step.node, "desc": step.desc, "status": "wait"} for step in result.plan]
    
    return {
        "plan": plan, 
        "current_step_index": 0,
        "intent_clear": True # 假设规划器通过 ClarifyIntent 节点处理清晰度检查
    }
