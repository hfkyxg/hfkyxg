from pathlib import Path

import pytest

from agent_framework.core.errors import ToolError
from agent_framework.core.permissions import always_allow
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolContext
from agent_framework.tools.files import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool


def fake_context(workdir):
    return ToolContext(
        workdir=Path(workdir),
        session=Session(),
        permission_gate=always_allow(),
    )


@pytest.mark.asyncio
async def test_read_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello\nworld")
    result = await ReadFileTool().run({"path": str(f)}, context=fake_context(tmp_path))
    assert "hello" in result
    assert "world" in result


@pytest.mark.asyncio
async def test_read_file_not_found(tmp_path):
    with pytest.raises(ToolError):
        await ReadFileTool().run(
            {"path": str(tmp_path / "missing.txt")}, context=fake_context(tmp_path)
        )


@pytest.mark.asyncio
async def test_write_and_edit(tmp_path):
    ctx = fake_context(tmp_path)
    await WriteFileTool().run({"path": "out.txt", "content": "aaa bbb"}, context=ctx)
    assert (tmp_path / "out.txt").read_text() == "aaa bbb"
    await EditFileTool().run(
        {"path": "out.txt", "old_string": "aaa", "new_string": "xxx"}, context=ctx
    )
    assert (tmp_path / "out.txt").read_text() == "xxx bbb"


@pytest.mark.asyncio
async def test_list_dir(tmp_path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.txt").write_text("")
    result = await ListDirTool().run({"path": str(tmp_path)}, context=fake_context(tmp_path))
    assert "a.py" in result
    assert "b.txt" in result
