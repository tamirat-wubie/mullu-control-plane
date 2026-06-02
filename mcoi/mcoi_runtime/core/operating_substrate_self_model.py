"""Read-only operating substrate self-model projection.

Purpose: build a bounded self-model read model from capability manifest,
subsystem health, world-state, and evidence surfaces.
Governance scope: Capability ABI coverage, self-model projection, world-state
health, evidence refs, and SolverOutcome classification.
Dependencies: meta-reasoning contracts, solver outcome contracts, and stable
identifier helpers.
Invariants:
  - Projection is read-only and never authorizes mutation.
  - Unknown or rejected hard surfaces fail closed into explicit outcomes.
  - Capability manifest evidence is carried forward as projection evidence.
  - Raw private reasoning is never included.
"""

from __future__ import annotations

from typing import Any, Mapping

from mcoi_runtime.contracts.meta_reasoning import (
    HealthStatus,
    OperatingSubstrateSelfModelProjection,
    SelfModelCapabilityProjection,
    SubsystemHealth,
)
from mcoi_runtime.contracts.solver_outcome import SolverOutcome
from mcoi_runtime.core.invariants import stable_identifier


def build_operating_substrate_self_model(
    *,
    capability_manifest_read_model: Mapping[str, Any],
    subsystem_health: tuple[SubsystemHealth, ...],
    world_state_status: HealthStatus,
    captured_at: str,
    evidence_refs: tuple[str, ...] = (),
) -> OperatingSubstrateSelfModelProjection:
    """Build a read-only self-model projection from admitted local surfaces."""

    capabilities = _capability_projections(capability_manifest_read_model)
    evidence = _projection_evidence(evidence_refs, capabilities, capability_manifest_read_model)
    solver_outcome = _solver_outcome_for(
        capabilities=capabilities,
        subsystem_health=subsystem_health,
        world_state_status=world_state_status,
    )
    projection_id = stable_identifier(
        "operating-substrate-self-model",
        {
            "captured_at": captured_at,
            "capabilities": [
                {
                    "capability_id": capability.capability_id,
                    "status": capability.status.value,
                    "admitted": capability.admitted,
                }
                for capability in capabilities
            ],
            "subsystems": [
                {"subsystem": subsystem.subsystem, "status": subsystem.status.value}
                for subsystem in subsystem_health
            ],
            "world_state_status": world_state_status.value,
        },
    )
    return OperatingSubstrateSelfModelProjection(
        projection_id=projection_id,
        captured_at=captured_at,
        capabilities=capabilities,
        subsystem_health=subsystem_health,
        world_state_status=world_state_status,
        evidence_refs=evidence,
        capability_count=len(capabilities),
        admitted_capability_count=sum(1 for capability in capabilities if capability.admitted),
        degraded_capability_count=sum(1 for capability in capabilities if capability.status is HealthStatus.DEGRADED),
        unknown_capability_count=sum(1 for capability in capabilities if capability.status is HealthStatus.UNKNOWN),
        solver_outcome=solver_outcome,
    )


def _capability_projections(read_model: Mapping[str, Any]) -> tuple[SelfModelCapabilityProjection, ...]:
    coverage_records = _mapping_sequence(read_model.get("capability_manifest_coverage", ()))
    if coverage_records:
        return tuple(
            sorted(
                (_projection_from_gateway_coverage(record) for record in coverage_records),
                key=lambda projection: projection.capability_id,
            )
        )
    abi_coverage_records = _mapping_sequence(read_model.get("capability_abi_coverage", ()))
    if abi_coverage_records:
        return tuple(
            sorted(
                (_projection_from_abi_coverage(record) for record in abi_coverage_records),
                key=lambda projection: projection.capability_id,
            )
        )

    projections: list[SelfModelCapabilityProjection] = []
    for manifest in _mapping_sequence(read_model.get("manifests", ())):
        projections.append(_projection_from_manifest(manifest))
    admitted_ids = {projection.capability_id for projection in projections}
    for admission in _mapping_sequence(read_model.get("admissions", ())):
        status = str(admission.get("status", "")).strip().lower()
        capability_id = str(admission.get("capability_id", "")).strip()
        if status in {"admitted", "accepted"} or capability_id in admitted_ids:
            continue
        projections.append(_projection_from_rejected_admission(admission))
    return tuple(sorted(projections, key=lambda projection: projection.capability_id))


def _projection_from_manifest(manifest: Mapping[str, Any]) -> SelfModelCapabilityProjection:
    evidence_refs = _text_tuple(manifest.get("evidence_refs", ()))
    status = HealthStatus.HEALTHY if evidence_refs else HealthStatus.UNKNOWN
    reason = "manifest_admitted" if evidence_refs else "manifest_admitted_without_evidence"
    return SelfModelCapabilityProjection(
        capability_id=_text_or_unknown(manifest.get("capability_id"), "capability:unknown"),
        maturity=_text_or_unknown(manifest.get("maturity"), "unknown"),
        risk=_text_or_unknown(manifest.get("risk"), "unknown"),
        admitted=True,
        status=status,
        reason=reason,
        evidence_refs=evidence_refs,
        open_incident_refs=(),
    )


def _projection_from_rejected_admission(admission: Mapping[str, Any]) -> SelfModelCapabilityProjection:
    errors = _text_tuple(admission.get("errors", ()))
    reason = ";".join(errors) if errors else "manifest_rejected"
    evidence_refs = tuple(
        ref
        for ref in (
            str(admission.get("source_ref", "")).strip(),
            str(admission.get("admission_id", "")).strip(),
        )
        if ref
    )
    return SelfModelCapabilityProjection(
        capability_id=_text_or_unknown(admission.get("capability_id"), "capability:unknown"),
        maturity="unknown",
        risk="unknown",
        admitted=False,
        status=HealthStatus.UNAVAILABLE,
        reason=reason,
        evidence_refs=evidence_refs,
        open_incident_refs=(),
    )


def _projection_from_gateway_coverage(record: Mapping[str, Any]) -> SelfModelCapabilityProjection:
    coverage_status = str(record.get("coverage_status", "")).strip()
    manifest_admitted = record.get("manifest_admitted") is True
    evidence_refs = _text_tuple(record.get("evidence_refs", ()))
    if coverage_status == "covered" and manifest_admitted:
        status = HealthStatus.HEALTHY if evidence_refs else HealthStatus.UNKNOWN
    elif coverage_status == "missing_manifest":
        status = HealthStatus.UNKNOWN
    else:
        status = HealthStatus.UNAVAILABLE
    return SelfModelCapabilityProjection(
        capability_id=_text_or_unknown(record.get("capability_id"), "capability:unknown"),
        maturity=_text_or_unknown(record.get("maturity"), "unknown"),
        risk=_text_or_unknown(record.get("risk"), "unknown"),
        admitted=manifest_admitted,
        status=status,
        reason=_text_or_unknown(record.get("reason"), coverage_status or "manifest_coverage_unknown"),
        evidence_refs=evidence_refs or _text_tuple((record.get("source_ref", ""),)),
        open_incident_refs=(),
    )


def _projection_from_abi_coverage(record: Mapping[str, Any]) -> SelfModelCapabilityProjection:
    coverage_status = str(record.get("coverage_status", "")).strip()
    evidence_refs = _text_tuple(record.get("evidence_refs", ()))
    admitted = coverage_status == "covered" and str(record.get("admission_status", "")) == "admitted"
    if admitted:
        status = HealthStatus.HEALTHY if evidence_refs else HealthStatus.UNKNOWN
    else:
        status = HealthStatus.UNAVAILABLE
    return SelfModelCapabilityProjection(
        capability_id=_text_or_unknown(record.get("capability_id"), "capability:unknown"),
        maturity=_text_or_unknown(record.get("maturity"), "unknown"),
        risk=_text_or_unknown(record.get("risk"), "unknown"),
        admitted=admitted,
        status=status,
        reason=_text_or_unknown(record.get("reason"), coverage_status or "manifest_coverage_unknown"),
        evidence_refs=evidence_refs or _text_tuple((record.get("source_ref", ""),)),
        open_incident_refs=(),
    )


def _solver_outcome_for(
    *,
    capabilities: tuple[SelfModelCapabilityProjection, ...],
    subsystem_health: tuple[SubsystemHealth, ...],
    world_state_status: HealthStatus,
) -> SolverOutcome:
    statuses = {world_state_status}
    statuses.update(capability.status for capability in capabilities)
    statuses.update(subsystem.status for subsystem in subsystem_health)
    if not capabilities or HealthStatus.UNKNOWN in statuses:
        return SolverOutcome.AWAITING_EVIDENCE
    if HealthStatus.UNAVAILABLE in statuses:
        return SolverOutcome.GOVERNANCE_BLOCKED
    if HealthStatus.DEGRADED in statuses:
        return SolverOutcome.SOLVED_UNVERIFIED
    return SolverOutcome.SOLVED_VERIFIED


def _projection_evidence(
    explicit_refs: tuple[str, ...],
    capabilities: tuple[SelfModelCapabilityProjection, ...],
    read_model: Mapping[str, Any],
) -> tuple[str, ...]:
    refs: list[str] = list(_text_tuple(explicit_refs))
    for capability in capabilities:
        refs.extend(capability.evidence_refs)
        refs.extend(capability.open_incident_refs)
    manifest_count = read_model.get("manifest_count")
    admission_count = read_model.get("admission_count")
    refs.append(f"capability-manifest-count:{int(manifest_count or 0)}")
    refs.append(f"capability-admission-count:{int(admission_count or 0)}")
    coverage_status = read_model.get("capability_manifest_coverage_status")
    if isinstance(coverage_status, str) and coverage_status.strip():
        refs.append(f"capability-manifest-coverage-status:{coverage_status.strip()}")
    abi_coverage_status = read_model.get("capability_abi_coverage_status")
    if isinstance(abi_coverage_status, str) and abi_coverage_status.strip():
        refs.append(f"capability-abi-coverage-status:{abi_coverage_status.strip()}")
    return tuple(dict.fromkeys(refs))


def _mapping_sequence(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (tuple, list)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _text_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if not isinstance(value, (tuple, list)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _text_or_unknown(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback

