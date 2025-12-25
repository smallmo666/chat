from typing import Optional, Literal
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

from src.state.state import AgentState
from src.utils.llm import get_llm

llm = get_llm()

class TableData(BaseModel):
    columns: list[str] = Field(..., description="List of column names")
    data: list[dict] = Field(..., description="List of rows, each row is a dict")

class EChartsOption(BaseModel):
    chart_type: Literal["echarts", "table"] = Field(..., description="The type of visualization: 'echarts' for charts, 'table' for data lists")
    option: Optional[dict] = Field(None, description="The ECharts option dictionary (if chart_type is echarts)")
    table_data: Optional[TableData] = Field(None, description="The table data (if chart_type is table)")
    reason: str = Field(None, description="Reason if no visualization is generated")

def visualization_node(state: AgentState) -> dict:
    """
    可视化节点。
    根据 SQL 执行结果，生成 ECharts 配置或表格数据。
    """
    query = ""
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            query = msg.content
            break
            
    results = state.get("results", "")
    
    # 简单的启发式检查：如果没有结果或结果是空的/错误的，跳过
    if not results or "Error" in results or "Empty" in results:
        return {"visualization": None}

    prompt = ChatPromptTemplate.from_template(
        "你是一个前端数据可视化专家。请根据用户的查询和数据结果，生成可视化配置。\n"
        "用户问题: {query}\n"
        "数据结果 (Markdown 表格):\n{results}\n\n"
        "任务：判断数据适合展示为图表（ECharts）还是表格（Table），并生成相应配置。\n\n"
        "判断标准（优先级从高到低）：\n"
        "1. **用户指定意图**：\n"
        "   - 如果用户明确要求“绘制柱状图”、“画个饼图”、“生成折线图”等具体图表类型，**必须**生成图表 (echarts)。\n"
        "   - 即使数据是明细清单，也尝试用 Name/ID 作为 X 轴，数值列作为 Y 轴绘制图表。\n"
        "   - 只有在数据完全无法绘图（如纯文本无数字）时，才回退到表格并说明原因。\n"
        "2. **数据特征**：\n"
        "   - **聚合数据**：默认生成图表 (echarts)。\n"
        "   - **明细数据**：默认生成表格 (table)，除非用户符合第1条的强制要求。\n\n"
        "3. **图表 (echarts) 配置要求**：\n"
        "   - 必须生成合法的 ECharts option JSON。\n"
        "   - 配置项：title, tooltip, legend, xAxis, yAxis, series 等。\n"
        "   - 如果是明细数据强制画图，Title 请注明“（明细数据可视化）”。\n\n"
        "4. **表格 (table) 配置要求**：\n"
        "   - 提取列名和行数据，生成 TableData 结构。\n\n"
        "输出要求：\n"
        "- 如果生成图表，chart_type='echarts'，并填充 option。\n"
        "- 如果生成表格，chart_type='table'，并填充 table_data。\n"
        "- 如果无法生成，返回空对象并说明 reason。\n"
    )
    
    chain = prompt | llm.with_structured_output(EChartsOption)
    
    try:
        # 截断结果以防 Token 溢出
        viz_data = chain.invoke({
            "query": query,
            "results": results[:3000] 
        })
        
        # 检查结果有效性
        if viz_data.chart_type == "echarts" and (not viz_data.option or not viz_data.option.keys()):
             # 回退逻辑
             pass
        elif viz_data.chart_type == "table" and (not viz_data.table_data):
             # 回退
             pass
        else:
             # 成功返回 Pydantic 模型，会自动转换为 dict
             return {"visualization": viz_data.dict()}
             
        # 失败处理
        reason = viz_data.reason or "数据不适合可视化。"
        return {
            "visualization": None,
            "messages": [AIMessage(content=reason)]
        }
            
    except Exception as e:
        print(f"Visualization error: {e}")
        return {
            "visualization": None,
            "messages": [AIMessage(content=f"可视化生成出错: {str(e)}")]
        }
