import operator
from typing import Annotated, Sequence, TypedDict, Optional, Union
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
