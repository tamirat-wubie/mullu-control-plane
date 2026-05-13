"""Purpose: governed capability manifest contracts for dynamic capability admission.
Governance scope: capability identity, schema refs, policy refs, maturity,
    evidence refs, sandbox/rollback obligations, and receipt contracts.
Dependencies: dataclasses, enum, typing, and shared contract utilities.
Invariants:
  - Every manifest has an owner, risk, maturity, policies, evidence, and schemas.
  - Effect-bearing posture is explicit and never inferred from prose.
  - Admission records are either admitted without errors or rejected with errors.
  - Metadata may extend the contract without changing required governance fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_non_empty_text,
    require_positive_int,
)


class CapabilityManifestRisk(StrEnum):
    """Bounded manifest risk classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CapabilityManifestMaturity(StrEnum):
    """C0-C7 capability maturity level."""

    C0 = "C0"
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"
    C4 = "C4"
    C5 = "C5"
    C6 = "C6"
    C7 = "C7"


class CapabilityManifestAdmissionStatus(StrEnum):
    """Outcome of manifest admission."""

    ADMITTED = "admitted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class CapabilityManifest(ContractRecord):
    """Governed manifest for one typed capability."""

    capability_id: str
    version: int
    kind: str
    risk: CapabilityManifestRisk
    owner: str
    input_schema_ref: str
    output_schema_ref: str
    allowed_environments: tuple[str, ...]
    required_gates: tuple[str, ...]
    rollback_required: bool
    sandbox_required: bool
    effect_bearing: bool
    maturity: CapabilityManifestMaturity
    evidence_refs: tuple[str, ...]
    policy_refs: tuple[str, ...]
    receipt_contract_ref: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "capability_id",
            "kind",
            "owner",
            "input_schema_ref",
            "output_schema_ref",
            "receipt_contract_ref",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "version", require_positive_int(self.version, "version"))
        if not isinstance(self.risk, CapabilityManifestRisk):
            raise ValueError("risk must be a CapabilityManifestRisk value")
        if not isinstance(self.maturity, CapabilityManifestMaturity):
            raise ValueError("maturity must be a CapabilityManifestMaturity value")
        for field_name in ("rollback_required", "sandbox_required", "effect_bearing"):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")
        object.__setattr__(
            self,
            "allowed_environments",
            _freeze_non_empty_text_tuple(self.allowed_environments, "allowed_environments"),
        )
        object.__setattr__(
            self,
            "required_gates",
            _freeze_non_empty_text_tuple(self.required_gates, "required_gates"),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _freeze_non_empty_text_tuple(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(
            self,
            "policy_refs",
            _freeze_non_empty_text_tuple(self.policy_refs, "policy_refs"),
        )
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CapabilityManifest":
        return cls(
            capability_id=payload["capability_id"],
            version=payload["version"],
            kind=payload["kind"],
            risk=CapabilityManifestRisk(payload["risk"]),
            owner=payload["owner"],
            input_schema_ref=payload["input_schema_ref"],
            output_schema_ref=payload["output_schema_ref"],
            allowed_environments=payload["allowed_environments"],
            required_gates=payload["required_gates"],
            rollback_required=payload["rollback_required"],
            sandbox_required=payload["sandbox_required"],
            effect_bearing=payload["effect_bearing"],
            maturity=CapabilityManifestMaturity(payload["maturity"]),
            evidence_refs=payload["evidence_refs"],
            policy_refs=payload["policy_refs"],
            receipt_contract_ref=payload["receipt_contract_ref"],
            metadata=payload.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class CapabilityManifestAdmission(ContractRecord):
    """Admission decision for a capability manifest."""

    admission_id: str
    status: CapabilityManifestAdmissionStatus
    capability_id: str
    environment: str
    source_ref: str
    manifest: CapabilityManifest | None
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    admitted_at: str

    def __post_init__(self) -> None:
        for field_name in ("admission_id", "capability_id", "environment", "source_ref", "admitted_at"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.status, CapabilityManifestAdmissionStatus):
            raise ValueError("status must be a CapabilityManifestAdmissionStatus value")
        if self.manifest is not None and not isinstance(self.manifest, CapabilityManifest):
            raise ValueError("manifest must be a CapabilityManifest or None")
        object.__setattr__(self, "errors", _freeze_text_tuple(self.errors, "errors", allow_empty=True))
        object.__setattr__(self, "warnings", _freeze_text_tuple(self.warnings, "warnings", allow_empty=True))
        for index, error in enumerate(self.errors):
            require_non_empty_text(error, f"errors[{index}]")
        for index, warning in enumerate(self.warnings):
            require_non_empty_text(warning, f"warnings[{index}]")
        if self.status is CapabilityManifestAdmissionStatus.ADMITTED and self.errors:
            raise ValueError("admitted manifest cannot carry errors")
        if self.status is CapabilityManifestAdmissionStatus.ADMITTED and self.manifest is None:
            raise ValueError("admitted manifest must include manifest")
        if self.status is CapabilityManifestAdmissionStatus.REJECTED and not self.errors:
            raise ValueError("rejected manifest must carry at least one error")


def _freeze_non_empty_text_tuple(values: object, field_name: str) -> tuple[str, ...]:
    return _freeze_text_tuple(values, field_name, allow_empty=False)


def _freeze_text_tuple(values: object, field_name: str, *, allow_empty: bool) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = freeze_value(list(values))
    if not isinstance(frozen, tuple) or not frozen:
        if allow_empty:
            return ()
        raise ValueError(f"{field_name} must contain at least one item")
    for index, value in enumerate(frozen):
        require_non_empty_text(value, f"{field_name}[{index}]")
    return frozen
