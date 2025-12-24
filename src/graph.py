import os
from langgraph.graph import StateGraph, START, END
# 替换为自定义的 SimpleRedisSaver
from src.utils.simple_redis_saver import SimpleRedisSaver
from redis import Redis

from src.state.state import AgentState
from src.agents.planner import planner_node
from src.agents.supervisor import supervisor_node
from src.agents.clarify import clarify_intent_node
from src.agents.gen_dsl import generate_dsl_node
from src.agents.dsl2sql import dsl_to_sql_node
from src.agents.execute import execute_sql_node
from src.agents.select_tables import select_tables_node
from src.agents.analysis import analysis_node
from src.agents.visualization import visualization_node
from src.agents.table_qa import table_qa_node

def create_graph():
    """
    创建并编译 LangGraph 工作流图。
    使用 Planner -> Supervisor -> Nodes 架构。
    """
    workflow = StateGraph(AgentState)

    # 添加节点 (Nodes)
    workflow.add_node("Planner", planner_node)
    workflow.add_node("Supervisor", supervisor_node)
    
    workflow.add_node("ClarifyIntent", clarify_intent_node)
    workflow.add_node("SelectTables", select_tables_node)
    workflow.add_node("GenerateDSL", generate_dsl_node)
    workflow.add_node("DSLtoSQL", dsl_to_sql_node)
    workflow.add_node("ExecuteSQL", execute_sql_node)
    workflow.add_node("DataAnalysis", analysis_node)
    workflow.add_node("Visualization", visualization_node)
    workflow.add_node("TableQA", table_qa_node)

    # 添加边 (Edges)
    # 起点 -> Planner -> Supervisor
    workflow.add_edge(START, "Planner")
    workflow.add_edge("Planner", "Supervisor")

    # Worker -> Supervisor (控制权回归循环)
    workflow.add_edge("ClarifyIntent", "Supervisor")
    workflow.add_edge("SelectTables", "Supervisor")
    workflow.add_edge("GenerateDSL", "Supervisor")
    workflow.add_edge("DSLtoSQL", "Supervisor")
    workflow.add_edge("ExecuteSQL", "Supervisor")
    workflow.add_edge("DataAnalysis", "Supervisor")
    workflow.add_edge("Visualization", "Supervisor")
    workflow.add_edge("TableQA", "Supervisor")

    # Supervisor 条件边 (Conditional Edges)
    workflow.add_conditional_edges(
        "Supervisor",
        lambda x: x["next"],
        {
            "ClarifyIntent": "ClarifyIntent",
            "SelectTables": "SelectTables",
            "GenerateDSL": "GenerateDSL",
            "DSLtoSQL": "DSLtoSQL",
            "ExecuteSQL": "ExecuteSQL",
            "DataAnalysis": "DataAnalysis",
            "Visualization": "Visualization",
            "TableQA": "TableQA",
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
