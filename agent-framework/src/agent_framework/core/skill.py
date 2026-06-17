"""Skills — reusable parameterized agent workflows stored as YAML."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SkillStep:
    name: str
    task: str                          # task template with {param} interpolation
    persona: str = "demo"
    workspace: str = "."
    auto_approve: bool = True


@dataclass
class Skill:
    name: str
    description: str
    params: list[str]                  # required parameter names
    steps: list[SkillStep]
    tags: list[str] = field(default_factory=list)
    author: str = ""
    version: str = "1.0.0"

    @classmethod
    def from_yaml(cls, path: Path) -> Skill:
        with open(path) as f:
            data = yaml.safe_load(f)
        steps = [
            SkillStep(
                name=s["name"],
                task=s["task"],
                persona=s.get("persona", "demo"),
                workspace=s.get("workspace", "."),
                auto_approve=s.get("auto_approve", True),
            )
            for s in data.get("steps", [])
        ]
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            params=data.get("params", []),
            steps=steps,
            tags=data.get("tags", []),
            author=data.get("author", ""),
            version=data.get("version", "1.0.0"),
        )

    @classmethod
    def load_dir(cls, path: Path) -> list[Skill]:
        if not path.is_dir():
            return []
        skills = []
        for f in sorted(path.rglob("*.yaml")):
            try:
                skills.append(cls.from_yaml(f))
            except Exception:
                pass
        return skills

    def render_task(self, step: SkillStep, params: dict[str, str]) -> str:
        task = step.task
        for k, v in params.items():
            task = task.replace(f"{{{k}}}", v)
        return task
