"""Tests for scripts/gate_merge.py (settled-merge barrier)."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "gate_merge.py"
CORPUS = REPO_ROOT / "tests" / "fixtures" / "gate_merge" / "corpus.json"

_spec = importlib.util.spec_from_file_location("gate_merge", SCRIPT)
gate_merge = importlib.util.module_from_spec(_spec)
# Register before exec so @dataclass can resolve sys.modules[cls.__module__].
sys.modules["gate_merge"] = gate_merge
_spec.loader.exec_module(gate_merge)
evaluate_merge_gate = gate_merge.evaluate_merge_gate


def _green_state():
    return {
        "pr_state": "OPEN", "mergeable": "MERGEABLE",
        "pr_head": "abc123", "remote_tip": "abc123", "expected_head": "abc123",
        "checks": [{"name": "A", "state": "SUCCESS"}, {"name": "B", "state": "SUCCESS"}],
    }


def test_fully_settled_green_is_allowed():
    d = evaluate_merge_gate(_green_state())
    assert d.allowed, d.reasons


def test_pending_check_blocks():
    s = _green_state()
    s["checks"][1]["state"] = "IN_PROGRESS"
    d = evaluate_merge_gate(s)
    assert not d.allowed
    assert any("not settled" in r for r in d.reasons)


def test_failing_check_blocks():
    s = _green_state()
    s["checks"][0]["state"] = "FAILURE"
    d = evaluate_merge_gate(s)
    assert not d.allowed
    assert any("not green" in r for r in d.reasons)


def test_moved_branch_blocks():
    s = _green_state()
    s["expected_head"] = "old999"  # operator verified an older commit
    d = evaluate_merge_gate(s)
    assert not d.allowed
    assert any("drift since verification" in r for r in d.reasons)


def test_remote_tip_divergence_blocks():
    s = _green_state()
    s["remote_tip"] = "newpush777"  # branch advanced past what CI ran on
    d = evaluate_merge_gate(s)
    assert not d.allowed
    assert any("branch moved" in r for r in d.reasons)


def test_already_merged_blocks():
    s = _green_state()
    s["pr_state"] = "MERGED"
    d = evaluate_merge_gate(s)
    assert not d.allowed


def test_zero_checks_blocks():
    s = _green_state()
    s["checks"] = []
    d = evaluate_merge_gate(s)
    assert not d.allowed
    assert any("zero CI signal" in r for r in d.reasons)


def test_conflicting_blocks():
    s = _green_state()
    s["mergeable"] = "CONFLICTING"
    d = evaluate_merge_gate(s)
    assert not d.allowed


def test_malformed_state_blocks():
    d = evaluate_merge_gate({"pr_state": "OPEN"})
    assert not d.allowed
    assert any("malformed" in r for r in d.reasons)


def test_calibration_corpus_reproduces_all_decisions():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--calibrate", str(CORPUS)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CALIBRATION PASS" in proc.stdout
