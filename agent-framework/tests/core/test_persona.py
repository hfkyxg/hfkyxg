"""Tests for Persona: YAML loading, validation, tool list helpers."""
from __future__ import annotations

from pathlib import Path

import yaml

from agent_framework.core.persona import Persona


def write_persona(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "persona.yaml"
    p.write_text(yaml.dump(data))
    return p


class TestPersonaFromYaml:
    def test_loads_minimal_valid_persona(self, tmp_path):
        p = write_persona(tmp_path, {
            "name": "tester",
            "system_prompt": "You are a test bot.",
            "provider": "anthropic/claude-sonnet-4-6",
            "enabled_tools": ["read_file", "bash"],
        })
        persona = Persona.from_yaml(p)
        assert persona.name == "tester"
        assert persona.provider == "anthropic/claude-sonnet-4-6"
        assert persona.enabled_tools == ["read_file", "bash"]

    def test_default_values_applied(self, tmp_path):
        p = write_persona(tmp_path, {
            "name": "test",
            "system_prompt": "s",
            "provider": "openai/gpt-4o",
            "enabled_tools": ["*"],
        })
        persona = Persona.from_yaml(p)
        assert persona.max_iterations == 25
        assert persona.temperature == 0.0
        assert persona.permission_overrides == []

    def test_custom_max_iterations(self, tmp_path):
        p = write_persona(tmp_path, {
            "name": "limited",
            "system_prompt": "s",
            "provider": "openai/gpt-4o",
            "enabled_tools": ["read_file"],
            "max_iterations": 5,
        })
        persona = Persona.from_yaml(p)
        assert persona.max_iterations == 5

    def test_real_default_persona_file(self):
        path = Path(__file__).parent.parent.parent / "personas" / "default.yaml"
        assert path.exists(), "personas/default.yaml not found"
        persona = Persona.from_yaml(path)
        assert persona.name == "default"
        assert "anthropic" in persona.provider

    def test_real_researcher_persona_file(self):
        path = Path(__file__).parent.parent.parent / "personas" / "researcher.yaml"
        assert path.exists(), "personas/researcher.yaml not found"
        persona = Persona.from_yaml(path)
        assert persona.name == "researcher"
        assert "write_file" not in persona.enabled_tools
        assert "bash" not in persona.enabled_tools


class TestPersonaHelpers:
    def test_allows_all_tools_with_star(self, tmp_path):
        p = write_persona(tmp_path, {
            "name": "t", "system_prompt": "s",
            "provider": "openai/gpt-4o", "enabled_tools": ["*"],
        })
        assert Persona.from_yaml(p).allows_all_tools() is True

    def test_does_not_allow_all_with_explicit_list(self, tmp_path):
        p = write_persona(tmp_path, {
            "name": "t", "system_prompt": "s",
            "provider": "openai/gpt-4o", "enabled_tools": ["read_file"],
        })
        assert Persona.from_yaml(p).allows_all_tools() is False
