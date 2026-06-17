"""Workflow model — Pydantic + YAML loader."""
from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class TriggerType(StrEnum):
    SCHEDULE = "schedule"
    WATCH = "watch"
    MANUAL = "manual"
    EVENT = "event"


class WorkflowTrigger(BaseModel):
    type: TriggerType
    # schedule
    interval: str | None = None  # "5m", "1h", "30s"
    cron: str | None = None       # "0 9 * * *"
    # watch
    path: str | None = None
    pattern: str = "*"
    events: list[str] = Field(default_factory=lambda: ["created", "modified"])
    # event (pub/sub)
    topic: str | None = None


class WorkflowStep(BaseModel):
    name: str
    persona: str = "demo"  # persona name or path relative to personas/
    task: str              # prompt template; {file}, {event}, {workflow} are substituted
    workspace: str = "."


class PermissionMode(StrEnum):
    AUTOPILOT = "autopilot"  # allow everything
    ASK = "ask"              # always ask
    WORKSPACE = "workspace"  # auto inside workspace, ask outside


class Workflow(BaseModel):
    name: str
    description: str = ""
    triggers: list[WorkflowTrigger] = Field(default_factory=list)
    steps: list[WorkflowStep] = Field(default_factory=list)
    parallel: bool = False
    permission: PermissionMode = PermissionMode.WORKSPACE
    max_retries: int = 1
    timeout_seconds: int = 300

    @classmethod
    def from_yaml(cls, path: str | Path) -> Workflow:
        data: dict[str, Any] = yaml.safe_load(Path(path).read_text())
        return cls.model_validate(data)

    @classmethod
    def load_all(cls, workflows_dir: str | Path) -> list[Workflow]:
        d = Path(workflows_dir)
        if not d.is_dir():
            return []
        workflows = []
        for p in sorted(d.glob("*.yaml")):
            try:
                workflows.append(cls.from_yaml(p))
            except Exception:
                pass
        return workflows
