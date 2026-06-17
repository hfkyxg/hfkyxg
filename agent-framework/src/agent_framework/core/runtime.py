"""AgentRuntime — the central coordinator for the apathy daemon."""
from __future__ import annotations

import asyncio
import os
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from agent_framework.core.eventbus import EventBus
from agent_framework.core.permissions import (
    PermissionDecision,
    PermissionGate,
    always_allow,
    workspace_gate,
)
from agent_framework.core.persona import Persona
from agent_framework.core.scheduler import AsyncScheduler, _parse_interval
from agent_framework.core.tool import ToolRegistry
from agent_framework.core.watcher import FileWatcher
from agent_framework.core.workflow import PermissionMode, TriggerType, Workflow


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    WAITING_PERM = "waiting_perm"


@dataclass
class AgentJob:
    id: str
    workflow_name: str
    step_name: str
    persona_name: str
    task: str
    workspace: str
    trigger_info: str = ""
    status: JobStatus = JobStatus.QUEUED
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: str | None = None
    error: str | None = None
    events_seen: list[str] = field(default_factory=list)

    @property
    def duration(self) -> str:
        if self.started_at is None:
            return "-"
        end = self.finished_at or datetime.now()
        s = int((end - self.started_at).total_seconds())
        return f"{s}s" if s < 60 else f"{s // 60}m{s % 60}s"


@dataclass
class PermissionRequest:
    job_id: str
    tool_name: str
    arguments: dict
    future: asyncio.Future
    created_at: datetime = field(default_factory=datetime.now)


class AgentRuntime:
    """Central coordinator: worker pool, schedulers, file watchers, permission broker."""

    def __init__(
        self,
        workflows: list[Workflow],
        personas: dict[str, Persona],
        base_tools: ToolRegistry,
        num_workers: int = 4,
        workdir: str = ".",
    ) -> None:
        self.workflows: dict[str, Workflow] = {w.name: w for w in workflows}
        self.personas = personas
        self.base_tools = base_tools
        self.workdir = workdir
        self.num_workers = num_workers
        self.started_at = datetime.now()

        self.jobs: dict[str, AgentJob] = {}
        self.event_log: deque[str] = deque(maxlen=200)
        self.perm_requests: dict[str, PermissionRequest] = {}

        self._queue: asyncio.Queue[AgentJob] = asyncio.Queue()
        self._scheduler = AsyncScheduler()
        self._bus = EventBus()
        self._stop_event = asyncio.Event()
        self._worker_tasks: list[asyncio.Task] = []
        self._trigger_tasks: list[asyncio.Task] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start workers and wire up all workflow triggers."""
        for i in range(self.num_workers):
            t = asyncio.create_task(self._worker(i))
            self._worker_tasks.append(t)

        for workflow in self.workflows.values():
            if not workflow.enabled:
                continue
            for trigger in workflow.triggers:
                if trigger.type == TriggerType.SCHEDULE:
                    interval = _parse_interval(trigger.interval or "1h")

                    async def _fire(wf: Workflow = workflow) -> None:
                        await self._enqueue_workflow(wf, trigger_info="scheduled")

                    self._scheduler.add_job(f"{workflow.name}_schedule", interval, _fire)
                elif trigger.type == TriggerType.WATCH:
                    t = asyncio.create_task(self._run_watcher(workflow, trigger))
                    self._trigger_tasks.append(t)
                elif trigger.type == TriggerType.EVENT:
                    t = asyncio.create_task(self._run_event_trigger(workflow, trigger))
                    self._trigger_tasks.append(t)

        await self._scheduler.start()
        self._log("runtime started")

    async def stop(self) -> None:
        """Gracefully stop all tasks."""
        self._stop_event.set()
        await self._scheduler.stop()
        for t in self._trigger_tasks + self._worker_tasks:
            t.cancel()
        self._log("runtime stopped")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def trigger_manual(self, workflow_name: str) -> str:
        """Manually enqueue a workflow. Returns the first job_id."""
        wf = self.workflows.get(workflow_name)
        if not wf:
            raise ValueError(f"Unknown workflow: {workflow_name}")
        return await self._enqueue_workflow(wf, trigger_info="manual")

    async def approve_permission(self, req_id: str, allow: bool) -> None:
        """Resolve a pending permission request."""
        req = self.perm_requests.get(req_id)
        if req and not req.future.done():
            req.future.set_result(allow)

    async def publish_event(self, topic: str, payload: dict) -> None:
        """Publish a payload to the internal event bus."""
        await self._bus.publish(topic, payload)

    @property
    def queued_count(self) -> int:
        """Number of jobs currently queued."""
        return self._queue.qsize()

    @property
    def uptime(self) -> str:
        """Human-readable uptime string."""
        delta = int((datetime.now() - self.started_at).total_seconds())
        h, rem = divmod(delta, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    @property
    def pending_permissions(self) -> list[PermissionRequest]:
        """List of pending permission requests."""
        return list(self.perm_requests.values())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.event_log.appendleft(f"{ts}  {msg}")

    async def _enqueue_workflow(
        self,
        workflow: Workflow,
        trigger_info: str = "",
        template_vars: dict | None = None,
    ) -> str:
        """Create jobs for all steps and enqueue them."""
        vars_: dict = template_vars or {}

        first_id = ""
        for step in workflow.steps:
            job = self._make_job(workflow, step, trigger_info, vars_)
            self.jobs[job.id] = job
            await self._queue.put(job)
            if not first_id:
                first_id = job.id
        return first_id

    def _make_job(self, workflow: Workflow, step, trigger_info: str, vars_: dict) -> AgentJob:
        task = step.task
        for k, v in vars_.items():
            task = task.replace("{" + k + "}", str(v))
        task = task.replace("{timestamp}", datetime.now().isoformat())
        return AgentJob(
            id=uuid.uuid4().hex[:8],
            workflow_name=workflow.name,
            step_name=step.name,
            persona_name=step.persona,
            task=task,
            workspace=step.workspace,
            trigger_info=trigger_info,
        )

    async def _worker(self, worker_id: int) -> None:
        while not self._stop_event.is_set():
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            await self._execute_job(job)
            self._queue.task_done()

    async def _execute_job(self, job: AgentJob) -> None:
        from agent_framework.core.agent import (
            Agent,
            AssistantTextEvent,
            ToolCallEvent,
            ToolResultEvent,
        )
        from agent_framework.core.orchestrator import Orchestrator
        from agent_framework.core.session import Session

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        self._log(f"[{job.workflow_name}/{job.step_name}] started: {job.task[:60]}")

        persona = self.personas.get(job.persona_name) or next(iter(self.personas.values()))

        workflow = self.workflows.get(job.workflow_name)
        perm_mode = workflow.permission if workflow else PermissionMode.ASK
        if perm_mode == PermissionMode.AUTOPILOT:
            gate: PermissionGate = always_allow()
        elif perm_mode == PermissionMode.WORKSPACE:
            gate = workspace_gate(job.workspace)
        else:
            gate = self._make_broker_gate(job)

        orch = Orchestrator(
            base_tools=self.base_tools,
            base_permission_gate=gate,
            workdir=job.workspace,
        )
        agent = Agent.from_persona(persona, self.base_tools, gate, job.workspace)
        agent._orchestrator = orch

        session = Session.with_system_prompt(persona.system_prompt)
        try:
            async for ev in agent.run_turn(session, job.task):
                if isinstance(ev, ToolCallEvent):
                    job.events_seen.append(f"  -> {ev.tool_call.name}")
                elif isinstance(ev, ToolResultEvent):
                    short = ev.result[:80].replace("\n", " ")
                    status_char = "x" if ev.is_error else "v"
                    job.events_seen.append(f"  {status_char} {ev.tool_name}: {short}")
                    self._log(f"[{job.step_name}] {status_char} {ev.tool_name}")
                elif isinstance(ev, AssistantTextEvent):
                    job.result = ev.text

            if job.result is None:
                job.result = "done"
            job.status = JobStatus.DONE
            self._log(f"[{job.workflow_name}/{job.step_name}] done")
        except Exception as exc:
            job.error = str(exc)
            job.status = JobStatus.FAILED
            self._log(f"[{job.workflow_name}/{job.step_name}] failed: {exc}")
        finally:
            job.finished_at = datetime.now()

    def _make_broker_gate(self, job: AgentJob) -> PermissionGate:
        """Create a permission gate that routes requests through the interactive broker."""
        runtime = self

        class BrokerGate(PermissionGate):
            def __init__(self) -> None:
                super().__init__()

            async def check(self, tool, arguments: dict) -> PermissionDecision:  # type: ignore[override]
                if not tool.requires_permission:
                    return PermissionDecision.ALLOW
                req_id = uuid.uuid4().hex[:6]
                loop = asyncio.get_running_loop()
                future: asyncio.Future = loop.create_future()
                req = PermissionRequest(
                    job_id=job.id,
                    tool_name=tool.name,
                    arguments=arguments,
                    future=future,
                )
                runtime.perm_requests[req_id] = req
                job.status = JobStatus.WAITING_PERM
                runtime._log(f"[{job.step_name}] permission needed: {tool.name}")
                try:
                    allow = await asyncio.wait_for(asyncio.shield(future), timeout=60.0)
                    return PermissionDecision.ALLOW if allow else PermissionDecision.DENY
                except TimeoutError:
                    runtime._log(f"[{job.step_name}] permission timeout -> denied")
                    return PermissionDecision.DENY
                finally:
                    runtime.perm_requests.pop(req_id, None)
                    if job.status == JobStatus.WAITING_PERM:
                        job.status = JobStatus.RUNNING

        return BrokerGate()

    async def _run_watcher(self, workflow: Workflow, trigger) -> None:
        path = trigger.path or "."
        pattern = trigger.pattern or "*"
        wanted_events = set(trigger.events or ["created", "modified"])
        watcher = FileWatcher(path, pattern, list(wanted_events))
        self._log(f"[watcher] watching {path}/{pattern}")
        async for event in watcher.watch():
            if self._stop_event.is_set():
                break
            if event.type in wanted_events:
                self._log(f"[watcher] {event.type}: {event.path}")
                vars_: dict = {
                    "file": event.path,
                    "file_name": os.path.basename(event.path),
                    "file_stem": os.path.splitext(os.path.basename(event.path))[0],
                    "event_type": event.type,
                }
                await self._enqueue_workflow(
                    workflow,
                    trigger_info=f"{event.type}: {event.path}",
                    template_vars=vars_,
                )

    async def _run_event_trigger(self, workflow: Workflow, trigger) -> None:
        topic = trigger.topic or trigger.event_topic or ""
        queue = await self._bus.subscribe(topic)
        while not self._stop_event.is_set():
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=1.0)
                await self._enqueue_workflow(
                    workflow,
                    trigger_info=f"event:{topic}",
                    template_vars=payload,
                )
            except TimeoutError:
                continue
