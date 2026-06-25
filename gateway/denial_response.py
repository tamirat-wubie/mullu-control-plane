"""Policy denial response composer.

Purpose: convert governed denial reasons into user-facing response bodies and
redaction metadata.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: Python standard library.
Invariants:
  - Denial response bodies are plain user-facing text.
  - Internal exception strings and raw payloads are not embedded in bodies.
  - Metadata records the template, redaction status, and bounded controls.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DenialResponseKind(StrEnum):
    """Supported policy denial templates."""

    TENANT_NOT_FOUND = "tenant_not_found"
    APPROVAL_CONTEXT_DENIED = "approval_context_denied"
    APPROVAL_STRENGTH_DENIED = "approval_strength_denied"
    APPROVAL_DENIED = "approval_denied"
    CAPABILITY_ADMISSION_REJECTED = "capability_admission_rejected"
    POLICY_DENIED = "policy_denied"


@dataclass(frozen=True, slots=True)
class DenialResponse:
    """Composed user-facing denial response."""

    kind: DenialResponseKind
    body: str
    metadata: dict[str, Any]


_DENIAL_BODY_BY_KIND: dict[DenialResponseKind, str] = {
    DenialResponseKind.TENANT_NOT_FOUND: (
        "I don't recognize your account, so I cannot verify governed access. "
        "Please use a registered account or ask the operator to add this channel binding."
    ),
    DenialResponseKind.APPROVAL_CONTEXT_DENIED: (
        "You are not allowed to resolve this approval request from this account. "
        "Use an authorized approver for the same tenant and request."
    ),
    DenialResponseKind.APPROVAL_STRENGTH_DENIED: (
        "This approval response does not satisfy channel approval-strength policy. "
        "Use the bound request, a fresh request ID, or an approved operator channel."
    ),
    DenialResponseKind.APPROVAL_DENIED: (
        "This request was denied, so it will not execute."
    ),
    DenialResponseKind.CAPABILITY_ADMISSION_REJECTED: (
        "This command requires capability review before execution."
    ),
    DenialResponseKind.POLICY_DENIED: (
        "I cannot continue because a governed policy check blocked this request."
    ),
}

_NEXT_ACTION_BY_KIND: dict[DenialResponseKind, str] = {
    DenialResponseKind.TENANT_NOT_FOUND: "register_or_bind_channel_account",
    DenialResponseKind.APPROVAL_CONTEXT_DENIED: "use_authorized_approver",
    DenialResponseKind.APPROVAL_STRENGTH_DENIED: "provide_bound_approval_evidence",
    DenialResponseKind.APPROVAL_DENIED: "inspect_denial_or_block_receipts",
    DenialResponseKind.CAPABILITY_ADMISSION_REJECTED: "complete_capability_review",
    DenialResponseKind.POLICY_DENIED: "inspect_denial_or_block_receipts",
}


def compose_policy_denial_response(
    kind: str | DenialResponseKind,
    *,
    request_id: str = "",
    required_controls: tuple[str, ...] = (),
    evidence_refs: tuple[str, ...] = (),
) -> DenialResponse:
    """Compose a redacted denial response for one governed policy block."""

    denial_kind = _coerce_kind(kind)
    metadata: dict[str, Any] = {
        "denial_template_id": f"policy_denial_response.{denial_kind.value}.v1",
        "denial_template_version": 1,
        "denial_kind": denial_kind.value,
        "denial_user_facing": True,
        "denial_redacted": True,
        "denial_internal_reason_exposed": False,
        "denial_next_action": _NEXT_ACTION_BY_KIND[denial_kind],
        "denial_required_controls": tuple(dict.fromkeys(required_controls)),
        "denial_evidence_refs": tuple(dict.fromkeys(evidence_refs)),
    }
    if request_id:
        metadata["request_id"] = request_id
    return DenialResponse(
        kind=denial_kind,
        body=_DENIAL_BODY_BY_KIND[denial_kind],
        metadata=metadata,
    )


def _coerce_kind(kind: str | DenialResponseKind) -> DenialResponseKind:
    if isinstance(kind, DenialResponseKind):
        return kind
    normalized = kind.strip().lower()
    for candidate in DenialResponseKind:
        if candidate.value == normalized:
            return candidate
    return DenialResponseKind.POLICY_DENIED
