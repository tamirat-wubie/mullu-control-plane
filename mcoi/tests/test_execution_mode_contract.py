"""Execution mode contract tests.

Purpose: verify the shared runtime execution-mode ABI.
Governance scope: backend admission mode classification.
Dependencies: mcoi_runtime.contracts.execution.
Invariants: real and shadow require a backend; replay requires evidence; dry-run, simulation, and test are explicit synthetic modes.
"""

import pytest

from mcoi_runtime.contracts.execution import (
    ExecutionMode,
    coerce_execution_mode,
    execution_mode_allows_synthetic_output,
    execution_mode_requires_backend,
    execution_mode_requires_replay_evidence,
)


def test_execution_mode_coercion_accepts_canonical_values():
    mode = coerce_execution_mode("dry_run")
    assert mode is ExecutionMode.DRY_RUN
    assert mode.value == "dry_run"
    assert coerce_execution_mode(ExecutionMode.REAL) is ExecutionMode.REAL
    assert coerce_execution_mode("replay") is ExecutionMode.REPLAY
    assert coerce_execution_mode("test") is ExecutionMode.TEST


def test_execution_mode_backend_admission_rules_are_explicit():
    assert execution_mode_requires_backend(ExecutionMode.REAL) is True
    assert execution_mode_requires_backend(ExecutionMode.SHADOW) is True
    assert execution_mode_allows_synthetic_output(ExecutionMode.DRY_RUN) is True
    assert execution_mode_allows_synthetic_output(ExecutionMode.SIMULATION) is True
    assert execution_mode_allows_synthetic_output(ExecutionMode.TEST) is True
    assert execution_mode_requires_replay_evidence(ExecutionMode.REPLAY) is True


def test_execution_mode_rejects_unknown_values():
    with pytest.raises(ValueError, match="unknown execution_mode"):
        coerce_execution_mode("stub")
    assert execution_mode_allows_synthetic_output(ExecutionMode.REAL) is False
    assert execution_mode_requires_backend(ExecutionMode.DRY_RUN) is False
    assert execution_mode_allows_synthetic_output(ExecutionMode.REPLAY) is False
    assert execution_mode_requires_backend(ExecutionMode.REPLAY) is False
    assert execution_mode_requires_replay_evidence(ExecutionMode.TEST) is False
