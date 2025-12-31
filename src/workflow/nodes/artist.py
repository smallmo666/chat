import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage

from src.workflow.state import AgentState
from src.core.llm import get_llm

ARTIST_PROMPT = """
你是一个精通 React 和 Tailwind CSS 的前端工程师 (UI Artist)。
你的任务是根据提供的数据分析结果，生成一个现代化的 React Dashboard 组件。

用户查询: {query}

### 可用数据:
1. **Insight (洞察)**: {insights}
2. **Visualization Config**: {viz_config}
3. **Data Sample**: {data_sample}

### 任务要求:
1. 生成一个 React Functional Component，命名为 `DashboardComponent`。
2. **布局**: 
   - 顶部：使用卡片 (Card) 展示关键指标 (KPI)，基于 `Insight` 中的数据。
   - 中间：预留一个容器用于渲染 ECharts (假设前端会处理 `VizConfig`)。或者你可以直接生成一个简单的表格。
   - 底部：如果有额外的洞察，以列表形式展示。
3. **样式**: 使用 Tailwind CSS 进行美化。
4. **输出格式**: 仅输出 React 代码 (JSX/TSX)，不要包含 Markdown 代码块标记，不要包含 import 语句（假设环境已提供 React）。

### 示例输出:
```jsx
function DashboardComponent({{ data, insights }}) {{
  return (
    <div className="p-4 bg-gray-50 rounded-lg">
      <h2 className="text-xl font-bold mb-4">销售分析看板</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {{insights.map((insight, idx) => (
           <div key={{idx}} className="bg-white p-4 rounded shadow border-l-4 border-blue-500">
             <p className="text-sm text-gray-600">洞察 {{idx + 1}}</p>
             <p className="font-semibold text-gray-800">{{insight}}</p>
           </div>
        ))}}
      </div>
      {/* ... 图表容器 ... */}
    </div>
  );
}}
```

请生成代码。
"""

async def ui_artist_node(state: AgentState, config: dict = None) -> dict:
    """
    UI Artist 节点。
    生成 React 组件代码。
    """
    print("DEBUG: Entering ui_artist_node")
    
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="UIArtist", project_id=project_id)
    
    # 获取上下文
    query = ""
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            query = msg.content
            break
            
    insights = state.get("insights", [])
    viz_config = state.get("visualization", {})
    results_str = state.get("results", "[]")
    
    # 采样数据
    try:
        results = json.loads(results_str)
        data_sample = json.dumps(results[:5], ensure_ascii=False) if results else "[]"
    except:
        data_sample = "[]"
    
    # 如果没有洞察且没有可视化，可能不需要生成 UI
    if not insights and not viz_config:
        return {"ui_component": None}
        
    prompt = ChatPromptTemplate.from_template(ARTIST_PROMPT)
    chain = prompt | llm
    
    try:
        response = await chain.ainvoke({
            "query": query,
            "insights": json.dumps(insights, ensure_ascii=False),
            "viz_config": json.dumps(viz_config, ensure_ascii=False),
            "data_sample": data_sample
        })
        
        code = response.content.strip()
        # 清理 Markdown 标记
        if code.startswith("```jsx"):
            code = code[6:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
            
        print("DEBUG: UI Artist generated component code.")
        return {"ui_component": code}
        
    except Exception as e:
        print(f"UI Artist failed: {e}")
        return {"ui_component": None}
