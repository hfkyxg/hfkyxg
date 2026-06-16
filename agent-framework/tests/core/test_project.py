"""Tests for TaskGraph, TaskNode, and ProjectCrew."""
from __future__ import annotations

import pytest

from agent_framework.core.errors import PlanningError
from agent_framework.core.messages import Message
from agent_framework.core.orchestrator import Orchestrator
from agent_framework.core.permissions import always_allow
from agent_framework.core.persona import Persona
from agent_framework.core.project import ProjectCrew, TaskGraph, TaskNode, TaskStatus
from agent_framework.core.provider import ModelProvider, ProviderResponse
from agent_framework.core.tool import ToolRegistry


def make_persona(name: str = "worker") -> Persona:
    return Persona(
        name=name,
        system_prompt="You are a worker agent.",
        provider="fake/model",
        enabled_tools=["*"],
    )


def end_resp(text: str) -> ProviderResponse:
    return ProviderResponse(
        message=Message(role="assistant", content=text),
        stop_reason="end_turn",
    )


class FakeProvider(ModelProvider):
    def __init__(self, responses: list[ProviderResponse]):
        super().__init__(model="fake/model")
        self._responses = responses
        self._idx = 0

    async def complete(self, messages, tools, **kw) -> ProviderResponse:
        resp = self._responses[self._idx % len(self._responses)]
        self._idx += 1
        return resp


# ---------------------------------------------------------------------------
# TaskGraph
# ---------------------------------------------------------------------------

class TestTaskGraph:
    def test_ready_tasks_with_no_deps(self):
        nodes = [
            TaskNode(id="a", description="A", role="backend"),
            TaskNode(id="b", description="B", role="frontend"),
        ]
        graph = TaskGraph(nodes)
        ready = graph.ready_tasks()
        assert {n.id for n in ready} == {"a", "b"}

    def test_ready_tasks_respects_depends_on(self):
        nodes = [
            TaskNode(id="a", description="A", role="backend"),
            TaskNode(id="b", description="B", role="frontend", depends_on=["a"]),
        ]
        graph = TaskGraph(nodes)
        ready = graph.ready_tasks()
        assert [n.id for n in ready] == ["a"]

    def test_dep_unlocked_after_done(self):
        nodes = [
            TaskNode(id="a", description="A", role="backend"),
            TaskNode(id="b", description="B", role="frontend", depends_on=["a"]),
        ]
        graph = TaskGraph(nodes)
        graph.get("a").status = TaskStatus.DONE
        ready = graph.ready_tasks()
        assert [n.id for n in ready] == ["b"]

    def test_all_done(self):
        nodes = [TaskNode(id="a", description="A", role="backend")]
        graph = TaskGraph(nodes)
        assert not graph.all_done()
        graph.get("a").status = TaskStatus.DONE
        assert graph.all_done()

    def test_is_stuck_when_failed_blocks_deps(self):
        nodes = [
            TaskNode(id="a", description="A", role="backend", status=TaskStatus.FAILED),
            TaskNode(id="b", description="B", role="frontend", depends_on=["a"]),
        ]
        graph = TaskGraph(nodes)
        assert graph.is_stuck()

    def test_from_json(self):
        data = [
            {"id": "t1", "description": "Do X", "role": "backend", "depends_on": []},
            {"id": "t2", "description": "Do Y", "role": "frontend", "depends_on": ["t1"]},
        ]
        graph = TaskGraph.from_json(data)
        assert len(graph.nodes) == 2
        assert graph.get("t2").depends_on == ["t1"]

    def test_from_json_generates_id_if_missing(self):
        data = [{"description": "Do Z", "role": "backend"}]
        graph = TaskGraph.from_json(data)
        assert graph.nodes[0].id  # auto-generated


# ---------------------------------------------------------------------------
# ProjectCrew
# ---------------------------------------------------------------------------

class TestProjectCrewPlan:
    @pytest.mark.asyncio
    async def test_plan_parses_json_array(self, tmp_path, monkeypatch):
        plan_json = '[{"id":"t1","description":"build api","role":"backend","depends_on":[]}]'
        fake = FakeProvider([end_resp(plan_json)])
        monkeypatch.setattr(
            "agent_framework.core.provider.ModelProvider.from_persona",
            lambda p: fake,
        )
        personas = {"planner": make_persona("planner"), "default": make_persona()}
        orch = Orchestrator(base_tools=ToolRegistry(), base_permission_gate=always_allow())
        crew = ProjectCrew(orchestrator=orch, personas=personas, workspace=tmp_path)
        graph = await crew.plan("build a REST API")
        assert len(graph.nodes) == 1
        assert graph.nodes[0].id == "t1"

    @pytest.mark.asyncio
    async def test_plan_raises_on_non_json(self, tmp_path, monkeypatch):
        fake = FakeProvider([end_resp("Sorry, I cannot plan that.")])
        monkeypatch.setattr(
            "agent_framework.core.provider.ModelProvider.from_persona",
            lambda p: fake,
        )
        personas = {"planner": make_persona("planner")}
        orch = Orchestrator(base_tools=ToolRegistry(), base_permission_gate=always_allow())
        crew = ProjectCrew(orchestrator=orch, personas=personas, workspace=tmp_path)
        with pytest.raises(PlanningError):
            await crew.plan("build something")

    @pytest.mark.asyncio
    async def test_plan_extracts_json_from_prose(self, tmp_path, monkeypatch):
        # Planner wraps JSON in prose — crew should still extract it
        response = 'Here is my plan:\n[{"id":"x","description":"task","role":"backend","depends_on":[]}]\nDone.'
        fake = FakeProvider([end_resp(response)])
        monkeypatch.setattr(
            "agent_framework.core.provider.ModelProvider.from_persona",
            lambda p: fake,
        )
        personas = {"planner": make_persona("planner")}
        orch = Orchestrator(base_tools=ToolRegistry(), base_permission_gate=always_allow())
        crew = ProjectCrew(orchestrator=orch, personas=personas, workspace=tmp_path)
        graph = await crew.plan("build something")
        assert graph.nodes[0].id == "x"


class TestProjectCrewExecute:
    @pytest.mark.asyncio
    async def test_single_task_executes_and_returns_result(self, tmp_path, monkeypatch):
        task_result = "I built the API."
        integration_result = "Everything is integrated."
        fake = FakeProvider([end_resp(task_result), end_resp('{"ok":true}'), end_resp(integration_result)])
        monkeypatch.setattr(
            "agent_framework.core.provider.ModelProvider.from_persona",
            lambda p: fake,
        )
        personas = {
            "backend": make_persona("backend"),
            "reviewer": make_persona("reviewer"),
            "integrator": make_persona("integrator"),
        }
        orch = Orchestrator(base_tools=ToolRegistry(), base_permission_gate=always_allow())
        crew = ProjectCrew(orchestrator=orch, personas=personas, workspace=tmp_path)
        nodes = [TaskNode(id="api", description="Build API", role="backend")]
        graph = TaskGraph(nodes)
        result = await crew.execute(graph)
        assert result.task_results["api"] == task_result
        assert result.success

    @pytest.mark.asyncio
    async def test_parallel_tasks_both_run(self, tmp_path, monkeypatch):
        call_log: list[str] = []

        async def fake_complete(self_inner, messages, tools, **kw):
            # detect which task by content
            content = " ".join(m.content or "" for m in messages if m.content)
            if "Backend" in content:
                call_log.append("backend")
            elif "Frontend" in content:
                call_log.append("frontend")
            elif "ok" in content.lower() or "review" in content.lower():
                call_log.append("review")
            else:
                call_log.append("other")
            return end_resp('{"ok":true}')

        monkeypatch.setattr(FakeProvider, "complete", fake_complete)
        monkeypatch.setattr(
            "agent_framework.core.provider.ModelProvider.from_persona",
            lambda p: FakeProvider([]),
        )
        personas = {
            "backend": make_persona("backend"),
            "frontend": make_persona("frontend"),
            "reviewer": make_persona("reviewer"),
            "integrator": make_persona("integrator"),
        }
        orch = Orchestrator(base_tools=ToolRegistry(), base_permission_gate=always_allow())
        crew = ProjectCrew(orchestrator=orch, personas=personas, workspace=tmp_path)
        nodes = [
            TaskNode(id="be", description="Backend task", role="backend"),
            TaskNode(id="fe", description="Frontend task", role="frontend"),
        ]
        graph = TaskGraph(nodes)
        await crew.execute(graph)
        assert graph.get("be").status == TaskStatus.DONE
        assert graph.get("fe").status == TaskStatus.DONE

    @pytest.mark.asyncio
    async def test_revision_loop_reschedules_task(self, tmp_path, monkeypatch):
        responses = [
            end_resp("bad result"),           # first task attempt
            end_resp('{"ok":false,"feedback":"missing endpoint"}'),  # reviewer says bad
            end_resp("good result"),           # second task attempt
            end_resp('{"ok":true}'),           # reviewer says good
            end_resp("all integrated"),        # integrator
        ]
        fake = FakeProvider(responses)
        monkeypatch.setattr(
            "agent_framework.core.provider.ModelProvider.from_persona",
            lambda p: fake,
        )
        personas = {
            "backend": make_persona("backend"),
            "reviewer": make_persona("reviewer"),
            "integrator": make_persona("integrator"),
        }
        orch = Orchestrator(base_tools=ToolRegistry(), base_permission_gate=always_allow())
        crew = ProjectCrew(orchestrator=orch, personas=personas, workspace=tmp_path)
        nodes = [TaskNode(id="api", description="Build API", role="backend")]
        graph = TaskGraph(nodes)
        result = await crew.execute(graph)
        assert graph.get("api").revision_count == 1
        assert result.task_results["api"] == "good result"

    @pytest.mark.asyncio
    async def test_stuck_graph_raises_planning_error(self, tmp_path, monkeypatch):
        # Task B depends on A, but A fails — graph gets stuck
        monkeypatch.setattr(
            "agent_framework.core.provider.ModelProvider.from_persona",
            lambda p: FakeProvider([end_resp("fail")]),
        )
        personas = {
            "backend": make_persona("backend"),
            "reviewer": make_persona("reviewer"),
            "integrator": make_persona("integrator"),
        }
        orch = Orchestrator(base_tools=ToolRegistry(), base_permission_gate=always_allow())
        crew = ProjectCrew(orchestrator=orch, personas=personas, workspace=tmp_path)

        nodes = [
            TaskNode(id="a", description="A", role="backend", status=TaskStatus.FAILED),
            TaskNode(id="b", description="B", role="backend", depends_on=["a"]),
        ]
        graph = TaskGraph(nodes)
        with pytest.raises(PlanningError, match="stuck"):
            await crew.execute(graph)
