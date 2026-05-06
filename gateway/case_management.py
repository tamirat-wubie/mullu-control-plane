"""Gateway operational case management.

Purpose: project approval chains, obligations, and escalation events into
    operator-owned governance cases.
Governance scope: human review queues, approval cases, incident cases,
    obligation closure, evidence references, deadline visibility, and stable
    case hashing.
Dependencies: gateway authority-obligation mesh contracts and command-spine
    canonical hashing.
Invariants:
  - Case records are read-model projections, not execution authority.
  - Every case has an owner, status, closure condition, evidence refs, and hash.
  - Pending approval and unresolved obligation states remain explicit.
  - Escalation events are represented as incident cases without hiding source evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

from gateway.authority_obligation_mesh import ApprovalChain, Obligation
from gateway.command_spine import canonical_hash


CASE_TYPES = (
    "approval_case",
    "risk_review_case",
    "payment_exception_case",
    "policy_exception_case",
    "incident_case",
    "accepted_risk_case",
    "requires_review_closure_case",
    "data_deletion_case",
    "capability_certification_case",
)
CASE_STATUSES = (
    "awaiting_approval",
    "open",
    "escalated",
    "closed",
    "denied",
    "expired",
    "cancelled",
)
SEVERITIES = ("low", "medium", "high", "critical")


@dataclass(frozen=True, slots=True)
class OperationalCase:
    """Operator-facing governance case projection."""

    case_id: str
    case_type: str
    tenant_id: str
    severity: str
    status: str
    owner: str
    approver: str
    requested_by: str
    action: str
    deadline: str
    evidence_refs: tuple[str, ...]
    decision_history: tuple[dict[str, Any], ...]
    obligations: tuple[str, ...]
    escalation_path: tuple[str, ...]
    closure_condition: str
    source_refs: tuple[str, ...]
    case_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.case_id, "case_id")
        if self.case_type not in CASE_TYPES:
            raise ValueError("case_type_invalid")
        _require_text(self.tenant_id, "tenant_id")
        if self.severity not in SEVERITIES:
            raise ValueError("case_severity_invalid")
        if self.status not in CASE_STATUSES:
            raise ValueError("case_status_invalid")
        _require_text(self.owner, "owner")
        _require_text(self.requested_by, "requested_by")
        _require_text(self.action, "action")
        _require_text(self.closure_condition, "closure_condition")
        evidence_refs = _normalize_text_tuple(self.evidence_refs, "evidence_refs")
        source_refs = _normalize_text_tuple(self.source_refs, "source_refs")
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "source_refs", source_refs)
        object.__setattr__(self, "decision_history", tuple(dict(item) for item in self.decision_history))
        object.__setattr__(self, "obligations", _normalize_text_tuple(self.obligations, "obligations", allow_empty=True))
        object.__setattr__(
            self,
            "escalation_path",
            _normalize_text_tuple(self.escalation_path, "escalation_path", allow_empty=True),
        )
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


def build_operational_case_read_model(
    *,
    approval_chains: Iterable[ApprovalChain],
    obligations: Iterable[Obligation],
    escalation_events: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return a deterministic case read model from authority mesh records."""
    cases = [
        *_cases_from_approval_chains(tuple(approval_chains)),
        *_cases_from_obligations(tuple(obligations)),
        *_cases_from_escalation_events(tuple(escalation_events)),
    ]
    cases = sorted(cases, key=lambda case: (_deadline_sort_key(case.deadline), case.case_id))
    return {
        "cases": [case.to_json_dict() for case in cases],
        "case_count": len(cases),
        "open_case_count": sum(1 for case in cases if case.status in {"awaiting_approval", "open", "escalated"}),
        "case_counts_by_type": _count_by(cases, "case_type"),
        "case_counts_by_status": _count_by(cases, "status"),
        "case_counts_by_severity": _count_by(cases, "severity"),
        "evidence_refs": [
            "authority:approval_chains_read_model",
            "authority:obligations_read_model",
            "authority:escalations_read_model",
        ],
    }


def _cases_from_approval_chains(chains: tuple[ApprovalChain, ...]) -> tuple[OperationalCase, ...]:
    return tuple(_stamp_case(_case_from_approval_chain(chain)) for chain in chains)


def _case_from_approval_chain(chain: ApprovalChain) -> OperationalCase:
    approvals = tuple(chain.approvals_received)
    status = {
        "pending": "awaiting_approval",
        "satisfied": "closed",
        "denied": "denied",
        "expired": "expired",
        "not_required": "closed",
    }.get(chain.status.value, "open")
    owner = chain.required_roles[0] if chain.required_roles else "approval_owner_unassigned"
    return OperationalCase(
        case_id=f"case-approval-{chain.chain_id}",
        case_type="approval_case",
        tenant_id=chain.tenant_id,
        severity="high",
        status=status,
        owner=owner,
        approver=",".join(approvals),
        requested_by=f"command:{chain.command_id}",
        action=f"approve command {chain.command_id}",
        deadline=chain.due_at,
        evidence_refs=(
            f"authority:approval_chain:{chain.chain_id}",
            f"command:{chain.command_id}",
        ),
        decision_history=tuple(
            {"decision": "approval_recorded", "actor": actor, "source_ref": f"authority:approval_chain:{chain.chain_id}"}
            for actor in approvals
        ),
        obligations=(),
        escalation_path=(chain.policy_id,),
        closure_condition="required approval count satisfied",
        source_refs=(f"authority:approval_chain:{chain.chain_id}",),
        metadata={
            "required_roles": list(chain.required_roles),
            "required_approver_count": chain.required_approver_count,
        },
    )


def _cases_from_obligations(obligations: tuple[Obligation, ...]) -> tuple[OperationalCase, ...]:
    return tuple(_stamp_case(_case_from_obligation(obligation)) for obligation in obligations)


def _case_from_obligation(obligation: Obligation) -> OperationalCase:
    status = {
        "open": "open",
        "satisfied": "closed",
        "expired": "expired",
        "escalated": "escalated",
        "cancelled": "cancelled",
    }.get(obligation.status.value, "open")
    return OperationalCase(
        case_id=f"case-obligation-{obligation.obligation_id}",
        case_type=_case_type_for_obligation(obligation.obligation_type),
        tenant_id=obligation.tenant_id,
        severity=_severity_for_obligation(obligation.status.value, obligation.obligation_type),
        status=status,
        owner=obligation.owner_id,
        approver="",
        requested_by=f"command:{obligation.command_id}",
        action=obligation.obligation_type,
        deadline=obligation.due_at,
        evidence_refs=(
            f"authority:obligation:{obligation.obligation_id}",
            *obligation.evidence_required,
        ),
        decision_history=(
            {
                "decision": f"obligation_{obligation.status.value}",
                "actor": obligation.owner_id,
                "source_ref": f"authority:obligation:{obligation.obligation_id}",
            },
        ),
        obligations=(obligation.obligation_id,),
        escalation_path=(obligation.escalation_policy_id,),
        closure_condition="obligation satisfied with required evidence",
        source_refs=(f"authority:obligation:{obligation.obligation_id}",),
        metadata={
            "owner_team": obligation.owner_team,
            "terminal_certificate_id": obligation.terminal_certificate_id,
        },
    )


def _cases_from_escalation_events(events: tuple[Mapping[str, Any], ...]) -> tuple[OperationalCase, ...]:
    return tuple(_stamp_case(_case_from_escalation_event(event)) for event in events)


def _case_from_escalation_event(event: Mapping[str, Any]) -> OperationalCase:
    event_hash = canonical_hash(dict(event))[:16]
    command_id = str(event.get("command_id", "unknown-command")).strip() or "unknown-command"
    tenant_id = str(event.get("tenant_id", "tenant:*")).strip() or "tenant:*"
    owner = str(
        event.get("owner_id")
        or event.get("fallback_owner_id")
        or event.get("escalation_team")
        or event.get("owner_team")
        or "incident_owner_unassigned"
    )
    return OperationalCase(
        case_id=f"case-incident-{event_hash}",
        case_type="incident_case",
        tenant_id=tenant_id,
        severity=str(event.get("severity") or "high") if str(event.get("severity") or "high") in SEVERITIES else "high",
        status="escalated",
        owner=owner,
        approver="",
        requested_by=f"command:{command_id}",
        action=str(event.get("reason") or event.get("event_type") or "escalation"),
        deadline=str(event.get("due_at") or ""),
        evidence_refs=(f"authority:escalation_event:{event_hash}",),
        decision_history=(
            {
                "decision": "escalation_recorded",
                "actor": owner,
                "source_ref": f"authority:escalation_event:{event_hash}",
            },
        ),
        obligations=tuple(str(event[key]) for key in ("obligation_id", "chain_id") if event.get(key)),
        escalation_path=tuple(str(event[key]) for key in ("escalation_policy_id", "escalation_team") if event.get(key)),
        closure_condition="incident reviewed and linked obligation or approval chain closed",
        source_refs=(f"authority:escalation_event:{event_hash}",),
        metadata={"event": dict(event)},
    )


def _stamp_case(case: OperationalCase) -> OperationalCase:
    payload = case.to_json_dict()
    payload["case_hash"] = ""
    return OperationalCase(**{**payload, "case_hash": canonical_hash(payload)})


def _case_type_for_obligation(obligation_type: str) -> str:
    text = obligation_type.lower()
    if "accepted_risk" in text:
        return "accepted_risk_case"
    if "payment" in text or "compensation" in text:
        return "payment_exception_case"
    if "policy" in text:
        return "policy_exception_case"
    return "requires_review_closure_case"


def _severity_for_obligation(status: str, obligation_type: str) -> str:
    if status == "escalated":
        return "critical"
    if "accepted_risk" in obligation_type.lower():
        return "high"
    return "medium"


def _count_by(cases: list[OperationalCase], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        value = str(getattr(case, field_name))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _deadline_sort_key(value: str) -> str:
    return value or "9999-12-31T23:59:59+00:00"


def _metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    payload = dict(metadata)
    payload["read_model_only"] = True
    payload["operator_case_projection"] = True
    payload["does_not_grant_execution_authority"] = True
    return payload


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
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
