from typing import List, Optional
from pydantic import BaseModel

class LLMProviderCreate(BaseModel):
    name: str
    provider: str = "openai"
    model_name: str
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    parameters: Optional[dict] = {}

class LLMProviderRead(BaseModel):
    id: int
    name: str
    provider: str
    model_name: str
    api_base: Optional[str]
    # Do not return api_key for security
    parameters: dict
