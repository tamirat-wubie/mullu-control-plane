"""Gateway interpretation contracts.

Purpose: Produce durable, redacted interpretation evidence before a user
message becomes a plan, approval request, search, or execution.
Governance scope: request interpretation, receipt creation, and authority
boundary between deterministic rules and lower-authority LLM proposals.
Dependencies: gateway capability intent contracts and command hashing.
Invariants:
  - Raw message text is represented by hash in interpretation receipts.
  - Deterministic resolver output is the highest-authority interpreter used here.
  - LLM-assisted interpretation is represented only as a future proposal lane.
  - Every produced receipt is tenant-bound, actor-bound, and request-bound.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from gateway.capability_dispatch import CapabilityIntent
from gateway.command_spine import canonical_hash


class InterpretableMessage(Protocol):
    """Minimal message shape required by the interpretation layer."""

    message_id: str
    channel: str
    sender_id: str
    body: str
    conversation_id: str


@dataclass(frozen=True, slots=True)
class InterpretedRequest:
    """Durable request interpretation used before planning or execution."""

    request_id: str
    tenant_id: str
    actor_id: str
    channel: str
    conversation_id: str
    raw_message_hash: str
    intent_class: str
    capability_id: str = ""
    extracted_slots: dict[str, Any] = field(default_factory=dict)
    missing_slots: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    search_needed: bool = False
    action_needed: bool = False
    risk_estimate: str = "low"
    approval_required: bool = False
    confidence: float = 0.0
    interpreter_kind: str = "deterministic_gateway"
    rejected_interpretations: tuple[str, ...] = ()
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        payload = asdict(self)
        payload["missing_slots"] = list(self.missing_slots)
        payload["constraints"] = list(self.constraints)
        payload["rejected_interpretations"] = list(self.rejected_interpretations)
        return payload


@dataclass(frozen=True, slots=True)
class InterpretationReceipt:
    """Redacted evidence of what the gateway believed the user requested."""

    receipt_id: str
    request_id: str
    raw_message_hash: str
    interpreted_intent: str
    extracted_slots: dict[str, Any] = field(default_factory=dict)
    missing_slots: tuple[str, ...] = ()
    confidence: float = 0.0
    model_or_rule_used: str = "deterministic_gateway"
    rejected_interpretations: tuple[str, ...] = ()
    risk_precheck: str = "low"
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe receipt without raw message text."""
        payload = asdict(self)
        payload["missing_slots"] = list(self.missing_slots)
        payload["rejected_interpretations"] = list(self.rejected_interpretations)
        return payload


def interpret_gateway_message(
    *,
    message: InterpretableMessage,
    tenant_id: str,
    actor_id: str,
    intent: CapabilityIntent | None,
    created_at: str,
    approval_command: bool = False,
) -> tuple[InterpretedRequest, InterpretationReceipt]:
    """Build a deterministic interpretation and redacted interpretation receipt.

    Input contract: message is already tenant-bound; ``intent`` is either the
    deterministic resolver result or ``None`` for conversational/unclear text.
    Output contract: returns request and receipt dictionaries that contain only
    hashes or structured slots, never the raw message body.
    Error contract: total for string-like message bodies; no external calls.
    """
    raw_message_hash = canonical_hash({"body": message.body})
    request_id = _request_id_for(message=message, tenant_id=tenant_id, actor_id=actor_id)
    intent_class = _intent_class_for(message.body, intent=intent, approval_command=approval_command)
    capability_id = intent.capability_id if intent is not None else ""
    extracted_slots = _extracted_slots_for(intent)
    missing_slots = _missing_slots_for(intent_class=intent_class, intent=intent, message_body=message.body)
    search_needed = capability_id == "enterprise.knowledge_search"
    action_needed = intent is not None or approval_command
    risk_estimate = _risk_estimate_for(capability_id=capability_id, intent_class=intent_class)
    approval_required = risk_estimate in {"medium", "high"} or intent_class == "approval_response"
    confidence = _confidence_for(intent_class=intent_class, intent=intent, missing_slots=missing_slots)
    rejected = _rejected_interpretations_for(intent=intent, intent_class=intent_class)

    interpreted = InterpretedRequest(
        request_id=request_id,
        tenant_id=tenant_id,
        actor_id=actor_id,
        channel=message.channel,
        conversation_id=message.conversation_id,
        raw_message_hash=raw_message_hash,
        intent_class=intent_class,
        capability_id=capability_id,
        extracted_slots=extracted_slots,
        missing_slots=missing_slots,
        constraints=("tenant_bound", "raw_message_hash_only"),
        search_needed=search_needed,
        action_needed=action_needed,
        risk_estimate=risk_estimate,
        approval_required=approval_required,
        confidence=confidence,
        interpreter_kind="deterministic_gateway",
        rejected_interpretations=rejected,
        created_at=created_at,
    )
    receipt = InterpretationReceipt(
        receipt_id=f"interpretation-receipt-{canonical_hash(interpreted.to_dict())[:16]}",
        request_id=request_id,
        raw_message_hash=raw_message_hash,
        interpreted_intent=capability_id or intent_class,
        extracted_slots=extracted_slots,
        missing_slots=missing_slots,
        confidence=confidence,
        model_or_rule_used="deterministic_gateway",
        rejected_interpretations=rejected,
        risk_precheck=risk_estimate,
        created_at=created_at,
    )
    return interpreted, receipt


def _request_id_for(*, message: InterpretableMessage, tenant_id: str, actor_id: str) -> str:
    digest = canonical_hash({
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "channel": message.channel,
        "sender_id": message.sender_id,
        "message_id": message.message_id,
        "conversation_id": message.conversation_id,
    })
    return f"interpreted-request-{digest[:16]}"


def _intent_class_for(
    message_body: str,
    *,
    intent: CapabilityIntent | None,
    approval_command: bool,
) -> str:
    if approval_command:
        return "approval_response"
    if intent is not None:
        return "explicit_command" if message_body.strip().startswith("/run ") else "action_request"
    stripped = message_body.strip()
    if not stripped:
        return "unclear_message"
    if _looks_like_question(stripped):
        return "question"
    if len(stripped.split()) < 3:
        return "unclear_message"
    return "question"


def _looks_like_question(message_body: str) -> bool:
    normalized = message_body.strip().lower()
    if normalized.endswith("?"):
        return True
    return normalized.startswith((
        "what ",
        "why ",
        "how ",
        "when ",
        "where ",
        "who ",
        "which ",
        "can you explain",
        "tell me",
    ))


def _extracted_slots_for(intent: CapabilityIntent | None) -> dict[str, Any]:
    if intent is None:
        return {}
    params = dict(intent.params)
    return {
        "domain": intent.domain,
        "action": intent.action,
        "capability_id": intent.capability_id,
        "param_names": sorted(str(key) for key in params),
        "params_hash": canonical_hash(params),
    }


def _missing_slots_for(
    *,
    intent_class: str,
    intent: CapabilityIntent | None,
    message_body: str,
) -> tuple[str, ...]:
    if intent_class == "unclear_message":
        return ("intent",)
    if message_body.strip().startswith("/run ") and intent is None:
        return ("capability_id",)
    return ()


def _risk_estimate_for(*, capability_id: str, intent_class: str) -> str:
    if intent_class == "approval_response":
        return "medium"
    if capability_id in {"financial.send_payment", "financial.refund"}:
        return "high"
    if capability_id in {"enterprise.notification_send", "enterprise.task_schedule"}:
        return "medium"
    return "low"


def _confidence_for(
    *,
    intent_class: str,
    intent: CapabilityIntent | None,
    missing_slots: tuple[str, ...],
) -> float:
    if missing_slots:
        return 0.25
    if intent is not None:
        return 0.95
    if intent_class == "question":
        return 0.75
    if intent_class == "approval_response":
        return 0.9
    return 0.4


def _rejected_interpretations_for(
    *,
    intent: CapabilityIntent | None,
    intent_class: str,
) -> tuple[str, ...]:
    if intent is not None:
        return ()
    if intent_class == "unclear_message":
        return ("deterministic_capability_intent:none", "question_confidence:low")
    return ("deterministic_capability_intent:none",)
