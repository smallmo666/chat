import sys
import io
import pandas as pd
import numpy as np
import traceback
import ast
import base64
import matplotlib
import matplotlib.pyplot as plt

# 设置非交互式后端，防止 plt.show() 阻塞或报错
matplotlib.use('Agg')

class SecurityError(Exception):
    pass

# 全局 Session 存储 (简单内存实现，生产环境应使用 Redis 序列化)
_sessions = {}

class StatefulSandbox:
    """
    支持会话状态保持的 Python 沙箱。
    """
    
    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        if session_id not in _sessions:
            _sessions[session_id] = {
                "globals": {},
                "locals": {}
            }
        self.context = _sessions[session_id]

    def _check_ast_safety(self, code: str):
        """
        检查 AST 是否包含不安全的节点。
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise SecurityError(f"Syntax Error: {e}")

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # 暂时允许 import，依靠运行时沙箱限制
                pass
            
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['exec', 'eval', 'compile', 'open', 'input', '__import__']:
                        raise SecurityError(f"Call to forbidden function '{node.func.id}' detected.")
            
            if isinstance(node, ast.Attribute):
                if node.attr.startswith("_"):
                    raise SecurityError("Accessing private attributes is prohibited.")

    def execute(self, code: str, additional_context: dict = None) -> dict:
        """
        执行 Python 代码，支持图片输出。
        """
        # 1. 静态检查
        try:
            self._check_ast_safety(code)
        except SecurityError as e:
            return {"output": "", "error": str(e), "result": None, "images": []}
        
        # 2. 准备环境
        # 合并持久化上下文和本次临时上下文
        if additional_context:
            self.context["locals"].update(additional_context)
            
        # 注入常用库
        safe_globals = {
            "__builtins__": {
                "print": print, "len": len, "range": range, "int": int, "float": float,
                "str": str, "list": list, "dict": dict, "set": set, "tuple": tuple,
                "bool": bool, "abs": abs, "round": round, "min": min, "max": max,
                "sum": sum, "any": any, "all": all, "sorted": sorted, "enumerate": enumerate,
                "zip": zip, "map": map, "filter": filter, "True": True, "False": False, "None": None
            },
            "pd": pd,
            "np": np,
            "plt": plt,
            "io": io,
            "base64": base64
        }
        # 恢复之前的 globals (如果需要支持自定义函数跨 step 调用)
        # self.context["globals"].update(safe_globals) 
        
        # 3. 执行
        old_stdout = sys.stdout
        redirected_output = sys.stdout = io.StringIO()
        images = []
        
        try:
            # 清除之前的绘图
            plt.clf()
            
            # Exec
            exec(code, safe_globals, self.context["locals"])
            
            # 捕获 Stdout
            stdout_str = redirected_output.getvalue()
            result_val = self.context["locals"].get("result", None)
            
            # 捕获 Matplotlib 图片
            if plt.get_fignums():
                buf = io.BytesIO()
                plt.savefig(buf, format='png', bbox_inches='tight')
                buf.seek(0)
                img_str = base64.b64encode(buf.read()).decode('utf-8')
                images.append(img_str)
                plt.close('all')
            
            return {
                "output": stdout_str,
                "error": None,
                "result": result_val,
                "images": images
            }
            
        except Exception as e:
            return {
                "output": redirected_output.getvalue(),
                "error": f"{type(e).__name__}: {str(e)}",
                "result": None,
                "images": []
            }
        finally:
            sys.stdout = old_stdout

def execute_pandas_analysis(df: pd.DataFrame, code: str, session_id: str = "default") -> dict:
    sandbox = StatefulSandbox(session_id)
    return sandbox.execute(code, additional_context={"df": df})
