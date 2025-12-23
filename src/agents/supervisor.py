from typing import Literal
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.messages import AIMessage

from src.state.state import AgentState
from src.utils.llm import get_llm

llm = get_llm()

class RouteResponse(BaseModel):
    next: Literal["ClarifyIntent", "GenerateDSL", "DSLtoSQL", "ExecuteSQL", "FINISH"] = Field(
        ..., description="下一个要路由到的 Agent 节点。"
    )

system_prompt = (
    "你是一个 Text2SQL 流水线的主管 Agent。\n"
    "你的目标是根据当前状态，将对话路由到下一个逻辑步骤。\n\n"
    "逻辑规则：\n"
    "1. 如果意图不清晰 (Intent Clear = False)：\n"
    "   - 如果最后一条消息是 AI 提出的澄清问题，说明我们需要等待用户回复，请路由到 'FINISH'。\n"
    "   - 如果最后一条消息是用户回复，或者还没有进行过澄清，请路由到 'ClarifyIntent'。\n"
    "2. 如果意图清晰 (Intent Clear = True)：\n"
    "   - 如果尚未生成 DSL，路由到 'GenerateDSL'。\n"
    "   - 如果已生成 DSL 但尚未生成 SQL，路由到 'DSLtoSQL'。\n"
    "   - 如果已生成 SQL 但尚未执行获得结果，路由到 'ExecuteSQL'。\n"
    "   - 如果已有执行结果，路由到 'FINISH'。\n\n"
    "当前状态：\n"
    "- 是否有 DSL: {dsl_present}\n"
    "- 是否有 SQL: {sql_present}\n"
    "- 是否有结果: {results_present}\n"
    "- 意图是否清晰: {intent_clear}\n"
)

def supervisor_node(state: AgentState) -> dict:
    dsl_present = state.get("dsl") is not None
    sql_present = state.get("sql") is not None
    results_present = state.get("results") is not None
    intent_clear = state.get("intent_clear", False)

    # DEBUG: 打印当前状态
    # print(f"DEBUG: Supervisor State -> Intent: {intent_clear}, DSL: {dsl_present}, SQL: {sql_present}, Results: {results_present}")

    # 特殊逻辑：处理人机交互中断
    # 如果意图不清晰，且最后一条消息是 AI 消息（澄清问题），则路由到 FINISH 以等待用户输入
    messages = state.get("messages", [])
    if not intent_clear and messages and isinstance(messages[-1], AIMessage):
        # 这里的 FINISH 意味着当前 Agent 运行结束，将控制权交还给用户（在 main.py 循环中）
        return {"next": "FINISH"}

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ]).partial(
        dsl_present=str(dsl_present),
        sql_present=str(sql_present),
        results_present=str(results_present),
        intent_clear=str(intent_clear)
    )

    chain = prompt | llm.with_structured_output(RouteResponse)
    result = chain.invoke(state)
    
    # print(f"DEBUG: Supervisor Decision -> {result.next}")
    return {"next": result.next}
