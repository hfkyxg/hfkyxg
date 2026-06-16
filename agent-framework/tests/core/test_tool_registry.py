import pytest

from agent_framework.core.tool import ToolRegistry
from agent_framework.tools.files import ReadFileTool


def test_register_and_get():
    r = ToolRegistry()
    t = ReadFileTool()
    r.register(t)
    assert r.get("read_file") is t


def test_specs_shape():
    r = ToolRegistry()
    r.register(ReadFileTool())
    specs = r.specs()
    assert len(specs) == 1
    assert specs[0]["type"] == "function"
    assert specs[0]["function"]["name"] == "read_file"


def test_filtered():
    from agent_framework.tools.shell import BashTool

    r = ToolRegistry()
    r.register(ReadFileTool())
    r.register(BashTool())
    filtered = r.filtered(allowed_names={"read_file"})
    assert filtered.get("read_file")
    with pytest.raises(KeyError):
        filtered.get("bash")
