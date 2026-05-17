"""Purpose: GCI capability contract schema and governance-grid evaluator.
Governance scope: capability admission before runtime execution.
Dependencies: shared contract base helpers and Python standard library enums.
Invariants:
  - Every capability contract carries the required 13 governance fields.
  - All T/E/C/R/V axes are populated before a capability can execute.
  - Capability level cannot exceed governance tier at execution admission.
  - Effectful requests from non-direct sources are blocked by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text, require_non_negative_int


class EffectClass(StrEnum):
    """Whether a capability only produces information or mutates state."""

    VALUE_PRODUCING = "value_producing"
    EFFECTFUL = "effectful"


class IntentSource(StrEnum):
    """Source trust binding for an execution request."""

    USER_DIRECT = "user_direct"
    MONITORED_CONTENT = "monitored_content"
    STANDING_RULE = "standing_rule"
    EXTERNAL_SIGNAL = "external_signal"


class CapabilityAdmissionStatus(StrEnum):
    """Result of checking a capability against the CxG governance grid."""

    ENABLED = "enabled"
    PHI_GOV_BLOCKED = "phi_gov_blocked"


@dataclass(frozen=True, slots=True)
class CapabilityContract(ContractRecord):
    """The fixed GCI unit of capability governance."""

    capability: str
    layer: str
    cap_level: int
    gov_tier: int
    axis_T: str
    axis_E: str
    axis_C: str
    axis_R: str
    axis_V: EffectClass
    precond: tuple[str, ...]
    fail_mode: tuple[str, ...]
    reversible: bool
    intent_source: IntentSource
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("capability", "layer", "axis_T", "axis_E", "axis_C", "axis_R"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "cap_level", require_non_negative_int(self.cap_level, "cap_level"))
        object.__setattr__(self, "gov_tier", require_non_negative_int(self.gov_tier, "gov_tier"))
        if not isinstance(self.axis_V, EffectClass):
            object.__setattr__(self, "axis_V", EffectClass(str(self.axis_V)))
        if not isinstance(self.intent_source, IntentSource):
            object.__setattr__(self, "intent_source", IntentSource(str(self.intent_source)))
        object.__setattr__(self, "precond", _text_tuple(self.precond, "precond"))
        object.__setattr__(self, "fail_mode", _text_tuple(self.fail_mode, "fail_mode"))
        if not isinstance(self.reversible, bool):
            raise ValueError("reversible must be a bool")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))

    @property
    def axes_populated(self) -> bool:
        return all((self.axis_T, self.axis_E, self.axis_C, self.axis_R, self.axis_V.value))


@dataclass(frozen=True, slots=True)
class CapabilityAdmissionDecision(ContractRecord):
    """Phi_gov admission decision for one capability execution attempt."""

    status: CapabilityAdmissionStatus
    allowed: bool
    capability: str
    reasons: tuple[str, ...]
    contract: CapabilityContract | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, CapabilityAdmissionStatus):
            object.__setattr__(self, "status", CapabilityAdmissionStatus(str(self.status)))
        if not isinstance(self.allowed, bool):
            raise ValueError("allowed must be a bool")
        object.__setattr__(self, "capability", require_non_empty_text(self.capability, "capability"))
        object.__setattr__(self, "reasons", _text_tuple(self.reasons, "reasons"))


def evaluate_capability_contract(
    contract: CapabilityContract | None,
    *,
    request_intent_source: IntentSource | str | None = None,
) -> CapabilityAdmissionDecision:
    """Evaluate the CxG grid and source-trust binding before execution."""
    if contract is None:
        return CapabilityAdmissionDecision(
            status=CapabilityAdmissionStatus.PHI_GOV_BLOCKED,
            allowed=False,
            capability="unknown",
            reasons=("capability_contract_missing",),
        )

    source = contract.intent_source
    if request_intent_source is not None:
        source = request_intent_source if isinstance(request_intent_source, IntentSource) else IntentSource(str(request_intent_source))

    reasons: list[str] = []
    if contract.gov_tier < contract.cap_level:
        reasons.append("governance_tier_below_capability_level")
    if not contract.axes_populated:
        reasons.append("capability_axes_incomplete")
    if contract.axis_V is EffectClass.EFFECTFUL and source is not IntentSource.USER_DIRECT:
        reasons.append("effectful_action_requires_user_direct_intent_source")

    if reasons:
        return CapabilityAdmissionDecision(
            status=CapabilityAdmissionStatus.PHI_GOV_BLOCKED,
            allowed=False,
            capability=contract.capability,
            reasons=tuple(reasons),
            contract=contract,
        )
    return CapabilityAdmissionDecision(
        status=CapabilityAdmissionStatus.ENABLED,
        allowed=True,
        capability=contract.capability,
        reasons=("capability_contract_satisfied",),
        contract=contract,
    )


def infer_effect_class(capability_name: str, declared_effects: tuple[str, ...] = ()) -> EffectClass:
    """Infer a conservative effect class for legacy tool registrations."""
    effect_tokens = (
        "send",
        "deploy",
        "delete",
        "modify",
        "write",
        "create",
        "update",
        "payment",
        "charge",
        "run",
        "execute",
    )
    text = " ".join((capability_name, *declared_effects)).lower()
    if any(token in text for token in effect_tokens):
        return EffectClass.EFFECTFUL
    return EffectClass.VALUE_PRODUCING


def default_capability_contract(
    *,
    capability: str,
    layer: str = "runtime_tool",
    cap_level: int = 1,
    gov_tier: int = 1,
    risk_tier: str = "low",
    declared_effects: tuple[str, ...] = (),
    intent_source: IntentSource = IntentSource.USER_DIRECT,
    reversible: bool = True,
) -> CapabilityContract:
    """Build a complete contract for legacy definitions that lack GCI fields."""
    effect_class = infer_effect_class(capability, declared_effects)
    return CapabilityContract(
        capability=capability,
        layer=layer,
        cap_level=cap_level,
        gov_tier=gov_tier,
        axis_T="current_episode",
        axis_E="bounded_by_budget_ref",
        axis_C="bounded_by_schema",
        axis_R=risk_tier or "low",
        axis_V=effect_class,
        precond=("registered", "parameters_validated", "audit_present"),
        fail_mode=("phi_gov_block", "receipt_recorded"),
        reversible=reversible and effect_class is EffectClass.VALUE_PRODUCING,
        intent_source=intent_source,
    )


def op_govdepth(
    *,
    current_gov_tier: int,
    requested_gov_tier: int,
    hard_risk: bool,
) -> int:
    """Adaptive governance depth operator with no downgrade on hard risk."""
    current = require_non_negative_int(current_gov_tier, "current_gov_tier")
    requested = require_non_negative_int(requested_gov_tier, "requested_gov_tier")
    if hard_risk and requested < current:
        return current
    return requested


def _text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    normalized = tuple(require_non_empty_text(str(value), f"{field_name}[]") for value in values)
    if not normalized:
        raise ValueError(f"{field_name} must contain at least one item")
    return normalized
