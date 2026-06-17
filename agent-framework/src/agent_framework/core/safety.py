"""Safety guards — give apathy discernment about risky operations.

These helpers let tools and the CLI reason about *how dangerous* an action is
before doing it: refuse to touch protected system folders, flag destructive
operations (move/delete/cloud-move), and warn on very large batches. This is
the "discernment" layer — apathy thinks before it acts.
"""
from __future__ import annotations

from pathlib import Path

# Protected locations that must never be bulk-modified, organized or deleted.
_PROTECTED_UNIX = (
    "/", "/etc", "/usr", "/bin", "/sbin", "/lib", "/lib64", "/boot", "/dev",
    "/proc", "/sys", "/var", "/root", "/opt", "/srv",
)
_PROTECTED_WINDOWS = (
    "c:\\windows", "c:\\program files", "c:\\program files (x86)",
    "c:\\programdata", "c:\\system volume information", "c:\\$recycle.bin",
)

# Risk levels, ordered from safest to most dangerous.
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_BLOCKED = "blocked"

_DESTRUCTIVE = frozenset({"move", "delete", "cloud_move", "sync"})


def is_protected_path(path: str | Path) -> bool:
    """Return True if *path* is a system/protected location (or the home root).

    Detects Windows system paths (by drive-letter pattern) on ANY host OS, so the
    guard behaves identically whether apathy runs on Windows, macOS or Linux.
    """
    raw = str(path)

    # Windows-style absolute path (e.g. "C:\\Windows") — detect by drive letter
    # regardless of the OS apathy is running on, so backslash paths aren't
    # mis-parsed as relative on POSIX hosts.
    if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha():
        win_s = raw.replace("/", "\\").lower().rstrip("\\")
        for prot in _PROTECTED_WINDOWS:
            if win_s == prot or win_s.startswith(prot + "\\"):
                return True
        return False

    p = Path(path).expanduser()
    try:
        resolved = p.resolve()
    except (OSError, RuntimeError):
        resolved = p

    # Unix absolute roots
    unix_s = str(resolved).rstrip("/") or "/"
    for prot in _PROTECTED_UNIX:
        prot_clean = prot.rstrip("/") or "/"
        if unix_s == prot_clean:
            return True

    # The home directory *root itself* is too broad to bulk-operate on
    # (but its subfolders like ~/Downloads are fine).
    home = str(Path.home())
    if str(resolved).rstrip("/\\").lower() == home.rstrip("/\\").lower():
        return True

    return False


def assess_risk(operation: str, path: str | Path, count: int = 0) -> tuple[str, str]:
    """Assess how risky an operation is.

    Returns ``(risk_level, human_reason)`` where risk_level is one of
    ``low | medium | high | blocked``.
    """
    if is_protected_path(path):
        return RISK_BLOCKED, f"'{path}' is a protected system location — refusing to touch it"
    if operation in _DESTRUCTIVE and count > 200:
        return RISK_HIGH, f"{operation} would affect {count} files (large batch)"
    if operation in _DESTRUCTIVE:
        return RISK_MEDIUM, f"{operation} is destructive — originals change or leave their place"
    return RISK_LOW, "read-only or safe in-place operation"


def guard(operation: str, path: str | Path, count: int = 0) -> None:
    """Raise ValueError if the operation targets a protected path."""
    level, reason = assess_risk(operation, path, count)
    if level == RISK_BLOCKED:
        raise ValueError(reason)
