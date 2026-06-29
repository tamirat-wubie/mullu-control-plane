"""Purpose: proof-of-success contracts for governed capability completion claims.
Governance scope: capability success predicates, proof obligations, evidence
    freshness, invariant preservation, verdict policy, and receipt requirements.
Dependencies: shared contract base helpers.
Invariants:
  - Mandatory proof obligations cannot be empty or averaged away.
  - Success predicates require evidence, scope, authority, causality,
    invariant, contradiction, and durability gates.
  - Pending, partial, and blocked verdicts remain distinct from clean success.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_non_empty_text,
    require_non_empty_tuple,
    require_non_negative_int,
)


class SuccessProofLevel(StrEnum):
    """Bounded proof level required before a capability may claim success."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"


class CapabilitySuccessClaimType(StrEnum):
    """Domain claim class used to bind success semantics to a capability."""

    READ_OBSERVATION = "read_observation"
    FILE_WRITE = "file_write"
    COMMAND_RUN = "command_run"
    EMAIL_SEND = "email_send"
    CALENDAR_WRITE = "calendar_write"
    DEPLOYMENT_WITNESS = "deployment_witness"
    PAYMENT = "payment"
    GITHUB_PR = "github_pr"
    SOFTWARE_CHANGE = "software_change"
    EVIDENCE_APPEND = "evidence_append"
    CUSTOM = "custom"


class CapabilitySuccessVerdict(StrEnum):
    """Refined false-success-safe verdict taxonomy."""

    VERIFIED_SUCCESS_CLEAN = "VERIFIED_SUCCESS_CLEAN"
    VERIFIED_SUCCESS_WITH_RESIDUAL_RISK = "VERIFIED_SUCCESS_WITH_RESIDUAL_RISK"
    PARTIAL_SUCCESS_DECLARED = "PARTIAL_SUCCESS_DECLARED"
    PENDING_EXTERNAL_SETTLEMENT = "PENDING_EXTERNAL_SETTLEMENT"
    PENDING_EVIDENCE = "PENDING_EVIDENCE"
    BLOCKED_FALSE_SUCCESS = "BLOCKED_FALSE_SUCCESS"
    BLOCKED_SCOPE_MISMATCH = "BLOCKED_SCOPE_MISMATCH"
    BLOCKED_AUTHORITY_MISMATCH = "BLOCKED_AUTHORITY_MISMATCH"
    BLOCKED_STALE_EVIDENCE = "BLOCKED_STALE_EVIDENCE"
    BLOCKED_CONTRADICTION = "BLOCKED_CONTRADICTION"
    BLOCKED_INVARIANT_DAMAGE = "BLOCKED_INVARIANT_DAMAGE"
    VERIFIED_FAILURE = "VERIFIED_FAILURE"
    INCONCLUSIVE_VERIFIER_FAILURE = "INCONCLUSIVE_VERIFIER_FAILURE"
    ESCALATED_FOR_HUMAN_REVIEW = "ESCALATED_FOR_HUMAN_REVIEW"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    ROLLED_BACK = "ROLLED_BACK"


class CapabilitySuccessRiskLevel(StrEnum):
    """Success-contract risk tier aligned with governed capability records."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class SuccessAuthorityContract(ContractRecord):
    required_permissions: tuple[str, ...]
    block_on_unknown_authority: bool
    human_confirmation_required: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_permissions", require_non_empty_tuple(self.required_permissions, "required_permissions"))
        for index, permission in enumerate(self.required_permissions):
            require_non_empty_text(permission, f"required_permissions[{index}]")
        for field_name in ("block_on_unknown_authority", "human_confirmation_required"):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SuccessAuthorityContract":
        return cls(
            required_permissions=tuple(payload["required_permissions"]),
            block_on_unknown_authority=payload["block_on_unknown_authority"],
            human_confirmation_required=payload["human_confirmation_required"],
        )


@dataclass(frozen=True, slots=True)
class SuccessExpectedDelta(ContractRecord):
    required_changes: tuple[str, ...]
    forbidden_changes: tuple[str, ...]
    optional_changes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_changes", require_non_empty_tuple(self.required_changes, "required_changes"))
        object.__setattr__(self, "forbidden_changes", require_non_empty_tuple(self.forbidden_changes, "forbidden_changes"))
        object.__setattr__(self, "optional_changes", freeze_value(list(self.optional_changes)))
        for field_name in ("required_changes", "forbidden_changes", "optional_changes"):
            for index, value in enumerate(getattr(self, field_name)):
                require_non_empty_text(value, f"{field_name}[{index}]")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SuccessExpectedDelta":
        return cls(
            required_changes=tuple(payload["required_changes"]),
            forbidden_changes=tuple(payload["forbidden_changes"]),
            optional_changes=tuple(payload.get("optional_changes", ())),
        )


@dataclass(frozen=True, slots=True)
class SuccessInvariantContract(ContractRecord):
    must_remain_true: tuple[str, ...]
    must_not_happen: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "must_remain_true", require_non_empty_tuple(self.must_remain_true, "must_remain_true"))
        object.__setattr__(self, "must_not_happen", require_non_empty_tuple(self.must_not_happen, "must_not_happen"))
        for field_name in ("must_remain_true", "must_not_happen"):
            for index, value in enumerate(getattr(self, field_name)):
                require_non_empty_text(value, f"{field_name}[{index}]")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SuccessInvariantContract":
        return cls(
            must_remain_true=tuple(payload["must_remain_true"]),
            must_not_happen=tuple(payload["must_not_happen"]),
        )


@dataclass(frozen=True, slots=True)
class SuccessProofObligation(ContractRecord):
    obligation_id: str
    what_must_be_proven: str
    evidence_fields: tuple[str, ...]
    evidence_type: str
    verifier: str
    freshness_window_seconds: int
    scope_binding: tuple[str, ...]
    mandatory: bool
    failure_effect: CapabilitySuccessVerdict

    def __post_init__(self) -> None:
        object.__setattr__(self, "obligation_id", require_non_empty_text(self.obligation_id, "obligation_id"))
        object.__setattr__(self, "what_must_be_proven", require_non_empty_text(self.what_must_be_proven, "what_must_be_proven"))
        object.__setattr__(self, "evidence_fields", require_non_empty_tuple(self.evidence_fields, "evidence_fields"))
        object.__setattr__(self, "evidence_type", require_non_empty_text(self.evidence_type, "evidence_type"))
        object.__setattr__(self, "verifier", require_non_empty_text(self.verifier, "verifier"))
        object.__setattr__(
            self,
            "freshness_window_seconds",
            require_non_negative_int(self.freshness_window_seconds, "freshness_window_seconds"),
        )
        object.__setattr__(self, "scope_binding", require_non_empty_tuple(self.scope_binding, "scope_binding"))
        if not isinstance(self.mandatory, bool):
            raise ValueError("mandatory must be a boolean")
        if not isinstance(self.failure_effect, CapabilitySuccessVerdict):
            raise ValueError("failure_effect must be a CapabilitySuccessVerdict value")
        for field_name in ("evidence_fields", "scope_binding"):
            for index, value in enumerate(getattr(self, field_name)):
                require_non_empty_text(value, f"{field_name}[{index}]")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SuccessProofObligation":
        return cls(
            obligation_id=payload["obligation_id"],
            what_must_be_proven=payload["what_must_be_proven"],
            evidence_fields=tuple(payload["evidence_fields"]),
            evidence_type=payload["evidence_type"],
            verifier=payload["verifier"],
            freshness_window_seconds=payload["freshness_window_seconds"],
            scope_binding=tuple(payload["scope_binding"]),
            mandatory=payload["mandatory"],
            failure_effect=CapabilitySuccessVerdict(payload["failure_effect"]),
        )


@dataclass(frozen=True, slots=True)
class SuccessFreshnessPolicy(ContractRecord):
    max_age_seconds: int
    recheck_required: bool
    durability_window_seconds: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_age_seconds", require_non_negative_int(self.max_age_seconds, "max_age_seconds"))
        object.__setattr__(
            self,
            "durability_window_seconds",
            require_non_negative_int(self.durability_window_seconds, "durability_window_seconds"),
        )
        if not isinstance(self.recheck_required, bool):
            raise ValueError("recheck_required must be a boolean")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SuccessFreshnessPolicy":
        return cls(
            max_age_seconds=payload["max_age_seconds"],
            recheck_required=payload["recheck_required"],
            durability_window_seconds=payload["durability_window_seconds"],
        )


@dataclass(frozen=True, slots=True)
class SuccessAcceptancePredicate(ContractRecord):
    all_mandatory_evidence_present: bool
    expected_delta_verified: bool
    forbidden_delta_absent: bool
    invariants_preserved: bool
    causal_trace_valid: bool
    contradictions_absent: bool
    durability_satisfied: bool

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SuccessAcceptancePredicate":
        return cls(
            all_mandatory_evidence_present=payload["all_mandatory_evidence_present"],
            expected_delta_verified=payload["expected_delta_verified"],
            forbidden_delta_absent=payload["forbidden_delta_absent"],
            invariants_preserved=payload["invariants_preserved"],
            causal_trace_valid=payload["causal_trace_valid"],
            contradictions_absent=payload["contradictions_absent"],
            durability_satisfied=payload["durability_satisfied"],
        )

    @property
    def requires_all_success_gates(self) -> bool:
        return all(bool(getattr(self, field_name)) for field_name in self.__dataclass_fields__)


@dataclass(frozen=True, slots=True)
class SuccessVerdictPolicy(ContractRecord):
    allow_partial_success: bool
    allow_pending_success: bool
    block_on_stale_evidence: bool
    block_on_scope_mismatch: bool
    block_on_unknown_authority: bool

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SuccessVerdictPolicy":
        return cls(
            allow_partial_success=payload["allow_partial_success"],
            allow_pending_success=payload["allow_pending_success"],
            block_on_stale_evidence=payload["block_on_stale_evidence"],
            block_on_scope_mismatch=payload["block_on_scope_mismatch"],
            block_on_unknown_authority=payload["block_on_unknown_authority"],
        )


@dataclass(frozen=True, slots=True)
class SuccessRepairPolicy(ContractRecord):
    retry_allowed: bool
    rollback_required_on_contamination: bool
    escalate_on_high_risk: bool

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SuccessRepairPolicy":
        return cls(
            retry_allowed=payload["retry_allowed"],
            rollback_required_on_contamination=payload["rollback_required_on_contamination"],
            escalate_on_high_risk=payload["escalate_on_high_risk"],
        )


@dataclass(frozen=True, slots=True)
class SuccessReceiptRequirements(ContractRecord):
    required_fields: tuple[str, ...]
    hash_chain_required: bool
    residual_gaps_required: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_fields", require_non_empty_tuple(self.required_fields, "required_fields"))
        for index, field_ref in enumerate(self.required_fields):
            require_non_empty_text(field_ref, f"required_fields[{index}]")
        for field_name in ("hash_chain_required", "residual_gaps_required"):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SuccessReceiptRequirements":
        return cls(
            required_fields=tuple(payload["required_fields"]),
            hash_chain_required=payload["hash_chain_required"],
            residual_gaps_required=payload["residual_gaps_required"],
        )


@dataclass(frozen=True, slots=True)
class CapabilitySuccessContract(ContractRecord):
    contract_id: str
    capability_id: str
    domain: str
    claim_type: CapabilitySuccessClaimType
    risk_level: CapabilitySuccessRiskLevel
    proof_level_required: SuccessProofLevel
    scope_bindings: tuple[str, ...]
    authority: SuccessAuthorityContract
    expected_delta: SuccessExpectedDelta
    invariants: SuccessInvariantContract
    proof_obligations: tuple[SuccessProofObligation, ...]
    independent_evidence_required: bool
    freshness: SuccessFreshnessPolicy
    acceptance_predicate: SuccessAcceptancePredicate
    verdict_policy: SuccessVerdictPolicy
    repair_policy: SuccessRepairPolicy
    receipt_requirements: SuccessReceiptRequirements
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("contract_id", "capability_id", "domain"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.claim_type, CapabilitySuccessClaimType):
            raise ValueError("claim_type must be a CapabilitySuccessClaimType value")
        if not isinstance(self.risk_level, CapabilitySuccessRiskLevel):
            raise ValueError("risk_level must be a CapabilitySuccessRiskLevel value")
        if not isinstance(self.proof_level_required, SuccessProofLevel):
            raise ValueError("proof_level_required must be a SuccessProofLevel value")
        object.__setattr__(self, "scope_bindings", require_non_empty_tuple(self.scope_bindings, "scope_bindings"))
        object.__setattr__(self, "proof_obligations", require_non_empty_tuple(self.proof_obligations, "proof_obligations"))
        if not isinstance(self.independent_evidence_required, bool):
            raise ValueError("independent_evidence_required must be a boolean")
        expected_types = (
            ("authority", SuccessAuthorityContract),
            ("expected_delta", SuccessExpectedDelta),
            ("invariants", SuccessInvariantContract),
            ("freshness", SuccessFreshnessPolicy),
            ("acceptance_predicate", SuccessAcceptancePredicate),
            ("verdict_policy", SuccessVerdictPolicy),
            ("repair_policy", SuccessRepairPolicy),
            ("receipt_requirements", SuccessReceiptRequirements),
        )
        for field_name, expected_type in expected_types:
            if not isinstance(getattr(self, field_name), expected_type):
                raise ValueError(f"{field_name} must be a {expected_type.__name__} value")
        for index, obligation in enumerate(self.proof_obligations):
            if not isinstance(obligation, SuccessProofObligation):
                raise ValueError(f"proof_obligations[{index}] must be a SuccessProofObligation value")
        if not any(obligation.mandatory for obligation in self.proof_obligations):
            raise ValueError("proof_obligations must contain at least one mandatory obligation")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CapabilitySuccessContract":
        return cls(
            contract_id=payload["contract_id"],
            capability_id=payload["capability_id"],
            domain=payload["domain"],
            claim_type=CapabilitySuccessClaimType(payload["claim_type"]),
            risk_level=CapabilitySuccessRiskLevel(payload["risk_level"]),
            proof_level_required=SuccessProofLevel(payload["proof_level_required"]),
            scope_bindings=tuple(payload["scope_bindings"]),
            authority=SuccessAuthorityContract.from_mapping(payload["authority"]),
            expected_delta=SuccessExpectedDelta.from_mapping(payload["expected_delta"]),
            invariants=SuccessInvariantContract.from_mapping(payload["invariants"]),
            proof_obligations=tuple(
                SuccessProofObligation.from_mapping(obligation)
                for obligation in payload["proof_obligations"]
            ),
            independent_evidence_required=payload["independent_evidence_required"],
            freshness=SuccessFreshnessPolicy.from_mapping(payload["freshness"]),
            acceptance_predicate=SuccessAcceptancePredicate.from_mapping(payload["acceptance_predicate"]),
            verdict_policy=SuccessVerdictPolicy.from_mapping(payload["verdict_policy"]),
            repair_policy=SuccessRepairPolicy.from_mapping(payload["repair_policy"]),
            receipt_requirements=SuccessReceiptRequirements.from_mapping(payload["receipt_requirements"]),
            metadata=payload.get("metadata", {}),
        )

    @property
    def mandatory_evidence_fields(self) -> tuple[str, ...]:
        """Return mandatory evidence field names in deterministic order."""
        fields: list[str] = []
        for obligation in self.proof_obligations:
            if obligation.mandatory:
                fields.extend(obligation.evidence_fields)
        return tuple(dict.fromkeys(fields))
