"""
backend/orchestrator/checkpointer.py

Durable Checkpoint Saver for LangGraph workflow persistence.

Provides multi-process checkpoint persistence across worker crashes,
graceful restarts, and distributed execution using Redis storage with
in-memory fallback for testing.
"""

from collections import defaultdict
import logging
import pickle
from typing import Any, Sequence
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.memory import InMemorySaver

logger = logging.getLogger(__name__)

CHECKPOINT_TTL_SECONDS = 7 * 86400  # 7 days retention for review workflow checkpoints


class DurableCheckpointSaver(InMemorySaver):
    """
    Durable checkpoint saver backed by Redis with in-memory caching.

    Preserves execution state after each node completion. Enables:
      - Clean resumption of interrupted reviews across process crashes
      - State inspection without re-running completed nodes
      - Scoped thread_id retention with automatic expiration
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def save_to_bytes(self, thread_id: str) -> bytes:
        """Serializes all checkpoint data for thread_id to portable bytes."""
        data = {
            "storage": self.storage.get(thread_id, {}),
            "writes": {k: v for k, v in self.writes.items() if k[0] == thread_id},
            "blobs": {k: v for k, v in self.blobs.items() if k[0] == thread_id},
        }
        return pickle.dumps(data)

    def load_from_bytes(self, thread_id: str, b: bytes) -> None:
        """Restores checkpoint data for thread_id from portable bytes."""
        data = pickle.loads(b)
        self.storage[thread_id] = data.get("storage", {})
        self.writes.update(data.get("writes", {}))
        self.blobs.update(data.get("blobs", {}))

    async def _persist_to_redis(self, thread_id: str) -> None:
        """Saves current thread state to Redis if available."""
        from backend.memory.redis_client import redis_client
        if not redis_client.is_connected:
            return
        try:
            pool = redis_client._require_connected()
            b = self.save_to_bytes(thread_id)
            redis_key = f"checkpoint:langgraph:{thread_id}"
            await pool.setex(redis_key, CHECKPOINT_TTL_SECONDS, b)
            logger.debug("checkpoint_persisted_to_redis | thread_id=%s bytes=%d", thread_id, len(b))
        except Exception as e:
            logger.warning("Failed to persist checkpoint to Redis for %s: %s", thread_id, e)

    async def _restore_from_redis_if_needed(self, thread_id: str) -> None:
        """Loads thread state from Redis if not present in local memory."""
        if thread_id in self.storage:
            return
        from backend.memory.redis_client import redis_client
        if not redis_client.is_connected:
            return
        try:
            pool = redis_client._require_connected()
            redis_key = f"checkpoint:langgraph:{thread_id}"
            raw = await pool.get(redis_key)
            if raw:
                self.load_from_bytes(thread_id, raw)
                logger.debug("checkpoint_restored_from_redis | thread_id=%s bytes=%d", thread_id, len(raw))
        except Exception as e:
            logger.warning("Failed to restore checkpoint from Redis for %s: %s", thread_id, e)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        updated_config = await super().aput(config, checkpoint, metadata, new_versions)
        thread_id = config["configurable"].get("thread_id")
        if thread_id:
            await self._persist_to_redis(thread_id)
        return updated_config

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        await super().aput_writes(config, writes, task_id, task_path)
        thread_id = config["configurable"].get("thread_id")
        if thread_id:
            await self._persist_to_redis(thread_id)

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id = config["configurable"].get("thread_id")
        if thread_id:
            await self._restore_from_redis_if_needed(thread_id)
        return await super().aget_tuple(config)

    async def adelete_thread(self, thread_id: str) -> None:
        await super().adelete_thread(thread_id)
        from backend.memory.redis_client import redis_client
        if redis_client.is_connected:
            try:
                pool = redis_client._require_connected()
                await pool.delete(f"checkpoint:langgraph:{thread_id}")
            except Exception as e:
                logger.warning("Failed to delete checkpoint in Redis for %s: %s", thread_id, e)
