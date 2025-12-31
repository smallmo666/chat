import pandas as pd
import json
import asyncio
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from src.workflow.state import AgentState
from src.core.llm import get_llm
from src.domain.sandbox import StatefulSandbox

CODE_GEN_PROMPT = """
你是一个 Python 数据分析专家。请根据用户的需求和数据结构，编写 Python 代码进行分析。
用户需求: {query}
数据结构 (DataFrame `df`): 
列名: {columns}
数据预览:
{df_preview}

环境说明:
- 变量 `df` 已经预先加载了完整数据，可以直接使用。
- 可用库: pandas (pd), numpy (np), matplotlib.pyplot (plt), io, base64, sklearn, scipy。
- **绘图支持**: 你可以使用 `plt` 进行绘图。无需调用 `plt.show()`，系统会自动捕获图表。
- 禁止使用 `import` 导入未列出的库。
- 禁止文件读写操作。
- 如果需要输出结果，请使用 `print()` 函数。
- 请只返回 Python 代码，不要包含 Markdown 标记 (```python ... ```)。
- 代码必须健壮，处理可能的空值或类型错误。
"""

SUMMARY_PROMPT = """
请根据 Python 代码的执行结果，回答用户的问题。
用户问题: {query}
执行代码:
```python
{code}
```
执行结果(Output):
{output}

生成的图表数量: {image_count}

请给出专业的分析结论。如果生成了图表，请在结论中引用图表内容。
"""

async def python_analysis_node(state: AgentState, config: dict = None) -> dict:
    """
    高级数据分析节点 (Async Optimized)。
    使用 StatefulSandbox (支持 Pandas/Matplotlib) 对 SQL 查询结果进行复杂的统计分析、预测或清洗。
    """
    project_id = config.get("configurable", {}).get("project_id", "default")
    llm = get_llm(node_name="PythonAnalysis", project_id=project_id)
    
    # 获取上下文
    query = ""
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            query = msg.content
            break
            
    sql_results = state.get("results", "[]")
    
    # 异步解析 JSON 数据为 DataFrame (CPU 密集型)
    def _parse_data_safe():
        try:
            data_list = json.loads(sql_results)
            if not isinstance(data_list, list) or not data_list:
                return None, None, None, "数据为空或格式不正确"
            
            df = pd.DataFrame(data_list)
            df_preview = df.head(5).to_markdown(index=False)
            columns_info = list(data_list[0].keys())
            return df, df_preview, columns_info, None
        except Exception as e:
            return None, None, None, str(e)

    df, df_preview, columns_info, parse_error = await asyncio.to_thread(_parse_data_safe)
    
    if parse_error:
         return {"messages": [AIMessage(content=f"无法进行高级分析：{parse_error}")]}

    # 1. 生成 Python 代码 (Async)
    prompt = ChatPromptTemplate.from_template(CODE_GEN_PROMPT)
    chain = prompt | llm
    
    code_result = await chain.ainvoke({
        "query": query,
        "columns": columns_info,
        "df_preview": df_preview
    })
    
    python_code = code_result.content.strip()
    
    # 清理代码块标记
    if "```python" in python_code:
        python_code = python_code.split("```python")[1].split("```")[0].strip()
    elif "```" in python_code:
        python_code = python_code.split("```")[1].split("```")[0].strip()
        
    print(f"DEBUG: Generated Python Code:\n{python_code}")
    
    # 2. 在沙箱中执行代码 (支持绘图和会话)
    # 使用 project_id 作为 session_id，实现项目级隔离
    sandbox = StatefulSandbox(session_id=str(project_id))
    
    # 准备上下文数据
    additional_context = {"df": df}
    
    # 异步执行 (run_in_executor)
    # StatefulSandbox.execute 是同步的，所以我们需要包装它
    try:
        exec_result = await asyncio.to_thread(sandbox.execute, python_code, additional_context)
    except Exception as e:
        return {
            "messages": [AIMessage(content=f"沙箱执行出错: {str(e)}")],
            "analysis": f"Execution Error: {str(e)}"
        }
    
    output = exec_result.get("output", "")
    error = exec_result.get("error")
    images = exec_result.get("images", []) # List of base64 strings
    
    if error:
         return {
            "messages": [AIMessage(content=f"代码执行报错:\n{error}")],
            "analysis": f"Error: {error}"
        }

    # 3. 结果解读
    # 将执行结果反馈给 LLM 生成最终回答
    summary_prompt = ChatPromptTemplate.from_template(SUMMARY_PROMPT)
    
    summary_chain = summary_prompt | llm
    
    # Async invoke
    final_response = await summary_chain.ainvoke({
        "query": query,
        "code": python_code,
        "output": output,
        "image_count": len(images)
    })
    
    content = final_response.content
    
    # 如果有图片，将 Base64 图片附加到消息中 (Markdown 格式)
    msg_content = content
    if images:
        msg_content += "\n\n**生成的图表:**\n"
        for i, img_b64 in enumerate(images):
            msg_content += f"\n![Chart {i+1}](data:image/png;base64,{img_b64})\n"
            
    return {
        "messages": [AIMessage(content=msg_content)],
        "analysis": content, # 分析结果文本
        "python_code": python_code # 增加 code 字段供前端展示
    }
