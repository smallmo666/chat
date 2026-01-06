import json
import asyncio
from typing import Optional, Literal
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.workflow.state import AgentState
from src.core.llm import get_llm

llm = None # 将在节点内部初始化

class TableData(BaseModel):
    columns: list[str] = Field(..., description="列名列表")
    data: list[dict] = Field(..., description="数据行列表，每行为一个字典")

class EChartsOption(BaseModel):
    chart_type: Literal["echarts", "table"] = Field(..., description="可视化类型：'echarts' 表示图表，'table' 表示数据列表")
    option: Optional[dict] = Field(None, description="ECharts 配置项字典（当 chart_type 为 echarts 时）")
    table_data: Optional[TableData] = Field(None, description="表格数据（当 chart_type 为 table 时）")
    reason: str = Field(None, description="如果未生成可视化，说明原因")

async def visualization_node(state: AgentState, config: dict = None) -> dict:
    """
    可视化节点。
    根据 VisualizationAdvisor 的建议 (viz_config) 和数据，生成具体的 ECharts 配置。
    """
    query = ""
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            query = msg.content
            break
    
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="Visualization", project_id=project_id)
    results = state.get("results", "")
    viz_config = state.get("visualization", {}) # 获取 Advisor 的建议
    
    # 简单的启发式检查：如果没有结果或结果是空的/错误的，跳过
    if not results or "Error" in results or "Empty" in results:
        return {"visualization": None}

    # --- 1. 数据解析 ---
    MAX_DATA_POINTS = 2000
    
    parsed_data = []
    try:
        parsed_data = json.loads(results)
        if not isinstance(parsed_data, list):
            parsed_data = []
    except:
        pass
        
    original_count = len(parsed_data)
    is_truncated = False
    
    if original_count > MAX_DATA_POINTS:
        # 简单截断
        parsed_data = parsed_data[:MAX_DATA_POINTS]
        is_truncated = True
        print(f"Visualization: Data truncated from {original_count} to {MAX_DATA_POINTS} points.")

    # 如果没有 Advisor 建议，或者建议是 table，直接返回表格
    # 或者如果 Advisor 建议了某种图表，我们就生成它
    
    recommended_chart = "table"
    reason = "默认展示"
    x_axis_hint = "自动推断"
    y_axis_hint = "自动推断"
    
    if viz_config:
        recommended_chart = viz_config.get("chart_type", "table")
        reason = viz_config.get("reason", "")
        x_axis_hint = viz_config.get("x_axis", "自动推断")
        y_axis_hint = str(viz_config.get("y_axis", "自动推断"))

    # 如果推荐是表格，直接返回，不浪费 LLM Token
    if recommended_chart == "table" and parsed_data:
        columns = list(parsed_data[0].keys()) if parsed_data else []
        return {
            "visualization": {
                "chart_type": "table",
                "table_data": {
                    "columns": columns,
                    "data": parsed_data
                },
                "reason": reason,
                "is_truncated": is_truncated,
                "original_count": original_count,
                # 保留原始建议供后续参考
                "advisor_config": viz_config 
            }
        }
    # ----------------------------------------------------

    # --- 2. LLM 生成图表配置 (ECharts) ---
    prompt = ChatPromptTemplate.from_template(
        "你是一个前端数据可视化专家。请根据用户的查询、数据特征和专家建议，生成 ECharts 可视化配置。\n"
        "用户问题: {query}\n"
        "专家建议: 推荐使用 **{recommended_chart}**，原因：{reason}\n"
        "建议维度: X轴={x_axis}, Y轴={y_axis}\n"
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
        "   - 如果数据量较大，建议开启 dataZoom 组件。\n"
        "4. **输出格式**：\n"
        "   - 仅返回 JSON 格式的 option 对象。\n"
    )
    
    chain = prompt | llm.with_structured_output(EChartsOption)
    
    try:
        # 准备 Prompt 上下文
        data_sample = json.dumps(parsed_data[:5], ensure_ascii=False) # 只给前5条作为样本
        
        viz_data = await chain.ainvoke({
            "query": query,
            "recommended_chart": recommended_chart,
            "reason": reason,
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
            
            # 如果发生了截断，在 subtitle 中提示
            if is_truncated:
                current_subtext = viz_data.option.get("title", {}).get("subtext", "")
                viz_data.option.setdefault("title", {})["subtext"] = f"{current_subtext} (仅展示前 {MAX_DATA_POINTS} 条，共 {original_count} 条)".strip()
                
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
                    },
                    "is_truncated": is_truncated,
                    "original_count": original_count
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
                    "reason": "Visualization generation failed, fallback to table.",
                    "is_truncated": is_truncated,
                    "original_count": original_count
                }
            }
        return {"visualization": None}

