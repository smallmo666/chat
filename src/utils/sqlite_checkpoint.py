import sqlite3
import pickle
from typing import Any, Dict, Optional, Iterator, AsyncIterator
from contextlib import contextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple
from langchain_core.runnables import RunnableConfig

class SqliteSaver(BaseCheckpointSaver):
    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id TEXT,
                thread_ts TEXT,
                parent_ts TEXT,
                checkpoint BLOB,
                metadata BLOB,
                PRIMARY KEY (thread_id, thread_ts)
            )
            """
        )
        self.conn.commit()

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        thread_ts = config["configurable"].get("thread_ts")
        
        if thread_ts:
            cursor = self.conn.execute(
                "SELECT checkpoint, metadata, parent_ts FROM checkpoints WHERE thread_id = ? AND thread_ts = ?",
                (thread_id, thread_ts),
            )
        else:
            cursor = self.conn.execute(
                "SELECT checkpoint, metadata, parent_ts, thread_ts FROM checkpoints WHERE thread_id = ? ORDER BY thread_ts DESC LIMIT 1",
                (thread_id,),
            )
            
        row = cursor.fetchone()
        if not row:
            return None
            
        if thread_ts:
            checkpoint_blob, metadata_blob, parent_ts = row
        else:
            checkpoint_blob, metadata_blob, parent_ts, thread_ts = row
            
        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "thread_ts": thread_ts}},
            checkpoint=pickle.loads(checkpoint_blob),
            metadata=pickle.loads(metadata_blob) if metadata_blob else {},
            parent_config={"configurable": {"thread_id": thread_id, "thread_ts": parent_ts}} if parent_ts else None,
        )

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        # Minimal implementation for listing
        query = "SELECT thread_id, thread_ts, parent_ts, checkpoint, metadata FROM checkpoints"
        params = []
        if config:
            query += " WHERE thread_id = ?"
            params.append(config["configurable"]["thread_id"])
        
        query += " ORDER BY thread_ts DESC"
        if limit:
            query += f" LIMIT {limit}"
            
        cursor = self.conn.execute(query, params)
        for row in cursor:
            thread_id, thread_ts, parent_ts, checkpoint_blob, metadata_blob = row
            yield CheckpointTuple(
                config={"configurable": {"thread_id": thread_id, "thread_ts": thread_ts}},
                checkpoint=pickle.loads(checkpoint_blob),
                metadata=pickle.loads(metadata_blob) if metadata_blob else {},
                parent_config={"configurable": {"thread_id": thread_id, "thread_ts": parent_ts}} if parent_ts else None,
            )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any],
    ) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        thread_ts = checkpoint["id"]
        parent_ts = config["configurable"].get("thread_ts")
        
        self.conn.execute(
            "INSERT OR REPLACE INTO checkpoints (thread_id, thread_ts, parent_ts, checkpoint, metadata) VALUES (?, ?, ?, ?, ?)",
            (
                thread_id,
                thread_ts,
                parent_ts,
                pickle.dumps(checkpoint),
                pickle.dumps(metadata),
            ),
        )
        self.conn.commit()
        
        return {
            "configurable": {
                "thread_id": thread_id,
                "thread_ts": thread_ts,
            }
        }
    
    # Async methods fallback to sync for simplicity in this demo environment
    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return self.get_tuple(config)

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any],
    ) -> RunnableConfig:
        return self.put(config, checkpoint, metadata, new_versions)
