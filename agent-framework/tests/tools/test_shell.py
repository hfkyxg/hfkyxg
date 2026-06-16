from pathlib import Path

import pytest

from agent_framework.core.errors import ToolError
from agent_framework.core.permissions import always_allow
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolContext
from agent_framework.tools.shell import BashTool


def fake_context(workdir):
    return ToolContext(
        workdir=Path(workdir),
        session=Session(),
        permission_gate=always_allow(),
    )


@pytest.mark.asyncio
async def test_echo(tmp_path):
    ctx = fake_context(tmp_path)
    result = await BashTool().run({"command": "echo hello-from-agent"}, context=ctx)
    assert "hello-from-agent" in result


@pytest.mark.asyncio
async def test_exit_code_nonzero(tmp_path):
    result = await BashTool().run({"command": "exit 1"}, context=fake_context(tmp_path))
    assert "exit code" in result.lower()


@pytest.mark.asyncio
async def test_timeout(tmp_path):
    with pytest.raises(ToolError, match="timed out"):
        await BashTool().run({"command": "sleep 10", "timeout": 1}, context=fake_context(tmp_path))
