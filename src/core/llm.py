from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from src.core.database import get_app_db
from src.core.models import Project, LLMProvider
from src.core.config import settings

def get_llm(node_name: str = None, project_id: int = None) -> BaseChatModel:
    """
    根据项目配置和节点上下文获取 LLM 实例。
    移除 LRU 缓存以确保配置更改（如 API Key 更新）能即时生效。
    LangChain 的 ChatModel 初始化开销极低，因此不缓存是安全的。
    """
    
    # 1. 尝试从数据库加载（如果提供了 project_id 和 node_name）
    if project_id and node_name:
        try:
            app_db = get_app_db()
            with app_db.get_session() as session:
                project = session.get(Project, project_id)
                if project and project.node_model_config:
                    llm_id = project.node_model_config.get(node_name)
                    if llm_id:
                        provider_config = session.get(LLMProvider, llm_id)
                        if provider_config:
                            return _create_llm_from_config(provider_config)
        except Exception as e:
            print(f"加载动态 LLM 配置失败: {e}. 回退到默认配置。")

    # 2. 回退到环境变量（系统默认）
    return ChatOpenAI(
        model=settings.OPENAI_MODEL_NAME,
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY,
        # settings currently doesn't have OPENAI_API_BASE, adding fallback if not present
        # but typically this is implied or handled by settings if needed.
        # Let's check settings definition again. It only had KEY and MODEL_NAME.
        # Assuming standard OpenAI or that settings will be updated if custom base needed.
    )

def _create_llm_from_config(config: LLMProvider) -> BaseChatModel:
    """
    工厂方法：根据 DB 配置创建 LangChain ChatModel。
    """
    params = config.parameters or {}
    temperature = params.get("temperature", 0)
    
    if config.provider == "openai":
        return ChatOpenAI(
            model=config.model_name,
            temperature=temperature,
            openai_api_key=config.api_key,
            openai_api_base=config.api_base
        )
    elif config.provider == "azure":
        # Azure 示例 (通常需要更多字段)
        from langchain_openai import AzureChatOpenAI
        return AzureChatOpenAI(
            azure_deployment=config.model_name,
            openai_api_version="2023-05-15",
            azure_endpoint=config.api_base,
            api_key=config.api_key,
            temperature=temperature
        )
    elif config.provider == "ollama":
        from langchain_community.chat_models import ChatOllama
        return ChatOllama(
            model=config.model_name,
            base_url=config.api_base,
            temperature=temperature
        )
    # 根据需要添加更多提供商 (Anthropic 等)
    
    # 默认回退
    return ChatOpenAI(api_key=config.api_key)
