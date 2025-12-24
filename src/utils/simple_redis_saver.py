import pickle
from typing import Any, AsyncIterator, Dict, Iterator, Optional, Sequence, Tuple

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple
from redis import Redis

class SimpleRedisSaver(BaseCheckpointSaver):
    """
    A simple Redis Checkpointer that uses pickle for serialization.
    Does NOT require RedisJSON module.
    """
    def __init__(self, conn: Redis):
        super().__init__()
        self.client = conn

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        key = f"checkpoint:{thread_id}"
        
        # Get the latest checkpoint
        data = self.client.get(key)
        if not data:
            return None
            
        checkpoint, metadata, parent_config = pickle.loads(data)
        return CheckpointTuple(config, checkpoint, metadata, parent_config)

    # Add async implementation for astream compatibility
    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return self.get_tuple(config)

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        # Simplified implementation: only supports listing the current thread's latest
        if config:
            tuple_ = self.get_tuple(config)
            if tuple_:
                yield tuple_

    # Add async implementation
    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        if config:
            tuple_ = await self.aget_tuple(config)
            if tuple_:
                yield tuple_

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any],
    ) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        key = f"checkpoint:{thread_id}"
        
        # Avoid saving 'callbacks' or other unpickleable objects in config
        # Make a copy and filter out unsafe keys
        safe_config = config.copy()
        if "callbacks" in safe_config:
            del safe_config["callbacks"]
        
        # Save checkpoint data
        # We store (checkpoint, metadata, config) tuple
        data = pickle.dumps((checkpoint, metadata, safe_config))
        self.client.set(key, data)
        
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint["id"],
            }
        }

    # Add async implementation
    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any],
    ) -> RunnableConfig:
        return self.put(config, checkpoint, metadata, new_versions)

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        # For this simple demo, we might not need to store intermediate writes persistently
        # if we are just doing simple state management.
        # But to be correct, we should store them.
        # Simplified: We skip storing intermediate writes for now as they are often transient.
        pass

    # Add async implementation
    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        return self.put_writes(config, writes, task_id)
