"""ActionLog — records every tool call with revert support.

Every destructive tool call (write_file, edit_file, bash, organize_files, etc.)
is recorded with enough context to undo it. The log is stored in memory and
optionally persisted to ~/.apathy/action_log.jsonl for cross-session history.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ActionEntry:
    id: str
    tool_name: str
    arguments: dict[str, Any]
    result: str
    timestamp: datetime
    job_id: str = ""
    session_id: str = ""
    revertible: bool = False
    reverted: bool = False
    revert_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
            "timestamp": self.timestamp.isoformat(),
            "job_id": self.job_id,
            "session_id": self.session_id,
            "revertible": self.revertible,
            "reverted": self.reverted,
            "revert_data": self.revert_data,
        }


class ActionLog:
    """In-memory action log with optional JSONL persistence and revert support."""

    _REVERTIBLE = frozenset({"write_file", "edit_file", "organize_files"})
    _LOG_PATH = Path.home() / ".apathy" / "action_log.jsonl"

    def __init__(self, persist: bool = True) -> None:
        self._entries: list[ActionEntry] = []
        self._persist = persist
        if persist:
            self._LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        entry_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: str,
        job_id: str = "",
        session_id: str = "",
    ) -> ActionEntry:
        revertible = tool_name in self._REVERTIBLE
        revert_data: dict[str, Any] = {}

        if revertible and tool_name in ("write_file", "edit_file"):
            path = arguments.get("path", "")
            if path:
                p = Path(path)
                if p.exists():
                    revert_data["existed"] = True
                    revert_data["original_content"] = p.read_text(errors="replace")
                else:
                    revert_data["existed"] = False

        entry = ActionEntry(
            id=entry_id,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            timestamp=datetime.now(),
            job_id=job_id,
            session_id=session_id,
            revertible=revertible,
            revert_data=revert_data,
        )
        self._entries.append(entry)

        if self._persist:
            try:
                with open(self._LOG_PATH, "a") as f:
                    f.write(json.dumps(entry.to_dict()) + "\n")
            except OSError:
                pass

        return entry

    def revert(self, entry_id: str) -> tuple[bool, str]:
        entry = self.load_entry(entry_id)
        if entry is None:
            return False, f"Entry {entry_id!r} not found"
        if entry.reverted:
            return False, f"Entry {entry_id!r} already reverted"
        if not entry.revertible:
            return False, f"Tool {entry.tool_name!r} does not support revert"

        try:
            if entry.tool_name in ("write_file", "edit_file"):
                path = Path(entry.arguments.get("path", ""))
                if entry.revert_data.get("existed"):
                    path.write_text(entry.revert_data["original_content"])
                    msg = f"Restored original content of {path}"
                else:
                    path.unlink(missing_ok=True)
                    msg = f"Deleted {path} (was not present before action)"
            elif entry.tool_name == "organize_files":
                manifest_path = Path(entry.arguments.get("path", "")) / "manifest.json"
                if not manifest_path.exists():
                    return False, "No manifest.json found — cannot revert"
                with open(manifest_path) as f:
                    manifest = json.load(f)
                root = Path(manifest["root"])
                count = 0
                for move in manifest.get("moves", []):
                    src = root / move["dest"]
                    dst = root / move["src"]
                    if src.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(src), str(dst))
                        count += 1
                manifest_path.unlink(missing_ok=True)
                msg = f"Reverted {count} file moves from organize_files"
            else:
                return False, f"No revert handler for {entry.tool_name!r}"

            entry.reverted = True
            return True, msg
        except Exception as exc:
            return False, f"Revert failed: {exc}"

    def recent(self, n: int = 20) -> list[ActionEntry]:
        # Merge in-memory with persisted file for cross-session reads
        all_entries = self._load_persisted() if self._persist else []
        # Merge: in-memory takes priority (has revert state)
        mem_ids = {e.id for e in self._entries}
        merged = [e for e in all_entries if e.id not in mem_ids] + self._entries
        merged.sort(key=lambda e: e.timestamp)
        return list(reversed(merged[-n:]))

    def _load_persisted(self) -> list[ActionEntry]:
        if not self._LOG_PATH.exists():
            return []
        entries = []
        try:
            with open(self._LOG_PATH) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        entry = ActionEntry(
                            id=d["id"],
                            tool_name=d["tool_name"],
                            arguments=d.get("arguments", {}),
                            result=d.get("result", ""),
                            timestamp=datetime.fromisoformat(d["timestamp"]),
                            job_id=d.get("job_id", ""),
                            session_id=d.get("session_id", ""),
                            revertible=d.get("revertible", False),
                            reverted=d.get("reverted", False),
                            revert_data=d.get("revert_data", {}),
                        )
                        entries.append(entry)
                    except Exception:
                        continue
        except OSError:
            pass
        return entries

    def revertible_entries(self) -> list[ActionEntry]:
        all_e = self._load_persisted() if self._persist else []
        merged = {e.id: e for e in all_e}
        merged.update({e.id: e for e in self._entries})
        return [e for e in merged.values() if e.revertible and not e.reverted]

    def clear(self) -> None:
        self._entries.clear()

    def load_entry(self, entry_id: str) -> ActionEntry | None:
        for e in self._entries:
            if e.id == entry_id:
                return e
        for e in self._load_persisted():
            if e.id == entry_id:
                return e
        return None


# Global singleton used by the CLI
_global_log = ActionLog(persist=True)


def get_log() -> ActionLog:
    return _global_log
