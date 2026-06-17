"""AgentRuntime — persistent daemon with worker pool, scheduler, and file watchers."""
from __future__ import annotations

import asyncio
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class AgentJob:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    workflow_name: str = ""
    step_name: str = ""
    task: str = ""
    persona: str = "demo"
    workspace: str = "."
    context: dict[str, str] = field(default_factory=dict)
    status: JobStatus = JobStatus.QUEUED
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: str = ""
    error: str = ""

    @property
    def duration(self) -> str:
        if self.started_at is None:
            return "-"
        end = self.finished_at or datetime.now()
        s = int((end - self.started_at).total_seconds())
        return f"{s}s" if s < 60 else f"{s // 60}m{s % 60}s"


@dataclass
class PermissionRequest:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    job_id: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    allowed: bool = False
    _event: asyncio.Event = field(default_factory=asyncio.Event)


class AgentRuntime:
    """Persistent async runtime: manages workers, scheduling, file watching, and permissions."""

    def __init__(
        self,
        *,
        workflows_dir: str = "workflows",
        personas_dir: str = "personas",
        num_workers: int = 4,
        max_log: int = 200,
    ) -> None:
        self.workflows_dir = workflows_dir
        self.personas_dir = personas_dir
        self.num_workers = num_workers
        self.started_at = datetime.now()

        self.jobs: dict[str, AgentJob] = {}
        self.event_log: deque[str] = deque(maxlen=max_log)
        self.perm_requests: dict[str, PermissionRequest] = {}

        self._queue: asyncio.Queue[AgentJob] = asyncio.Queue()
        self._stop_event = asyncio.Event()
        self._background: list[asyncio.Task] = []

        from agent_framework.core.eventbus import EventBus
        from agent_framework.core.scheduler import AsyncScheduler

        self._bus = EventBus()
        self._scheduler = AsyncScheduler()
        self._workflows: list[Any] = []  # list[Workflow] — loaded lazily

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._load_workflows()
        self._log("runtime started")

        # Spawn worker pool
        for i in range(self.num_workers):
            t = asyncio.create_task(self._worker(i), name=f"worker-{i}")
            self._background.append(t)

        # Register scheduled/watched workflows
        for wf in self._workflows:
            for trigger in wf.triggers:
                if trigger.type.value == "schedule" and trigger.interval:
                    from agent_framework.core.scheduler import _parse_interval

                    interval_secs = _parse_interval(trigger.interval)
                    self._scheduler.add_job(
                        f"sched-{wf.name}",
                        interval_secs,
                        lambda w=wf: self._enqueue_workflow(w, {}),
                    )
                elif trigger.type.value == "watch" and trigger.path:
                    t = asyncio.create_task(
                        self._run_watcher(wf, trigger), name=f"watch-{wf.name}"
                    )
                    self._background.append(t)

        await self._scheduler.start()
        self._log(f"loaded {len(self._workflows)} workflow(s)")

    async def stop(self) -> None:
        self._stop_event.set()
        await self._scheduler.stop()
        for t in self._background:
            t.cancel()
        self._log("runtime stopped")

    async def trigger_manual(self, workflow_name: str, extra: dict[str, str] | None = None) -> str:
        """Enqueue a workflow by name; returns the first job id."""
        wf = self._find_workflow(workflow_name)
        if wf is None:
            raise ValueError(f"Unknown workflow: {workflow_name!r}")
        jobs = await self._enqueue_workflow(wf, extra or {})
        return jobs[0].id if jobs else ""

    async def approve_permission(self, req_id: str, allow: bool) -> None:
        req = self.perm_requests.get(req_id)
        if req is None or req.resolved:
            return
        req.allowed = allow
        req.resolved = True
        req._event.set()
        self._log(f"permission {req_id} {'allowed' if allow else 'denied'}")

    # ------------------------------------------------------------------
    # Stats helpers
    # ------------------------------------------------------------------

    @property
    def active_jobs(self) -> list[AgentJob]:
        return [j for j in self.jobs.values() if j.status == JobStatus.RUNNING]

    @property
    def queued_count(self) -> int:
        return sum(1 for j in self.jobs.values() if j.status == JobStatus.QUEUED)

    @property
    def uptime(self) -> str:
        s = int((datetime.now() - self.started_at).total_seconds())
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        return f"{h}:{m:02d}:{sec:02d}"

    @property
    def pending_permissions(self) -> list[PermissionRequest]:
        return [r for r in self.perm_requests.values() if not r.resolved]

    # ------------------------------------------------------------------
    # Internal — worker pool
    # ------------------------------------------------------------------

    async def _worker(self, worker_id: int) -> None:
        while not self._stop_event.is_set():
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            await self._execute_job(job)
            self._queue.task_done()

    async def _execute_job(self, job: AgentJob) -> None:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        self._log(f"[{job.workflow_name}/{job.step_name}] started — {job.task[:60]}")

        try:
            from pathlib import Path as _Path

            from agent_framework.core.permissions import PermissionGate
            from agent_framework.core.persona import Persona
            from agent_framework.interfaces.cli.run_once import run_once

            # Resolve persona path
            persona_path = _Path(self.personas_dir) / f"{job.persona}.yaml"
            if not persona_path.exists():
                persona_path = _Path(job.persona)
            persona = Persona.from_yaml(persona_path)

            # Build a permission gate with interactive broker
            async def perm_callback(tool: Any, arguments: dict) -> bool:
                req = PermissionRequest(
                    job_id=job.id,
                    tool_name=tool.name,
                    arguments=arguments,
                )
                self.perm_requests[req.id] = req
                self._log(f"permission requested: {tool.name}({list(arguments.keys())})")
                await req._event.wait()
                return req.allowed

            gate = PermissionGate(ask_callback=perm_callback, autopilot=True)

            output_lines: list[str] = []

            async def capture(event: Any) -> None:
                from agent_framework.core.agent import AssistantTextEvent, ToolResultEvent

                if isinstance(event, AssistantTextEvent):
                    output_lines.append(event.text)
                elif isinstance(event, ToolResultEvent):
                    self._log(f"  tool {event.tool_name}: {str(event.output)[:80]}")

            await run_once(
                persona,
                job.task,
                job.workspace,
                auto_approve=True,
                event_hook=capture,
                permission_gate=gate,
            )

            job.result = "\n".join(output_lines)
            job.status = JobStatus.DONE
            self._log(f"[{job.workflow_name}/{job.step_name}] done in {job.duration}")
            await self._bus.publish(
                "job.done",
                {"job_id": job.id, "workflow": job.workflow_name, "result": job.result},
            )

        except Exception as exc:
            job.error = str(exc)
            job.status = JobStatus.FAILED
            self._log(f"[{job.workflow_name}/{job.step_name}] FAILED: {exc}")
        finally:
            job.finished_at = datetime.now()

    # ------------------------------------------------------------------
    # Internal — workflow helpers
    # ------------------------------------------------------------------

    def _load_workflows(self) -> None:
        from agent_framework.core.workflow import Workflow

        self._workflows = Workflow.load_all(self.workflows_dir)

    def _find_workflow(self, name: str) -> Any | None:
        for wf in self._workflows:
            if wf.name == name:
                return wf
        return None

    async def _enqueue_workflow(self, wf: Any, context: dict[str, str]) -> list[AgentJob]:
        jobs = []
        for step in wf.steps:
            task_text = step.task
            for k, v in context.items():
                task_text = task_text.replace(f"{{{k}}}", v)
            job = AgentJob(
                workflow_name=wf.name,
                step_name=step.name,
                task=task_text,
                persona=step.persona,
                workspace=step.workspace,
                context=context,
            )
            self.jobs[job.id] = job
            await self._queue.put(job)
            jobs.append(job)
        return jobs

    async def _run_watcher(self, wf: Any, trigger: Any) -> None:
        from agent_framework.core.watcher import FileWatcher

        watcher = FileWatcher(
            path=trigger.path,
            pattern=trigger.pattern,
            events=trigger.events,
        )
        self._log(f"watching {trigger.path!r} ({trigger.pattern}) for {wf.name}")
        try:
            async for event in watcher.watch():
                if self._stop_event.is_set():
                    break
                context = {"file": event.path, "event": event.type, "workflow": wf.name}
                await self._enqueue_workflow(wf, context)
        except asyncio.CancelledError:
            pass

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.event_log.append(f"[{ts}] {msg}")
