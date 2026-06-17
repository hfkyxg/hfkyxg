"""Tests for CloudSyncTool that run fully offline (rclone never invoked)."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_framework.core.errors import ToolError
from agent_framework.core.permissions import always_allow
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolContext
from agent_framework.tools.cloud_sync import CloudSyncTool


def _ctx(workdir: Path | str = ".") -> ToolContext:
    return ToolContext(
        workdir=Path(workdir),
        session=Session(),
        permission_gate=always_allow(),
    )


def test_metadata():
    tool = CloudSyncTool()
    assert tool.name == "cloud_sync"
    assert tool.requires_permission is True


async def test_rclone_not_installed(monkeypatch):
    tool = CloudSyncTool()
    monkeypatch.setattr(
        "agent_framework.tools.cloud_sync.shutil.which", lambda _: None
    )
    with pytest.raises(ToolError) as exc_info:
        await tool.run({"action": "remotes"}, context=_ctx())
    msg = str(exc_info.value).lower()
    assert "rclone" in msg
    assert "install" in msg


async def test_copy_missing_source_and_dest(monkeypatch):
    tool = CloudSyncTool()
    monkeypatch.setattr(
        "agent_framework.tools.cloud_sync.shutil.which",
        lambda _: "/usr/bin/rclone",
    )
    with pytest.raises(ToolError) as exc_info:
        await tool.run({"action": "copy"}, context=_ctx())
    msg = str(exc_info.value).lower()
    assert "source" in msg
    assert "dest" in msg


async def test_move_from_protected_path(monkeypatch):
    tool = CloudSyncTool()
    monkeypatch.setattr(
        "agent_framework.tools.cloud_sync.shutil.which",
        lambda _: "/usr/bin/rclone",
    )
    with pytest.raises(ToolError) as exc_info:
        await tool.run(
            {"action": "move", "source": "/etc", "dest": "gdrive:x"},
            context=_ctx(),
        )
    msg = str(exc_info.value).lower()
    assert "protected" in msg
