"""Tests for GrepTool and GlobTool."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_framework.core.permissions import always_allow
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolContext
from agent_framework.tools.search import GlobTool, GrepTool


def ctx(workdir: Path) -> ToolContext:
    return ToolContext(workdir=workdir, session=Session(), permission_gate=always_allow())


class TestGrepTool:
    @pytest.mark.asyncio
    async def test_finds_pattern_in_file(self, tmp_path):
        (tmp_path / "a.txt").write_text("hello world\nfoo bar\n")
        result = await GrepTool().run(
            {"pattern": "hello", "path": str(tmp_path)},
            context=ctx(tmp_path),
        )
        assert "hello" in result
        assert "a.txt" in result

    @pytest.mark.asyncio
    async def test_no_matches_returns_marker(self, tmp_path):
        (tmp_path / "a.txt").write_text("nothing here")
        result = await GrepTool().run(
            {"pattern": "xyzzynonexistent", "path": str(tmp_path)},
            context=ctx(tmp_path),
        )
        assert "no matches" in result.lower()

    @pytest.mark.asyncio
    async def test_glob_filter_restricts_to_extension(self, tmp_path):
        (tmp_path / "a.py").write_text("TARGET_PY")
        (tmp_path / "b.txt").write_text("TARGET_TXT")
        result = await GrepTool().run(
            {"pattern": "TARGET", "path": str(tmp_path), "glob": "*.py"},
            context=ctx(tmp_path),
        )
        assert "a.py" in result
        assert "b.txt" not in result

    @pytest.mark.asyncio
    async def test_case_insensitive_flag(self, tmp_path):
        (tmp_path / "c.txt").write_text("Hello World")
        result = await GrepTool().run(
            {"pattern": "hello", "path": str(tmp_path), "case_insensitive": True},
            context=ctx(tmp_path),
        )
        assert "Hello" in result

    @pytest.mark.asyncio
    async def test_relative_path_resolved_from_workdir(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "f.txt").write_text("match_me")
        result = await GrepTool().run(
            {"pattern": "match_me", "path": "sub"},
            context=ctx(tmp_path),
        )
        assert "match_me" in result

    @pytest.mark.asyncio
    async def test_includes_line_numbers_in_output(self, tmp_path):
        f = tmp_path / "nums.txt"
        f.write_text("line1\ntarget\nline3\n")
        result = await GrepTool().run(
            {"pattern": "target", "path": str(tmp_path)},
            context=ctx(tmp_path),
        )
        assert "2" in result  # line number of "target"


class TestGlobTool:
    @pytest.mark.asyncio
    async def test_finds_files_by_extension(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")
        result = await GlobTool().run(
            {"pattern": "*.py", "path": str(tmp_path)},
            context=ctx(tmp_path),
        )
        assert "a.py" in result
        assert "b.py" in result
        assert "c.txt" not in result

    @pytest.mark.asyncio
    async def test_recursive_glob(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("")
        result = await GlobTool().run(
            {"pattern": "**/*.py", "path": str(tmp_path)},
            context=ctx(tmp_path),
        )
        assert "deep.py" in result

    @pytest.mark.asyncio
    async def test_no_matches_returns_marker(self, tmp_path):
        result = await GlobTool().run(
            {"pattern": "*.nonexistent", "path": str(tmp_path)},
            context=ctx(tmp_path),
        )
        assert "no matches" in result.lower()

    @pytest.mark.asyncio
    async def test_relative_path_resolved_from_workdir(self, tmp_path):
        (tmp_path / "target.py").write_text("")
        result = await GlobTool().run(
            {"pattern": "*.py"},  # no path → uses workdir
            context=ctx(tmp_path),
        )
        assert "target.py" in result

    @pytest.mark.asyncio
    async def test_output_is_relative_paths(self, tmp_path):
        (tmp_path / "file.py").write_text("")
        result = await GlobTool().run(
            {"pattern": "*.py", "path": str(tmp_path)},
            context=ctx(tmp_path),
        )
        # Should be "file.py" not the full absolute path
        assert str(tmp_path) not in result
