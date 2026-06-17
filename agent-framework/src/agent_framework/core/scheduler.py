"""Async interval scheduler — runs callbacks at fixed intervals."""
from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Coroutine
from typing import Any


def _parse_interval(interval: str) -> float:
    """Convert human interval strings to seconds.

    Supported suffixes: s (seconds), m (minutes), h (hours), d (days).
    Plain integers are treated as seconds.

    Examples:
        "30s" -> 30.0
        "5m"  -> 300.0
        "1h"  -> 3600.0
        "1d"  -> 86400.0
        "60"  -> 60.0
    """
    interval = interval.strip()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smhd]?)", interval, re.IGNORECASE)
    if not match:
        raise ValueError(f"Cannot parse interval: {interval!r}")
    value = float(match.group(1))
    unit = match.group(2).lower()
    multipliers = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}
    return value * multipliers[unit]


class AsyncScheduler:
    """Runs async callbacks at configurable intervals."""

    def __init__(self) -> None:
        self._jobs: dict[str, tuple[float, Callable[[], Coroutine[Any, Any, None]]]] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False

    def add_job(
        self,
        job_id: str,
        interval_seconds: float,
        callback: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a recurring job. If already started, spawns the task immediately."""
        self._jobs[job_id] = (interval_seconds, callback)
        if self._running:
            self._spawn(job_id, interval_seconds, callback)

    def remove_job(self, job_id: str) -> None:
        """Cancel and remove a job."""
        self._jobs.pop(job_id, None)
        task = self._tasks.pop(job_id, None)
        if task:
            task.cancel()

    async def start(self) -> None:
        """Spawn all registered jobs. Must be called inside a running event loop."""
        self._running = True
        for job_id, (interval, callback) in self._jobs.items():
            if job_id not in self._tasks:
                self._spawn(job_id, interval, callback)

    async def stop(self) -> None:
        """Cancel all running job tasks."""
        self._running = False
        for task in list(self._tasks.values()):
            task.cancel()
        self._tasks.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _spawn(
        self,
        job_id: str,
        interval_seconds: float,
        callback: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        task = asyncio.create_task(self._loop(job_id, interval_seconds, callback))
        self._tasks[job_id] = task

    async def _loop(
        self,
        job_id: str,
        interval_seconds: float,
        callback: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                await callback()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # keep looping; callers handle their own errors
