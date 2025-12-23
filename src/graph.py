import os
from langgraph.graph import StateGraph, START, END
# 替换为自定义的 SimpleRedisSaver
from src.utils.simple_redis_saver import SimpleRedisSaver
from redis import Redis

from src.state.state import AgentState
from src.agents.supervisor import supervisor_node
from src.agents.clarify import clarify_intent_node
from src.agents.gen_dsl import generate_dsl_node
from src.agents.dsl2sql import dsl_to_sql_node
from src.agents.execute import execute_sql_node

def create_graph():
    """
    创建并编译 LangGraph 工作流图。
    使用 SimpleRedisSaver 进行状态持久化 (短期记忆)，支持多轮对话。
    """
    workflow = StateGraph(AgentState)

    # 添加节点 (Nodes)
    workflow.add_node("Supervisor", supervisor_node)
    workflow.add_node("ClarifyIntent", clarify_intent_node)
    workflow.add_node("GenerateDSL", generate_dsl_node)
    workflow.add_node("DSLtoSQL", dsl_to_sql_node)
    workflow.add_node("ExecuteSQL", execute_sql_node)

    # 添加边 (Edges)
    # 起点 -> Supervisor
    workflow.add_edge(START, "Supervisor")

    # Worker -> Supervisor (控制权回归循环)
    # 所有 Worker 执行完毕后都回到 Supervisor 进行下一步决策
    workflow.add_edge("ClarifyIntent", "Supervisor")
    workflow.add_edge("GenerateDSL", "Supervisor")
    workflow.add_edge("DSLtoSQL", "Supervisor")
    workflow.add_edge("ExecuteSQL", "Supervisor")

    # Supervisor 条件边 (Conditional Edges)
    # 根据 Supervisor 输出的 'next' 字段决定下一步去向
    workflow.add_conditional_edges(
        "Supervisor",
        lambda x: x["next"],
        {
            "ClarifyIntent": "ClarifyIntent",
            "GenerateDSL": "GenerateDSL",
            "DSLtoSQL": "DSLtoSQL",
            "ExecuteSQL": "ExecuteSQL",
            "FINISH": END
        }
    )

    # 初始化 Redis Checkpointer
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_password = os.getenv("REDIS_PASSWORD")

    try:
        redis_conn = Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=0,
            decode_responses=False # pickle serialization usually needs bytes
        )
        # 使用自定义的 SimpleRedisSaver，不需要 RedisJSON 模块支持
        checkpointer = SimpleRedisSaver(conn=redis_conn)
        print(f"成功连接到 Redis 状态存储 ({redis_host}:{redis_port})")
    except Exception as e:
        print(f"Redis 连接失败，回退到内存存储: {e}")
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer)
