from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

class UIStreamingCallbackHandler(BaseCallbackHandler):
    """Callback handler for streaming LLM tokens to a UI update function."""
    
    def __init__(self, update_callback):
        self.update_callback = update_callback
        self.current_text = ""
        
    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Run when LLM starts running."""
        self.current_text = ""
        # We don't need to emit empty string on start, it might confuse the stream
        # self.update_callback("")

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Run on new LLM token. Only available when streaming is enabled."""
        self.current_text += token
        # Send only the new token (chunk), not the full text
        self.update_callback(token)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run when LLM ends running."""
        # Optional: clear or finalize text
        pass
        
    def on_llm_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Run when LLM errors."""
        pass
