from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, model_validator
from typing import List, Literal, Any

from src.workflow.state import AgentState
from src.core.llm import get_llm

llm = None # 将在节点内部初始化

class PlanStep(BaseModel):
    node: Literal["ClarifyIntent", "SelectTables", "SchemaGuard", "GenerateDSL", "DSLtoSQL", "ExecuteSQL", "Visualization", "TableQA", "PythonAnalysis"] = Field(
        ..., description="要执行的节点名称"
    )
    desc: str = Field(..., description="步骤描述")

class PlannerResponse(BaseModel):
    plan: List[PlanStep] = Field(..., description="执行计划")

    @model_validator(mode='before')
    @classmethod
    def map_steps_to_plan(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "steps" in data and "plan" not in data:
                data["plan"] = data["steps"]
        return data

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

请制定执行计划，包含一系列步骤（node 和 desc），并以 JSON 格式严格输出。
输出必须是一个 JSON 对象，且必须包含一个名为 \"plan\" 的列表字段。
"""

REWRITE_SYSTEM_PROMPT = """
你是一个对话上下文重写专家。你的任务是将用户的最新回复，结合之前的对话历史，重写为一个完整、独立的查询语句。

规则：
1. 如果用户的最新回复依赖于上文（例如包含'它'、'这个'、'按地区呢'等），请补全上下文。
2. 如果用户的最新回复是独立的，请保持原样。
3. **忽略任何 JSON 格式的系统输出**（如 {{"status": "AMBIGUOUS"...}}），只关注自然语言对话。
4. 如果历史记录中包含系统生成的澄清问题（如选项列表），请将用户的选择与问题结合，形成完整的意图。
   例如：系统问“看哪个系统？”，用户答“跨境业务”，重写为“查看跨境业务系统的用户增长”。
5. 只输出重写后的纯文本查询，不要输出 JSON，不要输出 Markdown，不要输出解释。
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
        # 若为新会话启动（fresh_start）或仅有一条用户消息，则跳过多轮改写
        if state.get("fresh_start") or len(messages) <= 1:
            # 单轮对话或鲜明的新会话，直接取最后一条人类消息
            for msg in reversed(messages):
                if msg.type == "human":
                    rewritten_query = msg.content
                    break
        elif len(messages) > 1:
            print("DEBUG: Planner - Detecting multi-turn context, attempting rewrite...")
            rewrite_prompt = ChatPromptTemplate.from_messages([
                ("system", REWRITE_SYSTEM_PROMPT),
                ("placeholder", "{messages}")
            ])
            rewrite_chain = rewrite_prompt | llm
            try:
                # 异步调用重写
                rewrite_res = await rewrite_chain.ainvoke({"messages": messages})
                content = rewrite_res.content.strip()
                
                # 验证：如果结果看起来像 JSON，说明重写失败（LLM 被误导），回退到原始用户消息
                if content.startswith("{") or "AMBIGUOUS" in content:
                    print(f"DEBUG: Planner - Rewrite produced JSON artifact ('{content[:50]}...'). Fallback to raw user input.")
                    for msg in reversed(messages):
                        if msg.type == "human":
                            rewritten_query = msg.content
                            break
                else:
                    rewritten_query = content
                    print(f"DEBUG: Planner - Rewritten Query: {rewritten_query}")
            except Exception as e:
                print(f"DEBUG: Planner - Rewrite failed: {e}")
        # 清理 fresh_start，避免影响后续轮次
        if state.get("fresh_start"):
            # 返回时由上层 State 合并，这里仅显式意图
            pass

    # --------------------------------------------
    
    # 构建假设上下文
    hypotheses_context = "无"
    if hypotheses:
        hypotheses_context = "\n".join([f"- {h}" for h in hypotheses])
        print(f"DEBUG: Planner using hypotheses: {hypotheses}")

    # --- Clarification Context Integration ---
    # 如果存在澄清答案，说明用户刚刚完成澄清。我们需要将此信息显式注入 Prompt，
    # 引导 Planner 生成直接执行的计划，而不是再次询问。
    clarify_answer = state.get("clarify_answer")
    user_query_context = rewritten_query or "Unknown Query"
    
    if clarify_answer:
        print(f"DEBUG: Planner - Integrating clarification answer: {clarify_answer}")
        user_query_context += f"\n\n【重要】用户刚刚针对歧义进行了澄清，选择/回答是：'{clarify_answer}'。\n请基于此明确意图生成执行计划，**严禁**再次生成 ClarifyIntent 步骤。"

    prompt = ChatPromptTemplate.from_messages([
        ("system", BASE_SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ]).partial(
        user_query=user_query_context,
        hypotheses_context=hypotheses_context
    )
    
    chain = prompt | llm.with_structured_output(PlannerResponse)
    plan = []
    
    # --- 1. 尝试结构化输出 (Primary Strategy) ---
    try:
        print("DEBUG: Planner - Attempting structured output...")
        result = await chain.ainvoke({"messages": messages})
        plan = [{"node": step.node, "desc": step.desc, "status": "wait"} for step in result.plan]
        print(f"DEBUG: Planner - Structured output successful. Steps: {len(plan)}")
    except Exception as e:
        print(f"DEBUG: Planner structured output failed: {e}")
        
        # --- 2. 回退：非结构化调用 + JSON 解析 (Fallback Strategy) ---
        try:
            print("DEBUG: Planner - Attempting fallback (plain text parsing)...")
            plain_chain = prompt | llm
            plain_res = await plain_chain.ainvoke({"messages": messages})
            content = getattr(plain_res, "content", str(plain_res)).strip()
            
            # 清理 Markdown 代码块
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            import json, re
            # 尝试直接解析
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                # 正则提取 JSON 对象
                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                else:
                    raise ValueError("No JSON object found")
            
            steps = parsed.get("plan") or parsed.get("steps") or []
            if isinstance(steps, list) and steps:
                for s in steps:
                    node = s.get("node", "SelectTables")
                    desc = s.get("desc", "未提供描述")
                    plan.append({"node": node, "desc": desc, "status": "wait"})
                print(f"DEBUG: Planner - Fallback parsing successful. Steps: {len(plan)}")
        except Exception as e2:
            print(f"DEBUG: Planner fallback parse failed: {e2}")
    
    # --- 4. Loop Prevention: Remove ClarifyIntent if already clarified ---
    # 如果用户已经回答了澄清问题，或者意图被标记为清晰，则不应该再生成 ClarifyIntent 步骤
    if state.get("clarify_answer") or (state.get("intent_clear") and state.get("last_executed_node") == "ClarifyIntent"):
        original_len = len(plan)
        # 过滤掉所有 ClarifyIntent 节点
        plan = [step for step in plan if step["node"] != "ClarifyIntent"]
        if len(plan) < original_len:
            print(f"DEBUG: Planner - Removed {original_len - len(plan)} ClarifyIntent steps (Intent already clear/answered).")

    # --- 5. Dependency Validation: Ensure DSLtoSQL exists ---
    # 确保如果计划包含 GenerateDSL 和 ExecuteSQL，中间必须有 DSLtoSQL
    has_gen_dsl = False
    has_dsl2sql = False
    has_exec_sql = False
    gen_dsl_idx = -1
    
    for i, step in enumerate(plan):
        if step["node"] == "GenerateDSL":
            has_gen_dsl = True
            gen_dsl_idx = i
        elif step["node"] == "DSLtoSQL":
            has_dsl2sql = True
        elif step["node"] == "ExecuteSQL":
            has_exec_sql = True
    
    if has_gen_dsl and has_exec_sql and not has_dsl2sql:
        print("DEBUG: Planner - Detected missing DSLtoSQL step. Injecting it.")
        # 插入 DSLtoSQL 到 GenerateDSL 之后
        dsl2sql_step = {"node": "DSLtoSQL", "desc": "将 DSL 转换为可执行 SQL", "status": "wait"}
        plan.insert(gen_dsl_idx + 1, dsl2sql_step)

    # --- 3. 兜底默认计划 (Safety Net) ---
    if not plan:
        # 如果有澄清答案但计划为空（说明原计划只有 ClarifyIntent），则生成标准查询计划
        if state.get("clarify_answer"):
             print("DEBUG: Planner - Plan empty after filtering ClarifyIntent. Using STANDARD PLAN.")
             plan = [
                {"node": "SelectTables", "desc": "根据澄清后的意图选择数据表", "status": "wait"},
                {"node": "SchemaGuard", "desc": "Schema 预检", "status": "wait"},
                {"node": "GenerateDSL", "desc": "生成查询 DSL", "status": "wait"},
                {"node": "DSLtoSQL", "desc": "转换为 SQL", "status": "wait"},
                {"node": "ExecuteSQL", "desc": "执行查询", "status": "wait"},
            ]
        else:
            print("DEBUG: Planner - All strategies failed. Using DEFAULT PLAN.")
            plan = [
                {"node": "ClarifyIntent", "desc": "确认用户意图是否清晰", "status": "wait"},
                {"node": "SelectTables", "desc": "选择与问题相关的数据表", "status": "wait"},
                {"node": "SchemaGuard", "desc": "进行 Schema 预检并生成约束", "status": "wait"},
                {"node": "GenerateDSL", "desc": "生成中间 DSL 表达查询意图", "status": "wait"},
                {"node": "DSLtoSQL", "desc": "将 DSL 转换为可执行 SQL", "status": "wait"},
                {"node": "ExecuteSQL", "desc": "执行 SQL 并返回结果", "status": "wait"},
            ]
    
    return {
        "plan": plan, 
        "current_step_index": 0,
        "intent_clear": True,
        "rewritten_query": rewritten_query, # 保存到 State 供后续节点使用
        # 规划完成后，清除 clarify_answer，因为它已经被整合进 plan 或上下文，不需要再影响后续逻辑
        "clarify_answer": None 
    }
