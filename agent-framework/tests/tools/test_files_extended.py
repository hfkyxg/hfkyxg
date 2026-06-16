"""Extended file tool tests: offset/limit on reads, ambiguous edits, dir creation."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_framework.core.errors import ToolError
from agent_framework.core.permissions import always_allow
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolContext
from agent_framework.tools.files import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool


def ctx(workdir: Path) -> ToolContext:
    return ToolContext(workdir=workdir, session=Session(), permission_gate=always_allow())


class TestReadFileTool:
    @pytest.mark.asyncio
    async def test_offset_skips_lines(self, tmp_path):
        f = tmp_path / "lines.txt"
        f.write_text("line1\nline2\nline3\nline4\n")
        result = await ReadFileTool().run({"path": str(f), "offset": 3}, context=ctx(tmp_path))
        assert "line3" in result
        assert "line1" not in result

    @pytest.mark.asyncio
    async def test_limit_restricts_output(self, tmp_path):
        f = tmp_path / "lines.txt"
        f.write_text("\n".join(f"line{i}" for i in range(100)))
        result = await ReadFileTool().run({"path": str(f), "limit": 2, "offset": 1}, context=ctx(tmp_path))
        assert "line0" in result
        assert "line2" not in result  # only 2 lines from offset 1

    @pytest.mark.asyncio
    async def test_relative_path_resolved_from_workdir(self, tmp_path):
        (tmp_path / "sub").mkdir()
        f = tmp_path / "sub" / "data.txt"
        f.write_text("hello")
        result = await ReadFileTool().run({"path": "sub/data.txt"}, context=ctx(tmp_path))
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_not_a_file_raises_tool_error(self, tmp_path):
        with pytest.raises(ToolError):
            await ReadFileTool().run({"path": str(tmp_path)}, context=ctx(tmp_path))

    @pytest.mark.asyncio
    async def test_empty_file_returns_empty_marker(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        result = await ReadFileTool().run({"path": str(f)}, context=ctx(tmp_path))
        assert "empty" in result.lower()

    @pytest.mark.asyncio
    async def test_line_numbers_in_output(self, tmp_path):
        f = tmp_path / "n.txt"
        f.write_text("a\nb\nc")
        result = await ReadFileTool().run({"path": str(f)}, context=ctx(tmp_path))
        assert "1\t" in result or "1" in result  # numbered format


class TestWriteFileTool:
    @pytest.mark.asyncio
    async def test_creates_parent_directories(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "file.txt"
        await WriteFileTool().run({"path": str(path), "content": "data"}, context=ctx(tmp_path))
        assert path.read_text() == "data"

    @pytest.mark.asyncio
    async def test_overwrites_existing_file(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("old")
        await WriteFileTool().run({"path": str(f), "content": "new"}, context=ctx(tmp_path))
        assert f.read_text() == "new"

    @pytest.mark.asyncio
    async def test_reports_char_count(self, tmp_path):
        result = await WriteFileTool().run(
            {"path": str(tmp_path / "x.txt"), "content": "hello"},
            context=ctx(tmp_path),
        )
        assert "5" in result  # 5 chars


class TestEditFileTool:
    @pytest.mark.asyncio
    async def test_ambiguous_match_raises_tool_error(self, tmp_path):
        f = tmp_path / "dup.txt"
        f.write_text("abc abc abc")
        with pytest.raises(ToolError, match="found 3 times"):
            await EditFileTool().run(
                {"path": str(f), "old_string": "abc", "new_string": "xyz"},
                context=ctx(tmp_path),
            )

    @pytest.mark.asyncio
    async def test_old_string_not_found_raises(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("hello world")
        with pytest.raises(ToolError, match="not found"):
            await EditFileTool().run(
                {"path": str(f), "old_string": "nonexistent", "new_string": "x"},
                context=ctx(tmp_path),
            )

    @pytest.mark.asyncio
    async def test_multiline_replacement(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("def foo():\n    pass\n")
        await EditFileTool().run(
            {"path": str(f), "old_string": "    pass", "new_string": "    return 42"},
            context=ctx(tmp_path),
        )
        assert f.read_text() == "def foo():\n    return 42\n"

    @pytest.mark.asyncio
    async def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(ToolError):
            await EditFileTool().run(
                {"path": str(tmp_path / "missing.py"), "old_string": "x", "new_string": "y"},
                context=ctx(tmp_path),
            )


class TestListDirTool:
    @pytest.mark.asyncio
    async def test_dirs_have_slash_suffix(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        (tmp_path / "file.txt").write_text("")
        result = await ListDirTool().run({"path": str(tmp_path)}, context=ctx(tmp_path))
        assert "subdir/" in result
        assert "file.txt" in result

    @pytest.mark.asyncio
    async def test_not_a_directory_raises(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("")
        with pytest.raises(ToolError):
            await ListDirTool().run({"path": str(f)}, context=ctx(tmp_path))

    @pytest.mark.asyncio
    async def test_empty_directory_returns_marker(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        result = await ListDirTool().run({"path": str(d)}, context=ctx(tmp_path))
        assert "empty" in result.lower()
