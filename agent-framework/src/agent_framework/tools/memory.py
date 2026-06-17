"""Persistent memory tool — SQLite-backed key-value store that survives sessions."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from agent_framework.core.tool import ToolContext

_LOCK = threading.Lock()


def _db_path() -> Path:
    try:
        from agent_framework.config.settings import settings

        if settings.memory_db_path:
            return Path(settings.memory_db_path)
    except Exception:
        pass
    return Path.home() / ".apathy" / "memory.db"


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            namespace TEXT NOT NULL DEFAULT 'default',
            key       TEXT NOT NULL,
            value     TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (namespace, key)
        )
    """)
    conn.commit()
    return conn


class MemoryTool:
    name = "memory"
    description = (
        "Persistent key-value memory that survives across sessions. "
        "Actions: set (store), get (retrieve), list (show all keys), "
        "delete (remove), search (find by value substring)."
    )
    requires_permission = False
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["set", "get", "list", "delete", "search"],
                "description": "Operation to perform",
            },
            "key": {
                "type": "string",
                "description": "Key name (required for set/get/delete)",
            },
            "value": {
                "type": "string",
                "description": "Value to store (required for set)",
            },
            "query": {
                "type": "string",
                "description": "Text to search for in values (required for search)",
            },
            "namespace": {
                "type": "string",
                "default": "default",
                "description": "Namespace to scope memory (e.g. project name)",
            },
        },
        "required": ["action"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        action = arguments["action"]
        namespace = arguments.get("namespace", "default")
        key = arguments.get("key", "")
        value = arguments.get("value", "")
        query = arguments.get("query", "")

        with _LOCK:
            conn = _conn()
            try:
                if action == "set":
                    return self._set(conn, namespace, key, value)
                elif action == "get":
                    return self._get(conn, namespace, key)
                elif action == "list":
                    return self._list(conn, namespace)
                elif action == "delete":
                    return self._delete(conn, namespace, key)
                elif action == "search":
                    return self._search(conn, namespace, query)
                else:
                    return f"Unknown action: {action!r}"
            finally:
                conn.close()

    def _set(self, conn: sqlite3.Connection, ns: str, key: str, value: str) -> str:
        if not key:
            return "Error: key is required for set"
        conn.execute(
            """
            INSERT INTO memory (namespace, key, value, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT (namespace, key) DO UPDATE
              SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (ns, key, value),
        )
        conn.commit()
        preview = value[:80] + ("..." if len(value) > 80 else "")
        return f"Stored [{ns}/{key}] = {preview!r}"

    def _get(self, conn: sqlite3.Connection, ns: str, key: str) -> str:
        if not key:
            return "Error: key is required for get"
        row = conn.execute(
            "SELECT value, updated_at FROM memory WHERE namespace=? AND key=?", (ns, key)
        ).fetchone()
        if row is None:
            return f"Key [{ns}/{key}] not found"
        return f"[{ns}/{key}] (updated {row[1]})\n{row[0]}"

    def _list(self, conn: sqlite3.Connection, ns: str) -> str:
        rows = conn.execute(
            "SELECT key, length(value), updated_at FROM memory WHERE namespace=? ORDER BY key",
            (ns,),
        ).fetchall()
        if not rows:
            return f"No entries in namespace [{ns}]"
        lines = [f"Memory namespace [{ns}] — {len(rows)} entries:"]
        for key, vlen, updated in rows:
            lines.append(f"  {key}  ({vlen} chars, updated {updated})")
        return "\n".join(lines)

    def _delete(self, conn: sqlite3.Connection, ns: str, key: str) -> str:
        if not key:
            return "Error: key is required for delete"
        cur = conn.execute(
            "DELETE FROM memory WHERE namespace=? AND key=?", (ns, key)
        )
        conn.commit()
        if cur.rowcount == 0:
            return f"Key [{ns}/{key}] not found"
        return f"Deleted [{ns}/{key}]"

    def _search(self, conn: sqlite3.Connection, ns: str, query: str) -> str:
        if not query:
            return "Error: query is required for search"
        sql = (
            "SELECT key, value, updated_at FROM memory "
            "WHERE namespace=? AND value LIKE ? ORDER BY key"
        )
        rows = conn.execute(sql, (ns, f"%{query}%")).fetchall()
        if not rows:
            return f"No entries matching {query!r} in namespace [{ns}]"
        lines = [f"Found {len(rows)} entries matching {query!r}:"]
        for key, value, updated in rows:
            preview = value[:100] + ("..." if len(value) > 100 else "")
            lines.append(f"  [{key}] {preview!r}")
        return "\n".join(lines)
