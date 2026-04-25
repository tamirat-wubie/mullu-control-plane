"""Purpose: deterministic domain capsule compiler for the governed capability fabric.
Governance scope: convert a validated domain capsule into registry, policy, evidence,
    obligation, read-model, operator-view, and certification artifacts.
Dependencies: governed capability fabric contracts and stable identifier helpers.
Invariants:
  - Compilation is side-effect free and deterministic for a fixed clock.
  - Missing capability references fail compilation before artifact emission.
  - Domain mismatches fail compilation before artifact emission.
  - Non-certified capsule or capability state is surfaced as a warning, not hidden.
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
