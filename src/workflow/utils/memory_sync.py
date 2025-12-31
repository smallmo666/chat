import asyncio
from src.domain.memory.short_term import get_memory
# from src.domain.memory.few_shot import get_few_shot_retriever
# from src.domain.memory.semantic_cache import get_semantic_cache

async def sync_memory(user_id: str, project_id: str, user_query: str, dsl: str, sql: str, json_result: str):
    """
    Syncs successful query data to various memory stores.
    
    UPDATED (Phase 6): 
    - Only syncs to Long-term User Memory (Mem0) automatically.
    - Semantic Cache and Few-Shot are now updated via Feedback Loop (explicit user approval),
      to prevent pollution from incorrect queries.
    
    1. Long-term User Memory (Mem0) -> AUTO
    2. Semantic Cache (Redis/Chroma) -> MANUAL (via Feedback)
    3. Few-Shot Examples (Chroma) -> MANUAL (via Feedback)
    
    Uses asyncio.to_thread for potentially blocking operations, with isolated error handling.
    """
    if not json_result or json_result == "[]" or json_result == "null":
        return

    if not dsl or len(dsl) > 10000:
        return

    print(f"DEBUG: Syncing memory for query: {user_query[:50]}...")

    # Define isolated sync tasks
    def sync_mem0():
        try:
            # 只存储问题和 DSL 逻辑，作为用户偏好
            memory_text = f"Q: {user_query}\nDSL: {dsl}"
            memory_client = get_memory()
            if memory_client.add(user_id=user_id, text=memory_text):
                print(f"Saved RAG memory: {memory_text[:50]}...")
        except Exception as e:
            print(f"Failed to save RAG memory: {e}")

    # --- REMOVED AUTO SYNC FOR SEMANTIC CACHE & FEW SHOT ---
    # def sync_semantic_cache(): ...
    # def sync_few_shot(): ...
    # -------------------------------------------------------

    # Run tasks in thread pool concurrently
    try:
        await asyncio.gather(
            asyncio.to_thread(sync_mem0),
            # asyncio.to_thread(sync_semantic_cache), # Disabled
            # asyncio.to_thread(sync_few_shot)        # Disabled
        )
    except Exception as e:
        print(f"Error in memory sync task group: {e}")
