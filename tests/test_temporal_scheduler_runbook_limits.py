"""Purpose: prevent temporal scheduler runbook persistence-boundary drift.
Governance scope: temporal scheduler documentation, persistence evidence, and
lease-boundary status.
Dependencies: docs/61_temporal_scheduler_runbook.md and temporal scheduler
runtime/store/proof source.
Invariants:
  - The runbook distinguishes persisted action snapshots from lease ownership.
  - The runbook keeps multi-process lease ownership outside current closure.
  - The runbook lists every certified scheduler repair transition.
  - The runtime evidence remains aligned with the documented boundary.
"""
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = REPO_ROOT / "docs" / "61_temporal_scheduler_runbook.md"
SCHEDULER = REPO_ROOT / "mcoi" / "mcoi_runtime" / "core" / "temporal_scheduler.py"
PROOF_BRIDGE_TESTS = REPO_ROOT / "mcoi" / "tests" / "test_proof_bridge.py"
STORE = (
    REPO_ROOT
    / "mcoi"
    / "mcoi_runtime"
    / "persistence"
    / "temporal_scheduler_store.py"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _collapsed(text: str) -> str:
    return " ".join(text.split())


def test_runbook_distinguishes_persisted_scheduler_state_from_lease_boundary() -> None:
    runbook = _read(RUNBOOK)
    normalized_runbook = _collapsed(runbook)

    assert "durable local JSON persistence for scheduled action snapshots" in normalized_runbook
    assert "scheduler receipts" in normalized_runbook
    assert "`FileTemporalSchedulerStore` restart can restore saved actions" in normalized_runbook
    assert "lease ownership itself remains" in normalized_runbook


def test_runbook_keeps_multi_process_lease_ownership_as_current_limit() -> None:
    runbook = _read(RUNBOOK)
    current_limits = runbook.split("## Current Limits", maxsplit=1)[1]

    assert "distributed scheduler leader election" in current_limits
    assert "multi-process lease ownership persistence or recovery" in current_limits
    assert "external handler plugin loading" in current_limits
    assert "The remaining scheduler limits are later layers" in current_limits


def test_runbook_documents_reclaimed_lease_proof_transition() -> None:
    runbook = _read(RUNBOOK)
    proof_bridge_tests = _read(PROOF_BRIDGE_TESTS)

    assert "running -> pending      temporal_lease_reclaimed" in runbook
    assert "test_reclaimed_lease_receipt_certifies_running_to_pending_transition" in proof_bridge_tests
    assert 'proof.capsule.receipt.from_state == "running"' in proof_bridge_tests
    assert 'proof.capsule.receipt.to_state == "pending"' in proof_bridge_tests
    assert 'proof.capsule.receipt.action == "temporal_lease_reclaimed"' in proof_bridge_tests


def test_runtime_surface_matches_documented_persistence_boundary() -> None:
    scheduler_source = _read(SCHEDULER)
    store_source = _read(STORE)

    assert "class TemporalLease" in scheduler_source
    assert "self._leases: dict[str, TemporalLease]" in scheduler_source
    assert "def restore(self, actions: tuple[ScheduledTemporalAction, ...])" in scheduler_source
    assert '"actions": [' in store_source
    assert '"receipts": [' in store_source
