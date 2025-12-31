import json
import re
from langchain_core.messages import AIMessage
from src.workflow.state import AgentState
from src.core.database import get_query_db
from src.domain.memory.short_term import get_memory
from src.utils.security import is_safe_sql
from src.domain.memory.few_shot import get_few_shot_retriever
from src.domain.memory.semantic_cache import get_semantic_cache

async def execute_sql_node(state: AgentState, config: dict) -> dict:
    """
    执行 SQL 节点。
    获取生成的 SQL，在 QueryDatabase (querydb) 中执行，并返回结果。
    同时将成功的查询交互保存到长期记忆中。
    """
    sql = state.get("sql")
    if not sql:
        return {
            "error": "No SQL found in state to execute.",
            "results": "Error: No SQL generated."
        }

    # Security Check
    if not is_safe_sql(sql):
        error_msg = f"Security Alert: SQL contains forbidden keywords (DROP, DELETE, UPDATE, etc.). Execution blocked.\nSQL: {sql}"
        return {
            "error": error_msg,
            "results": "Execution Blocked: Security Violation"
        }

    # 使用 QueryDatabase 进行查询执行
    db = get_query_db()
    
    try:
        # 尝试使用异步执行
        try:
            db_result = await db.run_query_async(sql)
        except Exception as async_e:
            print(f"Async execution failed, falling back to sync: {async_e}")
            db_result = db.run_query(sql)
        
        # 检查数据库执行层面的错误 (虽然 db.run_query 内部 catch 了，但会返回 error 字段)
        if db_result.get("error"):
             raise Exception(db_result["error"])
        
        markdown_result = db_result.get("markdown", "")
        json_result = db_result.get("json", "[]")

        # 保存到长期记忆
        # 获取用户 ID
        user_id = config.get("configurable", {}).get("thread_id", "default_user")
        
        # 构建记忆内容：用户的查询意图 + 生成的 SQL
        # 优先使用 rewritten_query (更准确的意图)，如果不存在则使用 messages 中的
        rewritten_query = state.get("rewritten_query")
        
        messages = state.get("messages", [])
        user_query = "未知查询"
        if rewritten_query:
            user_query = rewritten_query
        else:
            for msg in reversed(messages):
                if msg.type == "human":
                    user_query = msg.content
                    break
        
        # --- RAG Optimization: Save Query -> DSL pair ---
        dsl = state.get("dsl", "")
        
        # --- Feedback Loop: Detect User Correction ---
        # 如果当前 SQL 与最初生成的 SQL 不一致 (假设 State 中保存了 original_sql，或者通过 comparison)
        # 这里的 state['sql'] 是最终执行的 SQL。
        # 如果这是 Human-in-the-Loop 流程，我们需要知道是否被修改过。
        # 简单判定：如果 state 中有 'manual_modified' 标记 (需要前端/API支持传递)
        # 或者，我们可以假设只要执行成功，就是好的样本。
        # 为了更精准，我们依赖 DSLtoSQL 生成的 sql 和最终执行的 sql 是否一致？
        # 但 DSLtoSQL 生成的 sql 已经覆盖写入 state['sql'] 了。
        # 我们假设只要执行成功，它就是高质量的样本 (Execution-based Filtering)。
        
        # Feedback Learning: 保存 (Question, SQL) 到 Few-Shot
        # 仅当结果不为空时才保存，认为这是一次有效的成功查询
        if json_result and json_result != "[]" and json_result != "null":
            project_id = config.get("configurable", {}).get("project_id")
            
            # 1. 存入 Few-Shot 样本库 (Chroma) - 项目维度 (自进化)
            # 这里的逻辑与上方重复了，合并处理
            pass 
        
        # --- RAG Optimization & Feedback Learning Merged ---
        if dsl and len(dsl) < 10000: # 简单保护
             memory_text = f"Q: {user_query}\nDSL: {dsl}"
             try:
                # 1. 存入长期记忆 (Mem0) - 用户维度
                memory_client = get_memory()
                if memory_client.add(user_id=user_id, text=memory_text):
                    print(f"已保存 RAG 记忆: {memory_text[:50]}...")
                
                # 2. 存入 Few-Shot 样本库 & Semantic Cache (Chroma) - 项目维度 (自进化)
                # 仅当结果不为空时才保存，认为这是一次有效的成功查询
                if json_result and json_result != "[]" and json_result != "null":
                    project_id = config.get("configurable", {}).get("project_id")
                    
                    # A. Semantic Cache (Direct Hit)
                    try:
                        cache = get_semantic_cache(project_id)
                        cache.add(user_query, sql)
                    except Exception as ce:
                        print(f"Failed to update Semantic Cache: {ce}")

                    # B. Few-Shot Examples (Reference)
                    try:
                        retriever = get_few_shot_retriever(project_id)
                        retriever.add_example(
                            question=user_query,
                            dsl=dsl,
                            sql=sql,
                            metadata={"user_id": user_id, "source": "auto_learning"} # Unified source
                        )
                        print(f"Feedback Loop: Saved successful query to Few-Shot. Query: {user_query}")
                    except Exception as fe:
                        print(f"Failed to update Few-Shot Retriever: {fe}")
             except Exception as e:
                print(f"保存 RAG 记忆失败: {e}")
        # ------------------------------------------------
        
        # 兼容旧逻辑 (可选，如果不再需要 SQL 记忆可移除，但保留无害)
        # memory_text_old = f"用户查询: {user_query} -> 生成 SQL: {sql}"
        
        # 我们返回结果，并将其作为一条消息添加到历史记录中
        # 注意：为了防止 Context Window 溢出，如果结果过长，我们在历史记录中只保存摘要。
        # 完整结果仍然通过 'results' 键传递给后续节点（如 DataAnalysis）。
        # 修改：我们将 'results' 字段改为存储 JSON 数据，以便后续 Agent 更好处理。
        
        display_result = markdown_result
        # 增加截断长度以支持更多数据的表格展示，避免破坏表格结构
        # 一般 LLM 上下文足够大，我们可以保留更多
        if len(markdown_result) > 5000:
            display_result = markdown_result[:5000] + "\n\n... (结果过长已截断，完整结果用于后续分析)"
            
        return {
            "results": json_result, # Store JSON string for agents
            # 移除 Markdown 表格展示，仅返回摘要提示，强制前端依赖 Visualization 节点渲染表格组件
            "messages": [AIMessage(content=f"查询执行成功，共找到 {len(json.loads(json_result))} 条记录。")],
            "error": None, # Clear error on success
            "retry_count": 0 # Reset retry count on success
        }
        
    except Exception as e:
        error_msg = str(e)
        
        # 针对只读副本错误的特殊处理
        # 如果是 "read only" 错误，但 SQL 看起来是安全的 (SELECT)，这通常意味着
        # 数据库连接配置为了只读，但某些操作（如 Pandas 内部临时表）触发了写检查，或者用户真的在写。
        # 但如果是 SELECT，我们应该提示用户检查配置。
        if "read only" in error_msg.lower():
             error_msg = f"Database Error: The database is in read-only mode. Please check your query or database configuration. ({error_msg})"

        return {
            "error": error_msg,
            "results": f"SQL Execution Failed: {error_msg}"
        }
