import os
from langgraph.graph import StateGraph, START, END
# 替换为自定义的 SimpleRedisSaver
from src.utils.redis_saver import SimpleRedisSaver
from redis import Redis

from src.workflow.state import AgentState
from src.workflow.nodes.planner import planner_node
from src.workflow.nodes.supervisor import supervisor_node
from src.workflow.nodes.clarify import clarify_intent_node
from src.workflow.nodes.gen_dsl import generate_dsl_node
from src.workflow.nodes.dsl2sql import dsl_to_sql_node
from src.workflow.nodes.execute import execute_sql_node
from src.workflow.nodes.select_tables import select_tables_node
from src.workflow.nodes.analysis import analysis_node
from src.workflow.nodes.visualization import visualization_node
from src.workflow.nodes.table_qa import table_qa_node
from src.workflow.nodes.python_analysis import python_analysis_node
from src.workflow.nodes.cache_check import cache_check_node
from src.workflow.nodes.correct_sql import correct_sql_node
from opentelemetry import trace

# Get tracer
tracer = trace.get_tracer(__name__)

# Wrap nodes with tracing manually since LangGraph doesn't support OTel natively yet
def trace_node(node_func, node_name):
    def wrapper(state, config=None):
        with tracer.start_as_current_span(f"node.{node_name}") as span:
            span.set_attribute("node.name", node_name)
            # Add input state attributes (careful with PII/Size)
            if "messages" in state and len(state["messages"]) > 0:
                span.set_attribute("input.last_message", str(state["messages"][-1].content)[:100])
            
            if config:
                return node_func(state, config)
            return node_func(state)
    return wrapper

def create_graph():
    """
    创建并编译 LangGraph 工作流图。
    使用 Planner -> Supervisor -> Nodes 架构。
    """
    workflow = StateGraph(AgentState)

    # 添加节点 (Nodes) - Wrapped with Tracing
    workflow.add_node("CacheCheck", trace_node(cache_check_node, "CacheCheck"))
    workflow.add_node("Planner", trace_node(planner_node, "Planner"))
    workflow.add_node("Supervisor", trace_node(supervisor_node, "Supervisor"))
    
    workflow.add_node("ClarifyIntent", trace_node(clarify_intent_node, "ClarifyIntent"))
    workflow.add_node("SelectTables", trace_node(select_tables_node, "SelectTables"))
    workflow.add_node("GenerateDSL", trace_node(generate_dsl_node, "GenerateDSL"))
    workflow.add_node("DSLtoSQL", trace_node(dsl_to_sql_node, "DSLtoSQL"))
    workflow.add_node("ExecuteSQL", trace_node(execute_sql_node, "ExecuteSQL"))
    workflow.add_node("CorrectSQL", trace_node(correct_sql_node, "CorrectSQL"))
    workflow.add_node("DataAnalysis", trace_node(analysis_node, "DataAnalysis"))
    workflow.add_node("Visualization", trace_node(visualization_node, "Visualization"))
    workflow.add_node("TableQA", trace_node(table_qa_node, "TableQA"))
    # Let's create a new node "AnalysisViz" (formerly PostProcess) that wraps Analysis and Viz.
    from src.workflow.nodes.post_process import analysis_viz_node
    workflow.add_node("AnalysisViz", trace_node(analysis_viz_node, "AnalysisViz"))
    workflow.add_node("PythonAnalysis", trace_node(python_analysis_node, "PythonAnalysis"))

    # 添加边 (Edges)
    # 起点 -> CacheCheck
    workflow.add_edge(START, "CacheCheck")
    
    # CacheCheck 条件边
    workflow.add_conditional_edges(
        "CacheCheck",
        lambda x: x.get("next", "Planner"), # 默认去 Planner
        {
            "ExecuteSQL": "Supervisor", # 如果命中，去 Supervisor 调度 ExecuteSQL
            "Planner": "Planner"
        }
    )
    
    workflow.add_edge("Planner", "Supervisor")

    # Worker -> Supervisor (控制权回归循环)
    workflow.add_edge("ClarifyIntent", "Supervisor")
    workflow.add_edge("SelectTables", "Supervisor")
    workflow.add_edge("GenerateDSL", "Supervisor")
    workflow.add_edge("DSLtoSQL", "Supervisor")
    
    # ExecuteSQL -> (Error Check) -> CorrectSQL or Supervisor (to let Planner decide next step)
    # If success, we go to Supervisor, which will pick next step from plan (e.g. AnalysisViz or PythonAnalysis)
    workflow.add_conditional_edges(
        "ExecuteSQL",
        lambda x: "CorrectSQL" if x.get("error") and x.get("retry_count", 0) < 3 else "Supervisor",
        {
            "CorrectSQL": "CorrectSQL",
            "Supervisor": "Supervisor"
        }
    )
    
    # CorrectSQL -> ExecuteSQL (Retry Loop)
    workflow.add_edge("CorrectSQL", "ExecuteSQL")
    
    # PostProcess -> Supervisor
    workflow.add_edge("AnalysisViz", "Supervisor")

    # PythonAnalysis -> Supervisor
    workflow.add_edge("PythonAnalysis", "Supervisor")

    # Worker -> Supervisor (Loop)
    workflow.add_edge("ClarifyIntent", "Supervisor")
    workflow.add_edge("SelectTables", "Supervisor")
    workflow.add_edge("GenerateDSL", "Supervisor")
    workflow.add_edge("DSLtoSQL", "Supervisor")
    workflow.add_edge("TableQA", "Supervisor")
    workflow.add_edge("AnalysisViz", "Supervisor")
    workflow.add_edge("PythonAnalysis", "Supervisor")

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
            # "DataAnalysis": "DataAnalysis", # Removed, handled by PostProcess
            # "Visualization": "Visualization", # Removed, handled by PostProcess
            "TableQA": "TableQA",
            "AnalysisViz": "AnalysisViz",
            "PythonAnalysis": "PythonAnalysis",
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
            decode_responses=False # pickle 序列化通常需要 bytes
        )
        # 使用自定义的 SimpleRedisSaver，不需要 RedisJSON 模块支持
        checkpointer = SimpleRedisSaver(conn=redis_conn)
        print(f"成功连接到 Redis 状态存储 ({redis_host}:{redis_port})")
    except Exception as e:
        print(f"Redis 连接失败，回退到内存存储: {e}")
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()

    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["ExecuteSQL"]
    )
