import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage

from src.workflow.state import AgentState
from src.core.llm import get_llm

ARTIST_PROMPT = """
你是一个精通 React 和 Ant Design 的前端工程师 (UI Artist)。
你的任务是根据提供的数据分析结果，生成一个现代化的 React Dashboard 组件。

用户查询: {query}

### 可用数据 (Props):
组件将接收一个 `data` 属性 (Array of Objects)，结构如下:
{columns_info}

### 可视化建议 (Viz Config):
{viz_config_desc}
(请务必遵循此配置来生成 ECharts 图表，特别是 chart_type, x_axis, y_axis, title)

### 分析上下文:
1. **Python Analysis Code**:
```python
{python_code}
```
2. **Python Analysis Text**:
{analysis_text}

3. **Python Generated Images (Base64)**:
{python_images_desc}
(注意：如果有 Base64 图片，它们将作为 `images` prop 传递给组件，数组格式。你可以使用 `<img src={{`data:image/png;base64,${{images[0]}}`}} />` 来展示)

### 任务要求:
1. 生成一个 React Functional Component，命名为 `DashboardComponent`。
   - Props: `({ data, images })`
2. **环境限制**:
   - 全局变量: `antd`, `React`, `icons` (Ant Design Icons), `ReactECharts` (echarts-for-react)。
   - **禁止使用 import**。
3. **布局策略**:
   - **混合排版**: 将 Python 生成的静态图表 (Images) 和 基于 SQL 数据的交互式图表 (ECharts/Table) 有机结合。
   - **KPI 卡片**: 在顶部展示关键数字 (从 SQL data 或 Analysis Text 中提取)。
   - **图表**: 如果 Python 代码生成了图表，优先展示 Python 图表（因为它们通常更高级）。如果 SQL 数据适合展示趋势，使用 ReactECharts 补充。
   - **表格**: 在底部展示详细数据 (AntD Table)。

4. **输出格式**: 
   - 仅输出组件代码。不要包含 Markdown。不要 `export default`。
   - 最后一行必须是 `render(DashboardComponent);`。

### 示例代码:
```javascript
const { Card, Row, Col, Statistic, Table, Typography, Divider } = antd;
const { ArrowUpOutlined } = icons;

const DashboardComponent = ({ data, images }) => {
  // 根据 Viz Config 生成 ECharts Option
  // 示例: Line Chart
  const option = {{
    title: {{ text: '示例趋势' }},
    tooltip: {{ trigger: 'axis' }},
    xAxis: {{ type: 'category', data: data.map(d => d.date) }},
    yAxis: {{ type: 'value' }},
    series: [{{ data: data.map(d => d.amount), type: 'line', smooth: true }}]
  }};

  return (
    <div style={{ padding: 24 }}>
      <Typography.Title level={3}>销售分析大屏</Typography.Title>
      
      {/* 1. KPI Area */}
      <Row gutter={16}>
         <Col span={8}><Card><Statistic title="Total Sales" value={data.reduce((a,b)=>a+b.amount,0)} prefix="$"/></Card></Col>
      </Row>
      <Divider />

      {/* 2. Python Charts Area */}
      {images && images.length > 0 && (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          {images.map((img, idx) => (
            <Col span={12} key={idx}>
              <Card title={{`预测模型图表 ${{idx+1}}`}}>
                <img src={{`data:image/png;base64,${{img}}`}} style={{ width: '100%' }} />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* 3. Interactive Charts Area (Based on Viz Config) */}
      <Card title="数据可视化" style={{ marginBottom: 24 }}>
        <ReactECharts option={option} style={{ height: 300 }} />
      </Card>

      {/* 4. Data Table */}
      <Table dataSource={data} columns={Object.keys(data[0] || {{}}).map(k => ({{ title: k, dataIndex: k }}))} />
    </div>
  );
};

render(DashboardComponent);
```
"""

REPORT_PROMPT = """
你是一个专业的数据分析师和前端工程师。
你的任务是根据历史对话和数据，生成一份详细的**数据分析报告**。

### 任务要求:
1. 生成一个 React 组件，用于展示一份完整的报告。
2. **内容结构**:
   - **标题**: 清晰的报告标题。
   - **摘要**: 对本次分析的简要总结。
   - **关键发现**: 使用列表展示核心洞察 (Insights)。
   - **数据概览**: 展示关键指标 (KPIs)。
   - **详细分析**: 结合文本和图表 (如果有可视化配置)。
   - **建议**: 基于数据提出的行动建议。

3. **环境限制**: (同上，使用全局 antd, React, icons, ReactECharts)

4. **样式**:
   - 使用 AntD 的 `Typography` (Title, Paragraph, Text) 进行排版。
   - 使用 `Card` 分隔不同章节。
   - 整体风格要专业、整洁，类似 PDF 报告或 Notion 文档。

5. **历史数据**:
   - Query: {query}
   - Analysis Text: {analysis_text}
   - Python Images: {python_images_desc}

### 示例代码结构:
```javascript
const { Typography, Card, Divider, List, Statistic, Row, Col, Button } = antd;
const { Title, Paragraph, Text } = Typography;
const { DownloadOutlined } = icons;

const AnalysisReport = ({ data, images }) => {
  return (
    <div style={{ padding: 40, background: '#fff', maxWidth: 900, margin: '0 auto', boxShadow: '0 0 20px rgba(0,0,0,0.05)' }}>
      <div style={{ textAlign: 'center', marginBottom: 40 }}>
        <Title level={2}>数据分析报告</Title>
        <Text type="secondary">生成时间: {new Date().toLocaleDateString()}</Text>
        <div style={{ marginTop: 20 }}>
            <Button icon={<DownloadOutlined />} onClick={() => window.print()}>导出 PDF</Button>
        </div>
      </div>
      
      <Title level={4}>1. 摘要</Title>
      <Paragraph>...</Paragraph>
      
      <Divider />
      
      <Title level={4}>2. 关键指标</Title>
      <Row gutter={16}>
         {/* Statistic Components */}
      </Row>
      
      {/* More Sections */}
    </div>
  );
};
render(AnalysisReport);
```

请生成代码。记得调用 `render`。
"""

EDIT_CHART_PROMPT = """
你是一个精通 ECharts 和 React 的前端工程师。
用户希望修改现有的图表配置。请根据用户的自然语言指令，生成一个新的 ECharts `option` 对象。

### 输入信息:
1. **用户指令**: {query}
2. **当前图表配置 (Option)**: 
```json
{current_option}
```

### 任务要求:
1. 这是一个**修改**任务，请保留原配置中未被修改的部分（如数据 data），只根据指令调整样式、类型、颜色、标题等。
2. 输出必须是一个合法的 JSON 对象，可以被 `JSON.parse` 解析。
3. **不要**输出任何 Markdown 标记、代码块或解释性文字。只输出纯 JSON 字符串。

### 示例:
输入: "把颜色改成红色"
输出:
{
  "title": { "text": "Sales" },
  "xAxis": { ... },
  "series": [{ "type": "bar", "data": [...], "itemStyle": { "color": "red" } }]
}
"""

async def ui_artist_node(state: AgentState, config: dict = None) -> dict:
    """
    UI Artist 节点 (Enhanced)。
    生成支持数据驱动和多模态展示的 React 组件。
    **新增**: 支持交互式图表编辑 (Edit Chart)。
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
            
    # Check for "edit_chart" intent in state (passed from Supervisor or Frontend)
    # 这里的逻辑是：如果 frontend 直接发起了 edit 请求，state 中会有 current_option
    current_option = state.get("current_option")
    
    if current_option:
        print("DEBUG: Handling Chart Edit Request...")
        prompt = ChatPromptTemplate.from_template(EDIT_CHART_PROMPT)
        chain = prompt | llm
        try:
            response = await chain.ainvoke({
                "query": query,
                "current_option": json.dumps(current_option, ensure_ascii=False)
            })
            new_option_str = response.content.strip()
            # Clean up
            if "```" in new_option_str:
                new_option_str = new_option_str.split("```")[1]
                if new_option_str.startswith("json"):
                    new_option_str = new_option_str[4:]
            
            new_option = json.loads(new_option_str.strip())
            
            # Return special signal for frontend to update chart only
            return {
                "messages": [AIMessage(content="图表已更新。", vizOption=new_option)],
                "vizOption": new_option # Update state
            }
        except Exception as e:
            print(f"Chart Edit failed: {e}")
            return {"messages": [AIMessage(content=f"修改图表失败: {e}")]}

    # 从 State 获取数据
    python_code = state.get("python_code", "")
    analysis_text = state.get("analysis", "") # PythonAnalysis 的文本结果
    viz_config = state.get("visualization", {}) # Viz Advisor 的建议
    
    viz_config_desc = "无特殊可视化建议，请自行判断。"
    if viz_config:
        viz_config_desc = json.dumps(viz_config, ensure_ascii=False, indent=2)
    
    python_images = state.get("ui_images", [])
    python_images_desc = f"包含 {len(python_images)} 张 Base64 图片" if python_images else "无图片"

    results_str = state.get("results", "[]")
    columns_info = "Unknown"
    try:
        results = json.loads(results_str)
        if results and isinstance(results, list):
            columns_info = f"Columns: {list(results[0].keys())}, Sample Row: {results[0]}"
    except:
        pass

    # 智能路由：判断是否生成报告
    is_report = "报告" in query or "总结" in query or "report" in query.lower()

    if is_report:
        print("DEBUG: Generating Analysis Report...")
        prompt = ChatPromptTemplate.from_template(REPORT_PROMPT)
    else:
        prompt = ChatPromptTemplate.from_template(ARTIST_PROMPT)
        
    chain = prompt | llm
    
    try:
        response = await chain.ainvoke({
            "query": query,
            "columns_info": columns_info,
            "python_code": python_code,
            "analysis_text": analysis_text,
            "python_images_desc": python_images_desc,
            "viz_config_desc": viz_config_desc
        })
        
        code = response.content.strip()
        # 清理 Markdown
        if "```" in code:
            code = code.split("```")[1]
            if code.startswith("jsx") or code.startswith("javascript") or code.startswith("js"):
                 code = code.split("\n", 1)[1]
        
        code = code.strip()
            
        print("DEBUG: UI Artist generated component code.")
        return {"ui_component": code}
        
    except Exception as e:
        print(f"UI Artist failed: {e}")
        return {"ui_component": None}

