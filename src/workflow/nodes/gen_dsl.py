import asyncio
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from src.workflow.state import AgentState
from src.core.llm import get_llm
from src.core.database import get_query_db
from src.domain.memory.few_shot import get_few_shot_retriever
from src.domain.schema.value import get_value_searcher
from src.domain.knowledge.glossary import get_glossary_retriever

# --- Prompts ---
BASE_SYSTEM_PROMPT = """
你是一个 DSL 生成器。你的任务是将用户的最新查询意图转换为严格的 JSON DSL 格式，该格式将用于生成标准 SQL。

注意：目标数据库为 PostgreSQL。请使用 PostgreSQL 方言的日期/时间语法与函数（例如：current_date、interval、date_trunc、extract），不要使用 MySQL 专有函数（如 CURDATE、DATE_SUB、DATE_FORMAT）。

数据库 Schema:
{schema_info}

允许使用的约束 (来自 SchemaGuard):
{allowed_schema_hints}

DSL 规范 (JSON):
{{
  "command": "SELECT",
  "from": "主表名",
  "joins": [
    {{"table": "连接表名", "type": "INNER/LEFT", "on": "关联条件 (例如 'orders.user_id = users.id')"}}
  ],
  "columns": [
    {{"name": "列名", "table": "所属表名 (可选)", "agg": "SUM/COUNT/AVG/MAX/MIN (可选)", "alias": "别名 (可选)"}}
  ],
  "where": {{
    "logic": "AND/OR",
    "conditions": [
      {{"column": "列名", "op": "操作符 (=, >, <, LIKE, IN)", "value": "值 (数字或字符串)"}},
      {{"logic": "AND/OR", "conditions": [...]}} (嵌套条件)
    ]
  }},
  "having": {{
    "logic": "AND/OR",
    "conditions": [
      {{"column": "聚合列 (例如 'sum(amount)')", "op": ">", "value": 100}}
    ]
  }},
  "group_by": ["列名1", "列名2"],
  "order_by": [{{"column": "列名", "direction": "ASC/DESC"}}],
  "limit": 整数,
  "distinct": true/false
}}

DSL 示例:
{{
  "command": "SELECT",
  "distinct": true,
  "from": "orders",
  "joins": [{{"table": "users", "type": "INNER", "on": "orders.user_id = users.id"}}],
  "columns": [{{"name": "username", "table": "users"}}, {{"name": "amount", "table": "orders", "agg": "SUM", "alias": "total"}}],
  "where": {{"logic": "AND", "conditions": [{{"column": "created_at", "op": ">=", "value": "2023-01-01"}}]}},
  "group_by": ["users.username"],
  "having": {{"logic": "AND", "conditions": [{{"column": "sum(amount)", "op": ">", "value": 1000}}]}},
  "order_by": [{{"column": "total", "direction": "DESC"}}],
  "limit": 5
}}

{value_hints}

{rag_examples}

{glossary_hints}

{rewritten_query_context}

{error_context}

规则:
1. 在输出 JSON 之前，必须先进行思考 (Chain-of-Thought)。请在 `<thinking>...</thinking>` 标签中详细描述你的推理过程。
   - 分析用户的意图是什么。
   - 确定需要查询哪些表。
   - 确定表之间的连接条件 (JOIN ON)。
   - 确定筛选条件 (WHERE) 和 聚合逻辑。
   - 检查是否有 Schema 中不存在的列或表。
2. 思考结束后，输出 ```json ... ``` 代码块。
3. 严格遵循 DSL 规范，不要编造字段；只能使用【relevant_schema】中呈现的表与列。
4. 如果用户查询包含与 [实体链接建议] 匹配的值，你必须使用建议中的精确值。
5. "joins" 数组用于多表查询。如果只涉及单表，忽略此字段。
6. "columns" 如果为空或未指定，默认为 SELECT * (但尽量明确列出)。
7. 优先参考 [业务术语定义] 来构建 WHERE 条件或选择字段。
8. JOIN 的 on 条件必须使用真实存在的列。你可以根据候选关联键（列名相似、*_id 命名、类型匹配）选择 ON；避免编造不存在的字段。一旦不确定，请减少 JOIN 并返回单表查询或请求澄清。
9. 若定义了列别名 (alias)，请在 order_by/group_by 等引用时优先使用该 alias。
10. 仅返回单个顶层 JSON 对象；如果需要多查询，请选择对用户问题最关键的单查询输出。严禁输出多个并列的 JSON 对象或数组。
11. 在涉及日期范围与按月统计时，优先使用：date_trunc('month', 列名) 及 current_date - interval 'N months' 等 PostgreSQL 语法。

输出格式示例:
<thinking>
用户想查询...
涉及表 A 和 B...
连接条件是...
</thinking>
```json
{{ ... }}
```
"""

from src.core.event_bus import EventBus

async def generate_dsl_node(state: AgentState, config: dict = None) -> dict:
    print("DEBUG: Entering generate_dsl_node (Async)")
    try:
        if state.get("interrupt_pending"):
            return {"messages": [], "error": None}
        project_id = config.get("configurable", {}).get("project_id") if config else None
        llm = get_llm(node_name="GenerateDSL", project_id=project_id)
        
        # Emit Initial Status
        await EventBus.emit_substep(
            node="GenerateDSL",
            step="准备中",
            detail="正在收集上下文信息 (Few-shot, 术语表, 实体值)..."
        )

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

        def _get_glossary_hints():
            try:
                if last_human_msg:
                    retriever = get_glossary_retriever(project_id)
                    return retriever.retrieve(last_human_msg)
            except Exception as e:
                print(f"Glossary retrieval failed: {e}")
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
        value_hints_task = asyncio.to_thread(_get_value_hints)
        glossary_hints_task = asyncio.to_thread(_get_glossary_hints)
        rag_examples_task = asyncio.to_thread(_get_few_shot_examples)
        
        # 1. 优先使用 State 中的 Schema
        schema_info = state.get("relevant_schema", "")
        
        # 2. 如果没有，并行启动 Schema 检查
        schema_task = None
        if not schema_info:
            print("DEBUG: No relevant_schema found, scheduling fallback inspection...")
            schema_task = asyncio.to_thread(_inspect_schema_fallback)

        # 等待所有任务
        tasks = [value_hints_task, rag_examples_task, glossary_hints_task]
        if schema_task:
            tasks.append(schema_task)
            
        results = await asyncio.gather(*tasks)
        
        value_hints = results[0]
        rag_examples = results[1]
        glossary_hints = results[2]
        
        if value_hints:
            await EventBus.emit_substep(node="GenerateDSL", step="实体链接", detail="已找到相关数据库值映射")
        if rag_examples:
            await EventBus.emit_substep(node="GenerateDSL", step="样本召回", detail="已加载相关 Few-shot 案例")
        if glossary_hints:
            await EventBus.emit_substep(node="GenerateDSL", step="术语召回", detail="已加载相关业务定义")

        if schema_task:
            full_schema_json = results[3]
            if full_schema_json:
                if len(full_schema_json) > 5000:
                    schema_info = full_schema_json[:5000] + "\n...(truncated)"
                else:
                    schema_info = full_schema_json
            else:
                schema_info = "Schema info unavailable"
        
        # 构建系统提示词上下文 (使用变量避免 Prompt Injection)
        rewritten_query_context = ""
        rewritten_query = state.get("rewritten_query")
        if rewritten_query:
            rewritten_query_context = f"\n\n上下文感知重写查询: '{rewritten_query}'"
        
        # 重试逻辑：错误上下文
        error_context = ""
        error = state.get("error")
        if error:
            print(f"DEBUG: GenerateDSL - Injecting error context: {error}")
            error_context = f"\n\n!!! 严重警告 !!!\n上一次生成的 DSL 导致了 SQL 错误:\n{error}\n请根据错误修复 DSL (检查表名/列名)。"
            await EventBus.emit_substep(node="GenerateDSL", step="错误重试", detail="正在基于报错信息调整生成策略")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", BASE_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="history"),
        ]).partial(
            schema_info=schema_info, 
            rag_examples=rag_examples, 
            value_hints=value_hints,
            glossary_hints=glossary_hints,
            rewritten_query_context=rewritten_query_context,
            error_context=error_context,
            allowed_schema_hints=""
        )
        allowed_map = state.get("allowed_schema") or {}
        if allowed_map:
            parts = []
            for t, cols in allowed_map.items():
                cols_str = ", ".join(cols[:30])
                parts.append(f"{t}: {cols_str}")
            prompt = ChatPromptTemplate.from_messages([
                ("system", BASE_SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="history"),
            ]).partial(
                schema_info=schema_info, 
                rag_examples=rag_examples, 
                value_hints=value_hints,
                glossary_hints=glossary_hints,
                rewritten_query_context=rewritten_query_context,
                error_context=error_context,
                allowed_schema_hints="\n".join(parts)
            )
        # 尝试结构化输出，失败则回退
        chain = prompt | llm
        
        print("DEBUG: Invoking LLM for DSL generation (Async)...")
        await EventBus.emit_substep(node="GenerateDSL", step="推理中", detail="正在思考并生成 DSL 结构...")
        
        result = await chain.ainvoke({"history": messages}, config=config)

        
        content = result.content.strip()
        print(f"DEBUG: LLM Response (len={len(content)})")
        
        # Extract Thinking Block (Optional log)
        if "<thinking>" in content and "</thinking>" in content:
            thinking = content.split("<thinking>")[1].split("</thinking>")[0]
            print(f"DEBUG: DSL Thinking Process:\n{thinking}")
            await EventBus.emit_substep(node="GenerateDSL", step="思考完成", detail=thinking[:100] + "...")

        # Extract JSON
        dsl_str = content
        if "```json" in content:
            dsl_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            dsl_str = content.split("```")[1].split("```")[0].strip()
            
        if not dsl_str:
             return {"dsl": '{"error": "Empty DSL generated"}'}
        # 若返回非 JSON（常见澄清文本），则走澄清路径
        if not dsl_str.strip().startswith("{"):
            return {
                "messages": [],
                "intent_clear": False
            }

        await EventBus.emit_substep(node="GenerateDSL", step="生成完成", detail="DSL 协议已就绪")
        return {"dsl": dsl_str}
        
    except Exception as e:
        print(f"ERROR in generate_dsl_node: {e}")
        import traceback
        traceback.print_exc()
        raise e
