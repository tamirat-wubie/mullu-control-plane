"""Purpose: governed capability fabric contracts for universal action admission.
Governance scope: capability registry entries, domain capsules, compiler artifacts,
    and compilation results.
Dependencies: shared contract base helpers and fabric schemas.
Invariants:
  - Capability entries always bind authority, evidence, isolation, recovery, cost, and obligations.
  - Domain capsules always bind capabilities to policies, evidence, recovery, tests, read models, and views.
  - Compiler results are immutable and carry explicit errors, warnings, and emitted artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
    require_non_negative_float,
    require_non_negative_int,
)


class CapabilityCertificationStatus(StrEnum):
    """Lifecycle state for a capability registry entry."""

    CANDIDATE = "candidate"
    CERTIFIED = "certified"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class DomainCapsuleCertificationStatus(StrEnum):
    """Lifecycle state for a domain capsule."""

    DRAFT = "draft"
    CERTIFIED = "certified"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class CapsuleCompilationStatus(StrEnum):
    """Outcome of compiling a domain capsule."""

    SUCCESS = "success"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"
    FAILED = "failed"


class CapsuleAdmissionStatus(StrEnum):
    """Outcome of admitting compiled capsule artifacts into a registry."""

    INSTALLED = "installed"
    REJECTED = "rejected"


class CommandCapabilityAdmissionStatus(StrEnum):
    """Outcome of resolving a typed command intent against installed capabilities."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class CapabilityEffectModel(ContractRecord):
    expected_effects: tuple[str, ...]
    forbidden_effects: tuple[str, ...]
    reconciliation_required: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "expected_effects", require_non_empty_tuple(self.expected_effects, "expected_effects"))
        object.__setattr__(self, "forbidden_effects", require_non_empty_tuple(self.forbidden_effects, "forbidden_effects"))
        for index, effect in enumerate(self.expected_effects):
            require_non_empty_text(effect, f"expected_effects[{index}]")
        for index, effect in enumerate(self.forbidden_effects):
            require_non_empty_text(effect, f"forbidden_effects[{index}]")
        if not isinstance(self.reconciliation_required, bool):
            raise ValueError("reconciliation_required must be a boolean")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CapabilityEffectModel":
        return cls(
            expected_effects=tuple(payload["expected_effects"]),
            forbidden_effects=tuple(payload["forbidden_effects"]),
            reconciliation_required=payload["reconciliation_required"],
        )


@dataclass(frozen=True, slots=True)
class CapabilityEvidenceModel(ContractRecord):
    required_evidence: tuple[str, ...]
    terminal_certificate_required: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_evidence", require_non_empty_tuple(self.required_evidence, "required_evidence"))
        for index, evidence in enumerate(self.required_evidence):
            require_non_empty_text(evidence, f"required_evidence[{index}]")
        if not isinstance(self.terminal_certificate_required, bool):
            raise ValueError("terminal_certificate_required must be a boolean")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CapabilityEvidenceModel":
        return cls(
            required_evidence=tuple(payload["required_evidence"]),
            terminal_certificate_required=payload["terminal_certificate_required"],
        )


@dataclass(frozen=True, slots=True)
class CapabilityAuthorityPolicy(ContractRecord):
    required_roles: tuple[str, ...]
    approval_chain: tuple[str, ...] = ()
    separation_of_duty: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_roles", require_non_empty_tuple(self.required_roles, "required_roles"))
        object.__setattr__(self, "approval_chain", freeze_value(list(self.approval_chain)))
        for index, role in enumerate(self.required_roles):
            require_non_empty_text(role, f"required_roles[{index}]")
        for index, approver in enumerate(self.approval_chain):
            require_non_empty_text(approver, f"approval_chain[{index}]")
        if not isinstance(self.separation_of_duty, bool):
            raise ValueError("separation_of_duty must be a boolean")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CapabilityAuthorityPolicy":
        return cls(
            required_roles=tuple(payload["required_roles"]),
            approval_chain=tuple(payload.get("approval_chain", ())),
            separation_of_duty=payload["separation_of_duty"],
        )


@dataclass(frozen=True, slots=True)
class CapabilityIsolationProfile(ContractRecord):
    execution_plane: str
    network_allowlist: tuple[str, ...]
    secret_scope: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "execution_plane", require_non_empty_text(self.execution_plane, "execution_plane"))
        object.__setattr__(self, "network_allowlist", freeze_value(list(self.network_allowlist)))
        object.__setattr__(self, "secret_scope", require_non_empty_text(self.secret_scope, "secret_scope"))
        for index, host in enumerate(self.network_allowlist):
            require_non_empty_text(host, f"network_allowlist[{index}]")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CapabilityIsolationProfile":
        return cls(
            execution_plane=payload["execution_plane"],
            network_allowlist=tuple(payload.get("network_allowlist", ())),
            secret_scope=payload["secret_scope"],
        )


@dataclass(frozen=True, slots=True)
class CapabilityRecoveryPlan(ContractRecord):
    rollback_capability: str = ""
    compensation_capability: str = ""
    review_required_on_failure: bool = True

    def __post_init__(self) -> None:
        if self.rollback_capability:
            object.__setattr__(self, "rollback_capability", require_non_empty_text(self.rollback_capability, "rollback_capability"))
        if self.compensation_capability:
            object.__setattr__(
                self,
                "compensation_capability",
                require_non_empty_text(self.compensation_capability, "compensation_capability"),
            )
        if not isinstance(self.review_required_on_failure, bool):
            raise ValueError("review_required_on_failure must be a boolean")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CapabilityRecoveryPlan":
        return cls(
            rollback_capability=payload.get("rollback_capability", ""),
            compensation_capability=payload.get("compensation_capability", ""),
            review_required_on_failure=payload["review_required_on_failure"],
        )


@dataclass(frozen=True, slots=True)
class CapabilityCostModel(ContractRecord):
    budget_class: str
    max_estimated_cost: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "budget_class", require_non_empty_text(self.budget_class, "budget_class"))
        object.__setattr__(self, "max_estimated_cost", require_non_negative_float(self.max_estimated_cost, "max_estimated_cost"))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CapabilityCostModel":
        return cls(
            budget_class=payload["budget_class"],
            max_estimated_cost=payload["max_estimated_cost"],
        )


@dataclass(frozen=True, slots=True)
class CapabilityObligationModel(ContractRecord):
    owner_team: str
    failure_due_seconds: int
    escalation_route: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_team", require_non_empty_text(self.owner_team, "owner_team"))
        object.__setattr__(self, "failure_due_seconds", require_non_negative_int(self.failure_due_seconds, "failure_due_seconds"))
        object.__setattr__(self, "escalation_route", require_non_empty_text(self.escalation_route, "escalation_route"))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CapabilityObligationModel":
        return cls(
            owner_team=payload["owner_team"],
            failure_due_seconds=payload["failure_due_seconds"],
            escalation_route=payload["escalation_route"],
        )


@dataclass(frozen=True, slots=True)
class CapabilityRegistryEntry(ContractRecord):
    capability_id: str
    domain: str
    version: str
    input_schema_ref: str
    output_schema_ref: str
    effect_model: CapabilityEffectModel
    evidence_model: CapabilityEvidenceModel
    authority_policy: CapabilityAuthorityPolicy
    isolation_profile: CapabilityIsolationProfile
    recovery_plan: CapabilityRecoveryPlan
    cost_model: CapabilityCostModel
    obligation_model: CapabilityObligationModel
    certification_status: CapabilityCertificationStatus
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("capability_id", "domain", "version", "input_schema_ref", "output_schema_ref"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name, expected_type in (
            ("effect_model", CapabilityEffectModel),
            ("evidence_model", CapabilityEvidenceModel),
            ("authority_policy", CapabilityAuthorityPolicy),
            ("isolation_profile", CapabilityIsolationProfile),
            ("recovery_plan", CapabilityRecoveryPlan),
            ("cost_model", CapabilityCostModel),
            ("obligation_model", CapabilityObligationModel),
        ):
            if not isinstance(getattr(self, field_name), expected_type):
                raise ValueError(f"{field_name} must be a {expected_type.__name__} value")
        if not isinstance(self.certification_status, CapabilityCertificationStatus):
            raise ValueError("certification_status must be a CapabilityCertificationStatus value")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CapabilityRegistryEntry":
        return cls(
            capability_id=payload["capability_id"],
            domain=payload["domain"],
            version=payload["version"],
            input_schema_ref=payload["input_schema_ref"],
            output_schema_ref=payload["output_schema_ref"],
            effect_model=CapabilityEffectModel.from_mapping(payload["effect_model"]),
            evidence_model=CapabilityEvidenceModel.from_mapping(payload["evidence_model"]),
            authority_policy=CapabilityAuthorityPolicy.from_mapping(payload["authority_policy"]),
            isolation_profile=CapabilityIsolationProfile.from_mapping(payload["isolation_profile"]),
            recovery_plan=CapabilityRecoveryPlan.from_mapping(payload["recovery_plan"]),
            cost_model=CapabilityCostModel.from_mapping(payload["cost_model"]),
            obligation_model=CapabilityObligationModel.from_mapping(payload["obligation_model"]),
            certification_status=CapabilityCertificationStatus(payload["certification_status"]),
            metadata=payload.get("metadata", {}),
            extensions=payload.get("extensions", {}),
        )


@dataclass(frozen=True, slots=True)
class DomainCapsule(ContractRecord):
    capsule_id: str
    domain: str
    version: str
    ontology_refs: tuple[str, ...]
    capability_refs: tuple[str, ...]
    policy_refs: tuple[str, ...]
    evidence_rules: tuple[str, ...]
    approval_rules: tuple[str, ...]
    recovery_rules: tuple[str, ...]
    test_fixture_refs: tuple[str, ...]
    read_model_refs: tuple[str, ...]
    operator_view_refs: tuple[str, ...]
    owner_team: str
    certification_status: DomainCapsuleCertificationStatus
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("capsule_id", "domain", "version", "owner_team"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in (
            "ontology_refs",
            "capability_refs",
            "policy_refs",
            "evidence_rules",
            "approval_rules",
            "recovery_rules",
            "test_fixture_refs",
            "read_model_refs",
            "operator_view_refs",
        ):
            values = require_non_empty_tuple(getattr(self, field_name), field_name)
            object.__setattr__(self, field_name, values)
            for index, value in enumerate(values):
                require_non_empty_text(value, f"{field_name}[{index}]")
        if not isinstance(self.certification_status, DomainCapsuleCertificationStatus):
            raise ValueError("certification_status must be a DomainCapsuleCertificationStatus value")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "DomainCapsule":
        return cls(
            capsule_id=payload["capsule_id"],
            domain=payload["domain"],
            version=payload["version"],
            ontology_refs=tuple(payload["ontology_refs"]),
            capability_refs=tuple(payload["capability_refs"]),
            policy_refs=tuple(payload["policy_refs"]),
            evidence_rules=tuple(payload["evidence_rules"]),
            approval_rules=tuple(payload["approval_rules"]),
            recovery_rules=tuple(payload["recovery_rules"]),
            test_fixture_refs=tuple(payload["test_fixture_refs"]),
            read_model_refs=tuple(payload["read_model_refs"]),
            operator_view_refs=tuple(payload["operator_view_refs"]),
            owner_team=payload["owner_team"],
            certification_status=DomainCapsuleCertificationStatus(payload["certification_status"]),
            metadata=payload.get("metadata", {}),
            extensions=payload.get("extensions", {}),
        )


@dataclass(frozen=True, slots=True)
class CapsuleCompilerArtifact(ContractRecord):
    artifact_id: str
    artifact_type: str
    source_capsule_id: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", require_non_empty_text(self.artifact_id, "artifact_id"))
        object.__setattr__(self, "artifact_type", require_non_empty_text(self.artifact_type, "artifact_type"))
        object.__setattr__(self, "source_capsule_id", require_non_empty_text(self.source_capsule_id, "source_capsule_id"))
        object.__setattr__(self, "payload", freeze_value(self.payload))


@dataclass(frozen=True, slots=True)
class CapsuleCompilationResult(ContractRecord):
    compilation_id: str
    capsule_id: str
    status: CapsuleCompilationStatus
    artifacts: tuple[CapsuleCompilerArtifact, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    compiled_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "compilation_id", require_non_empty_text(self.compilation_id, "compilation_id"))
        object.__setattr__(self, "capsule_id", require_non_empty_text(self.capsule_id, "capsule_id"))
        if not isinstance(self.status, CapsuleCompilationStatus):
            raise ValueError("status must be a CapsuleCompilationStatus value")
        object.__setattr__(self, "artifacts", freeze_value(list(self.artifacts)))
        for artifact in self.artifacts:
            if not isinstance(artifact, CapsuleCompilerArtifact):
                raise ValueError("each artifact must be a CapsuleCompilerArtifact value")
        object.__setattr__(self, "warnings", freeze_value(list(self.warnings)))
        object.__setattr__(self, "errors", freeze_value(list(self.errors)))
        for index, warning in enumerate(self.warnings):
            require_non_empty_text(warning, f"warnings[{index}]")
        for index, error in enumerate(self.errors):
            require_non_empty_text(error, f"errors[{index}]")
        object.__setattr__(self, "compiled_at", require_datetime_text(self.compiled_at, "compiled_at"))

    @property
    def succeeded(self) -> bool:
        return self.status in (
            CapsuleCompilationStatus.SUCCESS,
            CapsuleCompilationStatus.SUCCESS_WITH_WARNINGS,
        )


@dataclass(frozen=True, slots=True)
class CapsuleInstallationRecord(ContractRecord):
    installation_id: str
    capsule_id: str
    status: CapsuleAdmissionStatus
    capability_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    installed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "installation_id", require_non_empty_text(self.installation_id, "installation_id"))
        object.__setattr__(self, "capsule_id", require_non_empty_text(self.capsule_id, "capsule_id"))
        if not isinstance(self.status, CapsuleAdmissionStatus):
            raise ValueError("status must be a CapsuleAdmissionStatus value")
        object.__setattr__(self, "capability_ids", freeze_value(list(self.capability_ids)))
        object.__setattr__(self, "artifact_ids", freeze_value(list(self.artifact_ids)))
        object.__setattr__(self, "warnings", freeze_value(list(self.warnings)))
        object.__setattr__(self, "errors", freeze_value(list(self.errors)))
        for index, capability_id in enumerate(self.capability_ids):
            require_non_empty_text(capability_id, f"capability_ids[{index}]")
        for index, artifact_id in enumerate(self.artifact_ids):
            require_non_empty_text(artifact_id, f"artifact_ids[{index}]")
        for index, warning in enumerate(self.warnings):
            require_non_empty_text(warning, f"warnings[{index}]")
        for index, error in enumerate(self.errors):
            require_non_empty_text(error, f"errors[{index}]")
        object.__setattr__(self, "installed_at", require_datetime_text(self.installed_at, "installed_at"))


@dataclass(frozen=True, slots=True)
class CommandCapabilityAdmissionDecision(ContractRecord):
    command_id: str
    intent_name: str
    status: CommandCapabilityAdmissionStatus
    capability_id: str
    domain: str
    owner_team: str
    evidence_required: tuple[str, ...]
    reason: str
    decided_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "command_id", require_non_empty_text(self.command_id, "command_id"))
        object.__setattr__(self, "intent_name", require_non_empty_text(self.intent_name, "intent_name"))
        if not isinstance(self.status, CommandCapabilityAdmissionStatus):
            raise ValueError("status must be a CommandCapabilityAdmissionStatus value")
        if self.status is CommandCapabilityAdmissionStatus.ACCEPTED:
            object.__setattr__(self, "capability_id", require_non_empty_text(self.capability_id, "capability_id"))
            object.__setattr__(self, "domain", require_non_empty_text(self.domain, "domain"))
            object.__setattr__(self, "owner_team", require_non_empty_text(self.owner_team, "owner_team"))
            object.__setattr__(self, "evidence_required", require_non_empty_tuple(self.evidence_required, "evidence_required"))
        else:
            if self.capability_id:
                object.__setattr__(self, "capability_id", require_non_empty_text(self.capability_id, "capability_id"))
            if self.domain:
                object.__setattr__(self, "domain", require_non_empty_text(self.domain, "domain"))
            if self.owner_team:
                object.__setattr__(self, "owner_team", require_non_empty_text(self.owner_team, "owner_team"))
            object.__setattr__(self, "evidence_required", freeze_value(list(self.evidence_required)))
        for index, evidence in enumerate(self.evidence_required):
            require_non_empty_text(evidence, f"evidence_required[{index}]")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))
