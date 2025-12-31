import json
import asyncio
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from src.workflow.state import AgentState
from src.core.llm import get_llm
from src.core.database import get_query_db
from src.domain.memory.few_shot import get_few_shot_retriever
from src.domain.schema.value import get_value_searcher

# --- Prompts ---
BASE_SYSTEM_PROMPT = """
你是一个 DSL 生成器。你的任务是将用户的最新查询意图转换为 JSON DSL 格式。
数据库 Schema:
{schema_info}

DSL 结构示例: {{"table": "<表名>", "filters": [{{"field": "<列名>", "operator": "...", "value": "..."}}], "select": ["<列名1>", "<列名2>"]}}

{value_hints}

{rag_examples}

规则:
1. 仅返回有效的 JSON 字符串。不要包含 Markdown。
2. 如果用户查询包含与 [实体链接建议] 匹配的值，你必须使用建议中的精确值。
3. 如果用户是在回复澄清问题，请结合上下文处理。
"""

async def generate_dsl_node(state: AgentState, config: dict = None) -> dict:
    print("DEBUG: Entering generate_dsl_node (Async)")
    try:
        project_id = config.get("configurable", {}).get("project_id") if config else None
        llm = get_llm(node_name="GenerateDSL", project_id=project_id)
        
        messages = state["messages"]
        if len(messages) > 10:
            messages = messages[-10:]
            
        # 获取最新的用户查询
        last_human_msg = ""
        for msg in reversed(messages):
            if msg.type == "human":
                last_human_msg = msg.content
                break
        
        # 定义辅助函数以在线程池中运行同步任务
        def _get_value_hints():
            try:
                if last_human_msg and project_id:
                    searcher = get_value_searcher(project_id)
                    matches = searcher.search_similar_values(last_human_msg, limit=5)
                    
                    if matches:
                        hints = []
                        for m in matches:
                            if m['score'] < 1.5: 
                                hints.append(f"- 输入: '{m['value']}' -> 数据库值: '{m['value']}' (位于 {m['table']}.{m['column']})")
                        
                        if hints:
                            print(f"DEBUG: Value Linking Hints: {hints}")
                            return "### 实体链接建议 (请使用这些精确值):\n" + "\n".join(hints)
            except Exception as e:
                print(f"Value linking failed: {e}")
            return ""

        def _get_few_shot_examples():
            try:
                if last_human_msg:
                    retriever = get_few_shot_retriever(project_id)
                    examples = retriever.retrieve(last_human_msg, k=3)
                    if examples:
                        print(f"DEBUG: Retrieved few-shot examples")
                        return "### 参考示例 (Few-Shot):\n" + examples
            except Exception as e:
                print(f"Few-shot retrieval failed: {e}")
            return ""

        def _inspect_schema_fallback():
            try:
                query_db = get_query_db(project_id)
                # inspect_schema 是同步的
                return query_db.inspect_schema()
            except Exception as e:
                print(f"DEBUG: Error inspecting schema: {e}")
                return ""

        # 并行执行上下文检索
        # 注意：这些操作主要是在 ChromaDB 或 SQLite 上查询，虽然有 GIL，但在 I/O 期间会释放
        value_hints_task = asyncio.to_thread(_get_value_hints)
        rag_examples_task = asyncio.to_thread(_get_few_shot_examples)
        
        # 1. 优先使用 State 中的 Schema
        schema_info = state.get("relevant_schema", "")
        
        # 2. 如果没有，并行启动 Schema 检查
        schema_task = None
        if not schema_info:
            print("DEBUG: No relevant_schema found, scheduling fallback inspection...")
            schema_task = asyncio.to_thread(_inspect_schema_fallback)

        # 等待所有任务
        tasks = [value_hints_task, rag_examples_task]
        if schema_task:
            tasks.append(schema_task)
            
        results = await asyncio.gather(*tasks)
        
        value_hints = results[0]
        rag_examples = results[1]
        if schema_task:
            full_schema_json = results[2]
            if full_schema_json:
                if len(full_schema_json) > 5000:
                    schema_info = full_schema_json[:5000] + "\n...(truncated)"
                else:
                    schema_info = full_schema_json
            else:
                schema_info = "Schema info unavailable"
        
        # 构建系统提示词
        system_prompt = BASE_SYSTEM_PROMPT
        
        # 上下文提示：重写后的查询
        rewritten_query = state.get("rewritten_query")
        if rewritten_query:
            system_prompt += f"\n\n上下文感知重写查询: '{rewritten_query}'"
        
        # 重试逻辑：错误上下文
        error = state.get("error")
        if error:
            print(f"DEBUG: GenerateDSL - Injecting error context: {error}")
            system_prompt += f"\n\n!!! 严重警告 !!!\n上一次生成的 DSL 导致了 SQL 错误:\n{error}\n请根据错误修复 DSL (检查表名/列名)。"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="history"),
        ]).partial(schema_info=schema_info, rag_examples=rag_examples, value_hints=value_hints)
        
        chain = prompt | llm
        
        print("DEBUG: Invoking LLM for DSL generation (Async)...")
        result = await chain.ainvoke({"history": messages}, config=config)
        
        dsl_str = result.content.strip()
        print(f"DEBUG: DSL generated (len={len(dsl_str)})")
        
        # 清理 Markdown
        if "```json" in dsl_str:
            dsl_str = dsl_str.split("```json")[1].split("```")[0].strip()
        elif "```" in dsl_str:
            dsl_str = dsl_str.split("```")[1].split("```")[0].strip()
            
        if not dsl_str:
             return {"dsl": '{"error": "Empty DSL generated"}'}

        return {"dsl": dsl_str}
        
    except Exception as e:
        print(f"ERROR in generate_dsl_node: {e}")
        import traceback
        traceback.print_exc()
        raise e
