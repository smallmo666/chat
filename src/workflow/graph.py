import os
from langgraph.graph import StateGraph, START, END
# Use our custom MySQLSaver for persistence (fixes state loss on reload/restart)
from src.utils.mysql_checkpoint import MySQLSaver
import pymysql
from sqlalchemy.engine import make_url
from src.core.config import settings

from src.workflow.state import AgentState
from src.workflow.nodes.planner import planner_node
from src.workflow.nodes.supervisor import supervisor_node
from src.workflow.nodes.clarify import clarify_intent_node
from src.workflow.nodes.gen_dsl import generate_dsl_node
from src.workflow.nodes.dsl2sql import dsl_to_sql_node
from src.workflow.nodes.execute import execute_sql_node
from src.workflow.nodes.select_tables import select_tables_node
from src.workflow.nodes.schema_guard import schema_guard_node
from src.workflow.nodes.visualization import visualization_node
from src.workflow.nodes.table_qa import table_qa_node
from src.workflow.nodes.python_analysis import python_analysis_node
from src.workflow.nodes.cache_check import cache_check_node
from src.workflow.nodes.correct_sql import correct_sql_node
from src.workflow.nodes.detective import data_detective_node 
from src.workflow.nodes.insight import insight_miner_node 
from src.workflow.nodes.artist import ui_artist_node 
from src.workflow.nodes.visualization_advisor import visualization_advisor_node
from src.workflow.nodes.knowledge_retrieval import knowledge_retrieval_node
from opentelemetry import trace
import inspect

# 获取 tracer
tracer = trace.get_tracer(__name__)

# 手动包装节点以进行追踪，因为 LangGraph 目前尚未原生支持 OTel
def trace_node(node_func, node_name):
    # 如果 node_func 是异步函数，返回异步 wrapper
    if inspect.iscoroutinefunction(node_func):
        async def async_wrapper(state, config=None):
            with tracer.start_as_current_span(f"node.{node_name}") as span:
                span.set_attribute("node.name", node_name)
                # 添加输入状态属性 (注意 PII 和大小)
                if "messages" in state and len(state["messages"]) > 0:
                    span.set_attribute("input.last_message", str(state["messages"][-1].content)[:100])
                
                if config:
                    return await node_func(state, config)
                return await node_func(state)
        return async_wrapper
    else:
        # 同步 wrapper
        def sync_wrapper(state, config=None):
            with tracer.start_as_current_span(f"node.{node_name}") as span:
                span.set_attribute("node.name", node_name)
                # 添加输入状态属性 (注意 PII 和大小)
                if "messages" in state and len(state["messages"]) > 0:
                    span.set_attribute("input.last_message", str(state["messages"][-1].content)[:100])
                
                if config:
                    return node_func(state, config)
                return node_func(state)
        return sync_wrapper

def create_graph():
    """
    创建并编译 LangGraph 工作流图。
    使用 Planner -> Supervisor -> Nodes 架构。
    """
    workflow = StateGraph(AgentState)

    # 添加节点 (Nodes) - 使用 Tracing 包装
    workflow.add_node("CacheCheck", trace_node(cache_check_node, "CacheCheck"))
    workflow.add_node("DataDetective", trace_node(data_detective_node, "DataDetective")) # 新增
    workflow.add_node("KnowledgeRetrieval", trace_node(knowledge_retrieval_node, "KnowledgeRetrieval")) # 新增 Knowledge 节点
    workflow.add_node("Planner", trace_node(planner_node, "Planner"))
    workflow.add_node("Supervisor", trace_node(supervisor_node, "Supervisor"))
    
    workflow.add_node("ClarifyIntent", trace_node(clarify_intent_node, "ClarifyIntent"))
    workflow.add_node("SelectTables", trace_node(select_tables_node, "SelectTables"))
    workflow.add_node("SchemaGuard", trace_node(schema_guard_node, "SchemaGuard"))
    workflow.add_node("GenerateDSL", trace_node(generate_dsl_node, "GenerateDSL"))
    workflow.add_node("DSLtoSQL", trace_node(dsl_to_sql_node, "DSLtoSQL"))
    workflow.add_node("ExecuteSQL", trace_node(execute_sql_node, "ExecuteSQL"))
    workflow.add_node("CorrectSQL", trace_node(correct_sql_node, "CorrectSQL"))
    workflow.add_node("TableQA", trace_node(table_qa_node, "TableQA"))
    
    # Visualization: 纯 ECharts 可视化 (原 AnalysisViz 已废弃)
    workflow.add_node("Visualization", trace_node(visualization_node, "Visualization"))
    
    # VisualizationAdvisor: 智能图表推荐
    workflow.add_node("VisualizationAdvisor", trace_node(visualization_advisor_node, "VisualizationAdvisor"))

    # PythonAnalysis: 高级数据分析 (Pandas/Matplotlib)
    workflow.add_node("PythonAnalysis", trace_node(python_analysis_node, "PythonAnalysis"))
    
    # InsightMiner: 主动洞察挖掘
    workflow.add_node("InsightMiner", trace_node(insight_miner_node, "InsightMiner"))

    # UIArtist: 生成式 UI
    workflow.add_node("UIArtist", trace_node(ui_artist_node, "UIArtist"))

    # 添加边 (Edges)
    # 起点 -> CacheCheck
    workflow.add_edge(START, "CacheCheck")
    
    # CacheCheck 条件边
    def cache_check_router(state):
        if state.get("next") == "ExecuteSQL":
            return ["Supervisor"]
        else:
            return ["DataDetective", "KnowledgeRetrieval"]

    workflow.add_conditional_edges(
        "CacheCheck",
        cache_check_router,
        ["Supervisor", "DataDetective", "KnowledgeRetrieval"]
    )
    
    # DataDetective -> Planner
    workflow.add_edge("DataDetective", "Planner")

    # KnowledgeRetrieval -> Planner
    workflow.add_edge("KnowledgeRetrieval", "Planner")
    
    workflow.add_edge("Planner", "Supervisor")

    # Worker -> Supervisor (控制权回归循环)
    workflow.add_edge("ClarifyIntent", "Supervisor")
    workflow.add_edge("SelectTables", "Supervisor")
    workflow.add_edge("SchemaGuard", "Supervisor")
    workflow.add_edge("GenerateDSL", "Supervisor")
    workflow.add_edge("DSLtoSQL", "Supervisor")
    
    # ExecuteSQL -> (错误检查) -> CorrectSQL 或 Supervisor (让 Planner 决定下一步)
    # 如果成功，去 Supervisor，它将从计划中选择下一步 (例如 Visualization 或 PythonAnalysis)
    workflow.add_conditional_edges(
        "ExecuteSQL",
        # 如果 retry_count < 3 且有错误，去 CorrectSQL
        # 如果 retry_count >= 3 或无错误，或者 error 包含 "配置错误" (999)，去 Supervisor
        lambda x: "CorrectSQL" if x.get("error") and x.get("retry_count", 0) < 3 else "Supervisor",
        {
            "CorrectSQL": "CorrectSQL",
            "Supervisor": "Supervisor"
        }
    )
    
    # CorrectSQL -> ExecuteSQL (重试循环)
    workflow.add_edge("CorrectSQL", "ExecuteSQL")
    
    # Visualization -> Supervisor
    workflow.add_edge("Visualization", "Supervisor")

    # VisualizationAdvisor -> Supervisor
    workflow.add_edge("VisualizationAdvisor", "Supervisor")

    # PythonAnalysis -> Supervisor
    workflow.add_edge("PythonAnalysis", "Supervisor")
    
    # InsightMiner -> Supervisor
    workflow.add_edge("InsightMiner", "Supervisor")

    # UIArtist -> Supervisor
    workflow.add_edge("UIArtist", "Supervisor")

    # Worker -> Supervisor (循环)
    workflow.add_edge("TableQA", "Supervisor")

    # Supervisor 条件边 (Conditional Edges)
    workflow.add_conditional_edges(
        "Supervisor",
        lambda x: x["next"],
        {
            "Planner": "Planner",
            "ClarifyIntent": "ClarifyIntent",
            "SelectTables": "SelectTables",
            "SchemaGuard": "SchemaGuard",
            "GenerateDSL": "GenerateDSL",
            "DSLtoSQL": "DSLtoSQL",
            "ExecuteSQL": "ExecuteSQL",
            "TableQA": "TableQA",
            "Visualization": "Visualization",
            "VisualizationAdvisor": "VisualizationAdvisor", # 注册 Advisor
            "PythonAnalysis": "PythonAnalysis",
            "InsightMiner": "InsightMiner", 
            "UIArtist": "UIArtist", # 注册 UIArtist
            "FINISH": END
        }
    )

    # Initialize Checkpointer
    # Use custom MySQLSaver to persist state to remote DB
    # Use SQLAlchemy Pool for thread safety
    from sqlalchemy import create_engine
    
    # Parse DB URL from settings
    db_url = settings.APP_DB_URL
    
    # Create SQLAlchemy Engine with Pool
    # We use pymysql driver directly in connection string
    # Replace 'mysql+pymysql' with 'mysql+pymysql' (already correct)
    
    engine = create_engine(
        db_url,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
        pool_pre_ping=True
    )
    
    # MySQLSaver expects a raw pymysql connection or similar interface
    # But for thread safety with LangGraph, we should ideally pass a pool-aware object.
    # However, MySQLSaver implementation likely takes a single connection object.
    # If MySQLSaver doesn't support pool, we might need to modify it or use a connection factory.
    # Let's check MySQLSaver. For now, we can pass the engine and let MySQLSaver use engine.connect()
    # BUT, the original code passed a raw 'conn'.
    # If we pass a raw conn, it's shared and unsafe.
    
    # Let's use a lambda or factory if MySQLSaver supports it, OR update MySQLSaver to accept an engine.
    # Assuming we need to fix this in graph.py without changing MySQLSaver too much (unless needed).
    # The standard LangGraph Checkpointer usually manages its own connection or takes a pool.
    # Our custom MySQLSaver likely takes a 'conn'.
    
    # Better approach: Pass the engine to MySQLSaver, and let it manage connections per call.
    # We will need to update MySQLSaver to accept 'engine' instead of 'conn'.
    
    checkpointer = MySQLSaver(engine) 
    print(f"Graph: 使用 MySQLSaver (Pool) 进行状态管理")

    return workflow.compile(
        checkpointer=checkpointer,
    )
