"""TaskGraph, TaskNode, ProjectCrew: multi-role parallel agent team — Phase 3"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent_framework.core.errors import PlanningError
from agent_framework.core.persona import Persona

if TYPE_CHECKING:
    from agent_framework.core.orchestrator import Orchestrator


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    NEEDS_REVISION = "needs_revision"
    FAILED = "failed"


@dataclass
class TaskNode:
    id: str
    description: str
    role: str  # persona key: planner, backend, frontend, reviewer, integrator
    depends_on: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    revision_count: int = 0
    revision_feedback: str = ""
    allowed_tools: list[str] | None = None


class TaskGraph:
    def __init__(self, nodes: list[TaskNode]) -> None:
        self._nodes: dict[str, TaskNode] = {n.id: n for n in nodes}

    @property
    def nodes(self) -> list[TaskNode]:
        return list(self._nodes.values())

    def get(self, task_id: str) -> TaskNode:
        return self._nodes[task_id]

    def ready_tasks(self) -> list[TaskNode]:
        """Return tasks whose deps are all DONE and that are PENDING."""
        ready = []
        for node in self._nodes.values():
            if node.status != TaskStatus.PENDING:
                continue
            deps_done = all(
                self._nodes[dep].status == TaskStatus.DONE for dep in node.depends_on
            )
            if deps_done:
                ready.append(node)
        return ready

    def running_tasks(self) -> list[TaskNode]:
        return [n for n in self._nodes.values() if n.status == TaskStatus.RUNNING]

    def all_done(self) -> bool:
        return all(n.status in (TaskStatus.DONE, TaskStatus.FAILED) for n in self._nodes.values())

    def is_stuck(self) -> bool:
        """True when nothing is ready or running but the graph isn't fully resolved."""
        return not self.all_done() and not self.ready_tasks() and not self.running_tasks()

    def summary(self) -> str:
        lines = []
        for node in self._nodes.values():
            icon = {
                TaskStatus.PENDING: "○",
                TaskStatus.RUNNING: "◉",
                TaskStatus.DONE: "✓",
                TaskStatus.NEEDS_REVISION: "↺",
                TaskStatus.FAILED: "✗",
            }.get(node.status, "?")
            lines.append(f"  {icon} [{node.role}] {node.id}: {node.description[:60]}")
        return "\n".join(lines)

    @classmethod
    def from_json(cls, data: list[dict[str, Any]]) -> TaskGraph:
        nodes = []
        for item in data:
            nodes.append(TaskNode(
                id=item.get("id", uuid.uuid4().hex[:8]),
                description=item["description"],
                role=item.get("role", "backend"),
                depends_on=item.get("depends_on", []),
                allowed_tools=item.get("allowed_tools"),
            ))
        return cls(nodes)


@dataclass
class ProjectResult:
    success: bool
    summary: str
    task_results: dict[str, str]
    workspace: Path


_PLANNER_SYSTEM = """\
You are a senior software architect and project planner.
Given an objective, decompose it into concrete implementation tasks.
Each task must be assigned to one of these roles: backend, frontend, infra, reviewer, integrator.
Tasks that can run in parallel (no shared state dependencies) must have no depends_on between them.
Output ONLY a JSON array, no prose, no markdown fences. Each element:
{
  "id": "short_snake_case_id",
  "description": "clear, actionable task description",
  "role": "backend|frontend|infra|reviewer|integrator",
  "depends_on": ["other_task_id"],
  "allowed_tools": ["read_file","write_file","edit_file","bash","list_dir","glob","grep"]
}
"""

_REVIEWER_SYSTEM = """\
You are a senior code reviewer and QA engineer.
Review the provided artifacts for correctness, completeness and quality.
If you find problems, respond with JSON: {"ok": false, "feedback": "...specific issues..."}
If everything looks good, respond with JSON: {"ok": true, "feedback": "LGTM"}
Output ONLY valid JSON, no prose.
"""

_INTEGRATOR_SYSTEM = """\
You are an integration engineer. Your job is to verify that all parts of a project
work together correctly, fix any integration issues, and produce a concise summary
of what was built and how to run it.
Use your tools to inspect, test and fix. Then write a final summary.
"""


class ProjectCrew:
    MAX_REVISIONS = 2

    def __init__(
        self,
        orchestrator: Orchestrator,
        personas: dict[str, Persona],
        workspace: Path,
        *,
        progress_callback: Any | None = None,
    ) -> None:
        self._orch = orchestrator
        self._personas = personas
        self._workspace = workspace
        self._progress = progress_callback  # callable(node, event_str)

    def _emit(self, node: TaskNode | None, event: str) -> None:
        if self._progress:
            self._progress(node, event)

    def _persona(self, role: str) -> Persona:
        if role in self._personas:
            return self._personas[role]
        # fallback to "default" if role not found
        if "default" in self._personas:
            return self._personas["default"]
        return next(iter(self._personas.values()))

    async def plan(self, objective: str) -> TaskGraph:
        """Run the planner subagent and return a validated TaskGraph."""
        planner_persona = self._persona("planner")

        # Offline bypass: MockProvider can't return JSON, so build the plan directly.
        if planner_persona.provider.startswith(("mock/", "demo/")):
            from agent_framework.core.content_generator import make_project_plan

            lower_obj = objective.lower()
            detected_type = "fastapi"
            for kw, pt in [
                ("fastapi", "fastapi"), ("api", "fastapi"), ("rest", "fastapi"),
                ("cli", "cli"), ("tool", "cli"),
                ("webapp", "webapp"), ("web", "webapp"), ("html", "webapp"),
                ("data", "data"), ("analysis", "data"),
            ]:
                if kw in lower_obj:
                    detected_type = pt
                    break

            name_m = re.search(
                r"(?:chamado|named|called|nome|name)\s+([a-zA-Z0-9_\-]+)",
                objective, re.IGNORECASE
            )
            name = name_m.group(1) if name_m else "myapp"
            workspace = self._workspace

            plan_steps = make_project_plan(detected_type, str(workspace), name)

            def _role_for(path: str) -> str:
                ext = path.rsplit(".", 1)[-1].lower() if "." in path.split("/")[-1] else ""
                basename = path.split("/")[-1]
                if ext == "py":
                    if basename.startswith("test_"):
                        return "backend"
                    return "backend"
                if basename in ("Dockerfile", "Makefile", "makefile", ".gitignore",
                                ".dockerignore"):
                    return "infra"
                if ext in ("html", "css", "js"):
                    return "frontend"
                if basename.lower() == "readme.md":
                    return "planner"
                return "backend"

            nodes = [
                TaskNode(
                    id=f"file_{i:02d}",
                    description=step["task"],
                    role=_role_for(step["path"]),
                    depends_on=[],
                )
                for i, step in enumerate(plan_steps)
            ]
            return TaskGraph(nodes)

        prompt = (
            f"Objective: {objective}\n\n"
            f"Workspace directory: {self._workspace}\n\n"
            "Produce the task decomposition JSON array now."
        )
        raw = await self._orch.spawn_subagent(task_prompt=prompt, persona=planner_persona)

        # Extract JSON array from response
        raw = raw.strip()
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            raise PlanningError(f"Planner did not return a JSON array. Got: {raw[:300]}")
        try:
            data = json.loads(raw[start:end])
        except json.JSONDecodeError as exc:
            raise PlanningError(f"Planner JSON invalid: {exc}. Raw: {raw[:300]}") from exc

        if not isinstance(data, list) or not data:
            raise PlanningError("Planner returned an empty task list.")

        return TaskGraph.from_json(data)

    async def _run_task(self, node: TaskNode) -> None:
        node.status = TaskStatus.RUNNING
        self._emit(node, "started")
        persona = self._persona(node.role)

        context_parts = [f"Task: {node.description}"]
        context_parts.append(f"Workspace: {self._workspace}")
        if node.revision_feedback:
            context_parts.append(f"Previous attempt feedback: {node.revision_feedback}")
        prompt = "\n\n".join(context_parts)

        allowed = set(node.allowed_tools) if node.allowed_tools else None
        try:
            result = await self._orch.spawn_subagent(
                task_prompt=prompt,
                persona=persona,
                allowed_tools=allowed,
                workdir=str(self._workspace),
            )
            node.result = result
            node.status = TaskStatus.DONE
            self._emit(node, "done")
        except Exception as exc:
            node.result = f"Error: {exc}"
            node.status = TaskStatus.FAILED
            self._emit(node, f"failed: {exc}")

    async def _review_task(self, node: TaskNode) -> bool:
        """Run reviewer on a completed task. Returns True if OK."""
        reviewer_persona = self._persona("reviewer")
        prompt = (
            f"Review this task result:\n\nTask: {node.description}\n\n"
            f"Result/artifacts:\n{node.result[:3000]}\n\n"
            f"Workspace: {self._workspace}\n"
            "Inspect the actual files if needed. Then respond with JSON."
        )
        raw = await self._orch.spawn_subagent(
            task_prompt=prompt,
            persona=reviewer_persona,
            workdir=str(self._workspace),
        )
        raw = raw.strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1:
            return True  # reviewer gave no JSON → assume OK
        try:
            verdict = json.loads(raw[start:end])
            if verdict.get("ok", True):
                return True
            node.revision_feedback = verdict.get("feedback", "Needs improvement.")
            return False
        except json.JSONDecodeError:
            return True  # can't parse → assume OK

    async def execute(self, graph: TaskGraph) -> ProjectResult:
        """Drive the task graph to completion with parallel execution."""
        self._workspace.mkdir(parents=True, exist_ok=True)

        while not graph.all_done():
            if graph.is_stuck():
                failed = [n.id for n in graph.nodes if n.status == TaskStatus.FAILED]
                raise PlanningError(
                    f"Task graph is stuck — no tasks ready or running. Failed: {failed}"
                )

            ready = graph.ready_tasks()
            if not ready:
                await asyncio.sleep(0.05)
                continue

            # Run all ready tasks in parallel
            await asyncio.gather(*[self._run_task(node) for node in ready])

            # Review each just-completed task
            for node in ready:
                if node.status != TaskStatus.DONE:
                    continue
                if node.role in ("reviewer", "integrator", "planner"):
                    continue  # don't recursively review reviewers
                if node.revision_count >= self.MAX_REVISIONS:
                    continue

                ok = await self._review_task(node)
                if not ok:
                    node.revision_count += 1
                    node.status = TaskStatus.PENDING  # reschedule
                    self._emit(node, f"needs_revision (attempt {node.revision_count})")

        # Final integration pass
        integrator_persona = self._persona("integrator")
        task_summary = "\n".join(
            f"- [{n.role}] {n.id}: {n.description}\n  Result: {n.result[:500]}"
            for n in graph.nodes
        )
        integration_prompt = (
            f"All tasks are complete. Workspace: {self._workspace}\n\n"
            f"Task results:\n{task_summary}\n\n"
            "Inspect the workspace, verify everything works together, fix any integration "
            "issues, then write a concise summary of what was built and how to run it."
        )
        try:
            final_summary = await self._orch.spawn_subagent(
                task_prompt=integration_prompt,
                persona=integrator_persona,
                workdir=str(self._workspace),
            )
        except Exception as exc:
            final_summary = f"Integration pass failed: {exc}"

        return ProjectResult(
            success=all(n.status == TaskStatus.DONE for n in graph.nodes),
            summary=final_summary,
            task_results={n.id: n.result for n in graph.nodes},
            workspace=self._workspace,
        )
