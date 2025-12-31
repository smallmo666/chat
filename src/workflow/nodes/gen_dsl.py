import json
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from src.workflow.state import AgentState
from src.core.llm import get_llm
from src.core.database import get_app_db
from src.domain.memory.few_shot import get_few_shot_retriever
from src.domain.schema.value import get_value_searcher

llm = None # Will be initialized in node

# --- Prompts ---
BASE_SYSTEM_PROMPT = """
你是一个 DSL 生成器。根据用户的对话历史，将用户的最新查询意图转换为 JSON DSL 格式。
数据库 Schema 信息如下:
{schema_info}

Schema 结构示例: {{"table": "<表名>", "filters": [{{"field": "<列名>", "operator": "...", "value": "..."}}], "select": ["<列名1>", "<列名2>"]}}
{value_hints}
{rag_examples}

仅返回有效的 JSON 字符串，不要包含 Markdown 格式。
注意：如果用户是在回复澄清问题（例如'是的'），请结合上下文理解其真实意图。
"""

def generate_dsl_node(state: AgentState, config: dict = None) -> dict:
    print("DEBUG: Entering generate_dsl_node")
    try:
        project_id = config.get("configurable", {}).get("project_id") if config else None
        llm = get_llm(node_name="GenerateDSL", project_id=project_id)
        
        # 不再只取最后一条消息，而是使用整个对话历史来理解上下文
        messages = state["messages"]
        # 保留最后 10 条消息应该足够了
        if len(messages) > 10:
            messages = messages[-10:]
            
        # 获取最新的用户查询用于检索 Few-Shot
        last_human_msg = ""
        for msg in reversed(messages):
            if msg.type == "human":
                last_human_msg = msg.content
                break
        
        # --- 1. Entity Linking (Value Search) ---
        value_hints = ""
        try:
            if last_human_msg and project_id:
                searcher = get_value_searcher(project_id)
                matches = searcher.search_similar_values(last_human_msg, limit=5)
                
                if matches:
                    hints = []
                    for m in matches:
                        # 过滤掉相似度太低的
                        if m['score'] < 1.5: 
                            hints.append(f"- '{m['value']}' (found in {m['table']}.{m['column']})")
                    
                    if hints:
                        value_hints = "检测到潜在的数据库实体值匹配 (Entity Linking):\n" + "\n".join(hints)
                        print(f"DEBUG: Value Linking Hints: {hints}")
        except Exception as e:
            print(f"Value linking failed: {e}")
        # ----------------------------------------

        # --- 2. Few-Shot Retrieval ---
        retriever = get_few_shot_retriever(project_id)
        rag_examples = ""
        if last_human_msg:
            rag_examples = retriever.retrieve(last_human_msg, k=3)
            if rag_examples:
                print(f"DEBUG: Retrieved few-shot examples (len={len(rag_examples)})")
        # --------------------------
        
        # 获取数据库 Schema 信息
        schema_info = state.get("relevant_schema", "")
        print(f"DEBUG: Schema info length: {len(schema_info)}")
        
        if not schema_info:
            print("DEBUG: No relevant_schema found, falling back to stored schema")
            try:
                app_db = get_app_db()
                full_schema_json = app_db.get_stored_schema_info()
                if len(full_schema_json) > 5000:
                    schema_info = full_schema_json[:5000] + "\n...(truncated)"
                else:
                    schema_info = full_schema_json
            except Exception as e:
                print(f"DEBUG: Error fetching stored schema: {e}")
                schema_info = "Schema info unavailable"
        
        # 动态构建系统提示词
        system_prompt = BASE_SYSTEM_PROMPT
        
        # --- Context Hint: Rewritten Query ---
        rewritten_query = state.get("rewritten_query")
        if rewritten_query:
            print(f"DEBUG: GenerateDSL - Injecting rewritten query hint: {rewritten_query}")
            system_prompt += f"\n\n参考上下文重写后的查询: '{rewritten_query}'"
        # -------------------------------------
        
        # --- Retry Logic: Error Context ---
        error = state.get("error")
        if error:
            print(f"DEBUG: GenerateDSL - Injecting error context: {error}")
            system_prompt += f"\n\n!!! 重要提示 !!!\n上一次生成的 DSL 导致了 SQL 执行错误：\n{error}\n请根据错误信息修正 DSL（例如：检查表名、列名是否正确）。"
        # ----------------------------------
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="history"),
        ]).partial(schema_info=schema_info, rag_examples=rag_examples, value_hints=value_hints)
        
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
