import json
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from src.state.state import AgentState
from src.utils.llm import get_llm
from src.utils.db import get_app_db

llm = get_llm()

def generate_dsl_node(state: AgentState) -> dict:
    # 不再只取最后一条消息，而是使用整个对话历史来理解上下文
    messages = state["messages"]
    
    # 获取数据库 Schema 信息 (从 AppDB 获取存储的元数据)
    try:
        app_db = get_app_db()
        schema_info = app_db.get_stored_schema_info()
    except Exception as e:
        # schema_info = "无法获取数据库 Schema: " + str(e)
        schema_info = "Schema info unavailable"
    
    # 动态构建系统提示词
    system_prompt = (
        "你是一个 DSL 生成器。根据用户的对话历史，将用户的最新查询意图转换为 JSON DSL 格式。\n"
        "数据库 Schema 信息如下:\n"
        "{schema_info}\n\n"
        "Schema 结构示例: {{\"table\": \"<表名>\", \"filters\": [{{\"field\": \"<列名>\", \"operator\": \"...\", \"value\": \"...\"}}], \"select\": [\"<列名1>\", \"<列名2>\"]}}\n"
        "仅返回有效的 JSON 字符串，不要包含 Markdown 格式。\n"
        "注意：如果用户是在回复澄清问题（例如'是的'），请结合上下文理解其真实意图。"
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="history"),
    ]).partial(schema_info=schema_info)
    
    chain = prompt | llm
    result = chain.invoke({"history": messages})
    
    dsl_str = result.content.strip()
    # 清理可能存在的 markdown 代码块标记
    if "```json" in dsl_str:
        dsl_str = dsl_str.split("```json")[1].split("```")[0].strip()
    elif "```" in dsl_str:
        dsl_str = dsl_str.split("```")[1].split("```")[0].strip()
        
    return {"dsl": dsl_str}
