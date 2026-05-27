"""Purpose: verify Organization Kernel file persistence.
Governance scope: state snapshot, restore, malformed persistence, and replay-safe event sequence.
Dependencies: OrganizationKernel, FileOrganizationKernelStore, and default pilot helpers.
Invariants:
  - Persisted state restores without rewriting case events.
  - Latest plan-step gate decisions survive restore.
  - Malformed state fails closed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.contracts.organization_kernel import CaseEvidence, OrganizationProfile
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.organization_kernel import (
    OrganizationKernel,
    bootstrap_minimum_organization,
    open_launch_gateway_pilot,
)
from mcoi_runtime.persistence.errors import CorruptedDataError, PersistenceError
from mcoi_runtime.persistence.organization_kernel_store import FileOrganizationKernelStore


FIXED_CLOCK = "2026-05-27T12:00:00+00:00"


def _clock() -> str:
    return FIXED_CLOCK


def _bootstrapped_kernel() -> OrganizationKernel:
    kernel = OrganizationKernel(clock=_clock)
    bootstrap_minimum_organization(
        kernel,
        OrganizationProfile(
            org_id="org-mullu",
            tenant_id="tenant-mullu",
            name="Mullu",
            created_at=FIXED_CLOCK,
        ),
    )
    return kernel


def test_file_store_round_trip_restores_pilot_gate_state(tmp_path: Path) -> None:
    kernel = _bootstrapped_kernel()
    _case, _plan = open_launch_gateway_pilot(kernel, org_id="org-mullu")
    kernel.admit_case_evidence(
        CaseEvidence(
            evidence_ref="evidence:objective",
            case_id="case.launch_gateway_pilot",
            requirement_id="executive_objective",
            submitted_by="executive.owner",
            submitted_at=FIXED_CLOCK,
        )
    )
    decision = kernel.evaluate_plan_step(
        case_id="case.launch_gateway_pilot",
        step_id="executive_objective_freeze",
        checked_preconditions=("objective_received",),
    )
    store = FileOrganizationKernelStore(tmp_path / "organization-kernel.json")

    content = store.save_kernel(kernel)
    restored = OrganizationKernel(clock=_clock)
    state = store.restore_kernel(restored)
    restored_case = restored.get_case("case.launch_gateway_pilot")
    restored_state = restored.snapshot_state()

    assert content.startswith("{")
    assert state.event_sequence == 4
    assert restored_case is not None
    assert restored_case.plan_id == "plan.launch_gateway_pilot.v1"
    assert len(restored.list_case_events("case.launch_gateway_pilot")) == 4
    assert restored_state.latest_gate_decisions[0].decision_id == decision.decision_id
    assert restored_state.gate_decisions[0].status.value == "allowed"


def test_restore_rejects_non_empty_kernel(tmp_path: Path) -> None:
    source = _bootstrapped_kernel()
    store = FileOrganizationKernelStore(tmp_path / "organization-kernel.json")
    store.save_kernel(source)
    target = _bootstrapped_kernel()

    with pytest.raises(RuntimeCoreInvariantError, match="restore requires empty kernel"):
        store.restore_kernel(target)

    assert target.organization_count == 1
    assert target.department_count == 5
    assert target.case_count == 0


def test_file_store_fails_closed_on_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "organization-kernel.json"
    path.write_text("not json", encoding="utf-8")
    store = FileOrganizationKernelStore(path)

    with pytest.raises(CorruptedDataError, match=r"^malformed JSON"):
        store.load_state()

    assert store.exists() is True
    assert path.read_text(encoding="utf-8") == "not json"


def test_file_store_requires_file_path(tmp_path: Path) -> None:
    directory_path = tmp_path / "state-dir"
    directory_path.mkdir()

    with pytest.raises(PersistenceError, match="path must be a file"):
        FileOrganizationKernelStore(directory_path)

    assert directory_path.exists()
    assert directory_path.is_dir()
