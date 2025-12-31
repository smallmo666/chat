import json
from typing import Optional, Literal
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.workflow.state import AgentState
from src.core.llm import get_llm

llm = None # Will be initialized in node

class TableData(BaseModel):
    columns: list[str] = Field(..., description="List of column names")
    data: list[dict] = Field(..., description="List of rows, each row is a dict")

class EChartsOption(BaseModel):
    chart_type: Literal["echarts", "table"] = Field(..., description="The type of visualization: 'echarts' for charts, 'table' for data lists")
    option: Optional[dict] = Field(None, description="The ECharts option dictionary (if chart_type is echarts)")
    table_data: Optional[TableData] = Field(None, description="The table data (if chart_type is table)")
    reason: str = Field(None, description="Reason if no visualization is generated")

from src.workflow.nodes.visualization_advisor import get_viz_advisor

async def visualization_node(state: AgentState, config: dict = None) -> dict:
    """
    可视化节点。
    结合规则推荐 (VisualizationAdvisor) 和 LLM 生成 ECharts 配置。
    """
    query = ""
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            query = msg.content
            break
    
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="Visualization", project_id=project_id)
    results = state.get("results", "")
    
    # 简单的启发式检查：如果没有结果或结果是空的/错误的，跳过
    if not results or "Error" in results or "Empty" in results:
        return {"visualization": None}

    # --- 1. 数据解析与规则推荐 (Fast Path) ---
    parsed_data = []
    try:
        parsed_data = json.loads(results)
        if not isinstance(parsed_data, list):
            parsed_data = []
    except:
        pass
        
    advisor = get_viz_advisor()
    advice = advisor.analyze_data(parsed_data)
    print(f"DEBUG: Viz Advisor Recommendation: {advice['recommended_chart']} ({advice['reason']})")
    
    # 如果推荐是表格，直接返回，不浪费 LLM Token
    if advice["recommended_chart"] == "table" and parsed_data:
        columns = list(parsed_data[0].keys()) if parsed_data else []
        return {
            "visualization": {
                "chart_type": "table",
                "table_data": {
                    "columns": columns,
                    "data": parsed_data
                },
                "reason": advice["reason"]
            }
        }
    # ----------------------------------------------------

    # --- 2. LLM 生成图表配置 (ECharts) ---
    prompt = ChatPromptTemplate.from_template(
        "你是一个前端数据可视化专家。请根据用户的查询、数据特征和专家建议，生成 ECharts 可视化配置。\n"
        "用户问题: {query}\n"
        "专家建议: 推荐使用 **{recommended_chart}**，原因：{reason}\n"
        "数据样本 (JSON):\n{data_sample}\n\n"
        "任务要求：\n"
        "1. **图表类型**：请严格采纳专家的建议类型 ({recommended_chart})。如果是 'none' 或 'table'，则生成表格。\n"
        "2. **Dataset 模式**：\n"
        "   - **必须**使用 ECharts 的 `dataset` 属性来管理数据。\n"
        "   - 不要将数据硬编码在 `series.data` 中。\n"
        "   - 假设前端会将完整数据注入到 `dataset.source` 中。\n"
        "   - 你只需要配置 `series` 中的 `encode` 映射 (例如: `encode: {{x: '{x_axis}', y: '{y_axis}'}}`)。\n"
        "3. **配置完整性**：\n"
        "   - 必须包含 title (text, subtext), tooltip (trigger: 'axis'), legend, grid, xAxis, yAxis。\n"
        "   - 针对 {recommended_chart} 类型优化样式（例如：折线图加 smooth: true，柱状图加 barMaxWidth）。\n"
        "4. **输出格式**：\n"
        "   - 仅返回 JSON 格式的 option 对象。\n"
    )
    
    chain = prompt | llm.with_structured_output(EChartsOption)
    
    try:
        # 准备 Prompt 上下文
        data_sample = json.dumps(parsed_data[:5], ensure_ascii=False) # 只给前5条作为样本
        
        # 构建维度提示
        x_axis_hint = advice.get("x_axis") or "自动推断"
        y_axis_hint = ", ".join(advice.get("y_axis", [])) or "自动推断"
        
        viz_data = await chain.ainvoke({
            "query": query,
            "recommended_chart": advice["recommended_chart"],
            "reason": advice["reason"],
            "data_sample": data_sample,
            "x_axis": x_axis_hint,
            "y_axis": y_axis_hint
        })
        
        # 结果合并
        if viz_data.chart_type == "echarts" and viz_data.option:
            # 注入 dataset (虽然前端会注入，但为了完整性，或者如果 LLM 没写 dataset 结构)
            if "dataset" not in viz_data.option:
                viz_data.option["dataset"] = {"source": parsed_data}
            else:
                # 覆盖 source 以确保数据完整
                viz_data.option["dataset"]["source"] = parsed_data
                
            return {"visualization": viz_data.dict()}
            
        elif viz_data.chart_type == "table":
             # 回退到表格
             columns = list(parsed_data[0].keys()) if parsed_data else []
             return {
                "visualization": {
                    "chart_type": "table",
                    "table_data": {
                        "columns": columns,
                        "data": parsed_data
                    }
                }
            }
            
        return {"visualization": None}

    except Exception as e:
        print(f"Visualization LLM error: {e}")
        # 出错兜底：表格
        if parsed_data:
            columns = list(parsed_data[0].keys())
            return {
                "visualization": {
                    "chart_type": "table",
                    "table_data": {
                        "columns": columns,
                        "data": parsed_data
                    },
                    "reason": "Visualization generation failed, fallback to table."
                }
            }
        return {"visualization": None}
