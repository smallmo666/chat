import json
from typing import Optional, Literal
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

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

    # --- 1. 尝试直接解析 JSON 生成默认表格 (Fast Path) ---
    # 这可以作为兜底，或者在 LLM 失败时使用
    fallback_table_viz = None
    try:
        json_data = json.loads(results)
        if isinstance(json_data, list) and len(json_data) > 0 and isinstance(json_data[0], dict):
            # 这是一个标准的表格数据
            columns = list(json_data[0].keys())
            # 简单截断数据量以防前端渲染卡顿（虽然前端有分页，但传输太大也不好）
            # 这里保留全部，前端做分页
            fallback_table_viz = {
                "chart_type": "table",
                "table_data": {
                    "columns": columns,
                    "data": json_data
                }
            }
    except Exception:
        # JSON 解析失败，说明可能不是标准 JSON，后续交给 LLM 处理
        pass
    # ----------------------------------------------------

    prompt = ChatPromptTemplate.from_template(
        "你是一个前端数据可视化专家。请根据用户的查询和数据结果，生成可视化配置。\n"
        "用户问题: {query}\n"
        "数据结果 (JSON 格式):\n{results}\n\n"
        "任务：判断数据适合展示为图表（ECharts）还是表格（Table），并生成相应配置。\n\n"
        "判断标准（优先级从高到低）：\n"
        "1. **用户指定意图**：\n"
        "   - 如果用户明确要求“绘制柱状图”、“画个饼图”、“生成折线图”等具体图表类型，**必须**生成图表 (echarts)。\n"
        "   - 如果用户要求“列出数据”、“查看明细”、“显示表格”，**必须**生成表格 (table)。\n"
        "2. **数据特征**：\n"
        "   - **聚合数据**（如包含 COUNT, SUM, AVG 等统计值）：优先生成图表 (echarts)。\n"
        "   - **明细数据**（如 SELECT * FROM ... LIMIT ...）：**必须**生成表格 (table)。不要尝试强制用图表展示明细数据，除非用户特别要求。\n"
        "   - 如果数据包含大量文本列或维度过多，优先使用表格。\n\n"
        "3. **默认策略**：\n"
        "   - 如果没有特别强烈的画图特征，请默认生成表格 (table) 以展示数据概览。\n\n"
        "4. **图表 (echarts) 配置要求**：\n"
        "   - 必须生成合法的 ECharts option JSON。\n"
        "   - 配置项：title, tooltip, legend, xAxis, yAxis, series 等。\n"
        "   - 如果是明细数据强制画图，Title 请注明“（明细数据可视化）”。\n\n"
        "5. **表格 (table) 配置要求**：\n"
        "   - 提取列名和行数据，生成 TableData 结构。\n"
        "   - ！！！重要！！！：如果 LLM 判断生成表格，必须确保 table_data 字段不为空，且包含完整的 columns 和 data。\n"
        "   - 注意：如果结果是 JSON 数组，直接将其转换为 TableData 格式。\n\n"
        "输出要求：\n"
        "- 如果生成图表，chart_type='echarts'，并填充 option。\n"
        "- 如果生成表格，chart_type='table'，并填充 table_data。\n"
        "- 如果无法生成，返回空对象并说明 reason。\n"
    )
    
    chain = prompt | llm.with_structured_output(EChartsOption)
    
    try:
        # 截断结果以防 Token 溢出
        # 增加截断长度，确保表格数据尽可能完整
        # 检查是否为 JSON 列表结构，如果是，尝试进行智能截断
        viz_input_results = results
        if len(results) > 8000:
             # 尝试保留 JSON 结构的完整性，避免截断在对象中间
             # 简单策略：截取前 8000 字符，然后向后查找最近的 "},"
             truncated = results[:8000]
             last_brace_index = truncated.rfind("}")
             if last_brace_index != -1:
                 # 加上闭合的方括号，假设最外层是列表
                 viz_input_results = truncated[:last_brace_index+1] + "\n... (truncated)]"
             else:
                 viz_input_results = truncated
        
        # --- 如果 Fast Path 已经生成了表格，强制让 LLM 聚焦于 "是否需要画图" ---
        # 如果 LLM 还是无法生成画图配置，我们就可以放心地回退到 Fast Path 表格
        if fallback_table_viz:
             # 简化 prompt 以减少 token，同时暗示如果有表格数据则优先画图，画不出就放弃（我们会接管）
             pass 

        viz_data = chain.invoke({
            "query": query,
            "results": viz_input_results
        })
        
        # 检查结果有效性
        if viz_data.chart_type == "echarts" and (not viz_data.option or not viz_data.option.keys()):
             # 回退逻辑: 如果 LLM 想画图但没画出来，回退到表格
             if fallback_table_viz:
                 return {"visualization": fallback_table_viz}
        elif viz_data.chart_type == "table":
             # 强制使用 Fast Path 的数据，忽略 LLM 解析的 table_data (可能不完整)
             # 只要 LLM 认为是 table，或者 LLM 生成的 table_data 为空，我们都用 Python 解析的完整数据
             if fallback_table_viz:
                 return {"visualization": fallback_table_viz}
             elif not viz_data.table_data:
                 pass # No fallback, and LLM failed
        else:
             # 成功返回 Pydantic 模型，会自动转换为 dict
             return {"visualization": viz_data.dict()}
             
        # 失败处理
        if fallback_table_viz:
            return {"visualization": fallback_table_viz}

        reason = viz_data.reason or "数据不适合可视化。"
        return {
            "visualization": None,
            "messages": [AIMessage(content=reason)]
        }
            
    except Exception as e:
        print(f"Visualization error: {e}")
        # 出错时，如果有备用表格，直接返回
        if fallback_table_viz:
            return {"visualization": fallback_table_viz}
            
        return {
            "visualization": None,
            "messages": [AIMessage(content=f"可视化生成出错: {str(e)}")]
        }
