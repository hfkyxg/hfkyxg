from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator


class PermissionRuleConfig(BaseModel):
    tool: str
    decision: str  # "allow" | "deny" | "ask"
    when_method_in: list[str] | None = None


class Persona(BaseModel):
    name: str
    system_prompt: str
    provider: str  # litellm "provider/model" string
    enabled_tools: list[str]  # tool names; ["*"] means all registered
    permission_overrides: list[PermissionRuleConfig] = []
    max_iterations: int = 25
    temperature: float = 0.0

    @field_validator("enabled_tools", mode="before")
    @classmethod
    def normalize_tools(cls, v: Any) -> list[str]:
        if v == "*":
            return ["*"]
        return v

    @classmethod
    def from_yaml(cls, path: Path) -> "Persona":
        data = yaml.safe_load(path.read_text())
        return cls(**data)

    def allows_all_tools(self) -> bool:
        return self.enabled_tools == ["*"]
