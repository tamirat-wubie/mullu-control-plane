"""Tests for the operating substrate self-model projection.

Purpose: verify that Capability ABI coverage, world-state health, subsystem
health, and evidence refs produce a read-only self-model projection.
Governance scope: self-model projection, SolverOutcome classification,
Foundation Mode non-mutation, and fail-closed capability admission.
Dependencies: mcoi_runtime.core.operating_substrate_self_model and
mcoi_runtime.contracts.meta_reasoning.
Invariants:
  - Rejected manifests block through GovernanceBlocked.
  - Missing capability evidence remains AwaitingEvidence.
  - Projection never authorizes mutation or raw private reasoning.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.meta_reasoning import (
    HealthStatus,
    OperatingSubstrateSelfModelProjection,
    SelfModelCapabilityProjection,
    SubsystemHealth,
)
from mcoi_runtime.contracts.solver_outcome import SolverOutcome
from mcoi_runtime.core.operating_substrate_self_model import build_operating_substrate_self_model


_NOW = "2026-06-02T00:00:00+00:00"


def _subsystems(status: HealthStatus = HealthStatus.HEALTHY) -> tuple[SubsystemHealth, ...]:
    return (
        SubsystemHealth(subsystem="capability_fabric", status=status, details="local evidence available"),
        SubsystemHealth(subsystem="universal_action_orchestration", status=HealthStatus.HEALTHY, details="preflight passed"),
    )


def _manifest_read_model() -> dict[str, object]:
    return {
        "manifest_count": 1,
        "admission_count": 1,
        "capability_ids": ("software_dev.repo_map.read",),
        "manifests": (
            {
                "capability_id": "software_dev.repo_map.read",
                "maturity": "C4",
                "risk": "low",
                "evidence_refs": ("test://capability-manifest", "proof://repo-map-read"),
            },
        ),
        "admissions": (
            {
                "admission_id": "admission-1",
                "status": "admitted",
                "capability_id": "software_dev.repo_map.read",
                "source_ref": "capabilities/software_dev/manifests/software_dev_repo_map_read.capability.json",
                "errors": (),
            },
        ),
    }


def test_self_model_projection_closes_healthy_manifest_surface() -> None:
    projection = build_operating_substrate_self_model(
        capability_manifest_read_model=_manifest_read_model(),
        subsystem_health=_subsystems(),
        world_state_status=HealthStatus.HEALTHY,
        captured_at=_NOW,
        evidence_refs=("receipt://workspace-governance-preflight",),
    )

    assert projection.capability_count == 1
    assert projection.admitted_capability_count == 1
    assert projection.overall_status is HealthStatus.HEALTHY
    assert projection.solver_outcome is SolverOutcome.SOLVED_VERIFIED
    assert projection.mutation_authorized is False


def test_self_model_projection_blocks_rejected_manifest_surface() -> None:
    read_model = {
        "manifest_count": 0,
        "admission_count": 1,
        "manifests": (),
        "admissions": (
            {
                "admission_id": "admission-rejected",
                "status": "rejected",
                "capability_id": "software_dev.change.run",
                "source_ref": "capabilities/software_dev/manifests/software_dev_change_run.capability.json",
                "errors": ("effect_bearing_capability_requires_rollback",),
            },
        ),
    }

    projection = build_operating_substrate_self_model(
        capability_manifest_read_model=read_model,
        subsystem_health=_subsystems(),
        world_state_status=HealthStatus.HEALTHY,
        captured_at=_NOW,
    )

    assert projection.capability_count == 1
    assert projection.admitted_capability_count == 0
    assert projection.capabilities[0].status is HealthStatus.UNAVAILABLE
    assert projection.solver_outcome is SolverOutcome.GOVERNANCE_BLOCKED
    assert "effect_bearing_capability_requires_rollback" in projection.capabilities[0].reason


def test_self_model_projection_awaits_evidence_when_no_capabilities_exist() -> None:
    projection = build_operating_substrate_self_model(
        capability_manifest_read_model={"manifest_count": 0, "admission_count": 0, "manifests": (), "admissions": ()},
        subsystem_health=_subsystems(),
        world_state_status=HealthStatus.HEALTHY,
        captured_at=_NOW,
    )

    assert projection.capability_count == 0
    assert projection.overall_status is HealthStatus.HEALTHY
    assert projection.solver_outcome is SolverOutcome.AWAITING_EVIDENCE
    assert "capability-manifest-count:0" in projection.evidence_refs


def test_self_model_projection_downgrades_degraded_world_state() -> None:
    projection = build_operating_substrate_self_model(
        capability_manifest_read_model=_manifest_read_model(),
        subsystem_health=_subsystems(),
        world_state_status=HealthStatus.DEGRADED,
        captured_at=_NOW,
    )

    assert projection.overall_status is HealthStatus.DEGRADED
    assert projection.solver_outcome is SolverOutcome.SOLVED_UNVERIFIED
    assert projection.degraded_capability_count == 0


def test_self_model_projection_consumes_gateway_manifest_coverage() -> None:
    read_model = {
        "manifest_count": 1,
        "admission_count": 1,
        "capability_manifest_coverage_status": "partial",
        "capability_manifest_coverage": (
            {
                "capability_id": "software_dev.repo_map.read",
                "coverage_status": "covered",
                "manifest_admitted": True,
                "reason": "manifest_admitted",
                "maturity": "C4",
                "risk": "low",
                "source_ref": "capabilities/software_dev/manifests/software_dev_repo_map_read.capability.json",
                "evidence_refs": ("tests/test_software_dev_capability_pack.py",),
            },
            {
                "capability_id": "software_dev.change.run",
                "coverage_status": "missing_manifest",
                "manifest_admitted": False,
                "reason": "capability manifest is not admitted for typed intent",
                "maturity": "unknown",
                "risk": "unknown",
                "source_ref": "capability-manifest-registry",
                "evidence_refs": (),
            },
        ),
    }

    projection = build_operating_substrate_self_model(
        capability_manifest_read_model=read_model,
        subsystem_health=_subsystems(),
        world_state_status=HealthStatus.HEALTHY,
        captured_at=_NOW,
    )
    capabilities = {capability.capability_id: capability for capability in projection.capabilities}

    assert projection.capability_count == 2
    assert capabilities["software_dev.repo_map.read"].status is HealthStatus.HEALTHY
    assert capabilities["software_dev.change.run"].status is HealthStatus.UNKNOWN
    assert projection.solver_outcome is SolverOutcome.AWAITING_EVIDENCE
    assert "capability-manifest-coverage-status:partial" in projection.evidence_refs


def test_self_model_projection_blocks_rejected_abi_coverage() -> None:
    read_model = {
        "manifest_count": 0,
        "admission_count": 1,
        "capability_abi_coverage_status": "blocked",
        "capability_abi_coverage": (
            {
                "capability_id": "software_dev.change.run",
                "coverage_status": "blocked",
                "admission_status": "rejected",
                "reason": "effect_bearing_capability_requires_rollback",
                "maturity": "unknown",
                "risk": "unknown",
                "source_ref": "capabilities/software_dev/manifests/software_dev_change_run.capability.json",
                "evidence_refs": ("admission-rejected",),
            },
        ),
    }

    projection = build_operating_substrate_self_model(
        capability_manifest_read_model=read_model,
        subsystem_health=_subsystems(),
        world_state_status=HealthStatus.HEALTHY,
        captured_at=_NOW,
    )

    assert projection.capability_count == 1
    assert projection.capabilities[0].admitted is False
    assert projection.capabilities[0].status is HealthStatus.UNAVAILABLE
    assert projection.solver_outcome is SolverOutcome.GOVERNANCE_BLOCKED
    assert "capability-abi-coverage-status:blocked" in projection.evidence_refs


def test_self_model_projection_contract_rejects_mutation_authority() -> None:
    capability = SelfModelCapabilityProjection(
        capability_id="capability.read",
        maturity="C4",
        risk="low",
        admitted=True,
        status=HealthStatus.HEALTHY,
        reason="manifest_admitted",
        evidence_refs=("proof://capability",),
    )

    with pytest.raises(ValueError, match="cannot authorize mutation"):
        OperatingSubstrateSelfModelProjection(
            projection_id="projection-1",
            captured_at=_NOW,
            capabilities=(capability,),
            subsystem_health=_subsystems(),
            world_state_status=HealthStatus.HEALTHY,
            evidence_refs=("proof://capability",),
            capability_count=1,
            admitted_capability_count=1,
            degraded_capability_count=0,
            unknown_capability_count=0,
            solver_outcome=SolverOutcome.SOLVED_VERIFIED,
            mutation_authorized=True,
        )

