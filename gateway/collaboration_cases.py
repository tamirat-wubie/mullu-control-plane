"""Gateway governed collaboration cases.

Purpose: bind operational negotiation, approval requests, obligations, and
case closure to explicit evidence and authority controls.
Governance scope: collaboration case admission, approval separation, decider
authority, pending-control closure blocking, non-terminal case closure, and
schema-backed public contract export.
Dependencies: dataclasses and gateway command-spine canonical hashing.
Invariants:
  - A requester cannot be the approval decider for the same case.
  - Case closure is blocked while approval controls remain pending.
  - Only the declared decider may close a case.
  - Collaboration case closure is not terminal command closure.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from gateway.command_spine import canonical_hash


CONTROL_STATUSES = ("pending", "resolved", "waived")
CASE_STATUSES = ("open", "blocked", "closed", "requires_review")
CLOSURE_STATUSES = ("blocked", "closed")


@dataclass(frozen=True, slots=True)
class CollaborationControl:
    """One explicit control required before a collaboration case can close."""

    control_id: str
    control_type: str
    owner_id: str
    status: str = "pending"
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.control_id, "control_id")
        _require_text(self.control_type, "control_type")
        _require_text(self.owner_id, "owner_id")
        if self.status not in CONTROL_STATUSES:
            raise ValueError("control_status_invalid")
        evidence_refs = _normalize_text_tuple(
            self.evidence_refs, "evidence_refs", allow_empty=True
        )
        if self.status in {"resolved", "waived"} and not evidence_refs:
            raise ValueError("resolved_control_evidence_refs_required")
        object.__setattr__(self, "evidence_refs", evidence_refs)

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class CollaborationCase:
    """Governed collaboration case with approval and evidence controls."""

    case_id: str
    tenant_id: str
    requester_id: str
    subject: str
    approval_decider_id: str
    decider_authority_ref: str
    controls: tuple[CollaborationControl, ...]
    evidence_refs: tuple[str, ...]
    status: str = "open"
    closure_is_terminal: bool = False
    case_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.case_id, "case_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.requester_id, "requester_id")
        _require_text(self.subject, "subject")
        _require_text(self.approval_decider_id, "approval_decider_id")
        _require_text(self.decider_authority_ref, "decider_authority_ref")
        if self.requester_id == self.approval_decider_id:
            raise ValueError("approval_separation_required")
        if self.status not in CASE_STATUSES:
            raise ValueError("case_status_invalid")
        if self.closure_is_terminal:
            raise ValueError("closure_is_not_terminal_command_closure")
        controls = _normalize_controls(self.controls)
        evidence_refs = _normalize_text_tuple(self.evidence_refs, "evidence_refs")
        object.__setattr__(self, "controls", controls)
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "metadata", _case_metadata(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class CollaborationClosure:
    """Non-terminal closure decision for one collaboration case."""

    case_id: str
    closed_by: str
    closure_allowed: bool
    status: str
    blocked_reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    closure_is_terminal: bool = False
    closure_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.case_id, "case_id")
        _require_text(self.closed_by, "closed_by")
        if self.status not in CLOSURE_STATUSES:
            raise ValueError("closure_status_invalid")
        if self.closure_is_terminal:
            raise ValueError("closure_is_not_terminal_command_closure")
        blocked_reasons = _normalize_text_tuple(
            self.blocked_reasons, "blocked_reasons", allow_empty=True
        )
        evidence_refs = _normalize_text_tuple(
            self.evidence_refs, "evidence_refs", allow_empty=True
        )
        if self.closure_allowed and self.status != "closed":
            raise ValueError("allowed_closure_status_must_be_closed")
        if self.closure_allowed and blocked_reasons:
            raise ValueError("allowed_closure_cannot_have_blocked_reasons")
        if not self.closure_allowed and not blocked_reasons:
            raise ValueError("blocked_closure_reasons_required")
        object.__setattr__(self, "blocked_reasons", blocked_reasons)
        object.__setattr__(self, "evidence_refs", evidence_refs)

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible closure object."""
        return _json_ready(asdict(self))


class CollaborationCaseManager:
    """Create and close governed collaboration cases."""

    def open_case(
        self,
        *,
        case_id: str,
        tenant_id: str,
        requester_id: str,
        subject: str,
        approval_decider_id: str,
        decider_authority_ref: str,
        controls: tuple[CollaborationControl, ...],
        evidence_refs: tuple[str, ...],
        metadata: dict[str, Any] | None = None,
    ) -> CollaborationCase:
        """Open one evidence-backed case with explicit approval separation."""
        case = CollaborationCase(
            case_id=case_id,
            tenant_id=tenant_id,
            requester_id=requester_id,
            subject=subject,
            approval_decider_id=approval_decider_id,
            decider_authority_ref=decider_authority_ref,
            controls=controls,
            evidence_refs=evidence_refs,
            metadata=metadata or {},
        )
        return _stamp_case(case)

    def close_case(
        self, case: CollaborationCase, *, closed_by: str
    ) -> CollaborationClosure:
        """Evaluate non-terminal case closure against authority and controls."""
        _require_text(closed_by, "closed_by")
        blocked_reasons: list[str] = []
        if closed_by != case.approval_decider_id:
            blocked_reasons.append("decider_authority_required")
        if any(control.status == "pending" for control in case.controls):
            blocked_reasons.append("pending_controls_block_case_closure")
        evidence_refs = _combined_evidence_refs(case)
        if blocked_reasons:
            return _stamp_closure(
                CollaborationClosure(
                    case.case_id,
                    closed_by,
                    False,
                    "blocked",
                    tuple(blocked_reasons),
                    evidence_refs,
                )
            )
        return _stamp_closure(
            CollaborationClosure(
                case.case_id, closed_by, True, "closed", (), evidence_refs
            )
        )


def with_resolved_control(
    control: CollaborationControl, *, evidence_refs: tuple[str, ...]
) -> CollaborationControl:
    """Return a resolved copy of a control with required evidence refs."""
    return replace(
        control,
        status="resolved",
        evidence_refs=_normalize_text_tuple(evidence_refs, "evidence_refs"),
    )


def _stamp_case(case: CollaborationCase) -> CollaborationCase:
    stamped = replace(case, case_hash="")
    return replace(stamped, case_hash=canonical_hash(asdict(stamped)))


def _stamp_closure(closure: CollaborationClosure) -> CollaborationClosure:
    stamped = replace(closure, closure_hash="")
    return replace(stamped, closure_hash=canonical_hash(asdict(stamped)))


def _combined_evidence_refs(case: CollaborationCase) -> tuple[str, ...]:
    refs = list(case.evidence_refs)
    for control in case.controls:
        refs.extend(control.evidence_refs)
    return tuple(dict.fromkeys(refs))


def _case_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    payload = dict(metadata)
    payload["approval_separation_required"] = True
    payload["pending_controls_block_case_closure"] = True
    payload["decider_authority_required"] = True
    payload["closure_is_not_terminal_command_closure"] = True
    return payload


def _normalize_controls(
    values: tuple[CollaborationControl, ...],
) -> tuple[CollaborationControl, ...]:
    controls = tuple(values)
    if not controls:
        raise ValueError("controls_required")
    for control in controls:
        if not isinstance(control, CollaborationControl):
            raise ValueError("collaboration_control_required")
    return controls


def _normalize_text_tuple(
    values: tuple[str, ...], field_name: str, *, allow_empty: bool = False
) -> tuple[str, ...]:
    normalized = tuple(
        dict.fromkeys(str(value).strip() for value in values if str(value).strip())
    )
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
