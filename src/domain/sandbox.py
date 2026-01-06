import io
import base64
import contextlib
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# 设置非交互式后端，防止弹窗
matplotlib.use('Agg')

class StatefulSandbox:
    """
    Stateful Python Execution Sandbox.
    Allows executing Python code in a persistent local context.
    Captures stdout and matplotlib plots.

    WARNING: This sandbox executes arbitrary Python code in the host process using `exec()`.
    It is NOT secure for production use with untrusted input.
    Known risks:
    1. Infinite loops (CPU exhaustion)
    2. Excessive memory usage (Memory exhaustion)
    3. File system access (Read/Write arbitrary files)
    4. Network access (Data exfiltration)

    TODO: For production, migrate to a secure containerized environment (e.g., Docker, gVisor, Firecracker)
    or use a restricted execution environment like WebAssembly (Pyodide).
    """
    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.locals = {} # Persistent state
        self.globals = {
            "pd": pd,
            "np": np,
            "plt": plt,
            "io": io,
            "base64": base64
        }
        
    def execute(self, code: str, context: dict = None) -> dict:
        """
        Executes the provided Python code.
        
        Args:
            code (str): Python code to execute.
            context (dict): Additional variables to inject into the local scope.
            
        Returns:
            dict: {
                "output": str, # Stdout capture
                "error": str,  # Error message if any
                "images": list # List of base64 encoded images
            }
        """
        if context:
            self.locals.update(context)
            
        output_buffer = io.StringIO()
        images = []
        error = None
        
        # Capture stdout
        with contextlib.redirect_stdout(output_buffer):
            try:
                # Clear previous plots
                plt.clf()
                plt.close('all')
                
                # Execute code
                exec(code, self.globals, self.locals)
                
                # Check if any plot was created
                if plt.get_fignums():
                    # Save plot to buffer
                    img_buffer = io.BytesIO()
                    plt.savefig(img_buffer, format='png', bbox_inches='tight')
                    img_buffer.seek(0)
                    img_b64 = base64.b64encode(img_buffer.read()).decode('utf-8')
                    images.append(img_b64)
                    
            except Exception as e:
                import traceback
                error = traceback.format_exc()
                
        return {
            "output": output_buffer.getvalue(),
            "error": error,
            "images": images
        }
