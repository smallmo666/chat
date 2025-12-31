import os
import functools
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from src.core.database import get_app_db
from src.core.models import Project, LLMProvider

load_dotenv()

@functools.lru_cache(maxsize=32)
def get_llm(node_name: str = None, project_id: int = None) -> BaseChatModel:
    """
    Get LLM instance based on Project configuration and Node context.
    Cached to avoid frequent DB lookups and object creation overhead.
    """
    
    # 1. Try to load from Database if project_id and node_name provided
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
            print(f"Failed to load dynamic LLM config: {e}. Fallback to default.")

    # 2. Fallback to Env Vars (System Default)
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
        temperature=0,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base=os.getenv("OPENAI_API_BASE")
    )

def _create_llm_from_config(config: LLMProvider) -> BaseChatModel:
    """
    Factory to create LangChain ChatModel from DB config.
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
        # Example for Azure (requires more fields usually)
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
    # Add more providers as needed (Anthropic, etc.)
    
    # Default fallback
    return ChatOpenAI(api_key=config.api_key)
