import sys
import io
import pandas as pd
import numpy as np
import traceback
import ast
import base64
import matplotlib
import matplotlib.pyplot as plt
from collections import OrderedDict
import threading
import builtins

# 设置非交互式后端以防止阻塞
matplotlib.use('Agg')

class SecurityError(Exception):
    pass

# 全局会话存储与 LRU (最近最少使用) 淘汰策略
# 简单的内存实现。生产环境建议使用 Redis。
MAX_SESSIONS = 100
_sessions = OrderedDict()

# 全局执行锁，用于保护 sys.stdout 和 matplotlib.pyplot 等非线程安全资源
_execution_lock = threading.Lock()

# 允许导入的白名单模块
ALLOWED_MODULES = {
    'pandas', 'numpy', 'matplotlib', 'matplotlib.pyplot', 'io', 'base64', 'math', 'datetime', 'collections', 're', 'json', 'sklearn', 'scipy'
}

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    """
    自定义的安全导入函数，仅允许白名单模块。
    """
    if name in ALLOWED_MODULES:
        return __import__(name, globals, locals, fromlist, level)
    # 允许子模块导入 (e.g. sklearn.linear_model) 如果父模块在白名单
    base_module = name.split('.')[0]
    if base_module in ALLOWED_MODULES:
        return __import__(name, globals, locals, fromlist, level)
        
    raise SecurityError(f"Security: Import of module '{name}' is not allowed.")

class StatefulSandbox:
    """
    带有状态会话和 LRU 淘汰机制的 Python 沙箱。
    """
    
    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        
        # 访问全局会话
        global _sessions
        
        # LRU 逻辑:
        # 如果会话存在，移动到末尾 (标记为最近使用)
        if session_id in _sessions:
            _sessions.move_to_end(session_id)
        else:
            # 如果是新会话，检查容量
            if len(_sessions) >= MAX_SESSIONS:
                # 移除最旧的 (第一个) 项目
                removed_id, _ = _sessions.popitem(last=False)
                print(f"沙箱会话因 LRU 限制被驱逐: {removed_id}")
            
            # 创建新会话
            _sessions[session_id] = {
                "globals": {},
                "locals": {}
            }
            
        self.context = _sessions[session_id]

    def _check_ast_safety(self, code: str):
        """
        检查 AST 是否包含不安全节点。
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise SecurityError(f"语法错误: {e}")

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # 现在通过 safe_import 运行时检查，但也保留 AST 检查作为第一道防线
                # 可以在这里检查模块名
                pass
            
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['exec', 'eval', 'compile', 'open', 'input', 'exit', 'quit']:
                        raise SecurityError(f"检测到调用被禁止的函数 '{node.func.id}'。")
            
            if isinstance(node, ast.Attribute):
                if node.attr.startswith("_"):
                    raise SecurityError("禁止访问私有属性。")

    def execute(self, code: str, additional_context: dict = None) -> dict:
        """
        执行 Python 代码并捕获输出/图像。
        此方法是线程安全的（通过全局锁串行化）。
        """
        # 1. 静态检查
        try:
            self._check_ast_safety(code)
        except SecurityError as e:
            return {"output": "", "error": str(e), "result": None, "images": []}
        
        # 2. 准备环境
        # 将持久化的 locals 与附加上下文合并
        if additional_context:
            self.context["locals"].update(additional_context)
            
        # 注入安全的 globals
        # 复制 builtins 并覆盖危险函数
        safe_builtins = {k: v for k, v in builtins.__dict__.items() if k not in ['__import__', 'open', 'exec', 'eval', 'compile', 'exit', 'quit', 'input']}
        safe_builtins['__import__'] = safe_import
        
        safe_globals = {
            "__builtins__": safe_builtins,
            "pd": pd,
            "np": np,
            "plt": plt,
            "io": io,
            "base64": base64
        }
        
        # 3. 执行 (加锁保护)
        with _execution_lock:
            old_stdout = sys.stdout
            redirected_output = sys.stdout = io.StringIO()
            images = []
            
            try:
                # 清除之前的绘图
                plt.clf()
                
                # Exec
                # 我们使用会话中的持久化 'locals'
                exec(code, safe_globals, self.context["locals"])
                
                # 捕获标准输出
                stdout_str = redirected_output.getvalue()
                result_val = self.context["locals"].get("result", None)
                
                # 捕获 Matplotlib 图像
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
                # traceback.print_exc() # Debug
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
