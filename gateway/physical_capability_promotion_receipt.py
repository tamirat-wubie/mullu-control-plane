"""Physical capability promotion receipts.

Purpose: bind Forge requirements, certification handoff refs, registry
    extension state, and physical promotion preflight output into one
    operator-facing evidence receipt.
Governance scope: physical capability promotion evidence, handoff provenance,
    registry extension witness, preflight readiness, and non-authoritative
    operator review receipts.
Dependencies: capability forge contracts, governed capability registry
    contracts, physical preflight reports, and command-spine canonical hashing.
Invariants:
  - Receipt generation performs no physical effect and no registry mutation.
  - Receipt generation is not admission authority.
  - Receipt generation is not terminal command closure.
  - Capability, handoff, registry entry, and preflight refs must agree.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Mapping

from gateway.capability_forge import CandidateCapabilityPackage, CapabilityCertificationHandoff
from gateway.command_spine import canonical_hash
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry
from scripts.preflight_physical_capability_promotion import PhysicalPromotionPreflightReport


_PHYSICAL_LIVE_SAFETY_EXTENSION_KEY = "physical_live_safety_evidence"
_PHYSICAL_SAFETY_EVIDENCE_FIELD_ORDER = (
    "physical_action_receipt_schema_ref",
    "physical_action_receipt_ref",
    "simulation_ref",
    "operator_approval_ref",
    "manual_override_ref",
    "emergency_stop_ref",
    "sensor_confirmation_ref",
    "deployment_witness_ref",
)


@dataclass(frozen=True, slots=True)
class PhysicalCapabilityPromotionReceipt:
    """Operator-facing receipt for a physical capability promotion candidate."""

    receipt_id: str
    capability_id: str
    candidate_package_id: str
    candidate_package_hash: str
    handoff_hash: str
    installed_registry_capability_id: str
    promotion_status: str
    preflight_ready: bool
    preflight_readiness_level: str
    preflight_blockers: tuple[str, ...]
    forge_requirement_keys: tuple[str, ...]
    handoff_required_evidence_refs: tuple[str, ...]
    handoff_physical_safety_ref_keys: tuple[str, ...]
    registry_physical_safety_evidence_present: bool
    registry_physical_safety_evidence_keys: tuple[str, ...]
    registry_physical_safety_evidence_hash: str
    evidence_refs: tuple[str, ...]
    recorded_at: str
    receipt_is_not_admission_authority: bool = True
    receipt_is_not_terminal_closure: bool = True
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "receipt_id",
            "capability_id",
            "candidate_package_id",
            "candidate_package_hash",
            "handoff_hash",
            "installed_registry_capability_id",
            "promotion_status",
            "preflight_readiness_level",
            "recorded_at",
        ):
            _require_text(str(getattr(self, field_name)), field_name)
        if self.promotion_status not in {"ready", "blocked"}:
            raise ValueError("physical_promotion_receipt_status_invalid")
        if not isinstance(self.preflight_ready, bool):
            raise ValueError("preflight_ready_boolean_required")
        if self.preflight_ready and self.promotion_status != "ready":
            raise ValueError("preflight_ready_requires_ready_status")
        if not self.preflight_ready and self.promotion_status != "blocked":
            raise ValueError("preflight_blocked_requires_blocked_status")
        if self.receipt_is_not_admission_authority is not True:
            raise ValueError("promotion_receipt_is_not_admission_authority")
        if self.receipt_is_not_terminal_closure is not True:
            raise ValueError("promotion_receipt_is_not_terminal_closure")
        object.__setattr__(self, "preflight_blockers", _text_tuple(self.preflight_blockers, "preflight_blockers", allow_empty=True))
        object.__setattr__(self, "forge_requirement_keys", _text_tuple(self.forge_requirement_keys, "forge_requirement_keys"))
        object.__setattr__(
            self,
            "handoff_required_evidence_refs",
            _text_tuple(self.handoff_required_evidence_refs, "handoff_required_evidence_refs"),
        )
        object.__setattr__(
            self,
            "handoff_physical_safety_ref_keys",
            _text_tuple(self.handoff_physical_safety_ref_keys, "handoff_physical_safety_ref_keys", allow_empty=True),
        )
        object.__setattr__(
            self,
            "registry_physical_safety_evidence_keys",
            _text_tuple(
                self.registry_physical_safety_evidence_keys,
                "registry_physical_safety_evidence_keys",
                allow_empty=True,
            ),
        )
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _metadata(self.metadata))
        if self.receipt_hash:
            _require_text(self.receipt_hash, "receipt_hash")

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON payload."""
        return _json_ready(asdict(self))


def build_physical_capability_promotion_receipt(
    *,
    candidate: CandidateCapabilityPackage,
    handoff: CapabilityCertificationHandoff,
    installed_entry: CapabilityRegistryEntry,
    preflight_report: PhysicalPromotionPreflightReport,
    recorded_at: str,
) -> PhysicalCapabilityPromotionReceipt:
    """Return a non-mutating physical capability promotion evidence receipt."""
    _require_inputs(candidate, handoff, installed_entry, preflight_report)
    physical_safety_evidence = _physical_safety_evidence(installed_entry)
    physical_safety_keys = _physical_safety_keys(physical_safety_evidence)
    physical_safety_hash = canonical_hash(physical_safety_evidence) if physical_safety_evidence else ""
    promotion_status = "ready" if preflight_report.ready else "blocked"
    receipt_seed = {
        "capability_id": candidate.capability_id,
        "candidate_package_hash": candidate.package_hash,
        "handoff_hash": handoff.handoff_hash,
        "preflight_readiness_level": preflight_report.readiness_level,
        "physical_safety_hash": physical_safety_hash,
    }
    receipt = PhysicalCapabilityPromotionReceipt(
        receipt_id=f"physical-capability-promotion-receipt-{canonical_hash(receipt_seed)[:16]}",
        capability_id=candidate.capability_id,
        candidate_package_id=candidate.package_id,
        candidate_package_hash=candidate.package_hash,
        handoff_hash=handoff.handoff_hash,
        installed_registry_capability_id=installed_entry.capability_id,
        promotion_status=promotion_status,
        preflight_ready=preflight_report.ready,
        preflight_readiness_level=preflight_report.readiness_level,
        preflight_blockers=preflight_report.blockers,
        forge_requirement_keys=_forge_requirement_keys(candidate),
        handoff_required_evidence_refs=handoff.required_evidence_refs,
        handoff_physical_safety_ref_keys=tuple(handoff.physical_live_safety_evidence_refs),
        registry_physical_safety_evidence_present=bool(physical_safety_evidence),
        registry_physical_safety_evidence_keys=physical_safety_keys,
        registry_physical_safety_evidence_hash=physical_safety_hash,
        evidence_refs=_evidence_refs(candidate, handoff, installed_entry, preflight_report),
        recorded_at=recorded_at,
        metadata={
            "operator_receipt": True,
            "no_effect_execution": True,
            "preflight_result_bound": True,
            "registry_extension_state_bound": True,
        },
    )
    return _stamp_receipt(receipt)


def _require_inputs(
    candidate: CandidateCapabilityPackage,
    handoff: CapabilityCertificationHandoff,
    installed_entry: CapabilityRegistryEntry,
    preflight_report: PhysicalPromotionPreflightReport,
) -> None:
    if not isinstance(candidate, CandidateCapabilityPackage):
        raise ValueError("candidate_package_type_invalid")
    if not isinstance(handoff, CapabilityCertificationHandoff):
        raise ValueError("certification_handoff_type_invalid")
    if not isinstance(installed_entry, CapabilityRegistryEntry):
        raise ValueError("installed_registry_entry_type_invalid")
    if not isinstance(preflight_report, PhysicalPromotionPreflightReport):
        raise ValueError("physical_preflight_report_type_invalid")
    if candidate.capability_id != handoff.capability_id:
        raise ValueError("candidate_handoff_capability_mismatch")
    if candidate.capability_id != installed_entry.capability_id:
        raise ValueError("candidate_registry_capability_mismatch")
    if candidate.capability_id not in preflight_report.live_physical_candidates:
        raise ValueError("preflight_report_capability_missing")


def _forge_requirement_keys(candidate: CandidateCapabilityPackage) -> tuple[str, ...]:
    return tuple(
        requirement.evidence_key
        for requirement in candidate.promotion_evidence_requirements
        if requirement.required
    )


def _physical_safety_evidence(installed_entry: CapabilityRegistryEntry) -> Mapping[str, Any]:
    extension = installed_entry.extensions.get(_PHYSICAL_LIVE_SAFETY_EXTENSION_KEY, {})
    if not isinstance(extension, Mapping):
        return {}
    return dict(extension)


def _physical_safety_keys(evidence: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(key for key in _PHYSICAL_SAFETY_EVIDENCE_FIELD_ORDER if str(evidence.get(key, "")).strip())


def _evidence_refs(
    candidate: CandidateCapabilityPackage,
    handoff: CapabilityCertificationHandoff,
    installed_entry: CapabilityRegistryEntry,
    preflight_report: PhysicalPromotionPreflightReport,
) -> tuple[str, ...]:
    refs = (
        f"candidate_package:{candidate.package_id}",
        f"candidate_package_hash:{candidate.package_hash}",
        f"certification_handoff:{handoff.handoff_hash}",
        f"capability_registry:{installed_entry.capability_id}",
        f"physical_preflight:{preflight_report.readiness_level}",
        *handoff.required_evidence_refs,
    )
    return tuple(dict.fromkeys(ref for ref in refs if str(ref).strip()))


def _stamp_receipt(
    receipt: PhysicalCapabilityPromotionReceipt,
) -> PhysicalCapabilityPromotionReceipt:
    payload = asdict(replace(receipt, receipt_hash=""))
    return replace(receipt, receipt_hash=canonical_hash(payload))


def _metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    payload = dict(metadata)
    payload["operator_receipt"] = True
    payload["no_effect_execution"] = True
    payload["preflight_result_bound"] = True
    payload["registry_extension_state_bound"] = True
    return payload


def _text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(str(value).strip() for value in values if str(value).strip())
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name}_required")
    return normalized


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
