import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage

from src.workflow.state import AgentState
from src.core.llm import get_llm

ARTIST_PROMPT = """
你是一个精通 React 和 Ant Design 的前端工程师 (UI Artist)。
你的任务是根据提供的数据分析结果，生成一个现代化的 React Dashboard 组件。

用户查询: {query}

### 可用数据:
1. **Insight (洞察)**: {insights}
2. **Visualization Config**: {viz_config}
3. **Data Sample**: {data_sample}

### 任务要求:
1. 生成一个 React Functional Component，命名为 `DashboardComponent`。
2. **环境限制**:
   - 你**不能**使用 `import` 语句。所有 Ant Design 组件都已在全局变量 `antd` 中提供，例如 `const { Card, Statistic, Row, Col } = antd;`。
   - React Hooks 已在全局变量 `React` 中提供，例如 `const { useState, useEffect } = React;`。
   - 图表请使用 `echarts-for-react`，假设组件名为 `ReactECharts`，通过 `const ReactECharts = (window as any).ReactECharts || (() => null);` 获取（前端会注入）。或者简单地使用 AntD 的 Table 和 Statistic 组件。
   - 图标请使用 `@ant-design/icons`，假设已注入到 `icons` 变量中，例如 `const { UserOutlined } = icons;`。

3. **布局**: 
   - 顶部：使用 `Row` 和 `Col` 布局，展示关键指标 (Statistic / Card)。
   - 中间：展示数据表格 (Table) 或图表。
   - 样式：可以使用内联样式 `style={{...}}` 或 Tailwind CSS 类名（如果前端支持）。鉴于环境不确定，推荐优先使用 AntD 的内置样式和 `style` 属性。

4. **输出格式**: 
   - 仅输出组件函数的代码。
   - **不要**包含 Markdown 代码块标记 (```jsx)。
   - **不要**包含 `export default`。

### 示例代码:
```javascript
const { Card, Row, Col, Statistic, Table, Typography } = antd;
const { ArrowUpOutlined } = icons;

const DashboardComponent = ({ data }) => {
  return (
    <div style={{ padding: 20 }}>
      <Typography.Title level={4}>销售分析</Typography.Title>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic title="总销售额" value={112893} prefix="¥" />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic 
              title="增长率" 
              value={11.28} 
              precision={2} 
              valueStyle={{ color: '#3f8600' }} 
              prefix={<ArrowUpOutlined />} 
              suffix="%" 
            />
          </Card>
        </Col>
      </Row>
      <Table dataSource={data} columns={[{title: '日期', dataIndex: 'date'}, {title: '金额', dataIndex: 'amount'}]} />
    </div>
  );
};

render(DashboardComponent); // 必须包含这行以渲染组件
```

请生成代码。记得在最后调用 `render(DashboardComponent)`。
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

5. **输入数据**:
   - Query: {query}
   - Insights: {insights}
   - Data Sample: {data_sample}

### 示例代码结构:
```javascript
const { Typography, Card, Divider, List, Statistic, Row, Col } = antd;
const { Title, Paragraph, Text } = Typography;

const AnalysisReport = ({ data }) => {
  return (
    <div style={{ padding: 40, background: '#fff', maxWidth: 900, margin: '0 auto', boxShadow: '0 0 20px rgba(0,0,0,0.05)' }}>
      <div style={{ textAlign: 'center', marginBottom: 40 }}>
        <Title level={2}>数据分析报告</Title>
        <Text type="secondary">生成时间: {new Date().toLocaleDateString()}</Text>
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
    
    # 智能路由：判断是否生成报告
    is_report = "报告" in query or "总结" in query or "report" in query.lower()
    
    # 如果没有洞察且没有可视化，可能不需要生成 UI (除非是强制生成报告)
    if not insights and not viz_config and not is_report:
        return {"ui_component": None}
        
    if is_report:
        print("DEBUG: Generating Analysis Report...")
        prompt = ChatPromptTemplate.from_template(REPORT_PROMPT)
    else:
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
        elif code.startswith("```javascript"):
             code = code[13:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
            
        print("DEBUG: UI Artist generated component code.")
        return {"ui_component": code}
        
    except Exception as e:
        print(f"UI Artist failed: {e}")
        return {"ui_component": None}
