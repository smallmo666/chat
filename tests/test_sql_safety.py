import pytest
from src.workflow.nodes.python_analysis import is_safe_code

# Test cases for Python Sandbox Security

def test_safe_code_basic():
    """Test basic safe operations"""
    code = """
import numpy as np
a = 1
b = 2
print(a + b)
df['new_col'] = df['col1'] * 2
"""
    # Note: is_safe_code disallows import by default, so 'import numpy' should fail if strictly checked.
    # However, our is_safe_code implementation currently forbids all imports.
    # In python_analysis_node, we exec with pre-imported libs.
    # So generated code should NOT have import statements.
    
    # Let's adjust expectation: generated code should NOT have imports.
    # If LLM generates import, it is considered unsafe/invalid for our sandbox context.
    assert is_safe_code(code) == False

def test_safe_code_no_imports():
    """Test safe code without imports (as expected in sandbox)"""
    code = """
a = 1
b = 2
print(a + b)
# df is pre-defined
df['new_col'] = df['col1'] * 2
"""
    assert is_safe_code(code) == True

def test_unsafe_import_os():
    """Test injection of os module"""
    code = "import os\nos.system('ls')"
    assert is_safe_code(code) == False

def test_unsafe_import_subprocess():
    """Test injection of subprocess"""
    code = "import subprocess\nsubprocess.run(['ls'])"
    assert is_safe_code(code) == False

def test_unsafe_exec():
    """Test use of exec"""
    code = "exec('print(1)')"
    assert is_safe_code(code) == False

def test_unsafe_eval():
    """Test use of eval"""
    code = "eval('1+1')"
    assert is_safe_code(code) == False

def test_unsafe_open():
    """Test file access"""
    code = "f = open('/etc/passwd', 'r')"
    assert is_safe_code(code) == False

def test_unsafe_dunder():
    """Test access to private attributes"""
    code = "print(obj.__class__)"
    # Our simple check forbids attributes starting with _
    assert is_safe_code(code) == False

def test_unsafe_exit():
    """Test exit/quit"""
    code = "exit()"
    assert is_safe_code(code) == False

if __name__ == "__main__":
    # Manually run tests if pytest not installed
    try:
        test_safe_code_basic()
        print("test_safe_code_basic passed (or failed as expected)")
    except AssertionError:
        print("test_safe_code_basic failed")

    try:
        test_safe_code_no_imports()
        print("test_safe_code_no_imports passed")
    except AssertionError:
        print("test_safe_code_no_imports failed")
        
    try:
        test_unsafe_import_os()
        print("test_unsafe_import_os passed")
    except AssertionError:
        print("test_unsafe_import_os failed")
        
    print("All security tests finished.")
