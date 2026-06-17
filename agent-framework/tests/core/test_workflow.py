"""Tests for Workflow model loading and parsing."""
from __future__ import annotations

import pytest
import yaml

from agent_framework.core.scheduler import _parse_interval
from agent_framework.core.workflow import TriggerType, Workflow


class TestWorkflowLoadYaml:
    def test_workflow_load_yaml(self, tmp_path):
        data = {
            "name": "test_wf",
            "description": "A test workflow",
            "enabled": True,
            "triggers": [{"type": "schedule", "interval": "5m"}],
            "steps": [{"name": "step1", "persona": "demo", "task": "do something"}],
            "permission": "autopilot",
        }
        p = tmp_path / "wf.yaml"
        p.write_text(yaml.dump(data))

        wf = Workflow.from_yaml(p)
        assert wf.name == "test_wf"
        assert wf.description == "A test workflow"
        assert wf.enabled is True
        assert len(wf.triggers) == 1
        assert wf.triggers[0].type == TriggerType.SCHEDULE
        assert wf.triggers[0].interval == "5m"
        assert len(wf.steps) == 1
        assert wf.steps[0].name == "step1"
        assert wf.steps[0].persona == "demo"
        assert wf.permission.value == "autopilot"

    def test_workflow_defaults(self, tmp_path):
        data = {
            "name": "minimal",
            "triggers": [{"type": "manual"}],
            "steps": [{"name": "s", "task": "t"}],
        }
        p = tmp_path / "min.yaml"
        p.write_text(yaml.dump(data))
        wf = Workflow.from_yaml(p)
        assert wf.enabled is True
        assert wf.parallel is False
        assert wf.steps[0].persona == "demo"
        assert wf.steps[0].workspace == "."
        assert wf.steps[0].timeout == 300


class TestWorkflowLoadDir:
    def test_workflow_load_dir(self, tmp_path):
        for i in range(3):
            data = {
                "name": f"wf_{i}",
                "triggers": [{"type": "manual"}],
                "steps": [{"name": "step", "task": "task text"}],
            }
            (tmp_path / f"wf_{i}.yaml").write_text(yaml.dump(data))

        workflows = Workflow.load_dir(tmp_path)
        assert len(workflows) == 3
        names = {w.name for w in workflows}
        assert names == {"wf_0", "wf_1", "wf_2"}

    def test_workflow_load_dir_nonexistent(self, tmp_path):
        result = Workflow.load_dir(tmp_path / "does_not_exist")
        assert result == []

    def test_workflow_load_dir_skips_malformed(self, tmp_path):
        (tmp_path / "bad.yaml").write_text("not: valid: workflow: content")
        data = {
            "name": "good",
            "triggers": [{"type": "manual"}],
            "steps": [{"name": "step", "task": "t"}],
        }
        (tmp_path / "good.yaml").write_text(yaml.dump(data))
        workflows = Workflow.load_dir(tmp_path)
        assert len(workflows) == 1
        assert workflows[0].name == "good"

    def test_load_all_alias(self, tmp_path):
        data = {
            "name": "via_load_all",
            "triggers": [{"type": "manual"}],
            "steps": [{"name": "step", "task": "t"}],
        }
        (tmp_path / "wf.yaml").write_text(yaml.dump(data))
        result = Workflow.load_all(tmp_path)
        assert len(result) == 1
        assert result[0].name == "via_load_all"


class TestTriggerParseInterval:
    @pytest.mark.parametrize(
        "interval, expected",
        [
            ("5m", 300.0),
            ("1h", 3600.0),
            ("30s", 30.0),
            ("1d", 86400.0),
            ("60", 60.0),
            ("2h", 7200.0),
            ("10m", 600.0),
        ],
    )
    def test_parse_interval(self, interval, expected):
        assert _parse_interval(interval) == expected

    def test_parse_interval_invalid(self):
        with pytest.raises(ValueError):
            _parse_interval("invalid")


class TestWorkflowTemplateVars:
    def test_task_template_vars(self, tmp_path):
        data = {
            "name": "templated",
            "triggers": [{"type": "watch", "path": ".", "pattern": "*.py"}],
            "steps": [
                {
                    "name": "step",
                    "task": "process {file} ({file_name}) event: {event_type}",
                    "persona": "demo",
                }
            ],
        }
        p = tmp_path / "templated.yaml"
        p.write_text(yaml.dump(data))
        wf = Workflow.from_yaml(p)
        task_template = wf.steps[0].task
        # Simulate template substitution
        vars_ = {"file": "/src/main.py", "file_name": "main.py", "event_type": "modified"}
        result = task_template
        for k, v in vars_.items():
            result = result.replace("{" + k + "}", v)
        assert result == "process /src/main.py (main.py) event: modified"
