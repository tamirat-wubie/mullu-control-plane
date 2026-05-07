"""Purpose: deterministic domain capsule compiler for the governed capability fabric.
Governance scope: convert a validated domain capsule into registry, policy, evidence,
    obligation, read-model, operator-view, certification, and certification-evidence artifacts.
Dependencies: governed capability fabric contracts and stable identifier helpers.
Invariants:
  - Compilation is side-effect free and deterministic for a fixed clock.
  - Missing capability references fail compilation before artifact emission.
  - Domain mismatches fail compilation before artifact emission.
  - Non-certified capsule or capability state is surfaced as a warning, not hidden.
  - Certification evidence is surfaced as an audit artifact, not as admission.
"""

from __future__ import annotations

from typing import Callable, Iterable, Mapping

from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityCertificationStatus,
    CapabilityRegistryEntry,
    CapsuleCompilationResult,
    CapsuleCompilationStatus,
    CapsuleCompilerArtifact,
    DomainCapsule,
    DomainCapsuleCertificationStatus,
)

from .invariants import stable_identifier


_CERTIFICATION_EVIDENCE_EXTENSION_KEY = "capability_certification_evidence"
_CERTIFICATION_EVIDENCE_REF_FIELDS = (
    "certification_ref",
    "sandbox_receipt_ref",
    "live_read_receipt_ref",
    "live_write_receipt_ref",
    "worker_deployment_ref",
    "recovery_evidence_ref",
    "autonomy_controls_ref",
)
_CERTIFICATION_SOURCE_REF_FIELDS = (
    "source_package_id",
    "source_package_hash",
    "source_handoff_hash",
    "certification_evidence_hash",
)


class DomainCapsuleCompiler:
    """Compile domain capsules into deterministic governed fabric artifacts."""

    def __init__(self, clock: Callable[[], str]) -> None:
        self._clock = clock

    def compile(
        self,
        capsule: DomainCapsule,
        registry_entries: Iterable[CapabilityRegistryEntry],
    ) -> CapsuleCompilationResult:
        """Compile a capsule against available capability registry entries."""
        now = self._clock()
        registry = {entry.capability_id: entry for entry in registry_entries}
        errors = _reference_errors(capsule, registry)
        errors.extend(_domain_errors(capsule, registry))

        if errors:
            return CapsuleCompilationResult(
                compilation_id=_compilation_id(capsule, now),
                capsule_id=capsule.capsule_id,
                status=CapsuleCompilationStatus.FAILED,
                artifacts=(),
                warnings=(),
                errors=tuple(errors),
                compiled_at=now,
            )

        warnings = _certification_warnings(capsule, registry)
        artifacts = _compile_artifacts(capsule, registry)
        status = (
            CapsuleCompilationStatus.SUCCESS_WITH_WARNINGS
            if warnings
            else CapsuleCompilationStatus.SUCCESS
        )
        return CapsuleCompilationResult(
            compilation_id=_compilation_id(capsule, now),
            capsule_id=capsule.capsule_id,
            status=status,
            artifacts=artifacts,
            warnings=tuple(warnings),
            errors=(),
            compiled_at=now,
        )


def _compilation_id(capsule: DomainCapsule, compiled_at: str) -> str:
    return stable_identifier(
        "capsule-compilation",
        {
            "capsule_id": capsule.capsule_id,
            "domain": capsule.domain,
            "version": capsule.version,
            "compiled_at": compiled_at,
        },
    )


def _reference_errors(
    capsule: DomainCapsule,
    registry: Mapping[str, CapabilityRegistryEntry],
) -> list[str]:
    errors: list[str] = []
    for capability_id in capsule.capability_refs:
        if capability_id not in registry:
            errors.append(f"missing capability registry entry: {capability_id}")
    return errors


def _domain_errors(
    capsule: DomainCapsule,
    registry: Mapping[str, CapabilityRegistryEntry],
) -> list[str]:
    errors: list[str] = []
    for capability_id in capsule.capability_refs:
        entry = registry.get(capability_id)
        if entry is not None and entry.domain != capsule.domain:
            errors.append(
                f"capability domain mismatch: {capability_id} has {entry.domain}, expected {capsule.domain}"
            )
    return errors


def _certification_warnings(
    capsule: DomainCapsule,
    registry: Mapping[str, CapabilityRegistryEntry],
) -> list[str]:
    warnings: list[str] = []
    if capsule.certification_status is not DomainCapsuleCertificationStatus.CERTIFIED:
        warnings.append(f"capsule is not certified: {capsule.certification_status.value}")
    for capability_id in capsule.capability_refs:
        entry = registry[capability_id]
        if entry.certification_status is not CapabilityCertificationStatus.CERTIFIED:
            warnings.append(
                f"capability is not certified: {capability_id}={entry.certification_status.value}"
            )
    return warnings


def _compile_artifacts(
    capsule: DomainCapsule,
    registry: Mapping[str, CapabilityRegistryEntry],
) -> tuple[CapsuleCompilerArtifact, ...]:
    entries = tuple(registry[capability_id] for capability_id in capsule.capability_refs)
    return (
        _artifact(
            capsule,
            "capability_registry_manifest",
            {
                "capability_ids": capsule.capability_refs,
                "registry_entries": [entry.to_json_dict() for entry in entries],
            },
        ),
        _artifact(
            capsule,
            "capability_certification_evidence_manifest",
            _certification_evidence_manifest_payload(capsule, entries),
        ),
        _artifact(capsule, "policy_pack_manifest", {"policy_refs": capsule.policy_refs}),
        _artifact(capsule, "evidence_pack_manifest", {"evidence_rules": capsule.evidence_rules}),
        _artifact(capsule, "approval_pack_manifest", {"approval_rules": capsule.approval_rules}),
        _artifact(capsule, "recovery_pack_manifest", {"recovery_rules": capsule.recovery_rules}),
        _artifact(
            capsule,
            "obligation_template_manifest",
            {
                "owner_team": capsule.owner_team,
                "capability_obligations": {
                    entry.capability_id: entry.obligation_model.to_json_dict()
                    for entry in entries
                },
            },
        ),
        _artifact(capsule, "fixture_manifest", {"test_fixture_refs": capsule.test_fixture_refs}),
        _artifact(capsule, "read_model_manifest", {"read_model_refs": capsule.read_model_refs}),
        _artifact(capsule, "operator_view_manifest", {"operator_view_refs": capsule.operator_view_refs}),
        _artifact(
            capsule,
            "certification_report",
            {
                "capsule_status": capsule.certification_status.value,
                "capability_statuses": {
                    entry.capability_id: entry.certification_status.value
                    for entry in entries
                },
            },
        ),
    )


def _certification_evidence_manifest_payload(
    capsule: DomainCapsule,
    entries: tuple[CapabilityRegistryEntry, ...],
) -> dict[str, object]:
    records = [
        _certification_evidence_record(entry)
        for entry in entries
    ]
    return {
        "capsule_id": capsule.capsule_id,
        "capability_ids": capsule.capability_refs,
        "certification_evidence_records": records,
        "manifest_is_not_admission": True,
    }


def _certification_evidence_record(entry: CapabilityRegistryEntry) -> dict[str, object]:
    evidence = _certification_evidence_payload(entry)
    return {
        "capability_id": entry.capability_id,
        "certification_status": entry.certification_status.value,
        "has_certification_evidence": bool(evidence),
        "certification_evidence": evidence,
        "evidence_refs": [
            str(evidence[field_name])
            for field_name in _CERTIFICATION_EVIDENCE_REF_FIELDS
            if evidence.get(field_name)
        ],
        "source_refs": {
            field_name: str(evidence[field_name])
            for field_name in _CERTIFICATION_SOURCE_REF_FIELDS
            if evidence.get(field_name)
        },
        "certification_evidence_hash": str(evidence.get("certification_evidence_hash", "")),
    }


def _certification_evidence_payload(entry: CapabilityRegistryEntry) -> dict[str, object]:
    extensions = entry.to_json_dict().get("extensions", {})
    if not isinstance(extensions, Mapping):
        return {}
    evidence = extensions.get(_CERTIFICATION_EVIDENCE_EXTENSION_KEY, {})
    if not isinstance(evidence, Mapping):
        return {}
    return dict(evidence)


def _artifact(
    capsule: DomainCapsule,
    artifact_type: str,
    payload: Mapping[str, object],
) -> CapsuleCompilerArtifact:
    return CapsuleCompilerArtifact(
        artifact_id=stable_identifier(
            "capsule-artifact",
            {
                "capsule_id": capsule.capsule_id,
                "version": capsule.version,
                "artifact_type": artifact_type,
                "payload": payload,
            },
        ),
        artifact_type=artifact_type,
        source_capsule_id=capsule.capsule_id,
        payload=payload,
    )
