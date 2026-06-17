"""Tests for the autonomous project builder."""
from __future__ import annotations

import pytest

from agent_framework.core.content_generator import generate_content, make_project_plan
from agent_framework.core.messages import Message, ToolResult
from agent_framework.core.mock_provider import MockProvider


def specs_for(*names: str) -> list[dict]:
    return [
        {"type": "function", "function": {"name": n, "description": "", "parameters": {}}}
        for n in names
    ]


# ── make_project_plan tests ───────────────────────────────────────────────────

class TestProjectPlan:
    def test_project_plan_fastapi_has_all_files(self):
        plan = make_project_plan("fastapi", "/tmp/p", "todo")
        assert len(plan) >= 9
        paths = [s["path"] for s in plan]
        # All paths are absolute and under /tmp/p
        for path in paths:
            assert path.startswith("/tmp/p"), f"Path not under workspace: {path}"
        # All have task text
        for step in plan:
            assert step["task"], f"Empty task for {step['path']}"

    def test_project_plan_cli_has_correct_files(self):
        plan = make_project_plan("cli", "/tmp/cli_proj", "mycli")
        paths = [s["path"] for s in plan]
        basenames = [p.split("/")[-1] for p in paths]
        assert "main.py" in basenames
        # Has a test file
        assert any("test" in b for b in basenames)

    def test_project_plan_webapp_has_html_css_js(self):
        plan = make_project_plan("webapp", "/tmp/webapp_proj", "myapp")
        paths = [s["path"] for s in plan]
        exts = {p.rsplit(".", 1)[-1] for p in paths if "." in p.split("/")[-1]}
        assert "html" in exts
        assert "css" in exts
        assert "js" in exts

    def test_project_plan_unknown_type_defaults_to_fastapi(self):
        plan_unknown = make_project_plan("unknown", "/tmp/u", "app")
        plan_fastapi = make_project_plan("fastapi", "/tmp/u", "app")
        basenames_unknown = sorted(p["path"].split("/")[-1] for p in plan_unknown)
        basenames_fastapi = sorted(p["path"].split("/")[-1] for p in plan_fastapi)
        assert basenames_unknown == basenames_fastapi

    def test_project_plan_aliases(self):
        plan_api = make_project_plan("api", "/tmp/t", "app")
        plan_fastapi = make_project_plan("fastapi", "/tmp/t", "app")
        assert len(plan_api) == len(plan_fastapi)

        plan_tool = make_project_plan("tool", "/tmp/t", "app")
        plan_cli = make_project_plan("cli", "/tmp/t", "app")
        assert len(plan_tool) == len(plan_cli)


# ── MockProvider project mode tests ──────────────────────────────────────────

class TestMockProviderProjectMode:
    @pytest.mark.asyncio
    async def test_mock_provider_project_mode_creates_plan(self):
        """First response to a project request is write_file with path inside workspace."""
        p = MockProvider()
        msgs = [Message(role="user", content="crie um projeto fastapi completo em /tmp/testproj")]
        resp = await p.complete(msgs, specs_for("write_file", "list_dir"))
        assert resp.stop_reason == "tool_calls"
        assert resp.message.tool_calls[0].name == "write_file"
        path = resp.message.tool_calls[0].arguments["path"]
        assert path.startswith("/tmp/testproj")

    @pytest.mark.asyncio
    async def test_mock_provider_advances_steps_on_tool_result(self):
        """After first write result, complete() returns another write_file."""
        p = MockProvider()
        # First request
        msgs = [Message(role="user", content="crie um projeto fastapi completo em /tmp/tp2")]
        resp1 = await p.complete(msgs, specs_for("write_file", "list_dir"))
        assert resp1.stop_reason == "tool_calls"

        # Simulate tool result
        msgs2 = [
            Message(role="user", content="crie um projeto fastapi completo em /tmp/tp2"),
            Message(role="assistant", content=None, tool_calls=resp1.message.tool_calls),
            Message(role="tool", tool_results=[
                ToolResult(tool_call_id=resp1.message.tool_calls[0].id, content="ok")
            ]),
        ]
        resp2 = await p.complete(msgs2, specs_for("write_file", "list_dir"))
        # Should continue with another write_file (not end_turn)
        assert resp2.stop_reason == "tool_calls"
        assert resp2.message.tool_calls[0].name == "write_file"

    @pytest.mark.asyncio
    async def test_mock_provider_finishes_with_list_dir(self):
        """After all write steps, next response is list_dir."""
        p = MockProvider()
        # Manually set up a minimal 1-step plan so we can exhaust it quickly
        from agent_framework.core.content_generator import make_project_plan
        p._project_plan = make_project_plan("webapp", "/tmp/tp3", "test")
        p._plan_step = len(p._project_plan)  # pretend all steps done

        msgs = [
            Message(role="tool", tool_results=[
                ToolResult(tool_call_id="x1", content="wrote file")
            ]),
        ]
        resp = await p.complete(msgs, specs_for("write_file", "list_dir"))
        assert resp.stop_reason == "tool_calls"
        assert resp.message.tool_calls[0].name == "list_dir"

    @pytest.mark.asyncio
    async def test_mock_provider_final_summary_after_list_dir(self):
        """After list_dir result, returns rich completion message and resets state."""
        p = MockProvider()
        from agent_framework.core.content_generator import make_project_plan
        p._project_plan = make_project_plan("fastapi", "/tmp/tp4", "myapp")
        p._plan_step = len(p._project_plan)
        p._plan_finishing = True

        msgs = [
            Message(role="tool", tool_results=[
                ToolResult(tool_call_id="x2", content="main.py\nDockerfile")
            ]),
        ]
        resp = await p.complete(msgs, specs_for("write_file", "list_dir"))
        assert resp.stop_reason == "end_turn"
        assert "Projeto criado" in resp.message.content
        # State should be reset
        assert p._project_plan is None
        assert p._plan_step == 0
        assert p._plan_finishing is False


# ── CSS and JS template tests ─────────────────────────────────────────────────

class TestCSSAndJSTemplates:
    def test_css_generates_styles(self):
        content = generate_content("style.css", "")
        assert "body {" in content or "body{" in content or "*{" in content or "*, " in content

    def test_js_generates_module(self):
        content = generate_content("app.js", "")
        assert "function" in content or "const" in content

    def test_css_is_dark_themed(self):
        content = generate_content("style.css", "dark theme")
        # Should contain dark color values
        assert "#" in content  # hex colors

    def test_js_has_event_listener(self):
        content = generate_content("app.js", "webapp")
        assert "addEventListener" in content or "function" in content
