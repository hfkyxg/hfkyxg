"""Async pub/sub event bus for inter-agent messaging."""
from __future__ import annotations

import asyncio


class EventBus:
    """Simple asyncio-based pub/sub bus. Topics are strings; payloads are dicts."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[dict]]] = {}

    async def publish(self, topic: str, payload: dict) -> None:
        """Publish a payload to all subscribers of *topic*."""
        for queue in list(self._subscribers.get(topic, [])):
            await queue.put(payload)

    async def subscribe(self, topic: str) -> asyncio.Queue[dict]:
        """Return a new queue that will receive every message published to *topic*."""
        queue: asyncio.Queue[dict] = asyncio.Queue()
        self._subscribers.setdefault(topic, []).append(queue)
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue[dict]) -> None:
        """Remove *queue* from the subscriber list for *topic*."""
        try:
            self._subscribers.get(topic, []).remove(queue)
        except ValueError:
            pass
