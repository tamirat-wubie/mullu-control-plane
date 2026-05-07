"""Capability maturity assessment.

Purpose: derive bounded capability maturity from explicit evidence flags.
Governance scope: capability readiness, certification evidence synthesis,
    promotion claims, registry projection, recovery evidence, worker evidence,
    and autonomy controls.
Dependencies: dataclasses, governed capability fabric contracts, and canonical
    command-spine hashing.
Invariants:
  - Maturity is derived from explicit evidence, never declared directly.
  - Certification evidence bundles can generate maturity extensions, but cannot
    bypass production or autonomy gates.
  - Registry projections add readiness assessments without mutating registry entries.
  - Effect-bearing production claims require live write evidence.
  - Production readiness requires worker deployment and recovery evidence.
  - C7 autonomy requires bounded autonomy controls.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Mapping

from gateway.command_spine import canonical_hash
from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityCertificationStatus,
    CapabilityRegistryEntry,
    GovernedCapabilityRecord,
)


MATURITY_LEVELS = ("C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7")


@dataclass(frozen=True, slots=True)
class CapabilityMaturityEvidence:
    """Evidence inputs for one capability maturity assessment."""

    capability_id: str
    schema_valid: bool = False
    policy_bound: bool = False
    mock_eval_passed: bool = False
    sandbox_receipt_valid: bool = False
    live_read_receipt_valid: bool = False
    live_write_receipt_valid: bool = False
    worker_deployment_bound: bool = False
    recovery_evidence_present: bool = False
    autonomy_controls_bounded: bool = False
    effect_bearing: bool = False
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.capability_id.strip():
            raise ValueError("capability_id_required")
        object.__setattr__(self, "capability_id", self.capability_id.strip())
        object.__setattr__(self, "evidence_refs", tuple(str(ref) for ref in self.evidence_refs))


@dataclass(frozen=True, slots=True)
class CapabilityCertificationEvidenceBundle:
    """Structured certification output used to synthesize maturity evidence."""

    capability_id: str
    certification_ref: str = ""
    sandbox_receipt_ref: str = ""
    live_read_receipt_ref: str = ""
    live_write_receipt_ref: str = ""
    worker_deployment_ref: str = ""
    recovery_evidence_ref: str = ""
    autonomy_controls_ref: str = ""

    def __post_init__(self) -> None:
        if not self.capability_id.strip():
            raise ValueError("capability_id_required")
        object.__setattr__(self, "capability_id", self.capability_id.strip())
        for field_name in (
            "certification_ref",
            "sandbox_receipt_ref",
            "live_read_receipt_ref",
            "live_write_receipt_ref",
            "worker_deployment_ref",
            "recovery_evidence_ref",
            "autonomy_controls_ref",
        ):
            object.__setattr__(self, field_name, str(getattr(self, field_name)).strip())

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
        *,
        default_capability_id: str = "",
    ) -> "CapabilityCertificationEvidenceBundle":
        """Return a bundle from a registry extension payload."""
        return cls(
            capability_id=str(payload.get("capability_id") or default_capability_id),
            certification_ref=str(payload.get("certification_ref", "")),
            sandbox_receipt_ref=str(payload.get("sandbox_receipt_ref", "")),
            live_read_receipt_ref=str(payload.get("live_read_receipt_ref", "")),
            live_write_receipt_ref=str(payload.get("live_write_receipt_ref", "")),
            worker_deployment_ref=str(payload.get("worker_deployment_ref", "")),
            recovery_evidence_ref=str(payload.get("recovery_evidence_ref", "")),
            autonomy_controls_ref=str(payload.get("autonomy_controls_ref", "")),
        )


@dataclass(frozen=True, slots=True)
class CapabilityMaturityAssessment:
    """Derived readiness assessment for one capability."""

    assessment_id: str
    capability_id: str
    maturity_level: str
    production_ready: bool
    autonomy_ready: bool
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    assessment_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.maturity_level not in MATURITY_LEVELS:
            raise ValueError("maturity_level_invalid")
        if self.production_ready and self.maturity_level not in {"C6", "C7"}:
            raise ValueError("production_requires_C6_or_C7")
        if self.autonomy_ready and self.maturity_level != "C7":
            raise ValueError("autonomy_requires_C7")
        if self.autonomy_ready and not self.production_ready:
            raise ValueError("autonomy_requires_production_readiness")
        object.__setattr__(self, "blockers", tuple(str(blocker) for blocker in self.blockers))
        object.__setattr__(self, "evidence_refs", tuple(str(ref) for ref in self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class CapabilityMaturityAssessor:
    """Derive maturity from evidence flags and block overclaims."""

    def assess(self, evidence: CapabilityMaturityEvidence) -> CapabilityMaturityAssessment:
        """Return a deterministic maturity assessment for one capability."""
        production_blockers = _production_blockers(evidence)
        autonomy_blockers = _autonomy_blockers(evidence, production_blockers)
        maturity_level = _maturity_level(evidence)
        production_ready = not production_blockers and maturity_level in {"C6", "C7"}
        autonomy_ready = production_ready and evidence.autonomy_controls_bounded
        assessment = CapabilityMaturityAssessment(
            assessment_id="pending",
            capability_id=evidence.capability_id,
            maturity_level=maturity_level,
            production_ready=production_ready,
            autonomy_ready=autonomy_ready,
            blockers=tuple(dict.fromkeys((*production_blockers, *autonomy_blockers))),
            evidence_refs=evidence.evidence_refs,
            metadata={
                "effect_bearing": evidence.effect_bearing,
                "assessment_is_not_promotion": True,
            },
        )
        assessment_hash = canonical_hash(asdict(assessment))
        return replace(
            assessment,
            assessment_id=f"capability-maturity-{assessment_hash[:16]}",
            assessment_hash=assessment_hash,
        )


class CapabilityMaturityEvidenceSynthesizer:
    """Generate maturity evidence extensions from certification receipts."""

    def __init__(self, assessor: CapabilityMaturityAssessor | None = None) -> None:
        self._assessor = assessor or CapabilityMaturityAssessor()

    def materialize_extension(
        self,
        entry: CapabilityRegistryEntry,
        bundle: CapabilityCertificationEvidenceBundle,
        *,
        require_production_ready: bool = False,
    ) -> dict[str, Any]:
        """Return a registry extension payload derived from certification evidence."""
        if bundle.capability_id != entry.capability_id:
            raise ValueError("capability_certification_evidence_capability_mismatch")
        extension = _certification_bundle_to_maturity_extension(bundle)
        evidence = _maturity_evidence_from_extension(entry, extension)
        assessment = self._assessor.assess(evidence)
        if require_production_ready and not assessment.production_ready:
            raise ValueError("capability_certification_evidence_incomplete")
        return extension

    def registry_entry_with_maturity_evidence(
        self,
        entry: CapabilityRegistryEntry,
        bundle: CapabilityCertificationEvidenceBundle,
        *,
        require_production_ready: bool = False,
    ) -> CapabilityRegistryEntry:
        """Return a registry entry with synthesized maturity evidence installed."""
        extension = self.materialize_extension(
            entry,
            bundle,
            require_production_ready=require_production_ready,
        )
        return replace(
            entry,
            extensions={
                **dict(entry.extensions),
                "capability_maturity_evidence": extension,
            },
        )


class CapabilityRegistryMaturityProjector:
    """Project registry entries into maturity assessments for read models."""

    def __init__(self, assessor: CapabilityMaturityAssessor | None = None) -> None:
        self._assessor = assessor or CapabilityMaturityAssessor()

    def assess_entry(self, entry: CapabilityRegistryEntry) -> CapabilityMaturityAssessment:
        """Return maturity assessment for one registry entry."""
        return self._assessor.assess(capability_maturity_evidence_from_registry_entry(entry))

    def decorate_read_model(self, read_model: Mapping[str, Any]) -> dict[str, Any]:
        """Return read model with derived maturity assessments attached."""
        capability_items = tuple(read_model.get("capabilities", ()))
        governed_items = tuple(read_model.get("governed_capability_records", ()))
        assessments_by_capability: dict[str, dict[str, Any]] = {}
        decorated_capabilities: list[Any] = []

        for item in capability_items:
            if not isinstance(item, Mapping):
                decorated_capabilities.append(item)
                continue
            capability_payload = dict(item)
            try:
                entry = _entry_from_read_model_payload(capability_payload)
            except (KeyError, TypeError, ValueError):
                decorated_capabilities.append(capability_payload)
                continue
            assessment = self.assess_entry(entry)
            assessment_payload = _assessment_payload(assessment)
            assessments_by_capability[entry.capability_id] = assessment_payload
            decorated_capabilities.append({
                **capability_payload,
                "maturity_assessment": assessment_payload,
            })

        decorated_governed_records: list[Any] = []
        for item in governed_items:
            if not isinstance(item, Mapping):
                decorated_governed_records.append(item)
                continue
            governed_payload = dict(item)
            assessment = assessments_by_capability.get(str(governed_payload.get("capability_id", "")))
            if assessment is None:
                decorated_governed_records.append(governed_payload)
                continue
            decorated_governed_records.append({
                **governed_payload,
                "maturity_level": assessment["maturity_level"],
                "production_ready": assessment["production_ready"],
                "autonomy_ready": assessment["autonomy_ready"],
                "maturity_assessment_id": assessment["assessment_id"],
            })

        return {
            **dict(read_model),
            "capabilities": tuple(decorated_capabilities),
            "governed_capability_records": tuple(decorated_governed_records),
            "capability_maturity_assessments": tuple(assessments_by_capability.values()),
            "capability_maturity_counts": _maturity_counts(assessments_by_capability.values()),
            "production_ready_count": sum(
                1 for assessment in assessments_by_capability.values() if assessment["production_ready"] is True
            ),
            "autonomy_ready_count": sum(
                1 for assessment in assessments_by_capability.values() if assessment["autonomy_ready"] is True
            ),
        }


def capability_maturity_evidence_from_registry_entry(
    entry: CapabilityRegistryEntry,
) -> CapabilityMaturityEvidence:
    """Derive bounded maturity evidence from one registry entry and extensions."""
    maturity_extensions = _maturity_extension_from_registry_entry(entry)
    return _maturity_evidence_from_extension(entry, maturity_extensions)


def capability_maturity_evidence_extension_from_certification(
    entry: CapabilityRegistryEntry,
    bundle: CapabilityCertificationEvidenceBundle,
    *,
    require_production_ready: bool = False,
) -> dict[str, Any]:
    """Return the maturity extension produced by a certification bundle."""
    return CapabilityMaturityEvidenceSynthesizer().materialize_extension(
        entry,
        bundle,
        require_production_ready=require_production_ready,
    )


def registry_entry_with_certification_maturity_evidence(
    entry: CapabilityRegistryEntry,
    bundle: CapabilityCertificationEvidenceBundle,
    *,
    require_production_ready: bool = False,
) -> CapabilityRegistryEntry:
    """Return a registry entry with certification-derived maturity evidence."""
    return CapabilityMaturityEvidenceSynthesizer().registry_entry_with_maturity_evidence(
        entry,
        bundle,
        require_production_ready=require_production_ready,
    )


def _maturity_evidence_from_extension(
    entry: CapabilityRegistryEntry,
    maturity_extensions: Mapping[str, Any],
) -> CapabilityMaturityEvidence:
    governed_record = GovernedCapabilityRecord.from_registry_entry(entry)
    return CapabilityMaturityEvidence(
        capability_id=entry.capability_id,
        schema_valid=True,
        policy_bound=_policy_bound(entry),
        mock_eval_passed=entry.certification_status is CapabilityCertificationStatus.CERTIFIED,
        sandbox_receipt_valid=_extension_bool(maturity_extensions, "sandbox_receipt_valid"),
        live_read_receipt_valid=_extension_bool(maturity_extensions, "live_read_receipt_valid"),
        live_write_receipt_valid=_extension_bool(maturity_extensions, "live_write_receipt_valid"),
        worker_deployment_bound=_extension_bool(maturity_extensions, "worker_deployment_bound"),
        recovery_evidence_present=_recovery_evidence_present(entry, maturity_extensions),
        autonomy_controls_bounded=_extension_bool(maturity_extensions, "autonomy_controls_bounded"),
        effect_bearing=governed_record.world_mutating,
        evidence_refs=_evidence_refs(entry, maturity_extensions),
    )


def _maturity_extension_from_registry_entry(entry: CapabilityRegistryEntry) -> Mapping[str, Any]:
    if "capability_maturity_evidence" in entry.extensions:
        maturity_extensions = entry.extensions.get("capability_maturity_evidence", {})
        if isinstance(maturity_extensions, Mapping):
            return maturity_extensions
        return {}
    certification_extensions = entry.extensions.get("capability_certification_evidence", {})
    if not isinstance(certification_extensions, Mapping):
        return {}
    bundle = CapabilityCertificationEvidenceBundle.from_mapping(
        certification_extensions,
        default_capability_id=entry.capability_id,
    )
    return CapabilityMaturityEvidenceSynthesizer().materialize_extension(entry, bundle)


def _certification_bundle_to_maturity_extension(
    bundle: CapabilityCertificationEvidenceBundle,
) -> dict[str, Any]:
    refs = tuple(
        ref
        for ref in (
            bundle.certification_ref,
            bundle.sandbox_receipt_ref,
            bundle.live_read_receipt_ref,
            bundle.live_write_receipt_ref,
            bundle.worker_deployment_ref,
            bundle.recovery_evidence_ref,
            bundle.autonomy_controls_ref,
        )
        if ref
    )
    return {
        "generated_by": "capability_certification_evidence",
        "sandbox_receipt_valid": bool(bundle.sandbox_receipt_ref),
        "live_read_receipt_valid": bool(bundle.live_read_receipt_ref),
        "live_write_receipt_valid": bool(bundle.live_write_receipt_ref),
        "worker_deployment_bound": bool(bundle.worker_deployment_ref),
        "recovery_evidence_present": bool(bundle.recovery_evidence_ref),
        "autonomy_controls_bounded": bool(bundle.autonomy_controls_ref),
        "evidence_refs": list(refs),
    }


def _maturity_level(evidence: CapabilityMaturityEvidence) -> str:
    if not evidence.schema_valid:
        return "C0"
    if not evidence.policy_bound:
        return "C1"
    if not evidence.mock_eval_passed:
        return "C2"
    if not evidence.sandbox_receipt_valid:
        return "C3"
    if not evidence.live_read_receipt_valid:
        return "C4"
    if evidence.effect_bearing and not evidence.live_write_receipt_valid:
        return "C4"
    if not evidence.worker_deployment_bound or not evidence.recovery_evidence_present:
        return "C5"
    if not evidence.autonomy_controls_bounded:
        return "C6"
    return "C7"


def _production_blockers(evidence: CapabilityMaturityEvidence) -> tuple[str, ...]:
    blockers: list[str] = []
    if not evidence.schema_valid:
        blockers.append("schema_evidence_missing")
    if not evidence.policy_bound:
        blockers.append("policy_evidence_missing")
    if not evidence.mock_eval_passed:
        blockers.append("eval_evidence_missing")
    if not evidence.sandbox_receipt_valid:
        blockers.append("sandbox_receipt_missing")
    if not evidence.live_read_receipt_valid:
        blockers.append("live_read_receipt_missing")
    if evidence.effect_bearing and not evidence.live_write_receipt_valid:
        blockers.append("effect_bearing_production_requires_live_write")
    if not evidence.worker_deployment_bound:
        blockers.append("worker_deployment_evidence_missing")
    if not evidence.recovery_evidence_present:
        blockers.append("recovery_evidence_missing")
    return tuple(blockers)


def _autonomy_blockers(
    evidence: CapabilityMaturityEvidence,
    production_blockers: tuple[str, ...],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if production_blockers and evidence.autonomy_controls_bounded:
        blockers.append("autonomy_requires_production_readiness")
    if not evidence.autonomy_controls_bounded:
        blockers.append("autonomy_controls_missing")
    return tuple(blockers)


def _entry_from_read_model_payload(payload: Mapping[str, Any]) -> CapabilityRegistryEntry:
    entry_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"capsule_id", "maturity_assessment"}
    }
    return CapabilityRegistryEntry.from_mapping(entry_payload)


def _assessment_payload(assessment: CapabilityMaturityAssessment) -> dict[str, Any]:
    payload = asdict(assessment)
    payload["blockers"] = list(assessment.blockers)
    payload["evidence_refs"] = list(assessment.evidence_refs)
    return payload


def _policy_bound(entry: CapabilityRegistryEntry) -> bool:
    return bool(
        entry.authority_policy.required_roles
        and entry.evidence_model.required_evidence
        and entry.effect_model.expected_effects
        and entry.obligation_model.owner_team
    )


def _recovery_evidence_present(
    entry: CapabilityRegistryEntry,
    maturity_extensions: Mapping[str, Any],
) -> bool:
    if "recovery_evidence_present" in maturity_extensions:
        return _extension_bool(maturity_extensions, "recovery_evidence_present")
    return bool(entry.recovery_plan.rollback_capability or entry.recovery_plan.compensation_capability)


def _extension_bool(payload: Mapping[str, Any], key: str) -> bool:
    return payload.get(key) is True


def _evidence_refs(
    entry: CapabilityRegistryEntry,
    maturity_extensions: Mapping[str, Any],
) -> tuple[str, ...]:
    refs = maturity_extensions.get("evidence_refs", ())
    if not isinstance(refs, (list, tuple)):
        refs = ()
    return (
        f"capability_registry:{entry.capability_id}",
        f"capability_certification:{entry.certification_status.value}",
        *(str(ref) for ref in refs),
    )


def _maturity_counts(assessments: Any) -> dict[str, int]:
    counts = {level: 0 for level in MATURITY_LEVELS}
    for assessment in assessments:
        level = str(assessment.get("maturity_level", ""))
        if level in counts:
            counts[level] += 1
    return counts
