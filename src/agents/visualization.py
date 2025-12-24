import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

from src.state.state import AgentState
from src.utils.llm import get_llm

llm = get_llm()

class EChartsOption(BaseModel):
    option: dict = Field(..., description="The ECharts option dictionary")

def visualization_node(state: AgentState) -> dict:
    """
    可视化节点。
    根据 SQL 执行结果，生成 ECharts 配置。
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
        "你是一个前端数据可视化专家。请根据用户的查询和数据结果，生成一个 ECharts 的 option 配置对象 (JSON)。\n"
        "用户问题: {query}\n"
        "数据结果 (Markdown 表格):\n{results}\n\n"
        "要求：\n"
        "1. 选择最合适的图表类型（Bar, Line, Pie, Scatter 等）。\n"
        "2. 配置项必须包含 title, tooltip, legend, xAxis, yAxis (如果是笛卡尔坐标系), series。\n"
        "3. 颜色方案要现代、美观（推荐使用 Ant Design 风格色板）。\n"
        "4. 直接返回合法的 JSON 对象，不要包含 markdown 代码块标记。\n"
        "5. 如果数据不适合可视化（如单行单列文本），返回空 JSON {{}}。\n"
    )
    
    chain = prompt | llm.with_structured_output(EChartsOption)
    
    try:
        # 截断结果以防 Token 溢出，通常图表只需要前几十行数据就能看个大概，
        # 或者我们需要更智能的聚合。这里简单截断。
        viz_data = chain.invoke({
            "query": query,
            "results": results[:3000] 
        })
        
        if not viz_data.option or not viz_data.option.keys():
            return {"visualization": None}
            
        return {"visualization": viz_data.option}
    except Exception as e:
        print(f"Visualization error: {e}")
        return {"visualization": None}
