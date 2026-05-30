"""Tests for scripts/install_git_hooks.py (opt-in pre-push gate hook installer).

These exercise the installer against a throwaway hooks directory so they never
touch the real .git/hooks, and assert the shipped pre-push hook actually invokes
the aggregate gate (scripts/validate_release_status.py) rather than inventing a
parallel check.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALLER = REPO_ROOT / "scripts" / "install_git_hooks.py"
HOOK = REPO_ROOT / "scripts" / "githooks" / "pre-push"

_spec = importlib.util.spec_from_file_location("install_git_hooks", INSTALLER)
ig = importlib.util.module_from_spec(_spec)
sys.modules["install_git_hooks"] = ig
_spec.loader.exec_module(ig)


def test_source_hook_exists_and_runs_the_aggregate_gate():
    assert HOOK.exists()
    body = HOOK.read_text(encoding="utf-8")
    # The whole point: it triggers the EXISTING aggregate gate, no new checks.
    assert "scripts/validate_release_status.py" in body
    assert "--no-verify" in body  # documents the intentional bypass


def test_install_check_uninstall_roundtrip(tmp_path, monkeypatch):
    fake_hooks = tmp_path / "hooks"
    monkeypatch.setattr(ig, "_hooks_dir", lambda: fake_hooks)

    assert ig.check() == 1            # not installed yet
    assert ig.install() == 0
    installed = fake_hooks / "pre-push"
    assert installed.exists()
    assert ig.MARKER in installed.read_text(encoding="utf-8")
    assert ig.check() == 0            # now installed
    assert ig.uninstall() == 0
    assert not installed.exists()
    assert ig.check() == 1            # gone again


def test_install_is_idempotent(tmp_path, monkeypatch):
    fake_hooks = tmp_path / "hooks"
    monkeypatch.setattr(ig, "_hooks_dir", lambda: fake_hooks)
    assert ig.install() == 0
    assert ig.install() == 0          # second run must not error
    assert ig.check() == 0


def test_uninstall_leaves_foreign_hook_untouched(tmp_path, monkeypatch):
    fake_hooks = tmp_path / "hooks"
    fake_hooks.mkdir(parents=True)
    foreign = fake_hooks / "pre-push"
    foreign.write_text("#!/bin/sh\necho someone elses hook\n", encoding="utf-8")
    monkeypatch.setattr(ig, "_hooks_dir", lambda: fake_hooks)
    # uninstall must only remove hooks carrying our MARKER, never a foreign one.
    assert ig.uninstall() == 0
    assert foreign.exists()
    assert "someone elses hook" in foreign.read_text(encoding="utf-8")
