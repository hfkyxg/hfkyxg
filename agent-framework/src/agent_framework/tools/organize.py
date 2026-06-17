"""File organizer tool — classifies and moves files into typed subdirectories."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_framework.core.errors import ToolError
from agent_framework.core.tool import ToolContext

CATEGORIES: dict[str, list[str]] = {
    "code": [".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".cpp",
             ".c", ".h", ".cs", ".rb", ".php", ".swift", ".kt", ".scala", ".r", ".lua"],
    "web": [".html", ".htm", ".css", ".scss", ".sass", ".vue", ".svelte"],
    "data": [".csv", ".json", ".jsonl", ".xml", ".yaml", ".yml", ".toml", ".sql",
             ".parquet", ".xlsx", ".xls", ".ods"],
    "docs": [".md", ".rst", ".txt", ".pdf", ".docx", ".doc", ".odt", ".rtf",
             ".tex", ".org"],
    "images": [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp",
               ".tiff", ".psd", ".ai"],
    "videos": [".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv"],
    "audio": [".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"],
    "archives": [".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".whl",
                 ".egg"],
    "scripts": [".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd"],
    "configs": [".env", ".ini", ".cfg", ".conf", ".properties"],
    "logs": [".log", ".out", ".err"],
}

ALWAYS_SKIP = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", "dist", "build", ".eggs",
})


def _categorize(path: Path) -> str:
    ext = path.suffix.lower()
    name = path.name
    # Well-known extensionless
    if name in ("Makefile", "Dockerfile", "Jenkinsfile", ".gitignore", ".dockerignore"):
        return "configs"
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return "misc"


class FileOrganizeTool:
    name = "organize_files"
    description = (
        "Organize files in a directory by moving them into typed subdirectories "
        "(code/, docs/, data/, images/, archives/, etc.). "
        "Skips hidden files and common build/cache directories. "
        "Returns a summary of what was moved and generates a manifest.json."
    )
    requires_permission = True
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory to organize",
            },
            "mode": {
                "type": "string",
                "enum": ["by_type", "by_date", "by_size"],
                "default": "by_type",
                "description": (
                    "by_type: group by file category (code/docs/images/...); "
                    "by_date: group by year-month (YYYY-MM/); "
                    "by_size: group by size (large/>1MB, medium/100KB-1MB, small/<100KB)"
                ),
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": "If true, show what would happen without moving files",
            },
            "write_manifest": {
                "type": "boolean",
                "default": True,
                "description": "Write a manifest.json with the full move log",
            },
        },
        "required": ["path"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        root = Path(arguments["path"]).expanduser().resolve()
        mode = arguments.get("mode", "by_type")
        dry_run = bool(arguments.get("dry_run", False))
        write_manifest = bool(arguments.get("write_manifest", True))

        if not root.exists():
            raise ToolError(self.name, f"Path does not exist: {root}")
        if not root.is_dir():
            raise ToolError(self.name, f"Not a directory: {root}")

        files = [
            f for f in root.rglob("*")
            if f.is_file()
            and not any(part in ALWAYS_SKIP for part in f.parts)
            and not f.name.startswith(".")
            and f.name != "manifest.json"
        ]

        if not files:
            return f"No files found in {root} (skipped hidden files and build dirs)."

        moves: list[dict[str, str]] = []
        skipped: list[str] = []
        errors: list[str] = []

        for src in files:
            # Don't move files already in a category subdir
            try:
                rel = src.relative_to(root)
            except ValueError:
                continue
            parts = rel.parts
            if len(parts) > 1 and parts[0] in {*CATEGORIES.keys(), "misc"}:
                skipped.append(str(rel))
                continue

            if mode == "by_type":
                dest_dir = root / _categorize(src)
            elif mode == "by_date":
                mtime = datetime.fromtimestamp(src.stat().st_mtime)
                dest_dir = root / mtime.strftime("%Y-%m")
            else:  # by_size
                size = src.stat().st_size
                if size > 1_000_000:
                    dest_dir = root / "large"
                elif size > 100_000:
                    dest_dir = root / "medium"
                else:
                    dest_dir = root / "small"

            dest = dest_dir / src.name
            # Handle name collisions
            if dest.exists() and dest != src:
                stem, suffix = src.stem, src.suffix
                counter = 1
                while dest.exists():
                    dest = dest_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            moves.append({
                "src": str(src.relative_to(root)),
                "dest": str(dest.relative_to(root)),
                "category": _categorize(src),
                "size": src.stat().st_size,
            })

            if not dry_run:
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dest))
                except Exception as exc:
                    errors.append(f"{src.name}: {exc}")

        # Write manifest
        if write_manifest and not dry_run and moves:
            manifest = {
                "organized_at": datetime.now().isoformat(),
                "mode": mode,
                "root": str(root),
                "total_moved": len(moves),
                "skipped": len(skipped),
                "errors": errors,
                "moves": moves,
            }
            (root / "manifest.json").write_text(json.dumps(manifest, indent=2))

        # Build summary
        by_cat: dict[str, int] = {}
        total_bytes = 0
        for m in moves:
            by_cat[m["category"]] = by_cat.get(m["category"], 0) + 1
            total_bytes += m["size"]

        prefix = "[DRY RUN] " if dry_run else ""
        lines = [
            f"{prefix}Organized {len(moves)} files in {root} (mode={mode})",
            f"Total size: {total_bytes / 1024:.1f} KB",
            "",
            "By category:",
        ]
        for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
            lines.append(f"  {cat:12s} {count:3d} file(s)")

        if skipped:
            lines.append(f"\nSkipped {len(skipped)} already-organized files.")
        if errors:
            lines.append(f"\nErrors ({len(errors)}):")
            for e in errors[:5]:
                lines.append(f"  {e}")
        if not dry_run and write_manifest and moves:
            lines.append(f"\nManifest written to {root}/manifest.json")

        return "\n".join(lines)
