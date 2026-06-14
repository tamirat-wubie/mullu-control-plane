"""Purpose: bridge personal-assistant missing bindings to WHQR clarifications.
Governance scope: create operator-facing clarification requests from intake
gaps without execution or connector side effects.
Dependencies: personal-assistant intake contracts and conversation contracts.
Invariants:
  - Every missing binding is preserved in clarification context.
  - Clarification request ids are deterministic for a request and binding.
  - Bridge output is read-only and performs no action beyond projection.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts.conversation import ClarificationRequest

from .intake import GovernedIntent, MissingBinding


@dataclass(frozen=True, slots=True)
class PersonalAssistantClarificationBundle:
    """Clarification projection for one governed intent."""

    request_id: str
    clarifications: tuple[ClarificationRequest, ...]

    @property
    def empty(self) -> bool:
        """Return whether no clarification is required."""
        return not self.clarifications


def build_clarification_requests(
    intent: GovernedIntent,
    *,
    thread_id: str,
    requested_from_id: str,
    requested_at: str | None = None,
    request_prefix: str = "personal-assistant-whqr",
) -> PersonalAssistantClarificationBundle:
    """Build deterministic clarification requests from missing bindings."""
    _require_text(thread_id, "thread_id")
    _require_text(requested_from_id, "requested_from_id")
    _require_text(request_prefix, "request_prefix")
    timestamp = requested_at or intent.submitted_at
    clarifications = tuple(
        ClarificationRequest(
            request_id=_clarification_request_id(request_prefix, intent.request_id, binding, index),
            thread_id=thread_id,
            question=binding.question,
            context=_context(intent, binding),
            requested_from_id=requested_from_id,
            requested_at=timestamp,
        )
        for index, binding in enumerate(intent.missing_bindings, start=1)
    )
    return PersonalAssistantClarificationBundle(intent.request_id, clarifications)


def _clarification_request_id(
    request_prefix: str,
    request_id: str,
    binding: MissingBinding,
    index: int,
) -> str:
    safe_binding_id = binding.binding_id.replace(":", "_").replace(" ", "_")
    return f"{request_prefix}:{request_id}:{index}:{safe_binding_id}"


def _context(intent: GovernedIntent, binding: MissingBinding) -> str:
    return (
        "personal_assistant_whqr_gap "
        f"request_id={intent.request_id} "
        f"binding_id={binding.binding_id} "
        f"binding_type={binding.binding_type} "
        f"reason_code={binding.reason_code} "
        f"risk_level={intent.risk_level.value} "
        f"execution_mode={intent.execution_mode.value}"
    )


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value
