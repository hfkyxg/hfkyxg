"""Tests for the safety guards: protected paths, risk assessment, guard()."""
from __future__ import annotations

import pytest

from agent_framework.core.safety import (
    RISK_BLOCKED,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    assess_risk,
    guard,
    is_protected_path,
)


class TestIsProtectedPath:
    def test_etc_is_protected(self):
        assert is_protected_path("/etc") is True

    def test_root_is_protected(self):
        assert is_protected_path("/") is True

    def test_usr_is_protected(self):
        assert is_protected_path("/usr") is True

    # Windows system paths are detected by drive-letter pattern on ANY host OS,
    # so these hold on Linux/macOS too (not just on a real Windows machine).
    def test_windows_dir_is_protected(self):
        assert is_protected_path("C:\\Windows") is True

    def test_windows_system32_prefix_match(self):
        assert is_protected_path("C:\\Windows\\System32") is True

    def test_windows_program_files_is_protected(self):
        assert is_protected_path("C:\\Program Files") is True

    def test_windows_forward_slash_variant(self):
        assert is_protected_path("C:/Windows/System32") is True

    def test_windows_user_folder_not_protected(self):
        assert is_protected_path("C:\\Users\\Frank\\Videos") is False

    def test_user_tmp_folder_not_protected(self):
        assert is_protected_path("/tmp/some_user_folder") is False

    def test_home_subfolder_not_protected(self):
        assert is_protected_path("/home/user/Downloads") is False


class TestAssessRisk:
    def test_move_medium_batch(self):
        result = assess_risk("move", "/tmp/foo", count=5)
        assert isinstance(result, tuple)
        level, _reason = result
        assert level == RISK_MEDIUM
        assert level == "medium"

    def test_copy_is_low(self):
        level, _reason = assess_risk("copy", "/tmp/foo")
        assert level == RISK_LOW
        assert level == "low"

    def test_move_protected_is_blocked(self):
        level, _reason = assess_risk("move", "/etc")
        assert level == RISK_BLOCKED
        assert level == "blocked"

    def test_move_large_batch_is_high(self):
        level, _reason = assess_risk("move", "/tmp/foo", count=500)
        assert level == RISK_HIGH
        assert level == "high"


class TestGuard:
    def test_guard_raises_on_protected(self):
        with pytest.raises(ValueError):
            guard("organize", "/etc")

    def test_guard_allows_safe_op(self):
        assert guard("copy", "/tmp/foo") is None
