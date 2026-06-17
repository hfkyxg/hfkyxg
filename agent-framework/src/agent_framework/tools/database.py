"""Database query tool — SQLite built-in + PostgreSQL/MySQL via URL."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from agent_framework.core.errors import ToolError
from agent_framework.core.tool import ToolContext


class DatabaseTool:
    name = "database"
    description = (
        "Execute SQL queries against a database. "
        "Supports SQLite (local .db file path) and PostgreSQL/MySQL (connection URL). "
        "SELECT queries return rows as formatted table; "
        "INSERT/UPDATE/DELETE return affected row count."
    )
    requires_permission = True
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "SQL query to execute",
            },
            "database": {
                "type": "string",
                "description": (
                    "Database target: a .db file path for SQLite, "
                    "a postgresql://... URL for Postgres, "
                    "or ':memory:' for an in-memory SQLite database."
                ),
                "default": ":memory:",
            },
            "params": {
                "type": "array",
                "description": "Query parameters for parameterized queries (? placeholders)",
                "items": {},
            },
        },
        "required": ["query"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        query: str = arguments["query"].strip()
        database: str = arguments.get("database", ":memory:")
        params: list = arguments.get("params") or []

        # Safety: block dangerous DDL/DCL unless the user explicitly calls them
        upper_q = query.upper().lstrip()
        if any(
            upper_q.startswith(kw)
            for kw in ("DROP DATABASE", "DROP TABLE", "TRUNCATE", "ALTER TABLE")
        ):
            raise ToolError(
                self.name,
                f"Destructive DDL blocked for safety: {query[:60]}",
            )

        if database.startswith("postgresql://") or database.startswith("postgres://"):
            return await self._run_postgres(query, database, params)

        return self._run_sqlite(query, database, params)

    # ------------------------------------------------------------------
    # SQLite
    # ------------------------------------------------------------------

    def _run_sqlite(self, query: str, database: str, params: list) -> str:
        try:
            if database != ":memory:":
                db_path = Path(database).expanduser()
                db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(database))
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise ToolError(self.name, f"Cannot connect to SQLite {database!r}: {exc}") from exc

        try:
            cur = conn.execute(query, params)
            conn.commit()
            upper_q = query.upper().lstrip()
            if upper_q.startswith("SELECT") or upper_q.startswith("PRAGMA"):
                rows = cur.fetchall()
                return self._format_rows(rows)
            return f"{cur.rowcount} row(s) affected"
        except sqlite3.Error as exc:
            raise ToolError(self.name, f"SQLite error: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # PostgreSQL (asyncpg — optional dependency)
    # ------------------------------------------------------------------

    async def _run_postgres(self, query: str, url: str, params: list) -> str:
        try:
            import asyncpg  # type: ignore[import]
        except ImportError as exc:
            raise ToolError(
                self.name,
                "asyncpg is not installed. Install with: pip install asyncpg",
            ) from exc
        try:
            conn = await asyncpg.connect(url)
        except Exception as exc:
            raise ToolError(self.name, f"Postgres connection error: {exc}") from exc
        try:
            upper_q = query.upper().lstrip()
            if upper_q.startswith("SELECT"):
                rows = await conn.fetch(query, *params)
                return self._format_asyncpg_rows(rows)
            result = await conn.execute(query, *params)
            return str(result)
        except Exception as exc:
            raise ToolError(self.name, f"Postgres query error: {exc}") from exc
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def _format_rows(self, rows: list) -> str:
        if not rows:
            return "(no rows returned)"
        keys = list(rows[0].keys())
        col_widths = [max(len(k), max((len(str(r[k])) for r in rows), default=0)) for k in keys]
        sep = "  ".join("-" * w for w in col_widths)
        header = "  ".join(k.ljust(col_widths[i]) for i, k in enumerate(keys))
        lines = [header, sep]
        for row in rows[:200]:  # cap at 200 rows
            lines.append("  ".join(str(row[k]).ljust(col_widths[i]) for i, k in enumerate(keys)))
        if len(rows) > 200:
            lines.append(f"... ({len(rows) - 200} more rows truncated)")
        return "\n".join(lines)

    def _format_asyncpg_rows(self, rows: list) -> str:
        if not rows:
            return "(no rows returned)"
        keys = list(rows[0].keys())
        col_widths = [
            max(len(k), max((len(str(r[k])) for r in rows), default=0)) for k in keys
        ]
        sep = "  ".join("-" * w for w in col_widths)
        header = "  ".join(k.ljust(col_widths[i]) for i, k in enumerate(keys))
        lines = [header, sep]
        for row in rows[:200]:
            lines.append("  ".join(str(row[k]).ljust(col_widths[i]) for i, k in enumerate(keys)))
        return "\n".join(lines)
