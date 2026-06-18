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
  - Ambiguous action-like input produces clarification, not execution authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Protocol

from gateway.capability_dispatch import CapabilityIntent
from gateway.command_spine import canonical_hash


_ALLOWED_INTENT_CLASSES = {
    "question",
    "action_request",
    "explicit_command",
    "approval_response",
    "correction",
    "follow_up",
    "support_issue",
    "document_instruction",
    "connector_request",
    "blocked_request",
    "unclear_message",
}
_RAW_TEXT_KEYS = {"raw_message", "message", "message_body", "body", "text", "prompt"}


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


@dataclass(frozen=True, slots=True)
class ClarificationRequest:
    """Focused clarification required before planning or execution."""

    clarification_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    channel: str
    conversation_id: str
    raw_message_hash: str
    missing_fields: tuple[str, ...]
    reason: str
    max_questions: int
    safe_default: str
    question: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe clarification request without raw message text."""
        payload = asdict(self)
        payload["missing_fields"] = list(self.missing_fields)
        return payload


@dataclass(frozen=True, slots=True)
class LLMInterpretationProposal:
    """Lower-authority interpretation proposal validated behind deterministic rules."""

    proposal_id: str
    request_id: str
    raw_message_hash: str
    proposal_source: str
    proposed_intent_class: str
    proposed_capability_id: str
    proposed_slot_names: tuple[str, ...]
    proposed_slots_hash: str
    proposal_confidence: float
    deterministic_intent_class: str
    deterministic_capability_id: str
    deterministic_confidence: float
    validation_status: str
    authority_level: str
    deterministic_override_allowed: bool
    action_authority_granted: bool
    execution_allowed: bool
    rejected_reasons: tuple[str, ...]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe proposal without raw message or slot text."""
        payload = asdict(self)
        payload["proposed_slot_names"] = list(self.proposed_slot_names)
        payload["rejected_reasons"] = list(self.rejected_reasons)
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


def clarification_request_for(
    *,
    interpreted_request: InterpretedRequest,
    created_at: str,
) -> ClarificationRequest | None:
    """Return a safe clarification request when interpretation is incomplete.

    Input contract: ``interpreted_request`` has already been tenant-bound and
    redacted.
    Output contract: returns None when no clarification is required; otherwise
    returns a one-question request that references only missing fields and
    hashes, never raw user text.
    Error contract: total for valid InterpretedRequest objects.
    """
    missing_fields = tuple(interpreted_request.missing_slots)
    if not missing_fields:
        return None
    actionable_missing_fields = {"allowed_action", "capability_id", "target"}
    if not actionable_missing_fields.intersection(missing_fields):
        return None
    question = _clarification_question_for(missing_fields)
    raw_message_hash_ref = _clarification_raw_message_hash_ref(interpreted_request.raw_message_hash)
    payload = {
        "request_id": interpreted_request.request_id,
        "raw_message_hash": raw_message_hash_ref,
        "missing_fields": missing_fields,
        "safe_default": "no_execution",
    }
    return ClarificationRequest(
        clarification_id=f"clarification-request-{canonical_hash(payload)[:16]}",
        request_id=interpreted_request.request_id,
        tenant_id=interpreted_request.tenant_id,
        actor_id=interpreted_request.actor_id,
        channel=interpreted_request.channel,
        conversation_id=interpreted_request.conversation_id,
        raw_message_hash=raw_message_hash_ref,
        missing_fields=missing_fields,
        reason="missing_required_interpretation_slots",
        max_questions=1,
        safe_default="no_execution",
        question=question,
        created_at=created_at,
    )


def validate_llm_interpretation_proposal(
    *,
    interpreted_request: InterpretedRequest,
    proposal: Mapping[str, Any],
    created_at: str,
) -> LLMInterpretationProposal:
    """Validate a lower-authority interpretation proposal.

    Input contract: ``interpreted_request`` is the deterministic authority;
    ``proposal`` is untrusted and may contain only proposed classification
    facts.
    Output contract: returns a proposal-only record. It never grants action,
    approval, override, or execution authority, even when accepted.
    Error contract: malformed proposal fields are converted to explicit
    rejection reasons rather than exceptions.
    """
    proposal_source = _bounded_text(proposal.get("proposal_source"), default="llm_assisted_interpretation")
    proposed_intent_class = _bounded_text(proposal.get("intent_class"))
    proposed_capability_id = _bounded_text(proposal.get("capability_id"))
    proposed_slots = proposal.get("slots")
    proposed_slot_mapping = dict(proposed_slots) if isinstance(proposed_slots, Mapping) else {}
    proposed_slot_names = tuple(sorted(str(key) for key in proposed_slot_mapping))
    proposed_slots_hash = canonical_hash(proposed_slot_mapping)
    proposal_confidence = _bounded_float(proposal.get("confidence"))
    rejected_reasons: list[str] = []

    if proposed_intent_class not in _ALLOWED_INTENT_CLASSES:
        rejected_reasons.append("proposed_intent_class_unknown")
    if proposed_slots is not None and not isinstance(proposed_slots, Mapping):
        rejected_reasons.append("proposed_slots_not_mapping")
    if any(str(key).strip().lower() in _RAW_TEXT_KEYS for key in proposal):
        rejected_reasons.append("raw_payload_field_present")
    if _truthy(proposal.get("execution_allowed")):
        rejected_reasons.append("proposal_attempted_execution_authority")
    if _truthy(proposal.get("action_authority_granted")):
        rejected_reasons.append("proposal_attempted_action_authority")
    if _truthy(proposal.get("deterministic_override_allowed")):
        rejected_reasons.append("proposal_attempted_deterministic_override")
    if (
        interpreted_request.capability_id
        and proposed_capability_id
        and proposed_capability_id != interpreted_request.capability_id
    ):
        rejected_reasons.append("deterministic_capability_conflict")
    if (
        interpreted_request.confidence >= 0.75
        and proposed_intent_class
        and proposed_intent_class != interpreted_request.intent_class
    ):
        rejected_reasons.append("deterministic_interpretation_conflict")

    validation_status = "rejected" if rejected_reasons else "accepted_as_proposal"
    payload = {
        "request_id": interpreted_request.request_id,
        "raw_message_hash": interpreted_request.raw_message_hash,
        "proposal_source": proposal_source,
        "proposed_intent_class": proposed_intent_class,
        "proposed_capability_id": proposed_capability_id,
        "proposed_slots_hash": proposed_slots_hash,
        "validation_status": validation_status,
        "rejected_reasons": rejected_reasons,
    }
    return LLMInterpretationProposal(
        proposal_id=f"interpretation-proposal-{canonical_hash(payload)[:16]}",
        request_id=interpreted_request.request_id,
        raw_message_hash=interpreted_request.raw_message_hash,
        proposal_source=proposal_source,
        proposed_intent_class=proposed_intent_class,
        proposed_capability_id=proposed_capability_id,
        proposed_slot_names=proposed_slot_names,
        proposed_slots_hash=proposed_slots_hash,
        proposal_confidence=proposal_confidence,
        deterministic_intent_class=interpreted_request.intent_class,
        deterministic_capability_id=interpreted_request.capability_id,
        deterministic_confidence=interpreted_request.confidence,
        validation_status=validation_status,
        authority_level="proposal_only",
        deterministic_override_allowed=False,
        action_authority_granted=False,
        execution_allowed=False,
        rejected_reasons=tuple(dict.fromkeys(rejected_reasons)),
        created_at=created_at,
    )


def _clarification_raw_message_hash_ref(raw_message_hash: str) -> str:
    if raw_message_hash.startswith("hash://"):
        return raw_message_hash
    return f"hash://gateway-message/{raw_message_hash}"


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
    if _is_greeting(stripped):
        return "question"
    if _looks_like_question(stripped):
        return "question"
    if _looks_like_vague_action(stripped):
        return "unclear_message"
    if len(stripped.split()) < 3:
        return "unclear_message"
    return "question"


def _is_greeting(message_body: str) -> bool:
    return message_body.strip().lower() in {"hello", "hi", "hey", "good morning", "good afternoon"}


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


def _looks_like_vague_action(message_body: str) -> bool:
    normalized = message_body.strip().lower()
    action_prefixes = (
        "fix",
        "deploy",
        "commit",
        "push",
        "publish",
        "launch",
        "change",
        "update",
    )
    return normalized.startswith(action_prefixes)


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
        if _looks_like_vague_action(message_body):
            return ("target", "allowed_action")
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


def _clarification_question_for(missing_fields: tuple[str, ...]) -> str:
    if {"target", "allowed_action"}.issubset(set(missing_fields)):
        return "Which target should I use, and should I inspect only or make changes?"
    if "capability_id" in missing_fields:
        return "Which governed capability should handle this request?"
    return "What do you want me to know or do next?"


def _bounded_text(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()[:120]


def _bounded_float(value: Any) -> float:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return 0.0
    if numeric_value < 0:
        return 0.0
    if numeric_value > 1:
        return 1.0
    return numeric_value


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "present", "allowed"}
    return bool(value)
