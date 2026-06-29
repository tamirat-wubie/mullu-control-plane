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


def _require_text_tuple(
    values: object,
    field_name: str,
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = freeze_value(list(values))
    if not isinstance(frozen, tuple):
        raise ValueError(f"{field_name} must be an array")
    if not frozen and not allow_empty:
        raise ValueError(f"{field_name} must contain at least one item")
    for index, value in enumerate(frozen):
        require_non_empty_text(value, f"{field_name}[{index}]")
    return frozen


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
    repair_template_domain: str = ""
    repair_template_action_type: str = ""
    repair_template_effect_class: str = ""
    repair_template_reversibility_class: str = ""
    repair_template_snapshot_quality: int | None = None
    repair_template_evidence: tuple[str, ...] = ()
    repair_template_external_confirmation_refs: tuple[str, ...] = ()

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
            "repair_template_domain",
            "repair_template_action_type",
            "repair_template_effect_class",
            "repair_template_reversibility_class",
        ):
            value = getattr(self, field_name)
            if value:
                object.__setattr__(self, field_name, require_non_empty_text(value, field_name))
        for field_name in (
            "required_roles",
            "approval_chain",
            "evidence_required",
            "expected_effects",
            "forbidden_effects",
            "network_allowlist",
            "repair_template_evidence",
            "repair_template_external_confirmation_refs",
        ):
            raw_values = getattr(self, field_name)
            values = _require_text_tuple(
                raw_values,
                field_name,
                allow_empty=field_name
                not in {
                    "required_roles",
                    "evidence_required",
                    "expected_effects",
                    "forbidden_effects",
                },
            )
            object.__setattr__(self, field_name, values)
        if self.repair_template_snapshot_quality is not None:
            if (
                not isinstance(self.repair_template_snapshot_quality, int)
                or isinstance(self.repair_template_snapshot_quality, bool)
                or self.repair_template_snapshot_quality < 0
                or self.repair_template_snapshot_quality > 5
            ):
                raise ValueError("repair_template_snapshot_quality must be 0 through 5 or null")
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
    approval_chain: tuple[str, ...] = ()
    approval_refs: tuple[str, ...] = ()
    approval_actor_ids: tuple[str, ...] = ()
    separation_of_duty: bool = False

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
        object.__setattr__(
            self,
            "approval_refs",
            _require_text_tuple(self.approval_refs, "approval_refs", allow_empty=True),
        )
        object.__setattr__(
            self,
            "approval_chain",
            _require_text_tuple(self.approval_chain, "approval_chain", allow_empty=True),
        )
        object.__setattr__(
            self,
            "approval_actor_ids",
            _require_text_tuple(self.approval_actor_ids, "approval_actor_ids", allow_empty=True),
        )
        if not isinstance(self.separation_of_duty, bool):
            raise ValueError("separation_of_duty must be a boolean")
        missing_roles = tuple(role for role in self.required_roles if role not in self.actor_roles)
        if missing_roles:
            raise ValueError("authority proof missing required roles")
        if self.approval_chain and len(self.approval_refs) < len(self.approval_chain):
            raise ValueError("authority proof missing approval refs")
        if self.separation_of_duty:
            if not self.approval_actor_ids:
                raise ValueError("separation of duty requires approval actor ids")
            if self.approval_refs and len(self.approval_actor_ids) < len(self.approval_refs):
                raise ValueError("separation of duty requires approval actor id for each approval ref")
            if self.actor_id in self.approval_actor_ids:
                raise ValueError("separation of duty forbids self approval")


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
        repair_template_domain=_metadata_text(entry.metadata, "causal_repair_template_domain"),
        repair_template_action_type=_metadata_text(entry.metadata, "causal_repair_template_action_type"),
        repair_template_effect_class=_metadata_text(entry.metadata, "causal_repair_effect_class"),
        repair_template_reversibility_class=_metadata_text(entry.metadata, "causal_repair_reversibility_class"),
        repair_template_snapshot_quality=_metadata_snapshot_quality(entry.metadata),
        repair_template_evidence=_metadata_text_tuple(
            entry.metadata,
            "causal_repair_template_evidence",
            fallback=entry.evidence_model.required_evidence,
        ),
        repair_template_external_confirmation_refs=_metadata_text_tuple(
            entry.metadata,
            "causal_repair_external_confirmation_refs",
        ),
    )


def _metadata_text(metadata: Mapping[str, Any], key: str) -> str:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def _metadata_text_tuple(
    metadata: Mapping[str, Any],
    key: str,
    *,
    fallback: tuple[str, ...] = (),
) -> tuple[str, ...]:
    value = metadata.get(key, fallback)
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    if not isinstance(value, (tuple, list)):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _metadata_snapshot_quality(metadata: Mapping[str, Any]) -> int | None:
    value = metadata.get("causal_repair_snapshot_quality")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("causal_repair_snapshot_quality metadata must be an integer")
    if value < 0 or value > 5:
        raise ValueError("causal_repair_snapshot_quality metadata must be 0 through 5")
    return value
