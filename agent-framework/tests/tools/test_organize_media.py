"""Tests for FileOrganizeTool 'by_media' mode (one folder per media file)."""
from __future__ import annotations

from pathlib import Path

from agent_framework.core.permissions import always_allow
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolContext
from agent_framework.tools.organize import FileOrganizeTool


def _ctx(workdir: Path | str = ".") -> ToolContext:
    return ToolContext(
        workdir=Path(workdir),
        session=Session(),
        permission_gate=always_allow(),
    )


async def test_by_media_groups_siblings(tmp_path):
    tool = FileOrganizeTool()

    (tmp_path / "holiday.mp4").write_bytes(b"video")
    (tmp_path / "holiday.srt").write_bytes(b"subs")
    (tmp_path / "holiday.jpg").write_bytes(b"thumb")
    (tmp_path / "concert.mkv").write_bytes(b"vid2")
    (tmp_path / "random.txt").write_bytes(b"text")

    await tool.run(
        {"path": str(tmp_path), "mode": "by_media", "dry_run": False},
        context=_ctx(tmp_path),
    )

    # The media file and its same-stem siblings join one folder.
    assert (tmp_path / "holiday" / "holiday.mp4").exists()
    assert (tmp_path / "holiday" / "holiday.srt").exists()
    assert (tmp_path / "holiday" / "holiday.jpg").exists()

    # A second media file gets its own folder.
    assert (tmp_path / "concert" / "concert.mkv").exists()

    # A file with no media stem is left in place.
    assert (tmp_path / "random.txt").exists()


async def test_by_media_dry_run_moves_nothing(tmp_path):
    tool = FileOrganizeTool()

    video = tmp_path / "trip.mp4"
    video.write_bytes(b"video")

    await tool.run(
        {"path": str(tmp_path), "mode": "by_media", "dry_run": True},
        context=_ctx(tmp_path),
    )

    # Dry run must not move anything.
    assert video.exists()
    assert not (tmp_path / "trip" / "trip.mp4").exists()
