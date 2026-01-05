import operator
from typing import Annotated, Sequence, TypedDict, Optional, Union, List
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """
    Agent 状态定义
    
    Attributes:
        messages: 对话历史消息列表，使用 operator.add 进行追加合并
        next: 下一步要执行的节点名称
        dsl: 生成的中间 DSL (JSON 格式)
        sql: 生成的 SQL 语句
        results: SQL 执行结果
        intent_clear: 用户意图是否已澄清
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str
    dsl: Optional[str]
    sql: Optional[str]
    results: Optional[str]
    intent_clear: bool
    relevant_schema: Optional[str]
    rewritten_query: Optional[str]
    manual_selected_tables: Optional[list[str]]
    
    # Swarm / Detective Fields
    hypotheses: Optional[List[str]] # 侦探提出的假设列表
    analysis_depth: Optional[str] # "simple" or "deep"
    
    # Dynamic Planning Fields
    plan: Optional[list[dict]] # List of steps [{"node": "...", "desc": "...", "status": "..."}]
    current_step_index: int
    
    # Advanced Capabilities Fields
    visualization: Optional[dict] # ECharts option JSON
    analysis: Optional[str] # Markdown analysis result
    python_code: Optional[str] # Generated Python code for analysis
    insights: Optional[List[str]] # 主动洞察结果列表
    ui_component: Optional[str] # 生成的 React 组件代码
    
    # RAG Knowledge
    knowledge_context: Optional[str] # Retrieved business terms and definitions

    # Error Handling Fields
    error: Optional[str]
    retry_count: Optional[int] # SQL Execution Retry Count (Inner Loop)
    plan_retry_count: Optional[int] # Plan Regeneration Retry Count (Outer Loop)
