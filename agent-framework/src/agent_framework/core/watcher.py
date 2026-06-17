"""File-system watcher using polling (no external dependencies)."""
from __future__ import annotations

import asyncio
import fnmatch
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class WatchEvent:
    type: str  # "created" | "modified" | "deleted"
    path: str
    timestamp: datetime = field(default_factory=datetime.now)


class FileWatcher:
    """Poll a directory tree for file-system changes every 2 seconds.

    Uses ``os.walk`` + mtime tracking; no extra dependencies required.
    """

    def __init__(
        self,
        path: str,
        pattern: str = "*",
        events: list[str] | None = None,
    ) -> None:
        self.path = os.path.expanduser(path)
        self.pattern = pattern
        self.wanted_events: set[str] = set(events or ["created", "modified"])
        self._stop = asyncio.Event()
        self._snapshot: dict[str, float] = {}

    async def watch(self) -> AsyncIterator[WatchEvent]:
        """Async generator that yields WatchEvent instances as changes are detected."""
        # Seed the initial snapshot so we don't report pre-existing files as 'created'.
        self._snapshot = self._current_snapshot()

        while not self._stop.is_set():
            await asyncio.sleep(2)
            if self._stop.is_set():
                break

            new_snapshot = self._current_snapshot()

            prev_paths = set(self._snapshot.keys())
            curr_paths = set(new_snapshot.keys())

            for p in curr_paths - prev_paths:
                if "created" in self.wanted_events:
                    yield WatchEvent(type="created", path=p)

            for p in prev_paths - curr_paths:
                if "deleted" in self.wanted_events:
                    yield WatchEvent(type="deleted", path=p)

            for p in prev_paths & curr_paths:
                if new_snapshot[p] != self._snapshot[p]:
                    if "modified" in self.wanted_events:
                        yield WatchEvent(type="modified", path=p)

            self._snapshot = new_snapshot

    async def stop(self) -> None:
        """Signal the watcher to stop on its next poll cycle."""
        self._stop.set()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _current_snapshot(self) -> dict[str, float]:
        """Walk the watched directory and return {abs_path: mtime}."""
        snapshot: dict[str, float] = {}
        if not os.path.isdir(self.path):
            return snapshot
        for dirpath, _dirs, files in os.walk(self.path):
            for fname in files:
                if fnmatch.fnmatch(fname, self.pattern):
                    full = os.path.join(dirpath, fname)
                    try:
                        snapshot[full] = os.path.getmtime(full)
                    except OSError:
                        pass
        return snapshot
