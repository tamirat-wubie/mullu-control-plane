"""Phase 194 — Adversarial tests for Execution Authority / Bypass Prevention.

Purpose: verify that the entry-point registry correctly identifies all governed,
    legacy, and bypass paths, and that the authority token model is structurally sound.
Governance scope: coverage closure enforcement.
Dependencies: execution_authority module.
Invariants: every execution-capable surface is inventoried; legacy paths are honestly
    flagged as violations; internal-safe paths are not violations.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.core.execution_authority import (
    EntryPointRegistry,
    ExecutionAuthority,
    ExecutionAuthorityError,
    build_known_registry,
)


# ─── 1. Authority token verification ───


def test_authority_token_verification():
    """A well-formed token must verify; a token with empty fields must not."""
    valid = ExecutionAuthority(
        authority_id="auth-001",
        actor_id="actor-a",
        intent_hash="sha256:abc123",
        gates_passed=("identity", "prediction", "economics"),
        issued_at="2026-03-26T12:00:00+00:00",
    )
    assert valid.verify() is True

    empty_id = ExecutionAuthority(
        authority_id="",
        actor_id="actor-a",
        intent_hash="sha256:abc123",
        gates_passed=("identity",),
        issued_at="2026-03-26T12:00:00+00:00",
    )
    assert empty_id.verify() is False

    empty_gates = ExecutionAuthority(
        authority_id="auth-002",
        actor_id="actor-b",
        intent_hash="sha256:def456",
        gates_passed=(),
        issued_at="2026-03-26T12:00:00+00:00",
    )
    assert empty_gates.verify() is False


# ─── 2. ExecutionAuthorityError is a proper exception ───


def test_authority_error_raised_without_context():
    """ExecutionAuthorityError must be catchable as a standard Exception."""
    with pytest.raises(ExecutionAuthorityError):
        raise ExecutionAuthorityError("no authority context present")


# ─── 3. Registry detects ungoverned paths ───


def test_registry_ungoverned_paths_detected():
    """build_known_registry must flag legacy execution paths as ungoverned violations."""
    reg = build_known_registry()
    violations = reg.ungoverned_production_paths()
    assert len(violations) > 0, "Expected at least one ungoverned production path"
    violation_paths = {v.path for v in violations}
    assert "core.dispatcher.Dispatcher.dispatch" in violation_paths


# ─── 4. Coverage score is honestly < 1.0 ───


def test_registry_coverage_score_not_100():
    """Coverage must be below 100% because legacy paths exist."""
    reg = build_known_registry()
    score = reg.coverage_score()
    assert 0.0 < score < 1.0, f"Expected partial coverage, got {score}"


# ─── 5. dispatcher.dispatch flagged as violation ───


def test_registry_violations_list_legacy_execution():
    """The raw dispatcher.dispatch must appear in the violations list."""
    reg = build_known_registry()
    violations = reg.ungoverned_production_paths()
    paths = [v.path for v in violations]
    assert "core.dispatcher.Dispatcher.dispatch" in paths


# ─── 6. Persistence paths are NOT violations ───


def test_registry_internal_safe_not_violations():
    """Persistence and event-spine paths must not appear as violations."""
    reg = build_known_registry()
    violations = reg.ungoverned_production_paths()
    violation_paths = {v.path for v in violations}
    safe_paths = [
        "persistence.trace_store.TraceStore.append",
        "persistence.replay_store.ReplayStore.save",
        "persistence.snapshot_store.SnapshotStore.save",
        "persistence.memory_store.MemoryStore.save",
        "persistence.coordination_store.CoordinationStore.save_state",
        "core.event_spine.EventSpineEngine.emit",
    ]
    for sp in safe_paths:
        assert sp not in violation_paths, f"{sp} should not be a violation"


# ─── 7. Coverage matrix structure ───


def test_coverage_matrix_structure():
    """The coverage matrix must contain all expected keys with correct types."""
    reg = build_known_registry()
    matrix = reg.coverage_matrix()
    expected_keys = {
        "total_entries",
        "governed",
        "legacy",
        "bypass",
        "internal_safe",
        "violations",
        "coverage_score",
    }
    assert set(matrix.keys()) == expected_keys
    assert isinstance(matrix["total_entries"], int)
    assert isinstance(matrix["coverage_score"], float)
    assert matrix["total_entries"] > 0


# ─── 8. Governed path is registered ───


def test_governed_path_is_registered():
    """GovernedDispatcher.governed_dispatch must be in the registry as 'governed'."""
    reg = build_known_registry()
    entry = reg.get(
        "core.governed_dispatcher.GovernedDispatcher.governed_dispatch"
    )
    assert entry is not None
    assert entry.routing == "governed"
    assert entry.effect_type == "execution"


# ─── 9. Operator loop paths are flagged as legacy ───


def test_operator_loop_paths_are_legacy():
    """All operator-loop entry points must be flagged as legacy."""
    reg = build_known_registry()
    op_paths = [
        "app.operator_loop.OperatorLoop.run_step",
        "app.operator_requests.run_skill_step",
        "app.operator_workflows.run_workflow_step",
        "app.operator_goals.run_goal_step",
    ]
    for path in op_paths:
        entry = reg.get(path)
        assert entry is not None, f"Missing registry entry: {path}"
        assert entry.routing == "legacy", f"{path} should be legacy, got {entry.routing}"
        assert entry.governed_required is True


# ─── 10. Adapter paths are flagged as legacy ───


def test_adapter_paths_are_legacy():
    """Direct adapter execution surfaces must be flagged as legacy."""
    reg = build_known_registry()
    adapter_paths = [
        "adapters.shell_executor.ShellExecutor.execute",
        "adapters.http_connector.HttpConnector.fetch",
        "adapters.smtp_communication.SmtpChannel.send",
        "adapters.browser_adapter.BrowserAdapter.run",
        "adapters.stub_model.StubModelAdapter.generate",
        "adapters.process_model.ProcessModelAdapter.generate",
        "adapters.code_adapter.LocalCodeAdapter.run_build",
    ]
    for path in adapter_paths:
        entry = reg.get(path)
        assert entry is not None, f"Missing registry entry: {path}"
        assert entry.routing == "legacy", f"{path} should be legacy, got {entry.routing}"
        assert entry.effect_type == "external"


# ─── 11. No paths classified as "bypass" ───


def test_zero_bypass_paths():
    """No paths should be classified as 'bypass' — honest 'legacy' labelling only."""
    reg = build_known_registry()
    matrix = reg.coverage_matrix()
    assert matrix["bypass"] == 0, "Expected zero bypass paths; all ungoverned should be legacy"


# ─── 12. Golden coverage report ───


def test_golden_coverage_report():
    """Full coverage report showing current honest state of governance routing."""
    reg = build_known_registry()
    matrix = reg.coverage_matrix()

    # Structural expectations
    assert matrix["governed"] >= 1, "Must have at least one governed path"
    assert matrix["legacy"] >= 10, "Must have at least 10 legacy paths (honest inventory)"
    assert matrix["internal_safe"] >= 5, "Must have at least 5 internal-safe paths"
    assert matrix["violations"] >= 10, "Must report at least 10 violations (legacy governed-required)"
    assert matrix["coverage_score"] < 0.15, (
        f"Coverage score {matrix['coverage_score']} is suspiciously high — "
        "indicates legacy paths are being undercounted"
    )

    # Print the report for visibility
    print("\n=== Phase 194 — Governance Coverage Report ===")
    for k, v in matrix.items():
        print(f"  {k}: {v}")
    violations = reg.ungoverned_production_paths()
    print(f"\n  Ungoverned production paths ({len(violations)}):")
    for v in violations:
        print(f"    [{v.effect_type}] {v.path} (routing={v.routing})")
    print("=== End Report ===\n")
