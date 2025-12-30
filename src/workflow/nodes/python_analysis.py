import pandas as pd
import json
import io
import contextlib
import ast
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from src.workflow.state import AgentState
from src.core.llm import get_llm

def is_safe_code(code: str) -> bool:
    """
    使用 AST 检查 Python 代码是否包含危险操作。
    """
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            # 禁止 import
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # 允许部分白名单库 (虽然 exec 环境已经限制了，但双重保险)
                # 其实在 exec 中我们通常不允许 import 任何东西，除非是预置的
                return False
            # 禁止访问私有属性 (以 _ 开头)
            if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
                return False
            # 禁止使用 exec, eval (虽然是 builtins，但 AST 也可以查)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ['exec', 'eval', 'open', 'exit', 'quit']:
                    return False
        return True
    except SyntaxError:
        return False

def python_analysis_node(state: AgentState, config: dict = None) -> dict:
    """
    高级数据分析节点。
    使用 Python (Pandas) 对 SQL 查询结果进行复杂的统计分析、预测或清洗。
    包含安全沙箱检查。
    """
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="PythonAnalysis", project_id=project_id)
    
    # 获取上下文
    query = ""
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            query = msg.content
            break
            
    sql_results = state.get("results", "[]")
    
    # 尝试解析 JSON 数据为 DataFrame
    try:
        data_list = json.loads(sql_results)
        if not isinstance(data_list, list) or not data_list:
            return {"messages": [AIMessage(content="无法进行高级分析：数据为空或格式不正确。")]}
        
        # 转换为 DataFrame 预览供 LLM 参考
        df_preview = pd.DataFrame(data_list[:5]).to_markdown(index=False)
        columns_info = list(data_list[0].keys())
        
    except Exception as e:
        return {"messages": [AIMessage(content=f"无法进行高级分析：数据解析失败 ({e})")]}

    # 1. 生成 Python 代码
    prompt = ChatPromptTemplate.from_template(
        "你是一个 Python 数据分析专家。请根据用户的需求和数据结构，编写 Python 代码进行分析。\n"
        "用户需求: {query}\n"
        "数据结构 (DataFrame `df`): \n"
        "列名: {columns}\n"
        "数据预览:\n{df_preview}\n\n"
        "环境说明:\n"
        "- 变量 `df` 已经预先加载了完整数据，可以直接使用。\n"
        "- 可用库: pandas (pd), numpy (np), scipy, sklearn。\n"
        "- 禁止使用 `import` 导入其他库。\n"
        "- 禁止文件读写操作。\n"
        "- 如果需要输出结果，请使用 `print()` 函数。\n"
        "- 如果需要绘图，目前暂不支持直接绘图，请计算绘图所需的数据点并 print 出来。\n"
        "- 请只返回 Python 代码，不要包含 Markdown 标记 (```python ... ```)。\n"
        "- 代码必须健壮，处理可能的空值或类型错误。\n"
    )
    
    chain = prompt | llm
    code_result = chain.invoke({
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
    
    # 2. 安全检查与执行
    if not is_safe_code(python_code):
         return {
            "messages": [AIMessage(content="生成的代码包含不安全的操作（如导入库或访问私有属性），已被系统拦截。")],
            "analysis": "Error: Security Violation in generated code."
        }

    output_buffer = io.StringIO()
    try:
        # 准备受限执行环境
        # 仅允许白名单内的库和变量
        import numpy as np
        # 动态导入 sklearn 和 scipy 如果环境中有的话，否则忽略
        safe_globals = {
            "df": pd.DataFrame(data_list),
            "pd": pd,
            "np": np,
            "json": json,
            "print": print, # 实际上 print 会被重定向，这里给个引用也没事
            "__builtins__": {
                "abs": abs, "round": round, "min": min, "max": max, "len": len,
                "sum": sum, "range": range, "zip": zip, "enumerate": enumerate,
                "list": list, "dict": dict, "set": set, "tuple": tuple,
                "int": int, "float": float, "str": str, "bool": bool
            }
        }
        
        with contextlib.redirect_stdout(output_buffer):
            exec(python_code, safe_globals)
            
        execution_output = output_buffer.getvalue()
        
        if not execution_output:
            execution_output = "代码执行成功，但没有输出结果。"
            
    except Exception as e:
        execution_output = f"代码执行出错:\n{e}"
        
    # 3. 结果解读
    # 将执行结果反馈给 LLM 生成最终回答
    summary_prompt = ChatPromptTemplate.from_template(
        "请根据 Python 代码的执行结果，回答用户的问题。\n"
        "用户问题: {query}\n"
        "执行代码:\n```python\n{code}\n```\n"
        "执行结果:\n{output}\n\n"
        "请给出专业的分析结论。"
    )
    
    summary_chain = summary_prompt | llm
    final_response = summary_chain.invoke({
        "query": query,
        "code": python_code,
        "output": execution_output
    })
    
    return {
        "messages": [AIMessage(content=final_response.content)],
        "analysis": final_response.content, # 同时更新 analysis 状态
        "python_code": python_code # 增加 code 字段供前端展示
    }
