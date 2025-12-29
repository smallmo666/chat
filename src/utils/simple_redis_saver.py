import pickle
import zlib
from typing import Any, AsyncIterator, Dict, Iterator, Optional, Sequence, Tuple

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple
from redis import Redis

class SimpleRedisSaver(BaseCheckpointSaver):
    """
    A Redis Checkpointer that uses Redis Hashes and zlib compression for incremental storage.
    Stores channels as individual hash fields to optimize access and storage.
    """
    def __init__(self, conn: Redis):
        super().__init__()
        self.client = conn

    def _compress(self, data: Any) -> bytes:
        return zlib.compress(pickle.dumps(data))

    def _decompress(self, data: bytes) -> Any:
        return pickle.loads(zlib.decompress(data))

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        key = f"checkpoint:{thread_id}"
        
        # Get all fields from the hash
        data = self.client.hgetall(key)
        if not data:
            return None
            
        # Decode fields (redis returns bytes if decode_responses=False)
        # We expect raw bytes for values because they are compressed pickles
        
        try:
            # 1. Metadata
            metadata = self._decompress(data[b"metadata"])
            
            # 2. Config
            parent_config = self._decompress(data[b"config"])
            
            # 3. Checkpoint Info (id, ts, etc, without channel_values)
            checkpoint = self._decompress(data[b"info"])
            
            # 4. Reconstruct Channel Values
            channel_values = {}
            for k, v in data.items():
                if k.startswith(b"chan:"):
                    channel_name = k[5:].decode("utf-8") # Remove 'chan:' prefix
                    channel_values[channel_name] = self._decompress(v)
            
            checkpoint["channel_values"] = channel_values
            
            return CheckpointTuple(config, checkpoint, metadata, parent_config)
        except Exception as e:
            print(f"Error loading checkpoint from Redis: {e}")
            return None

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

    def _sanitize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively remove unpickleable objects (like local functions) from config.
        """
        if not isinstance(config, dict):
            return config
            
        clean_config = {}
        for k, v in config.items():
            if k == "callbacks": # Explicitly skip callbacks
                continue
            
            if callable(v):
                # Skip functions/methods as they are often not picklable or not needed for checkpoint
                continue
                
            if isinstance(v, dict):
                clean_config[k] = self._sanitize_config(v)
            elif isinstance(v, list):
                # Clean lists if they contain dicts
                clean_config[k] = [self._sanitize_config(i) if isinstance(i, dict) else i for i in v]
            else:
                clean_config[k] = v
        return clean_config

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
        safe_config = self._sanitize_config(config)
        
        # Prepare Hash Data
        hset_data = {}
        
        # 1. Metadata & Config
        hset_data["metadata"] = self._compress(metadata)
        hset_data["config"] = self._compress(safe_config)
        
        # 2. Checkpoint Info (exclude channel_values to save space/redundancy in 'info' field)
        # We make a shallow copy and remove channel_values temporarily for serialization
        checkpoint_copy = checkpoint.copy()
        channel_values = checkpoint_copy.pop("channel_values", {})
        hset_data["info"] = self._compress(checkpoint_copy)
        
        # 3. Channel Values (Incremental updates)
        # We update all channels present in the current checkpoint.
        # Ideally, we could only update those in new_versions, but 'checkpoint' has the full state.
        # Writing to Hash is efficient enough.
        for name, value in channel_values.items():
            hset_data[f"chan:{name}"] = self._compress(value)
            
        self.client.hset(key, mapping=hset_data)
        
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
        pass

    # Add async implementation
    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        return self.put_writes(config, writes, task_id)
