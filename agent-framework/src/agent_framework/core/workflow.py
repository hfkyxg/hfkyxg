"""Workflow model — Pydantic + YAML loader."""
from __future__ import annotations

import os
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


class PermissionMode(StrEnum):
    AUTOPILOT = "autopilot"  # allow everything
    ASK = "ask"              # always ask
    WORKSPACE = "workspace"  # auto inside workspace, ask outside


class WorkflowTrigger(BaseModel):
    type: TriggerType
    # schedule
    interval: str | None = None  # "5m", "1h", "30s"
    cron: str | None = None       # "0 9 * * *"
    # watch
    path: str | None = None
    pattern: str = "*"
    events: list[str] = Field(default_factory=lambda: ["created", "modified"])
    # event (pub/sub) — also aliased as event_topic for spec compatibility
    topic: str | None = None
    event_topic: str | None = None


class WorkflowStep(BaseModel):
    name: str
    persona: str = "demo"  # persona name
    task: str              # prompt template; {file}, {event}, {timestamp} are substituted
    workspace: str = "."
    timeout: int = 300


class Workflow(BaseModel):
    name: str
    description: str = ""
    enabled: bool = True
    triggers: list[WorkflowTrigger] = Field(default_factory=list)
    steps: list[WorkflowStep] = Field(default_factory=list)
    parallel: bool = False
    permission: PermissionMode = PermissionMode.ASK
    max_retries: int = 1
    timeout_seconds: int = 300

    @classmethod
    def from_yaml(cls, path: str | Path) -> Workflow:
        """Load a Workflow from a YAML file."""
        data: dict[str, Any] = yaml.safe_load(Path(path).read_text())
        return cls.model_validate(data)

    @classmethod
    def load_dir(cls, directory: str | Path) -> list[Workflow]:
        """Load all .yaml/.yml files in *directory* as Workflow objects."""
        directory = Path(os.path.expanduser(str(directory)))
        workflows: list[Workflow] = []
        if not directory.is_dir():
            return workflows
        for p in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
            try:
                workflows.append(cls.from_yaml(p))
            except Exception:
                pass  # skip malformed files silently
        return workflows

    @classmethod
    def load_all(cls, workflows_dir: str | Path) -> list[Workflow]:
        """Alias for load_dir — load all workflows from directory."""
        return cls.load_dir(workflows_dir)
