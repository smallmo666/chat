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
    "- AnalysisViz: (并行节点) 已有查询结果，同时进行数据分析和可视化生成。适用于常规分析。\n"
    "- PythonAnalysis: (高级分析) 当用户需要复杂的统计计算、预测、高级数据清洗时使用。使用 Pandas 执行 Python 代码。\n"
    "- TableQA: 当用户询问数据库表结构、字段含义等元数据问题时使用（不需要生成 SQL）。\n\n"
    "典型场景：\n"
    "1. 常规查询与分析：SelectTables -> GenerateDSL -> DSLtoSQL -> ExecuteSQL -> AnalysisViz\n"
    "2. 复杂统计/预测/高级计算：SelectTables -> GenerateDSL -> DSLtoSQL -> ExecuteSQL -> PythonAnalysis\n"
    "3. 仅查询数据：SelectTables -> GenerateDSL -> DSLtoSQL -> ExecuteSQL\n"
    "4. 询问表信息：TableQA\n"
    "5. 意图不明：ClarifyIntent\n"
    "6. 对已有数据做预测/复杂处理：PythonAnalysis\n\n"
    "注意：\n"
    "- 如果用户提到“预测”、“线性回归”、“相关性”、“复杂清洗”，请务必使用 **PythonAnalysis**。\n"
    "- 常规的“绘制”、“画图”、“可视化”使用 AnalysisViz 即可。\n"
    "- 只有明确询问“数据库里有什么表”、“表的结构是什么”时，才使用 TableQA。\n\n"
    "请制定执行计划，包含一系列步骤（node 和 desc），并以 JSON 格式输出。\n"
    "输出格式示例：\n"
    "{{\n"
    "  \"plan\": [\n"
    "    {{\"node\": \"SelectTables\", \"desc\": \"选择相关表\"}},\n"
    "    {{\"node\": \"GenerateDSL\", \"desc\": \"生成查询 DSL\"}}\n"
    "  ]\n"
    "}}"
)

def planner_node(state: AgentState, config: dict = None) -> dict:
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
