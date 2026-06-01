"""Purpose: immutable governed action contract for intent-to-dispatch admission.
Governance scope: typed intent, capability passport, authority proof, and
    recovery/evidence obligations that must bind before execution.
Dependencies: shared contract helpers and governed capability fabric contracts.
Invariants:
  - A governed action always carries typed intent, passport, and authority proof.
  - Authority proof must cover every role required by the capability passport.
  - World-mutating capabilities require rollback or compensation before admission.
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
)
from .governed_capability_fabric import (
    CapabilityRegistryEntry,
    GovernedCapabilityRecord,
)


class GovernedActionState(StrEnum):
    """Lifecycle state for the admitted governed action unit."""

    ADMITTED = "admitted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class TypedIntentRecord(ContractRecord):
    """Formal intent record compiled before a capability may execute."""

    command_id: str
    tenant_id: str
    actor_id: str
    intent_name: str
    objective: str
    input_hash: str

    def __post_init__(self) -> None:
        for field_name in (
            "command_id",
            "tenant_id",
            "actor_id",
            "intent_name",
            "objective",
            "input_hash",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True, slots=True)
class CapabilityPassportRecord(ContractRecord):
    """Capability passport projected from an installed registry entry."""

    capability_id: str
    version: str
    passport_hash: str
    risk_level: str
    input_schema_ref: str
    output_schema_ref: str
    required_roles: tuple[str, ...]
    approval_chain: tuple[str, ...]
    separation_of_duty: bool
    evidence_required: tuple[str, ...]
    terminal_certificate_required: bool
    expected_effects: tuple[str, ...]
    forbidden_effects: tuple[str, ...]
    execution_plane: str
    network_allowlist: tuple[str, ...]
    secret_scope: str
    rollback_capability: str
    compensation_capability: str
    review_required_on_failure: bool
    budget_class: str
    max_estimated_cost: float
    world_mutating: bool
    reconciliation_required: bool

    def __post_init__(self) -> None:
        for field_name in (
            "capability_id",
            "version",
            "passport_hash",
            "risk_level",
            "input_schema_ref",
            "output_schema_ref",
            "execution_plane",
            "secret_scope",
            "budget_class",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        for field_name in (
            "required_roles",
            "approval_chain",
            "evidence_required",
            "expected_effects",
            "forbidden_effects",
            "network_allowlist",
        ):
            raw_values = getattr(self, field_name)
            values = (
                require_non_empty_tuple(raw_values, field_name)
                if field_name
                in {
                    "required_roles",
                    "evidence_required",
                    "expected_effects",
                    "forbidden_effects",
                }
                else freeze_value(list(raw_values))
            )
            object.__setattr__(self, field_name, values)
            for index, value in enumerate(values):
                require_non_empty_text(value, f"{field_name}[{index}]")
        for field_name in ("rollback_capability", "compensation_capability"):
            value = getattr(self, field_name)
            if value:
                object.__setattr__(self, field_name, require_non_empty_text(value, field_name))
        for field_name in (
            "separation_of_duty",
            "terminal_certificate_required",
            "review_required_on_failure",
            "world_mutating",
            "reconciliation_required",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")
        object.__setattr__(
            self,
            "max_estimated_cost",
            require_non_negative_float(self.max_estimated_cost, "max_estimated_cost"),
        )

    @property
    def has_recovery_path(self) -> bool:
        """Return whether direct rollback or compensation is available."""
        return bool(self.rollback_capability or self.compensation_capability)


@dataclass(frozen=True, slots=True)
class AuthorityProofRecord(ContractRecord):
    """Proof that the actor has authority to use the capability."""

    actor_id: str
    tenant_id: str
    required_roles: tuple[str, ...]
    actor_roles: tuple[str, ...]
    approval_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("actor_id", "tenant_id"):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        for field_name in ("required_roles", "actor_roles"):
            values = require_non_empty_tuple(getattr(self, field_name), field_name)
            object.__setattr__(self, field_name, values)
            for index, value in enumerate(values):
                require_non_empty_text(value, f"{field_name}[{index}]")
        object.__setattr__(self, "approval_refs", freeze_value(list(self.approval_refs)))
        for index, value in enumerate(self.approval_refs):
            require_non_empty_text(value, f"approval_refs[{index}]")
        missing_roles = tuple(role for role in self.required_roles if role not in self.actor_roles)
        if missing_roles:
            raise ValueError("authority proof missing required roles")


@dataclass(frozen=True, slots=True)
class GovernedAction(ContractRecord):
    """Single governed unit binding meaning, capability, authority, and recovery."""

    governed_action_id: str
    command_id: str
    tenant_id: str
    actor_id: str
    typed_intent: TypedIntentRecord
    capability_passport: CapabilityPassportRecord
    authority_proof: AuthorityProofRecord
    state: GovernedActionState
    issued_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("governed_action_id", "command_id", "tenant_id", "actor_id"):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if not isinstance(self.typed_intent, TypedIntentRecord):
            raise ValueError("typed_intent must be a TypedIntentRecord")
        if not isinstance(self.capability_passport, CapabilityPassportRecord):
            raise ValueError("capability_passport must be a CapabilityPassportRecord")
        if not isinstance(self.authority_proof, AuthorityProofRecord):
            raise ValueError("authority_proof must be an AuthorityProofRecord")
        if not isinstance(self.state, GovernedActionState):
            raise ValueError("state must be a GovernedActionState value")
        object.__setattr__(self, "issued_at", require_datetime_text(self.issued_at, "issued_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        if self.capability_passport.world_mutating and not self.capability_passport.has_recovery_path:
            raise ValueError("world-mutating governed action requires rollback or compensation")


def build_capability_passport(
    entry: CapabilityRegistryEntry,
    *,
    passport_hash: str,
) -> CapabilityPassportRecord:
    """Project a registry entry into the execution-facing passport contract."""
    record = GovernedCapabilityRecord.from_registry_entry(entry)
    return CapabilityPassportRecord(
        capability_id=entry.capability_id,
        version=entry.version,
        passport_hash=require_non_empty_text(passport_hash, "passport_hash"),
        risk_level=record.risk_level.value,
        input_schema_ref=entry.input_schema_ref,
        output_schema_ref=entry.output_schema_ref,
        required_roles=entry.authority_policy.required_roles,
        approval_chain=entry.authority_policy.approval_chain,
        separation_of_duty=entry.authority_policy.separation_of_duty,
        evidence_required=entry.evidence_model.required_evidence,
        terminal_certificate_required=entry.evidence_model.terminal_certificate_required,
        expected_effects=entry.effect_model.expected_effects,
        forbidden_effects=entry.effect_model.forbidden_effects,
        execution_plane=entry.isolation_profile.execution_plane,
        network_allowlist=entry.isolation_profile.network_allowlist,
        secret_scope=entry.isolation_profile.secret_scope,
        rollback_capability=entry.recovery_plan.rollback_capability,
        compensation_capability=entry.recovery_plan.compensation_capability,
        review_required_on_failure=entry.recovery_plan.review_required_on_failure,
        budget_class=entry.cost_model.budget_class,
        max_estimated_cost=entry.cost_model.max_estimated_cost,
        world_mutating=record.world_mutating,
        reconciliation_required=entry.effect_model.reconciliation_required,
    )
