import json
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from src.state.state import AgentState
from src.utils.llm import get_llm
from src.utils.db import get_app_db

llm = get_llm()

def generate_dsl_node(state: AgentState, config: dict = None) -> dict:
    print("DEBUG: Entering generate_dsl_node")
    try:
        # 不再只取最后一条消息，而是使用整个对话历史来理解上下文
        messages = state["messages"]
        
        # 截断历史记录以避免 Token 溢出
        # 保留最后 10 条消息应该足够了
        if len(messages) > 10:
            messages = messages[-10:]
        
        # 获取数据库 Schema 信息
        # 优先使用 SelectTables 节点筛选出的相关 Schema
        schema_info = state.get("relevant_schema", "")
        print(f"DEBUG: Schema info length: {len(schema_info)}")
        
        if not schema_info:
            print("DEBUG: No relevant_schema found, falling back to stored schema")
            # Fallback: 获取部分 Schema 信息 (从 AppDB 获取存储的元数据)
            try:
                app_db = get_app_db()
                full_schema_json = app_db.get_stored_schema_info()
                # 简单截断以防止溢出
                if len(full_schema_json) > 5000:
                    schema_info = full_schema_json[:5000] + "\n...(truncated)"
                else:
                    schema_info = full_schema_json
            except Exception as e:
                print(f"DEBUG: Error fetching stored schema: {e}")
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
        
        # 传递 config 给 invoke 以传播回调
        invoke_args = {"history": messages}
        print("DEBUG: Invoking LLM for DSL generation...")
        if config:
            result = chain.invoke(invoke_args, config=config)
        else:
            result = chain.invoke(invoke_args)
        
        dsl_str = result.content.strip()
        print(f"DEBUG: DSL generated (len={len(dsl_str)})")
        
        # 清理可能存在的 markdown 代码块标记
        if "```json" in dsl_str:
            dsl_str = dsl_str.split("```json")[1].split("```")[0].strip()
        elif "```" in dsl_str:
            dsl_str = dsl_str.split("```")[1].split("```")[0].strip()
            
        if not dsl_str:
             print("DEBUG: Generated DSL is empty!")
             return {"dsl": '{"error": "Empty DSL generated"}'}

        return {"dsl": dsl_str}
        
    except Exception as e:
        print(f"ERROR in generate_dsl_node: {e}")
        import traceback
        traceback.print_exc()
        # 返回一个虚拟 DSL 以防止崩溃，还是重新抛出？
        # 重新抛出允许服务器捕获它并发送错误事件
        raise e
