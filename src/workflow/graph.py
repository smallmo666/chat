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
from src.workflow.nodes.visualization import visualization_node
from src.workflow.nodes.table_qa import table_qa_node
from src.workflow.nodes.python_analysis import python_analysis_node
from src.workflow.nodes.cache_check import cache_check_node
from src.workflow.nodes.correct_sql import correct_sql_node
from src.workflow.nodes.detective import data_detective_node 
from src.workflow.nodes.insight import insight_miner_node 
from src.workflow.nodes.artist import ui_artist_node 
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
    workflow.add_node("Planner", trace_node(planner_node, "Planner"))
    workflow.add_node("Supervisor", trace_node(supervisor_node, "Supervisor"))
    
    workflow.add_node("ClarifyIntent", trace_node(clarify_intent_node, "ClarifyIntent"))
    workflow.add_node("SelectTables", trace_node(select_tables_node, "SelectTables"))
    workflow.add_node("GenerateDSL", trace_node(generate_dsl_node, "GenerateDSL"))
    workflow.add_node("DSLtoSQL", trace_node(dsl_to_sql_node, "DSLtoSQL"))
    workflow.add_node("ExecuteSQL", trace_node(execute_sql_node, "ExecuteSQL"))
    workflow.add_node("CorrectSQL", trace_node(correct_sql_node, "CorrectSQL"))
    workflow.add_node("TableQA", trace_node(table_qa_node, "TableQA"))
    
    # Visualization: 纯 ECharts 可视化 (原 AnalysisViz 已废弃)
    workflow.add_node("Visualization", trace_node(visualization_node, "Visualization"))
    
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
    workflow.add_conditional_edges(
        "CacheCheck",
        lambda x: x.get("next", "DataDetective"), # 默认修改为去 DataDetective (原为 Planner)
        {
            "ExecuteSQL": "Supervisor", # 如果缓存命中，直接去 Supervisor (跳过 Detective/Planner)
            "DataDetective": "DataDetective",
            "Planner": "Planner" # 保留向后兼容
        }
    )
    
    # DataDetective -> Planner
    workflow.add_edge("DataDetective", "Planner")
    
    workflow.add_edge("Planner", "Supervisor")

    # Worker -> Supervisor (控制权回归循环)
    workflow.add_edge("ClarifyIntent", "Supervisor")
    workflow.add_edge("SelectTables", "Supervisor")
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
            "ClarifyIntent": "ClarifyIntent",
            "SelectTables": "SelectTables",
            "GenerateDSL": "GenerateDSL",
            "DSLtoSQL": "DSLtoSQL",
            "ExecuteSQL": "ExecuteSQL",
            "TableQA": "TableQA",
            "Visualization": "Visualization",
            "PythonAnalysis": "PythonAnalysis",
            "InsightMiner": "InsightMiner", 
            "UIArtist": "UIArtist", # 注册 UIArtist
            "FINISH": END
        }
    )

    # Initialize Checkpointer
    # Use custom MySQLSaver to persist state to remote DB
    # This prevents the graph from restarting from the beginning when resuming from an interrupt
    
    # Parse DB URL from settings
    db_url = make_url(settings.APP_DB_URL)
    
    # Connect to MySQL
    # Note: In production, consider using a connection pool or managing connection lifecycle better
    conn = pymysql.connect(
        host=db_url.host,
        port=db_url.port or 3306,
        user=db_url.username,
        password=db_url.password,
        database=db_url.database,
        autocommit=True
    )
    
    checkpointer = MySQLSaver(conn)
    print(f"Graph: 使用 MySQLSaver ({db_url.host}/{db_url.database}) 进行状态管理")

    return workflow.compile(
        checkpointer=checkpointer,
        # interrupt_before=["ExecuteSQL"] # 暂时禁用人工审批，以解决执行等待问题
    )
