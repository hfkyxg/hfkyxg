"""Tests for the autonomous multi-agent runtime."""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest

from agent_framework.core.messages import Message
from agent_framework.core.persona import Persona
from agent_framework.core.provider import ModelProvider, ProviderResponse
from agent_framework.core.runtime import AgentRuntime, JobStatus
from agent_framework.core.tool import ToolRegistry
from agent_framework.core.workflow import (
    PermissionMode,
    TriggerType,
    Workflow,
    WorkflowStep,
    WorkflowTrigger,
)

# ── EventBus ────────────────────────────────────────────────────────────────

class TestEventBus:
    @pytest.mark.asyncio
    async def test_publish_delivers_to_subscriber(self):
        from agent_framework.core.eventbus import EventBus

        bus = EventBus()
        q = await bus.subscribe("test.topic")
        await bus.publish("test.topic", {"x": 1})
        msg = await asyncio.wait_for(q.get(), timeout=1)
        assert msg == {"x": 1}

    @pytest.mark.asyncio
    async def test_no_delivery_after_unsubscribe(self):
        from agent_framework.core.eventbus import EventBus

        bus = EventBus()
        q = await bus.subscribe("t")
        bus.unsubscribe("t", q)
        await bus.publish("t", {"y": 2})
        assert q.empty()

    @pytest.mark.asyncio
    async def test_multiple_subscribers_all_receive(self):
        from agent_framework.core.eventbus import EventBus

        bus = EventBus()
        q1 = await bus.subscribe("ping")
        q2 = await bus.subscribe("ping")
        await bus.publish("ping", {"msg": "hello"})
        assert (await q1.get()) == {"msg": "hello"}
        assert (await q2.get()) == {"msg": "hello"}

    @pytest.mark.asyncio
    async def test_no_cross_topic_delivery(self):
        from agent_framework.core.eventbus import EventBus

        bus = EventBus()
        q = await bus.subscribe("topic.a")
        await bus.publish("topic.b", {"data": "other"})
        assert q.empty()


# ── Scheduler ───────────────────────────────────────────────────────────────

class TestScheduler:
    def test_parse_interval_seconds(self):
        from agent_framework.core.scheduler import _parse_interval

        assert _parse_interval("30s") == 30.0
        assert _parse_interval("60") == 60.0

    def test_parse_interval_minutes(self):
        from agent_framework.core.scheduler import _parse_interval

        assert _parse_interval("5m") == 300.0

    def test_parse_interval_hours(self):
        from agent_framework.core.scheduler import _parse_interval

        assert _parse_interval("1h") == 3600.0

    def test_parse_interval_days(self):
        from agent_framework.core.scheduler import _parse_interval

        assert _parse_interval("1d") == 86400.0

    def test_parse_interval_invalid_raises(self):
        from agent_framework.core.scheduler import _parse_interval

        with pytest.raises(ValueError):
            _parse_interval("5x")

    @pytest.mark.asyncio
    async def test_job_fires_after_interval(self):
        from agent_framework.core.scheduler import AsyncScheduler

        called = []
        sched = AsyncScheduler()

        async def cb():
            called.append(1)

        sched.add_job("test", 0.05, cb)
        await sched.start()
        await asyncio.sleep(0.15)
        await sched.stop()
        assert len(called) >= 1


# ── FileWatcher ──────────────────────────────────────────────────────────────

class TestFileWatcher:
    @pytest.mark.asyncio
    async def test_detects_new_file(self, tmp_path: Path):
        from agent_framework.core.watcher import FileWatcher

        watcher = FileWatcher(path=str(tmp_path), pattern="*.txt", events=["created"])
        events = []

        async def _collect():
            async for evt in watcher.watch():
                events.append(evt)
                break  # stop after first

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0.1)
        (tmp_path / "hello.txt").write_text("hi")
        try:
            await asyncio.wait_for(task, timeout=5)
        except TimeoutError:
            task.cancel()

        assert any(e.type == "created" for e in events)

    @pytest.mark.asyncio
    async def test_ignores_non_matching_pattern(self, tmp_path: Path):
        from agent_framework.core.watcher import FileWatcher

        watcher = FileWatcher(path=str(tmp_path), pattern="*.py", events=["created"])
        events = []

        async def _collect():
            async for evt in watcher.watch():
                events.append(evt)
                break

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0.1)
        (tmp_path / "readme.txt").write_text("text")  # should not match *.py
        try:
            await asyncio.wait_for(task, timeout=3)
        except TimeoutError:
            pass
        task.cancel()
        assert events == []


# ── Workflow model ────────────────────────────────────────────────────────────

class TestWorkflowModel:
    def test_load_from_yaml(self, tmp_path: Path):
        from agent_framework.core.workflow import Workflow

        yaml_content = """
name: test_wf
description: A test workflow
triggers:
  - type: schedule
    interval: "5m"
steps:
  - name: step1
    persona: demo
    task: "do something"
    workspace: "."
permission: autopilot
"""
        p = tmp_path / "test_wf.yaml"
        p.write_text(yaml_content)
        wf = Workflow.from_yaml(p)
        assert wf.name == "test_wf"
        assert wf.triggers[0].interval == "5m"
        assert wf.steps[0].name == "step1"
        assert wf.permission.value == "autopilot"

    def test_load_all_skips_invalid(self, tmp_path: Path):
        from agent_framework.core.workflow import Workflow

        (tmp_path / "good.yaml").write_text("name: good\ntriggers: []\nsteps: []\n")
        (tmp_path / "bad.yaml").write_text("{{not yaml}}")
        wfs = Workflow.load_all(tmp_path)
        assert len(wfs) == 1
        assert wfs[0].name == "good"

    def test_load_all_empty_dir(self, tmp_path: Path):
        from agent_framework.core.workflow import Workflow

        wfs = Workflow.load_all(tmp_path)
        assert wfs == []

    def test_watch_trigger_fields(self, tmp_path: Path):
        from agent_framework.core.workflow import Workflow

        yaml_content = """
name: watcher
triggers:
  - type: watch
    path: ./src
    pattern: "*.py"
    events: [modified, created]
steps: []
"""
        p = tmp_path / "watcher.yaml"
        p.write_text(yaml_content)
        wf = Workflow.from_yaml(p)
        t = wf.triggers[0]
        assert t.type.value == "watch"
        assert t.path == "./src"
        assert "modified" in t.events


# ── WorkspaceGate ─────────────────────────────────────────────────────────────

class TestWorkspaceGate:
    @pytest.mark.asyncio
    async def test_inside_workspace_allowed(self, tmp_path: Path):
        from unittest.mock import MagicMock

        from agent_framework.core.permissions import PermissionDecision, workspace_gate

        gate = workspace_gate(str(tmp_path))
        tool = MagicMock()
        tool.name = "read_file"
        tool.requires_permission = False
        decision = await gate.check(tool, {"path": str(tmp_path / "file.txt")})
        assert decision == PermissionDecision.ALLOW

    @pytest.mark.asyncio
    async def test_outside_workspace_asks(self, tmp_path: Path):
        from unittest.mock import AsyncMock, MagicMock

        from agent_framework.core.permissions import PermissionDecision, workspace_gate

        ask_mock = AsyncMock(return_value=False)
        gate = workspace_gate(str(tmp_path), ask_callback=ask_mock)
        tool = MagicMock()
        tool.name = "write_file"
        tool.requires_permission = True
        decision = await gate.check(tool, {"path": "/etc/passwd"})
        assert decision == PermissionDecision.DENY
        ask_mock.assert_called_once()


# ── AgentRuntime integration tests ───────────────────────────────────────────


class FakeProvider(ModelProvider):
    """Cycles through preset responses."""

    def __init__(self, responses: list[ProviderResponse]):
        super().__init__(model="fake/model")
        self._responses = responses
        self._i = 0

    async def complete(self, messages, tools, **kw) -> ProviderResponse:
        r = self._responses[self._i % len(self._responses)]
        self._i += 1
        return r


def _end_turn(text: str = "done") -> ProviderResponse:
    return ProviderResponse(
        message=Message(role="assistant", content=text),
        stop_reason="end_turn",
    )


def _test_persona(name: str = "test") -> Persona:
    return Persona(
        name=name,
        system_prompt="You are a test agent.",
        provider="fake/model",
        enabled_tools=["*"],
    )


def _simple_workflow(name: str = "wf", permission: str = "autopilot") -> Workflow:
    return Workflow(
        name=name,
        triggers=[WorkflowTrigger(type=TriggerType.MANUAL)],
        steps=[WorkflowStep(name="step1", persona="test", task="do something")],
        permission=PermissionMode(permission),
    )


class TestRuntimeExecutesJob:
    @pytest.mark.asyncio
    async def test_runtime_executes_job(self, monkeypatch):
        """Job reaches DONE status when provider returns end_turn."""
        persona = _test_persona()
        workflow = _simple_workflow()
        registry = ToolRegistry()

        runtime = AgentRuntime(
            workflows=[workflow],
            personas={"test": persona},
            base_tools=registry,
            num_workers=2,
        )

        fake_prov = FakeProvider([_end_turn("all done")])
        monkeypatch.setattr(
            "agent_framework.core.provider.ModelProvider.from_persona",
            lambda p: fake_prov,
        )

        await runtime.start()
        job_id = await runtime.trigger_manual("wf")
        # Wait for job to complete (max 10s)
        deadline = asyncio.get_event_loop().time() + 10
        while asyncio.get_event_loop().time() < deadline:
            job = runtime.jobs.get(job_id)
            if job and job.status in (JobStatus.DONE, JobStatus.FAILED):
                break
            await asyncio.sleep(0.05)
        await runtime.stop()

        job = runtime.jobs.get(job_id)
        assert job is not None
        assert job.status == JobStatus.DONE, f"Expected DONE, got {job.status}; error={job.error}"

    @pytest.mark.asyncio
    async def test_runtime_permission_broker_allow(self, monkeypatch):
        """Broker gate pre-approves: tool runs successfully."""
        from agent_framework.core.messages import ToolCall
        from agent_framework.tools.files import WriteFileTool

        persona = _test_persona()
        workflow = _simple_workflow("wf_ask", permission="ask")
        registry = ToolRegistry()
        registry.register(WriteFileTool())

        runtime = AgentRuntime(
            workflows=[workflow],
            personas={"test": persona},
            base_tools=registry,
            num_workers=1,
        )

        tc_id = uuid.uuid4().hex
        write_resp = ProviderResponse(
            message=Message(
                role="assistant",
                tool_calls=[
                    ToolCall(
                        id=tc_id,
                        name="write_file",
                        arguments={"path": "/tmp/apathy_test_broker.txt", "content": "hi"},
                    )
                ],
            ),
            stop_reason="tool_calls",
        )
        fake_prov = FakeProvider([write_resp, _end_turn("written")])
        monkeypatch.setattr(
            "agent_framework.core.provider.ModelProvider.from_persona",
            lambda p: fake_prov,
        )

        await runtime.start()
        job_id = await runtime.trigger_manual("wf_ask")

        async def _auto_approve() -> None:
            for _ in range(20):
                await asyncio.sleep(0.1)
                for req_id in list(runtime.perm_requests.keys()):
                    await runtime.approve_permission(req_id, allow=True)

        approve_task = asyncio.create_task(_auto_approve())

        deadline = asyncio.get_event_loop().time() + 10
        while asyncio.get_event_loop().time() < deadline:
            job = runtime.jobs.get(job_id)
            if job and job.status in (JobStatus.DONE, JobStatus.FAILED):
                break
            await asyncio.sleep(0.05)

        approve_task.cancel()
        await runtime.stop()

        job = runtime.jobs[job_id]
        assert job.status == JobStatus.DONE, f"Expected DONE, got {job.status}; error={job.error}"

    @pytest.mark.asyncio
    async def test_runtime_permission_broker_deny(self, monkeypatch):
        """Broker gate denies: tool is blocked, job still finishes."""
        from agent_framework.core.messages import ToolCall
        from agent_framework.tools.files import WriteFileTool

        persona = _test_persona()
        workflow = _simple_workflow("wf_deny", permission="ask")
        registry = ToolRegistry()
        registry.register(WriteFileTool())

        runtime = AgentRuntime(
            workflows=[workflow],
            personas={"test": persona},
            base_tools=registry,
            num_workers=1,
        )

        tc_id = uuid.uuid4().hex
        write_resp = ProviderResponse(
            message=Message(
                role="assistant",
                tool_calls=[
                    ToolCall(
                        id=tc_id,
                        name="write_file",
                        arguments={"path": "/tmp/apathy_deny.txt", "content": "no"},
                    )
                ],
            ),
            stop_reason="tool_calls",
        )
        fake_prov = FakeProvider([write_resp, _end_turn("denied by broker")])
        monkeypatch.setattr(
            "agent_framework.core.provider.ModelProvider.from_persona",
            lambda p: fake_prov,
        )

        await runtime.start()
        job_id = await runtime.trigger_manual("wf_deny")

        async def _auto_deny() -> None:
            for _ in range(20):
                await asyncio.sleep(0.1)
                for req_id in list(runtime.perm_requests.keys()):
                    await runtime.approve_permission(req_id, allow=False)

        deny_task = asyncio.create_task(_auto_deny())

        deadline = asyncio.get_event_loop().time() + 10
        while asyncio.get_event_loop().time() < deadline:
            job = runtime.jobs.get(job_id)
            if job and job.status in (JobStatus.DONE, JobStatus.FAILED):
                break
            await asyncio.sleep(0.05)

        deny_task.cancel()
        await runtime.stop()

        job = runtime.jobs[job_id]
        assert job.status in (JobStatus.DONE, JobStatus.FAILED)
