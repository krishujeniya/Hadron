# backend/job_queue/heartbeat.py
#
# Background worker heartbeat manager.
# Emits periodic heartbeats to Redis to prove worker process liveness.
# Enables health checks (/health/ready) to distinguish an idle cluster from
# an offline worker fleet where incoming reviews will never be processed.

import asyncio
import logging
import os
import socket
import time
from typing import Any

from backend.config.settings import get_settings
from backend.memory.redis_client import redis_client

logger = logging.getLogger(__name__)


class WorkerHeartbeat:
    """
    Manages the heartbeat loop for an individual worker process.
    """

    def __init__(
        self,
        worker_id: str | None = None,
        interval_seconds: float = 10.0,
        ttl_seconds: int = 45,
    ) -> None:
        self.hostname = socket.gethostname()
        self.pid = os.getpid()
        self.worker_id = worker_id or f"worker-{self.hostname}-{self.pid}"
        self.interval_seconds = interval_seconds
        self.ttl_seconds = ttl_seconds
        self.started_at = time.time()
        self._task: asyncio.Task | None = None
        self._stopped = False

    async def start(self) -> None:
        """Starts the periodic background heartbeat loop."""
        self._stopped = False
        await self._emit_beat()
        self._task = asyncio.create_task(self._run_loop(), name=f"heartbeat-{self.worker_id}")
        logger.info(
            "Worker heartbeat loop started | worker_id=%s interval=%.1fs ttl=%ds",
            self.worker_id,
            self.interval_seconds,
            self.ttl_seconds,
        )

    async def stop(self) -> None:
        """Cancels the heartbeat loop and removes the worker record from Redis."""
        self._stopped = True
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await redis_client.remove_worker_heartbeat(self.worker_id)
        logger.info("Worker heartbeat stopped and unregistered | worker_id=%s", self.worker_id)

    async def _emit_beat(self) -> None:
        metadata: dict[str, Any] = {
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "pid": self.pid,
            "started_at": self.started_at,
            "uptime_seconds": round(time.time() - self.started_at, 1),
        }
        await redis_client.record_worker_heartbeat(
            worker_id=self.worker_id,
            metadata=metadata,
            ttl=self.ttl_seconds,
        )

    async def _run_loop(self) -> None:
        while not self._stopped:
            try:
                await asyncio.sleep(self.interval_seconds)
                if not self._stopped:
                    await self._emit_beat()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error emitting worker heartbeat: %s", exc)


_heartbeat_instance: WorkerHeartbeat | None = None


async def start_worker_heartbeat(
    worker_id: str | None = None,
    interval_seconds: float = 10.0,
    ttl_seconds: int = 45,
) -> WorkerHeartbeat:
    """Starts the worker heartbeat singleton."""
    global _heartbeat_instance
    cfg = get_settings()
    ttl = getattr(cfg, "worker_heartbeat_ttl_seconds", ttl_seconds)
    if _heartbeat_instance is None or _heartbeat_instance._stopped:
        _heartbeat_instance = WorkerHeartbeat(
            worker_id=worker_id,
            interval_seconds=interval_seconds,
            ttl_seconds=ttl,
        )
        await _heartbeat_instance.start()
    return _heartbeat_instance


async def stop_worker_heartbeat() -> None:
    """Stops the worker heartbeat singleton."""
    global _heartbeat_instance
    if _heartbeat_instance is not None:
        try:
            await _heartbeat_instance.stop()
        finally:
            _heartbeat_instance = None
