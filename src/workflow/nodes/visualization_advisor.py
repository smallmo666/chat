import pandas as pd
import json
import asyncio
from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from src.workflow.state import AgentState
from src.core.llm import get_llm

class VizRecommendation(BaseModel):
    chart_type: str = Field(..., description="Recommended chart type (bar, line, pie, scatter, table, map)")
    x_axis: str = Field(..., description="Column for X-axis or Category")
    y_axis: List[str] = Field(..., description="Columns for Y-axis or Value")
    reason: str = Field(..., description="Reason for recommendation")
    title: str = Field(..., description="Chart title")

VIZ_ADVISOR_PROMPT = """
你是一个数据可视化专家。请根据数据特征和用户查询，推荐最合适的图表类型。

用户查询: {query}

数据概览:
- 列名: {columns}
- 数据类型: {dtypes}
- 样本数据 (前3行):
{sample_data}

### 推荐原则:
1. **趋势分析** (关键词: 趋势, 变化, 走势): 优先 **Line Chart**。通常 X 轴为时间。
2. **比较分析** (关键词: 对比, 排名, Top): 优先 **Bar Chart**。
3.33→3. **占比分析** (关键词: 占比, 分布, 构成): 如果类别少 (<8)，用 **Pie Chart**；否则用 Bar Chart。
34→4. **关系分析**: 两个数值列的相关性用 **Scatter Chart**。
35→5. **明细查询**: 如果用户想看详细信息，推荐 **Table**。
36→6. **双轴/组合图** (关键词: 效能, 比率, 趋势+总量): 当需要同时展示两个量级差异巨大的指标（如“销售额”和“毛利率”，或“UV”和“转化率”）时，推荐 **Combination Chart**。
37→
38→### 输出要求:
39→请输出严格的 JSON 格式，必须包含以下字段（键名必须是英文）:
40→- "chart_type": string (bar, line, pie, scatter, table, map, combination)
41→- "x_axis": string (X轴字段名)
42→- "y_axis": list[string] (Y轴字段名列表)
- "title": string (图表标题)
- "reason": string (推荐理由)

示例:
{{
    "chart_type": "bar",
    "x_axis": "region",
    "y_axis": ["sales"],
    "title": "各地区销售额对比",
    "reason": "用户查询各地区销售情况，且类别数量适中，适合用柱状图展示。"
}}
"""

async def visualization_advisor_node(state: AgentState, config: dict = None) -> dict:
    """
    可视化顾问节点。
    结合规则 (Pandas Profiling) 和 LLM 语义理解，生成最佳图表配置。
    """
    print("DEBUG: Entering visualization_advisor_node")
    
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="VizAdvisor", project_id=project_id)
    
    # 获取上下文
    query = ""
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            query = msg.content
            break
            
    results_str = state.get("results", "[]")
    
    # 快速空数据检查 (防御性编程)
    if not results_str or results_str.strip() == "[]":
        print("VizAdvisor: Empty data detected (pre-check), skipping.")
        return {"visualization": None}
    
    try:
        data = json.loads(results_str)
        if not data or not isinstance(data, list):
            print("VizAdvisor: No valid data found.")
            return {"visualization": None}
            
        df = pd.DataFrame(data)
        
        # 1. Data Profiling
        columns = df.columns.tolist()
        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
        sample_data = df.head(3).to_dict(orient='records')
        
        # 2. LLM Recommendation (Manual JSON Parsing for Robustness)
        prompt = ChatPromptTemplate.from_template(VIZ_ADVISOR_PROMPT)
        chain = prompt | llm
        
        try:
            response = await chain.ainvoke({
                "query": query,
                "columns": columns,
                "dtypes": dtypes,
                "sample_data": sample_data
            })
            
            content = response.content.strip()
            # Clean Markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            viz_config = json.loads(content)
            
            # Simple validation
            if "chart_type" not in viz_config:
                viz_config["chart_type"] = "table"
                viz_config["reason"] = "Fallback: Missing chart_type in LLM response."
                
        except Exception as parse_error:
            print(f"VizAdvisor: JSON Parse/Validation Failed: {parse_error}. Using fallback.")
            # Fallback configuration
            viz_config = {
                "chart_type": "table",
                "x_axis": columns[0] if columns else "",
                "y_axis": columns[1:] if len(columns) > 1 else [],
                "title": "Data Preview",
                "reason": "Automatic fallback due to visualization recommendation failure."
            }
        
        print(f"DEBUG: Viz Recommendation: {viz_config.get('chart_type')} ({viz_config.get('reason')})")
        
        # 3. 增强：添加数据特征
        if viz_config.get("chart_type") == "bar" and df[viz_config.get("x_axis", "")].nunique() > 20:
             print("VizAdvisor: Too many categories for bar chart.")
        
        return {"visualization": viz_config}
        
    except Exception as e:
        print(f"VizAdvisor failed: {e}")
        # Final fallback to avoid infinite loops
        return {"visualization": {"chart_type": "table", "reason": "System Error Fallback"}}
