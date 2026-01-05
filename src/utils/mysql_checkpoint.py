import pickle
from typing import Any, Dict, Optional, Iterator, AsyncIterator, List, Tuple
import pymysql.cursors
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple
from langchain_core.runnables import RunnableConfig

class MySQLSaver(BaseCheckpointSaver):
    def __init__(self, conn: pymysql.connections.Connection):
        super().__init__()
        self.conn = conn
        self._init_table()

    def _init_table(self):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints_v2 (
                    thread_id VARCHAR(191) NOT NULL,
                    thread_ts VARCHAR(191) NOT NULL,
                    parent_ts VARCHAR(191),
                    checkpoint LONGBLOB,
                    metadata LONGBLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (thread_id, thread_ts),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        self.conn.commit()

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        thread_ts = config["configurable"].get("thread_ts")
        
        # Ping to keep connection alive
        self.conn.ping(reconnect=True)

        with self.conn.cursor() as cursor:
            if thread_ts:
                cursor.execute(
                    "SELECT checkpoint, metadata, parent_ts FROM checkpoints_v2 WHERE thread_id = %s AND thread_ts = %s",
                    (thread_id, thread_ts),
                )
                row = cursor.fetchone()
                if row:
                    checkpoint_blob, metadata_blob, parent_ts = row
                    return CheckpointTuple(
                        config={"configurable": {"thread_id": thread_id, "thread_ts": thread_ts}},
                        checkpoint=pickle.loads(checkpoint_blob),
                        metadata=pickle.loads(metadata_blob) if metadata_blob else {},
                        parent_config={"configurable": {"thread_id": thread_id, "thread_ts": parent_ts}} if parent_ts else None,
                    )
            else:
                # Use created_at for sorting instead of thread_ts
                cursor.execute(
                    "SELECT checkpoint, metadata, parent_ts, thread_ts FROM checkpoints_v2 WHERE thread_id = %s ORDER BY created_at DESC LIMIT 1",
                    (thread_id,),
                )
                row = cursor.fetchone()
                if row:
                    checkpoint_blob, metadata_blob, parent_ts, thread_ts = row
                    return CheckpointTuple(
                        config={"configurable": {"thread_id": thread_id, "thread_ts": thread_ts}},
                        checkpoint=pickle.loads(checkpoint_blob),
                        metadata=pickle.loads(metadata_blob) if metadata_blob else {},
                        parent_config={"configurable": {"thread_id": thread_id, "thread_ts": parent_ts}} if parent_ts else None,
                    )
        return None

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        # Minimal implementation
        query = "SELECT thread_id, thread_ts, parent_ts, checkpoint, metadata FROM checkpoints_v2"
        params = []
        if config:
            query += " WHERE thread_id = %s"
            params.append(config["configurable"]["thread_id"])
        
        # Use created_at for sorting
        query += " ORDER BY created_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        
        # Ping to keep connection alive
        self.conn.ping(reconnect=True)
            
        with self.conn.cursor() as cursor:
            cursor.execute(query, tuple(params))
            for row in cursor.fetchall():
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
        
        # Ping to keep connection alive
        self.conn.ping(reconnect=True)

        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO checkpoints_v2 (thread_id, thread_ts, parent_ts, checkpoint, metadata) 
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    checkpoint=VALUES(checkpoint), 
                    metadata=VALUES(metadata), 
                    parent_ts=VALUES(parent_ts),
                    created_at=CURRENT_TIMESTAMP
                """,
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
    
    # Async fallbacks
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
        
    def put_writes(
        self,
        config: RunnableConfig,
        writes: List[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """
        Store intermediate writes.
        Currently a no-op or minimal implementation since we are focusing on checkpoint persistence.
        For full functionality, we should store these in a separate table 'checkpoint_writes'.
        """
        pass

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: List[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        return self.put_writes(config, writes, task_id)
