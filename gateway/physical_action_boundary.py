"""Gateway physical-action boundary.

Purpose: evaluate physical, IoT, and robotics action requests before any
    worker can claim dispatch authority.
Governance scope: hardware identity, safety envelope, simulation evidence,
    operator approval, manual override, emergency stop, sensor confirmation,
    and non-terminal receipt emission.
Dependencies: dataclasses and command-spine canonical hashing.
Invariants:
  - Every physical request emits a deterministic receipt.
  - Live effects require stricter controls than sandbox replays.
  - Sandbox receipts explicitly state that no physical effect was applied.
  - Physical-action receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Mapping

from gateway.command_spine import canonical_hash


PHYSICAL_ACTION_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:physical-action-receipt:1"
PHYSICAL_STATUSES = ("allowed", "blocked", "requires_review")
EFFECT_MODES = ("sandbox", "live")
RISK_LEVELS = ("low", "medium", "high", "critical")
BASE_PHYSICAL_CONTROLS = (
    "hardware_identity",
    "safety_envelope",
    "simulation",
    "manual_override",
    "emergency_stop",
    "worker_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class PhysicalActionRequest:
    """One candidate physical-world action before worker dispatch."""

    request_id: str
    tenant_id: str
    command_id: str
    actuator_id: str
    action: str
    effect_mode: str
    safety_envelope_ref: str
    environment_ref: str
    risk_level: str = "high"
    simulation_passed: bool = False
    operator_approval_ref: str = ""
    manual_override_ref: str = ""
    emergency_stop_ref: str = ""
    sensor_confirmation_ref: str = ""
    evidence_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.command_id, "command_id")
        _require_text(self.actuator_id, "actuator_id")
        _require_text(self.action, "action")
        _require_text(self.safety_envelope_ref, "safety_envelope_ref")
        _require_text(self.environment_ref, "environment_ref")
        if self.effect_mode not in EFFECT_MODES:
            raise ValueError("effect_mode_invalid")
        if self.risk_level not in RISK_LEVELS:
            raise ValueError("risk_level_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class PhysicalActionPolicy:
    """Policy envelope for one physical-action family."""

    policy_id: str
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...] = ()
    production_certified: bool = False
    sandbox_only: bool = True
    simulation_required: bool = True
    operator_approval_required: bool = True
    manual_override_required: bool = True
    emergency_stop_required: bool = True
    sensor_confirmation_required: bool = True
    physical_worker_receipt_required: bool = True
    terminal_closure_required: bool = True
    receipt_schema_ref: str = PHYSICAL_ACTION_RECEIPT_SCHEMA_REF
    policy_refs: tuple[str, ...] = (
        "policy:physical-safety-envelope",
        "policy:operator-approval",
        "policy:terminal-closure",
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.policy_id, "policy_id")
        object.__setattr__(self, "allowed_actions", _normalize_text_tuple(self.allowed_actions, "allowed_actions"))
        object.__setattr__(self, "forbidden_actions", _normalize_text_tuple(self.forbidden_actions, "forbidden_actions", allow_empty=True))
        object.__setattr__(self, "policy_refs", _normalize_text_tuple(self.policy_refs, "policy_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class PhysicalActionReceipt:
    """Deterministic non-terminal receipt for a physical-action decision."""

    receipt_id: str
    request_id: str
    tenant_id: str
    command_id: str
    actuator_id: str
    action: str
    effect_mode: str
    risk_level: str
    status: str
    reason: str
    policy_id: str
    safety_envelope_ref: str
    environment_ref: str
    simulation_passed: bool
    operator_approval_ref: str
    manual_override_ref: str
    emergency_stop_ref: str
    sensor_confirmation_ref: str
    evidence_refs: tuple[str, ...]
    required_controls: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    review_reasons: tuple[str, ...]
    policy_refs: tuple[str, ...]
    receipt_schema_ref: str
    physical_worker_receipt_required: bool
    operator_approval_required: bool
    manual_override_required: bool
    emergency_stop_required: bool
    sensor_confirmation_required: bool
    terminal_closure_required: bool
    no_physical_effect_applied: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in PHYSICAL_STATUSES:
            raise ValueError("physical_receipt_status_invalid")
        if self.effect_mode not in EFFECT_MODES:
            raise ValueError("effect_mode_invalid")
        if self.terminal_closure_required is not True:
            raise ValueError("physical_receipt_requires_terminal_closure")
        if self.physical_worker_receipt_required is not True:
            raise ValueError("physical_worker_receipt_required")
        if self.manual_override_required is not True:
            raise ValueError("physical_manual_override_required")
        if self.emergency_stop_required is not True:
            raise ValueError("physical_emergency_stop_required")
        if self.effect_mode == "sandbox" and self.no_physical_effect_applied is not True:
            raise ValueError("sandbox_physical_receipt_requires_no_effect")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "required_controls", tuple(self.required_controls))
        object.__setattr__(self, "blocked_reasons", tuple(self.blocked_reasons))
        object.__setattr__(self, "review_reasons", tuple(self.review_reasons))
        object.__setattr__(self, "policy_refs", tuple(self.policy_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-schema compatible projection."""
        return _json_ready(asdict(self))


class PhysicalActionBoundary:
    """Governed evaluator for physical worker admission."""

    def __init__(self, policy: PhysicalActionPolicy | None = None) -> None:
        self._policy = policy or default_physical_action_policy()

    def evaluate(self, request: PhysicalActionRequest) -> PhysicalActionReceipt:
        """Evaluate one physical-action request and emit a receipt."""
        policy = self._policy
        required_controls = list(BASE_PHYSICAL_CONTROLS)
        blocked_reasons: list[str] = []
        review_reasons: list[str] = []

        if request.action in policy.forbidden_actions:
            blocked_reasons.append("physical_action_forbidden")
        if request.action not in policy.allowed_actions:
            blocked_reasons.append("physical_action_not_allowlisted")
        if not request.evidence_refs:
            blocked_reasons.append("physical_evidence_refs_required")
        if policy.simulation_required and not request.simulation_passed:
            blocked_reasons.append("simulation_pass_required")
        if policy.manual_override_required and not request.manual_override_ref:
            blocked_reasons.append("manual_override_ref_required")
        if policy.emergency_stop_required and not request.emergency_stop_ref:
            blocked_reasons.append("emergency_stop_ref_required")

        if policy.operator_approval_required:
            _append_unique(required_controls, "operator_approval")
            if not request.operator_approval_ref:
                review_reasons.append("operator_approval_ref_required")

        if policy.sensor_confirmation_required:
            _append_unique(required_controls, "sensor_confirmation")
            if not request.sensor_confirmation_ref:
                review_reasons.append("sensor_confirmation_ref_required")

        if request.effect_mode == "live":
            _append_unique(required_controls, "production_certification")
            if policy.sandbox_only:
                blocked_reasons.append("live_physical_effect_not_allowed")
            if not policy.production_certified:
                blocked_reasons.append("production_certification_required")

        blocked_reasons = list(dict.fromkeys(blocked_reasons))
        review_reasons = list(dict.fromkeys(review_reasons))
        if blocked_reasons:
            status = "blocked"
            reason = blocked_reasons[0]
        elif review_reasons:
            status = "requires_review"
            reason = review_reasons[0]
        else:
            status = "allowed"
            reason = "physical_action_allowed"

        return _stamp_receipt(PhysicalActionReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            command_id=request.command_id,
            actuator_id=request.actuator_id,
            action=request.action,
            effect_mode=request.effect_mode,
            risk_level=request.risk_level,
            status=status,
            reason=reason,
            policy_id=policy.policy_id,
            safety_envelope_ref=request.safety_envelope_ref,
            environment_ref=request.environment_ref,
            simulation_passed=request.simulation_passed,
            operator_approval_ref=request.operator_approval_ref,
            manual_override_ref=request.manual_override_ref,
            emergency_stop_ref=request.emergency_stop_ref,
            sensor_confirmation_ref=request.sensor_confirmation_ref,
            evidence_refs=request.evidence_refs,
            required_controls=tuple(required_controls),
            blocked_reasons=tuple(blocked_reasons),
            review_reasons=tuple(review_reasons),
            policy_refs=policy.policy_refs,
            receipt_schema_ref=policy.receipt_schema_ref,
            physical_worker_receipt_required=True,
            operator_approval_required=policy.operator_approval_required,
            manual_override_required=True,
            emergency_stop_required=True,
            sensor_confirmation_required=policy.sensor_confirmation_required,
            terminal_closure_required=True,
            no_physical_effect_applied=request.effect_mode == "sandbox",
            metadata={
                "receipt_is_not_terminal_closure": True,
                "sandbox_only_policy": policy.sandbox_only,
                "production_certified": policy.production_certified,
            },
        ))


def default_physical_action_policy() -> PhysicalActionPolicy:
    """Return the conservative default physical-action policy."""
    return PhysicalActionPolicy(
        policy_id="physical-action-policy:sandbox:v1",
        allowed_actions=("sandbox_replay", "simulate_actuator_command"),
        forbidden_actions=("unlock_door", "start_machine", "move_robot", "dispatch_live_signal"),
        production_certified=False,
        sandbox_only=True,
    )


def _stamp_receipt(receipt: PhysicalActionReceipt) -> PhysicalActionReceipt:
    payload = asdict(replace(receipt, receipt_id="pending", receipt_hash=""))
    receipt_hash = canonical_hash(payload)
    return replace(receipt, receipt_id=f"physical-action-receipt-{receipt_hash[:16]}", receipt_hash=receipt_hash)


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}_required")
    return value.strip()


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(values, tuple | list):
        raise ValueError(f"{field_name}_must_be_array")
    normalized = tuple(str(value).strip() for value in values)
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name}_required")
    if any(not value for value in normalized):
        raise ValueError(f"{field_name}_item_required")
    return normalized


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_ready(item) for item in value]
    return value
