import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

def get_llm():
    """
    初始化并返回 ChatOpenAI 实例。
    配置从环境变量中读取。
    """
    model_name = os.getenv("MODEL_NAME", "qwen-max")
    api_base = os.getenv("OPENAI_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("警告: 未找到 OPENAI_API_KEY 环境变量")

    return ChatOpenAI(
        model=model_name,
        base_url=api_base,
        api_key=api_key,
        temperature=0
    )
