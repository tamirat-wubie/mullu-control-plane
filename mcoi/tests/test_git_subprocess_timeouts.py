"""Robustness: git subprocesses are bounded by a timeout and handled gracefully.

A hung git (network fetch, credential prompt, locked index) could otherwise hang
change-assurance / code-intelligence indefinitely (the global exception handler
bounds raised exceptions but cannot bound a hang). Each git call now passes
timeout=, and subprocess.TimeoutExpired is handled -- raised as a governed
invariant error for required calls, or degraded to None / "unknown" for optional
lookups.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mcoi_runtime.core import change_assurance, code_intelligence
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


def _raise_timeout(*args, **kwargs):
    raise subprocess.TimeoutExpired(cmd="git", timeout=30)


def test_run_git_raises_governed_error_on_timeout(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _raise_timeout)
    with pytest.raises(RuntimeCoreInvariantError, match="timed out"):
        change_assurance._run_git(Path("."), ["rev-parse", "HEAD"])


def test_optional_git_returns_none_on_timeout(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _raise_timeout)
    assert change_assurance._optional_git(Path("."), ["rev-parse", "HEAD"]) is None


def test_git_file_list_returns_none_on_timeout(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _raise_timeout)
    assert code_intelligence._git_file_list(Path(".")) is None


def test_resolve_commit_sha_unknown_on_timeout(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _raise_timeout)
    assert code_intelligence._resolve_commit_sha(Path(".")) == "unknown"
