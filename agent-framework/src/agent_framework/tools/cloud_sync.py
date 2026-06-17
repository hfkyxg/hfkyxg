"""Cloud sync tool — upload/move files to PRIVATE cloud storage via rclone.

rclone (https://rclone.org) supports 70+ providers: Google Drive, OneDrive,
Dropbox, Box, MEGA, pCloud, Amazon S3, Backblaze B2, and more. The user
authenticates their OWN account once with ``rclone config``; everything
uploaded therefore lands in that private account and is never made public.

This tool shells out to the ``rclone`` binary, so the heavy lifting (OAuth,
chunked uploads, retries) is handled by a battle-tested external program
rather than reimplemented here.
"""
from __future__ import annotations

import asyncio
import shutil
from typing import Any

from agent_framework.core.errors import ToolError
from agent_framework.core.safety import is_protected_path
from agent_framework.core.tool import ToolContext

_INSTALL_HELP = (
    "rclone is not installed. It is the engine apathy uses to talk to cloud "
    "drives privately.\n"
    "  Windows : winget install Rclone.Rclone   (or download from rclone.org/downloads)\n"
    "  macOS   : brew install rclone\n"
    "  Linux   : curl https://rclone.org/install.sh | sudo bash\n"
    "Then connect your private account once:  rclone config\n"
    "  (choose 'n' for new remote, name it e.g. 'gdrive', pick Google Drive/OneDrive/etc.)"
)


class CloudSyncTool:
    name = "cloud_sync"
    description = (
        "Upload, copy, move, sync or list files on PRIVATE cloud storage using rclone "
        "(Google Drive, OneDrive, Dropbox, MEGA, S3 and 70+ providers). "
        "Files go to YOUR authenticated account and stay private — nothing is shared. "
        "Actions: 'copy' (keep local), 'move' (delete local after upload), "
        "'sync' (mirror, deletes extra files at dest), 'list' (browse a remote), "
        "'remotes' (show configured accounts). "
        "A remote path looks like 'gdrive:Backup/Videos'."
    )
    requires_permission = True
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["copy", "move", "sync", "list", "remotes"],
                "default": "copy",
                "description": "What to do (copy keeps local; move deletes local after upload)",
            },
            "source": {
                "type": "string",
                "description": "Local path or 'remote:path' to read from",
            },
            "dest": {
                "type": "string",
                "description": "'remote:path' (e.g. gdrive:Backup) or local path to write to",
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": "Preview the transfer without changing anything",
            },
            "extra_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Extra rclone flags (advanced)",
            },
        },
        "required": ["action"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        action = arguments.get("action", "copy")
        source = arguments.get("source", "")
        dest = arguments.get("dest", "")
        dry_run = bool(arguments.get("dry_run", False))
        extra_flags = arguments.get("extra_flags") or []

        rclone = shutil.which("rclone")
        if rclone is None:
            raise ToolError(self.name, _INSTALL_HELP)

        if action == "remotes":
            out = await self._run_rclone([rclone, "listremotes"])
            if not out.strip():
                return (
                    "No cloud accounts configured yet.\n"
                    "Connect one privately with:  rclone config\n"
                    "Then this tool can upload to it."
                )
            return "Configured private remotes:\n" + out

        if action == "list":
            target = source or dest
            if not target:
                raise ToolError(self.name, "list requires a 'source' remote, e.g. gdrive:")
            return await self._run_rclone([rclone, "lsf", "--max-depth", "2", target])

        # copy / move / sync need both source and dest
        if not source or not dest:
            raise ToolError(self.name, f"action '{action}' requires both 'source' and 'dest'")

        # Discernment: never let a destructive op read from a protected local root.
        if action in ("move", "sync") and ":" not in source[:3] and is_protected_path(source):
            raise ToolError(
                self.name,
                f"Refusing to {action} from protected system path '{source}'.",
            )

        cmd = [rclone, action, source, dest, "--stats-one-line", "--stats", "1s"]
        if dry_run:
            cmd.append("--dry-run")
        cmd += list(extra_flags)

        out = await self._run_rclone(cmd, timeout=900)
        verb = {
            "copy": "Copied", "move": "Moved", "sync": "Synced",
        }.get(action, "Transferred")
        prefix = "[DRY RUN] " if dry_run else ""
        msg = f"{prefix}{verb} '{source}' → '{dest}' (private)."
        if out.strip():
            msg += "\n" + out.strip()
        return msg

    async def _run_rclone(self, cmd: list[str], timeout: int = 120) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError as exc:
            raise ToolError(self.name, f"rclone timed out after {timeout}s") from exc
        except OSError as exc:
            raise ToolError(self.name, f"Could not run rclone: {exc}") from exc

        text = stdout.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            raise ToolError(self.name, f"rclone failed (exit {proc.returncode}):\n{text[:800]}")
        return text
