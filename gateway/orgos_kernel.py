"""Mullu OrgOS governed organization kernel.

Purpose: model organizations as governed work surfaces with departments,
    roles, cases, authority rules, plan-step gates, closure, and admitted
    learning bindings.
Governance scope: organization topology, department mandates, work ownership,
    authority admission, certified capability use, evidence closure, and
    learning admission boundaries.
Dependencies: gateway command hashing, enterprise authority decisions, and
    MCOI terminal closure and learning contracts.
Invariants:
  - No organization, department, role, case, plan step, or closure is ownerless.
  - Departments are accountable surfaces, not personalities.
  - No plan step is executable from free-form request text alone.
  - No step executes without authority, certified capability, evidence, and
    checked preconditions.
  - No case closes without evidence, effect reconciliation, and terminal
    disposition.
  - No closure enters reusable learning without a learning admission decision.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from gateway.command_spine import canonical_hash
from gateway.enterprise_authority import AuthorityDecision
from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus
from mcoi_runtime.contracts.terminal_closure import TerminalClosureCertificate


RISK_TIERS = ("low", "medium", "high", "critical")
RISK_RANK = {risk: index for index, risk in enumerate(RISK_TIERS)}
CASE_STATUSES = (
    "open",
    "planned",
    "awaiting_approval",
    "executing",
    "awaiting_evidence",
    "closed",
    "requires_review",
)
GATE_VERDICTS = ("allow", "deny", "escalate")
CLOSURE_VERDICTS = ("allow", "deny")
TERMINAL_DISPOSITIONS = ("committed", "compensated", "accepted_risk", "requires_review")
ORGOS_EVENT_ANCHOR_STATUSES = ("not_requested", "pending", "anchored", "failed")
ORGOS_EVENT_ANCHOR_TARGETS = ("audit_chain", "transparency_log", "external_ledger", "regulatory_archive")
CASE_EVENT_TYPES = (
    "organization_registered",
    "department_registered",
    "case_opened",
    "case_updated",
    "plan_step_added",
    "authority_decision_recorded",
    "evidence_added",
    "closure_attempted",
    "closure_decided",
    "learning_bound",
    "operator_note",
)


@dataclass(frozen=True, slots=True)
class Organization:
    """Tenant-bound organization surface."""

    org_id: str
    tenant_id: str
    name: str
    owner_role_id: str
    evidence_refs: tuple[str, ...]
    organization_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.org_id, "org_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.name, "name")
        _require_text(self.owner_role_id, "owner_role_id")
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _metadata(self.metadata, {"orgos_surface": True}))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible organization record."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class DepartmentPack:
    """Mandate, authority boundary, evidence rules, and metrics for one department."""

    department_id: str
    name: str
    mission: str
    owns: tuple[str, ...]
    allowed_case_types: tuple[str, ...]
    allowed_capabilities: tuple[str, ...]
    required_evidence: tuple[str, ...]
    approval_roles: tuple[str, ...]
    escalation_departments: tuple[str, ...]
    metrics: tuple[str, ...]
    failure_modes: tuple[str, ...]
    pack_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.department_id, "department_id")
        _require_text(self.name, "name")
        _require_text(self.mission, "mission")
        object.__setattr__(self, "owns", _text_tuple(self.owns, "owns"))
        object.__setattr__(self, "allowed_case_types", _text_tuple(self.allowed_case_types, "allowed_case_types"))
        object.__setattr__(self, "allowed_capabilities", _text_tuple(self.allowed_capabilities, "allowed_capabilities"))
        object.__setattr__(self, "required_evidence", _text_tuple(self.required_evidence, "required_evidence"))
        object.__setattr__(self, "approval_roles", _text_tuple(self.approval_roles, "approval_roles", allow_empty=True))
        object.__setattr__(
            self,
            "escalation_departments",
            _text_tuple(self.escalation_departments, "escalation_departments", allow_empty=True),
        )
        object.__setattr__(self, "metrics", _text_tuple(self.metrics, "metrics"))
        object.__setattr__(self, "failure_modes", _text_tuple(self.failure_modes, "failure_modes"))
        object.__setattr__(self, "metadata", _metadata(self.metadata, {"department_pack": True}))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible department pack."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class Role:
    """Organization role bound to a department and explicit permissions."""

    role_id: str
    department_id: str
    permissions: tuple[str, ...]
    approval_limit_risk: str
    evidence_refs: tuple[str, ...]
    role_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.role_id, "role_id")
        _require_text(self.department_id, "department_id")
        object.__setattr__(self, "permissions", _text_tuple(self.permissions, "permissions"))
        if self.approval_limit_risk not in RISK_TIERS:
            raise ValueError("approval_limit_risk_invalid")
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _metadata(self.metadata, {"role_surface": True}))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible role."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class AuthorityRule:
    """Role-scoped authority rule for actions on resource types."""

    rule_id: str
    role_id: str
    action: str
    resource_type: str
    max_risk: str
    requires_dual_control: bool
    separation_of_duty: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    rule_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.rule_id, "rule_id")
        _require_text(self.role_id, "role_id")
        _require_text(self.action, "action")
        _require_text(self.resource_type, "resource_type")
        if self.max_risk not in RISK_TIERS:
            raise ValueError("max_risk_invalid")
        if not isinstance(self.requires_dual_control, bool):
            raise ValueError("requires_dual_control_must_be_boolean")
        object.__setattr__(
            self,
            "separation_of_duty",
            _text_tuple(self.separation_of_duty, "separation_of_duty", allow_empty=True),
        )
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _metadata(self.metadata, {"authority_rule": True}))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible authority rule."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class OrgCase:
    """Durable organization work container."""

    case_id: str
    org_id: str
    tenant_id: str
    department_id: str
    case_type: str
    goal: str
    risk_tier: str
    owner_role_id: str
    status: str
    evidence_refs: tuple[str, ...]
    authority_decision_refs: tuple[str, ...] = ()
    plan_certificate_ref: str = ""
    closure_certificate_ref: str = ""
    learning_admission_ref: str = ""
    case_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.case_id, "case_id")
        _require_text(self.org_id, "org_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.department_id, "department_id")
        _require_text(self.case_type, "case_type")
        _require_text(self.goal, "goal")
        if self.risk_tier not in RISK_TIERS:
            raise ValueError("risk_tier_invalid")
        _require_text(self.owner_role_id, "owner_role_id")
        if self.status not in CASE_STATUSES:
            raise ValueError("case_status_invalid")
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(
            self,
            "authority_decision_refs",
            _text_tuple(self.authority_decision_refs, "authority_decision_refs", allow_empty=True),
        )
        for field_name in ("plan_certificate_ref", "closure_certificate_ref", "learning_admission_ref"):
            value = getattr(self, field_name)
            if value:
                _require_text(value, field_name)
        object.__setattr__(self, "metadata", _metadata(self.metadata, {"durable_work_container": True}))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible case."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class OrgPlanStep:
    """One governed work step inside an organization case."""

    step_id: str
    case_id: str
    department_id: str
    capability_id: str
    risk_tier: str
    preconditions: tuple[str, ...]
    postconditions: tuple[str, ...]
    evidence_required: tuple[str, ...]
    approvals_required: tuple[str, ...]
    expected_effects: tuple[str, ...]
    forbidden_effects: tuple[str, ...]
    rollback_plan_id: str | None = None
    step_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.step_id, "step_id")
        _require_text(self.case_id, "case_id")
        _require_text(self.department_id, "department_id")
        _require_text(self.capability_id, "capability_id")
        if self.risk_tier not in RISK_TIERS:
            raise ValueError("risk_tier_invalid")
        object.__setattr__(self, "preconditions", _text_tuple(self.preconditions, "preconditions"))
        object.__setattr__(self, "postconditions", _text_tuple(self.postconditions, "postconditions"))
        object.__setattr__(self, "evidence_required", _text_tuple(self.evidence_required, "evidence_required"))
        object.__setattr__(
            self,
            "approvals_required",
            _text_tuple(self.approvals_required, "approvals_required", allow_empty=True),
        )
        object.__setattr__(self, "expected_effects", _text_tuple(self.expected_effects, "expected_effects"))
        object.__setattr__(self, "forbidden_effects", _text_tuple(self.forbidden_effects, "forbidden_effects"))
        if self.rollback_plan_id is not None:
            object.__setattr__(self, "rollback_plan_id", _require_text(self.rollback_plan_id, "rollback_plan_id"))
        object.__setattr__(self, "metadata", _metadata(self.metadata, {"plan_step_gate_required": True}))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible plan step."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class PlanStepGateDecision:
    """Deterministic admission decision for one plan step."""

    decision_id: str
    case_id: str
    step_id: str
    verdict: str
    reasons: tuple[str, ...]
    required_controls: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    decision_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.decision_id, "decision_id")
        _require_text(self.case_id, "case_id")
        _require_text(self.step_id, "step_id")
        if self.verdict not in GATE_VERDICTS:
            raise ValueError("gate_verdict_invalid")
        object.__setattr__(self, "reasons", _text_tuple(self.reasons, "reasons"))
        object.__setattr__(self, "required_controls", _text_tuple(self.required_controls, "required_controls", allow_empty=True))
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _metadata(self.metadata, {"decision_is_not_execution": True}))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible gate decision."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class EffectClosureBinding:
    """Case-level binding between expected effects, observed effects, and disposition."""

    case_id: str
    expected_effects: tuple[str, ...]
    observed_effects: tuple[str, ...]
    forbidden_effects_checked: bool
    evidence_refs: tuple[str, ...]
    effect_reconciliation_ref: str
    terminal_disposition: str
    terminal_certificate_ref: str = ""
    compensation_ref: str = ""
    accepted_risk_ref: str = ""
    review_case_ref: str = ""
    closure_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.case_id, "case_id")
        object.__setattr__(self, "expected_effects", _text_tuple(self.expected_effects, "expected_effects"))
        object.__setattr__(self, "observed_effects", _text_tuple(self.observed_effects, "observed_effects"))
        if not isinstance(self.forbidden_effects_checked, bool):
            raise ValueError("forbidden_effects_checked_must_be_boolean")
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs, "evidence_refs"))
        _require_text(self.effect_reconciliation_ref, "effect_reconciliation_ref")
        if self.terminal_disposition not in TERMINAL_DISPOSITIONS:
            raise ValueError("terminal_disposition_invalid")
        for field_name in ("terminal_certificate_ref", "compensation_ref", "accepted_risk_ref", "review_case_ref"):
            value = getattr(self, field_name)
            if value:
                _require_text(value, field_name)
        object.__setattr__(self, "metadata", _metadata(self.metadata, {"effect_reconciliation_binding": True}))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible effect closure binding."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class CaseClosureDecision:
    """Decision produced by the case closure gate."""

    decision_id: str
    case_id: str
    verdict: str
    resulting_status: str
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    closure_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.decision_id, "decision_id")
        _require_text(self.case_id, "case_id")
        if self.verdict not in CLOSURE_VERDICTS:
            raise ValueError("closure_verdict_invalid")
        if self.resulting_status not in CASE_STATUSES:
            raise ValueError("resulting_status_invalid")
        object.__setattr__(self, "reasons", _text_tuple(self.reasons, "reasons"))
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _metadata(self.metadata, {"terminal_closure_gate": True}))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible closure decision."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class LearningAdmissionBinding:
    """Case closure to learning admission binding."""

    binding_id: str
    case_id: str
    admission_id: str
    knowledge_id: str
    reusable: bool
    evidence_refs: tuple[str, ...]
    binding_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.binding_id, "binding_id")
        _require_text(self.case_id, "case_id")
        _require_text(self.admission_id, "admission_id")
        _require_text(self.knowledge_id, "knowledge_id")
        if not isinstance(self.reusable, bool):
            raise ValueError("reusable_must_be_boolean")
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _metadata(self.metadata, {"closure_learning_gate": True}))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible learning binding."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class OrgCaseEventReceiptConfig:
    """Signing and external-anchor policy for OrgOS event receipts."""

    signing_secret: str
    signature_key_id: str
    anchor_target: str = "audit_chain"
    external_anchor_status: str = "not_requested"
    external_anchor_ref: str = ""
    lock_timeout_seconds: float = 5.0
    stale_lock_seconds: float = 60.0

    def __post_init__(self) -> None:
        _require_text(self.signing_secret, "signing_secret")
        _require_text(self.signature_key_id, "signature_key_id")
        if self.anchor_target not in ORGOS_EVENT_ANCHOR_TARGETS:
            raise ValueError("orgos_event_anchor_target_invalid")
        if self.external_anchor_status not in ORGOS_EVENT_ANCHOR_STATUSES:
            raise ValueError("orgos_event_external_anchor_status_invalid")
        if self.external_anchor_status == "anchored" and not self.external_anchor_ref:
            raise ValueError("anchored_orgos_event_requires_external_anchor_ref")
        if self.lock_timeout_seconds <= 0:
            raise ValueError("lock_timeout_seconds_positive")
        if self.stale_lock_seconds <= 0:
            raise ValueError("stale_lock_seconds_positive")


@dataclass(frozen=True, slots=True)
class OrgCaseEventReceipt:
    """Signed receipt for one append-only OrgOS case-loop event."""

    receipt_id: str
    event_id: str
    case_id: str
    tenant_id: str
    event_type: str
    prev_event_hash: str
    payload_hash: str
    evidence_root_hash: str
    issued_at: str
    anchor_target: str
    external_anchor_status: str
    external_anchor_ref: str
    signature_key_id: str
    signature: str
    receipt_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.receipt_id, "receipt_id")
        _require_text(self.event_id, "event_id")
        _require_text(self.case_id, "case_id")
        _require_text(self.tenant_id, "tenant_id")
        if self.event_type not in CASE_EVENT_TYPES:
            raise ValueError("case_event_type_invalid")
        _require_text(self.prev_event_hash, "prev_event_hash")
        _require_text(self.payload_hash, "payload_hash")
        _require_text(self.evidence_root_hash, "evidence_root_hash")
        _require_text(self.issued_at, "issued_at")
        if self.anchor_target not in ORGOS_EVENT_ANCHOR_TARGETS:
            raise ValueError("orgos_event_anchor_target_invalid")
        if self.external_anchor_status not in ORGOS_EVENT_ANCHOR_STATUSES:
            raise ValueError("orgos_event_external_anchor_status_invalid")
        if self.external_anchor_status == "anchored" and not self.external_anchor_ref:
            raise ValueError("anchored_orgos_event_requires_external_anchor_ref")
        _require_text(self.signature_key_id, "signature_key_id")
        _require_text(self.signature, "signature")
        if not self.signature.startswith("hmac-sha256:"):
            raise ValueError("orgos_event_signature_not_hmac_sha256")
        _require_text(self.receipt_hash, "receipt_hash")
        object.__setattr__(self, "metadata", _metadata(self.metadata, {"event_receipt_is_not_terminal_closure": True}))
        if self.metadata.get("event_receipt_is_not_terminal_closure") is not True:
            raise ValueError("event_receipt_non_terminal_marker_required")

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible event receipt."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class OrgCaseEvent:
    """Append-only case-loop event with hash-chain witness fields."""

    event_id: str
    case_id: str
    tenant_id: str
    event_type: str
    actor_id: str
    payload: dict[str, Any]
    evidence_refs: tuple[str, ...]
    occurred_at: str
    receipt: OrgCaseEventReceipt
    prev_event_hash: str = ""
    event_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.event_id, "event_id")
        _require_text(self.case_id, "case_id")
        _require_text(self.tenant_id, "tenant_id")
        if self.event_type not in CASE_EVENT_TYPES:
            raise ValueError("case_event_type_invalid")
        _require_text(self.actor_id, "actor_id")
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload_must_be_mapping")
        object.__setattr__(self, "payload", dict(self.payload))
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs, "evidence_refs"))
        _require_text(self.occurred_at, "occurred_at")
        if not isinstance(self.receipt, OrgCaseEventReceipt):
            raise ValueError("receipt_must_be_orgos_case_event_receipt")
        _verify_event_receipt_binding(
            self.receipt,
            event_id=self.event_id,
            case_id=self.case_id,
            tenant_id=self.tenant_id,
            event_type=self.event_type,
            payload=self.payload,
            evidence_refs=self.evidence_refs,
            occurred_at=self.occurred_at,
            prev_event_hash=self.prev_event_hash,
        )
        if self.prev_event_hash:
            _require_text(self.prev_event_hash, "prev_event_hash")
        if self.event_hash:
            _require_text(self.event_hash, "event_hash")
        object.__setattr__(self, "metadata", _metadata(self.metadata, {"append_only_case_event": True}))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible case event."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class OrgCaseEventPage:
    """Bounded newest-first OrgOS case-event page."""

    events: tuple[OrgCaseEvent, ...]
    total: int
    limit: int
    offset: int
    next_offset: int | None

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible event page."""
        return {
            "events": [event.to_json_dict() for event in self.events],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "next_offset": self.next_offset,
        }


class DepartmentRegistry:
    """Deterministic registry for department packs."""

    def __init__(self, departments: Iterable[DepartmentPack] = ()) -> None:
        self._departments: dict[str, DepartmentPack] = {}
        for department in departments:
            self.register(department)

    def register(self, department: DepartmentPack) -> DepartmentPack:
        """Register one department pack and return its stamped copy."""
        if department.department_id in self._departments:
            raise ValueError("department_already_registered")
        stamped = _stamp(department, "pack_hash")
        self._departments[stamped.department_id] = stamped
        return stamped

    def require(self, department_id: str) -> DepartmentPack:
        """Return a department pack or fail closed."""
        _require_text(department_id, "department_id")
        department = self._departments.get(department_id)
        if department is None:
            raise ValueError("department_unknown")
        return department

    def list(self) -> tuple[DepartmentPack, ...]:
        """Return all department packs in stable order."""
        return tuple(self._departments[key] for key in sorted(self._departments))


class InMemoryOrgCaseEventLog:
    """Bounded in-memory append-only OrgOS case event log."""

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        max_events: int = 1000,
        receipt_config: OrgCaseEventReceiptConfig | None = None,
    ) -> None:
        self._clock = clock
        self._max_events = _bounded_event_limit(max_events)
        self._receipt_config = receipt_config or _orgos_event_receipt_config_from_env(os.environ)
        self._events: list[OrgCaseEvent] = []
        self._lock = threading.Lock()

    def record(
        self,
        *,
        case_id: str,
        tenant_id: str,
        event_type: str,
        actor_id: str,
        payload: Mapping[str, Any],
        evidence_refs: Iterable[str],
    ) -> OrgCaseEvent:
        """Append one event and return its hash-chained witness."""
        with self._lock:
            event = _build_case_event(
                sequence=len(self._events) + 1,
                case_id=case_id,
                tenant_id=tenant_id,
                event_type=event_type,
                actor_id=actor_id,
                payload=payload,
                evidence_refs=evidence_refs,
                occurred_at=self._clock(),
                prev_event_hash=self._events[-1].event_hash if self._events else "genesis",
                receipt_config=self._receipt_config,
            )
            self._events.append(event)
            del self._events[:-self._max_events]
            return event

    def list(
        self,
        *,
        case_id: str = "",
        tenant_id: str = "",
        event_type: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> OrgCaseEventPage:
        """Return a bounded newest-first event page."""
        with self._lock:
            return _event_page(
                tuple(reversed(self._events)),
                case_id=case_id,
                tenant_id=tenant_id,
                event_type=event_type,
                limit=limit,
                offset=offset,
            )


class JsonlOrgCaseEventLog:
    """Append-only JSONL OrgOS case event log."""

    def __init__(
        self,
        path: str | Path,
        *,
        clock: Callable[[], str],
        receipt_config: OrgCaseEventReceiptConfig | None = None,
    ) -> None:
        path_text = str(path).strip()
        if not path_text:
            raise ValueError("orgos case event log path is required")
        resolved_path = Path(path_text)
        if resolved_path.exists() and resolved_path.is_dir():
            raise ValueError("orgos case event log path must be a file path")
        self._path = resolved_path
        self._clock = clock
        self._receipt_config = receipt_config or _orgos_event_receipt_config_from_env(os.environ)
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        """Return the JSONL event log path."""
        return self._path

    def record(
        self,
        *,
        case_id: str,
        tenant_id: str,
        event_type: str,
        actor_id: str,
        payload: Mapping[str, Any],
        evidence_refs: Iterable[str],
    ) -> OrgCaseEvent:
        """Append one event to the JSONL hash chain."""
        with self._lock:
            with _OrgosJsonlFileLock(self._path, self._receipt_config):
                events = self._read_all()
                event = _build_case_event(
                    sequence=len(events) + 1,
                    case_id=case_id,
                    tenant_id=tenant_id,
                    event_type=event_type,
                    actor_id=actor_id,
                    payload=payload,
                    evidence_refs=evidence_refs,
                    occurred_at=self._clock(),
                    prev_event_hash=events[-1].event_hash if events else "genesis",
                    receipt_config=self._receipt_config,
                )
                self._path.parent.mkdir(parents=True, exist_ok=True)
                line = json.dumps(event.to_json_dict(), sort_keys=True, separators=(",", ":"))
                with self._path.open("a", encoding="utf-8") as handle:
                    handle.write(f"{line}\n")
                return event

    def list(
        self,
        *,
        case_id: str = "",
        tenant_id: str = "",
        event_type: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> OrgCaseEventPage:
        """Return a bounded newest-first event page from disk."""
        with self._lock:
            with _OrgosJsonlFileLock(self._path, self._receipt_config):
                return _event_page(
                    tuple(reversed(self._read_all())),
                    case_id=case_id,
                    tenant_id=tenant_id,
                    event_type=event_type,
                    limit=limit,
                    offset=offset,
                )

    def _read_all(self) -> tuple[OrgCaseEvent, ...]:
        if not self._path.exists():
            return ()
        events: list[OrgCaseEvent] = []
        previous_hash = "genesis"
        with self._path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                    event = OrgCaseEvent(
                        event_id=str(parsed["event_id"]),
                        case_id=str(parsed["case_id"]),
                        tenant_id=str(parsed["tenant_id"]),
                        event_type=str(parsed["event_type"]),
                        actor_id=str(parsed["actor_id"]),
                        payload=dict(parsed["payload"]),
                        evidence_refs=tuple(parsed["evidence_refs"]),
                        occurred_at=str(parsed["occurred_at"]),
                        receipt=_event_receipt_from_payload(parsed["receipt"]),
                        prev_event_hash=str(parsed.get("prev_event_hash", "")),
                        event_hash=str(parsed["event_hash"]),
                        metadata=dict(parsed.get("metadata", {})),
                    )
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"invalid orgos case event JSONL record at {self._path}:{line_number}"
                    ) from exc
                if event.prev_event_hash != previous_hash:
                    raise ValueError(
                        f"invalid orgos case event hash chain at {self._path}:{line_number}"
                    )
                if _stamp(event, "event_hash").event_hash != event.event_hash:
                    raise ValueError(
                        f"invalid orgos case event hash at {self._path}:{line_number}"
                    )
                if not _event_receipt_signature_valid(event.receipt, self._receipt_config):
                    raise ValueError(
                        f"invalid orgos case event receipt signature at {self._path}:{line_number}"
                    )
                previous_hash = event.event_hash
                events.append(event)
        return tuple(events)


class _OrgosJsonlFileLock:
    """Small cross-process lock for JSONL event-log read/write sections."""

    def __init__(self, path: Path, receipt_config: OrgCaseEventReceiptConfig) -> None:
        self._lock_path = Path(f"{path}.lock")
        self._timeout_seconds = receipt_config.lock_timeout_seconds
        self._stale_lock_seconds = receipt_config.stale_lock_seconds
        self._acquired = False

    def __enter__(self) -> "_OrgosJsonlFileLock":
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self._timeout_seconds
        while True:
            try:
                descriptor = os.open(str(self._lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as exc:
                if self._lock_is_stale():
                    self._lock_path.unlink(missing_ok=True)
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError("orgos_case_event_log_lock_timeout") from exc
                time.sleep(0.05)
                continue
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "pid": os.getpid(),
                    "lock_path": str(self._lock_path),
                    "created_unix": time.time(),
                }, sort_keys=True))
            self._acquired = True
            return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._acquired:
            self._lock_path.unlink(missing_ok=True)
            self._acquired = False

    def _lock_is_stale(self) -> bool:
        try:
            lock_age_seconds = time.time() - self._lock_path.stat().st_mtime
        except FileNotFoundError:
            return False
        return lock_age_seconds > self._stale_lock_seconds


class OrganizationKernel:
    """OrgOS v0 in-memory control kernel."""

    def __init__(self, *, departments: Iterable[DepartmentPack] = ()) -> None:
        self.department_registry = DepartmentRegistry(departments)
        self._organizations: dict[str, Organization] = {}
        self._roles: dict[str, Role] = {}
        self._authority_rules: dict[str, AuthorityRule] = {}
        self._cases: dict[str, OrgCase] = {}
        self._plan_steps: dict[str, OrgPlanStep] = {}
        self._gate_decisions: dict[str, PlanStepGateDecision] = {}
        self._closures: dict[str, EffectClosureBinding] = {}
        self._closure_decisions: dict[str, CaseClosureDecision] = {}
        self._learning_bindings: dict[str, LearningAdmissionBinding] = {}

    def register_organization(self, organization: Organization) -> Organization:
        """Register a tenant organization and return its stamped copy."""
        if organization.org_id in self._organizations:
            raise ValueError("organization_already_registered")
        if organization.owner_role_id not in self._roles:
            raise ValueError("organization_owner_role_unknown")
        stamped = _stamp(organization, "organization_hash")
        self._organizations[stamped.org_id] = stamped
        return stamped

    def register_department(self, department: DepartmentPack) -> DepartmentPack:
        """Register a department pack and return its stamped copy."""
        return self.department_registry.register(department)

    def register_role(self, role: Role) -> Role:
        """Register a role after its department exists."""
        if role.role_id in self._roles:
            raise ValueError("role_already_registered")
        self.department_registry.require(role.department_id)
        stamped = _stamp(role, "role_hash")
        self._roles[stamped.role_id] = stamped
        return stamped

    def register_authority_rule(self, rule: AuthorityRule) -> AuthorityRule:
        """Register an authority rule after its role exists."""
        if rule.rule_id in self._authority_rules:
            raise ValueError("authority_rule_already_registered")
        role = self._roles.get(rule.role_id)
        if role is None:
            raise ValueError("authority_rule_role_unknown")
        if rule.action not in role.permissions and "*" not in role.permissions:
            raise ValueError("authority_rule_action_outside_role_permissions")
        stamped = _stamp(rule, "rule_hash")
        self._authority_rules[stamped.rule_id] = stamped
        return stamped

    def register_organization_surface(
        self,
        organization: Organization,
        *,
        roles: Iterable[Role] = (),
        authority_rules: Iterable[AuthorityRule] = (),
    ) -> tuple[Organization, tuple[Role, ...], tuple[AuthorityRule, ...]]:
        """Atomically register one organization with role and authority surfaces."""
        role_tuple = tuple(roles)
        rule_tuple = tuple(authority_rules)
        if organization.org_id in self._organizations:
            raise ValueError("organization_already_registered")
        if len({role.role_id for role in role_tuple}) != len(role_tuple):
            raise ValueError("role_duplicates_forbidden")
        if len({rule.rule_id for rule in rule_tuple}) != len(rule_tuple):
            raise ValueError("authority_rule_duplicates_forbidden")
        for role in role_tuple:
            if role.role_id in self._roles:
                raise ValueError("role_already_registered")
            self.department_registry.require(role.department_id)
        candidate_roles = {**self._roles, **{role.role_id: role for role in role_tuple}}
        owner_role = candidate_roles.get(organization.owner_role_id)
        if owner_role is None:
            raise ValueError("organization_owner_role_unknown")
        for rule in rule_tuple:
            if rule.rule_id in self._authority_rules:
                raise ValueError("authority_rule_already_registered")
            role = candidate_roles.get(rule.role_id)
            if role is None:
                raise ValueError("authority_rule_role_unknown")
            if rule.action not in role.permissions and "*" not in role.permissions:
                raise ValueError("authority_rule_action_outside_role_permissions")

        stamped_roles = tuple(_stamp(role, "role_hash") for role in role_tuple)
        stamped_rules = tuple(_stamp(rule, "rule_hash") for rule in rule_tuple)
        stamped_organization = _stamp(organization, "organization_hash")
        for role in stamped_roles:
            self._roles[role.role_id] = role
        for rule in stamped_rules:
            self._authority_rules[rule.rule_id] = rule
        self._organizations[stamped_organization.org_id] = stamped_organization
        return stamped_organization, stamped_roles, stamped_rules

    def open_case(self, work_case: OrgCase) -> OrgCase:
        """Open a case only when organization, role, and department mandates align."""
        if work_case.case_id in self._cases:
            raise ValueError("case_already_registered")
        organization = self._organizations.get(work_case.org_id)
        if organization is None:
            raise ValueError("case_organization_unknown")
        if work_case.tenant_id != organization.tenant_id:
            raise ValueError("case_tenant_mismatch")
        department = self.department_registry.require(work_case.department_id)
        if work_case.owner_role_id not in self._roles:
            raise ValueError("case_owner_role_unknown")
        if self._roles[work_case.owner_role_id].department_id != work_case.department_id:
            raise ValueError("case_owner_department_mismatch")
        if work_case.case_type not in department.allowed_case_types:
            raise ValueError("case_type_not_allowed_for_department")
        if work_case.status != "open":
            raise ValueError("new_case_must_start_open")
        stamped = _stamp(work_case, "case_hash")
        self._cases[stamped.case_id] = stamped
        return stamped

    def add_plan_step(self, step: OrgPlanStep) -> OrgPlanStep:
        """Attach a governed plan step to an open or planned case."""
        if step.step_id in self._plan_steps:
            raise ValueError("plan_step_already_registered")
        work_case = self._require_case(step.case_id)
        if work_case.status not in {"open", "planned", "awaiting_approval"}:
            raise ValueError("case_status_not_plannable")
        department = self.department_registry.require(step.department_id)
        if work_case.department_id != step.department_id:
            raise ValueError("step_department_mismatch")
        if _risk_rank(step.risk_tier) > _risk_rank(work_case.risk_tier):
            raise ValueError("step_risk_exceeds_case_risk")
        if step.capability_id not in department.allowed_capabilities:
            raise ValueError("step_capability_not_allowed_for_department")
        missing_department_evidence = tuple(
            evidence for evidence in department.required_evidence if evidence not in step.evidence_required
        )
        if missing_department_evidence:
            raise ValueError("step_missing_department_required_evidence")
        stamped = _stamp(step, "step_hash")
        self._plan_steps[stamped.step_id] = stamped
        self._cases[work_case.case_id] = _stamp(replace(work_case, status="planned"), "case_hash")
        return stamped

    def evaluate_plan_step(
        self,
        step_id: str,
        *,
        authority_decision: AuthorityDecision | None,
        policy_allowed: bool,
        world_refs: Iterable[str],
        certified_capabilities: Iterable[str],
        evidence_refs: Iterable[str],
        approval_refs: Iterable[str] = (),
    ) -> PlanStepGateDecision:
        """Evaluate whether one plan step is admissible for bounded execution."""
        step = self._require_step(step_id)
        work_case = self._require_case(step.case_id)
        department = self.department_registry.require(step.department_id)
        world_ref_set = set(_text_tuple(tuple(world_refs), "world_refs", allow_empty=True))
        capability_set = set(_text_tuple(tuple(certified_capabilities), "certified_capabilities", allow_empty=True))
        evidence_set = set(_text_tuple(tuple(evidence_refs), "evidence_refs", allow_empty=True))
        approval_set = set(_text_tuple(tuple(approval_refs), "approval_refs", allow_empty=True))
        authority_evidence_set: set[str] = set()

        reasons: list[str] = []
        controls: list[str] = []
        if authority_decision is None:
            reasons.append("authority_decision_missing")
            controls.append("authority_decision")
        else:
            authority_evidence_set = set(authority_decision.evidence_refs)
            if authority_decision.verdict != "allow":
                reasons.append(f"authority_{authority_decision.verdict}:{authority_decision.reason}")
                controls.extend(authority_decision.required_controls)
            if authority_decision.tenant_id != work_case.tenant_id:
                reasons.append("authority_tenant_mismatch")
                controls.append("tenant_bound_authority")
            if not _authority_decision_covers_step(
                authority_decision,
                work_case=work_case,
                step=step,
                rules=self._authority_rules,
            ):
                reasons.append("authority_rule_not_bound_to_step")
                controls.append("authority_rule_binding")
        if not policy_allowed:
            reasons.append("policy_denied")
            controls.append("policy_review")
        if work_case.status not in {"planned", "awaiting_approval", "executing"}:
            reasons.append("case_not_ready_for_execution")
            controls.append("case_plan")
        if step.capability_id not in department.allowed_capabilities:
            reasons.append("capability_outside_department_mandate")
            controls.append("department_pack_update")
        if step.capability_id not in capability_set:
            reasons.append("capability_not_certified")
            controls.append("capability_certification")
        missing_preconditions = tuple(ref for ref in step.preconditions if ref not in world_ref_set)
        if missing_preconditions:
            reasons.append("world_preconditions_missing")
            controls.extend(f"world_ref:{ref}" for ref in missing_preconditions)
        missing_evidence = tuple(ref for ref in step.evidence_required if ref not in evidence_set)
        if missing_evidence:
            reasons.append("evidence_missing")
            controls.extend(f"evidence:{ref}" for ref in missing_evidence)
        missing_approvals = tuple(ref for ref in step.approvals_required if ref not in approval_set)
        if step.risk_tier in {"high", "critical"} and not step.approvals_required:
            reasons.append("approval_requirement_missing_for_high_risk")
            controls.append("approval_requirement")
        if step.risk_tier in {"high", "critical"} and missing_approvals:
            reasons.append("approval_missing_for_high_risk")
            controls.extend(f"approval:{ref}" for ref in missing_approvals)
        if step.risk_tier in {"high", "critical"} and step.rollback_plan_id is None:
            reasons.append("recovery_path_missing_for_high_risk")
            controls.append("rollback_or_compensation_plan")

        verdict = "deny" if reasons else "allow"
        decision_evidence_refs = tuple(
            sorted(
                evidence_set
                | world_ref_set
                | authority_evidence_set
                | approval_set
                or {"orgos:evidence:none"}
            )
        )
        decision = PlanStepGateDecision(
            decision_id=_stable_id("orgos-gate", {"case_id": step.case_id, "step_id": step.step_id, "reasons": reasons}),
            case_id=step.case_id,
            step_id=step.step_id,
            verdict=verdict,
            reasons=tuple(reasons or ["admissible_for_bounded_execution"]),
            required_controls=tuple(dict.fromkeys(controls)),
            evidence_refs=decision_evidence_refs,
            metadata={
                "case_owner_role_id": work_case.owner_role_id,
                "department_id": department.department_id,
                "policy_allowed": policy_allowed,
                "authority_decision_id": authority_decision.decision_id if authority_decision else "",
                "world_precondition_count": len(step.preconditions),
            },
        )
        stamped = _stamp(decision, "decision_hash")
        self._gate_decisions[stamped.decision_id] = stamped
        if stamped.verdict == "allow":
            self._cases[work_case.case_id] = _stamp(
                replace(
                    work_case,
                    status="executing",
                    authority_decision_refs=(
                        *work_case.authority_decision_refs,
                        authority_decision.decision_id if authority_decision else "",
                    ),
                ),
                "case_hash",
            )
        return stamped

    def apply_gate_decision_projection(self, decision: PlanStepGateDecision) -> PlanStepGateDecision:
        """Project a previously recorded gate decision without re-running checks."""
        step = self._require_step(decision.step_id)
        work_case = self._require_case(decision.case_id)
        if step.case_id != work_case.case_id:
            raise ValueError("gate_decision_step_case_mismatch")
        stamped = _stamp(decision, "decision_hash")
        self._gate_decisions[stamped.decision_id] = stamped
        if stamped.verdict == "allow":
            authority_decision_id = str(stamped.metadata.get("authority_decision_id", "")).strip()
            authority_refs = (
                (*work_case.authority_decision_refs, authority_decision_id)
                if authority_decision_id
                else work_case.authority_decision_refs
            )
            self._cases[work_case.case_id] = _stamp(
                replace(work_case, status="executing", authority_decision_refs=authority_refs),
                "case_hash",
            )
        return stamped

    def close_case(
        self,
        closure: EffectClosureBinding,
        *,
        terminal_certificate: TerminalClosureCertificate | None = None,
    ) -> CaseClosureDecision:
        """Close a case only after evidence and effect reconciliation are terminal."""
        work_case = self._require_case(closure.case_id)
        reasons = _closure_rejection_reasons(work_case, closure, terminal_certificate)
        verdict = "deny" if reasons else "allow"
        if verdict == "allow" and closure.terminal_disposition == "requires_review":
            resulting_status = "requires_review"
        elif verdict == "allow":
            resulting_status = "closed"
        else:
            resulting_status = "awaiting_evidence"
        certificate_ref = (
            terminal_certificate.certificate_id
            if terminal_certificate is not None
            else closure.terminal_certificate_ref
        )
        evidence_refs = tuple(
            dict.fromkeys(
                (
                    *closure.evidence_refs,
                    f"terminal:{certificate_ref}" if certificate_ref else "terminal:missing",
                    f"effect_reconciliation:{closure.effect_reconciliation_ref}",
                )
            )
        )
        decision = CaseClosureDecision(
            decision_id=_stable_id(
                "orgos-closure",
                {"case_id": closure.case_id, "disposition": closure.terminal_disposition, "reasons": reasons},
            ),
            case_id=closure.case_id,
            verdict=verdict,
            resulting_status=resulting_status,
            reasons=tuple(reasons or ["closure_admissible"]),
            evidence_refs=evidence_refs,
            metadata={
                "terminal_disposition": closure.terminal_disposition,
                "expected_effect_count": len(closure.expected_effects),
                "observed_effect_count": len(closure.observed_effects),
            },
        )
        stamped_closure = _stamp(closure, "closure_hash")
        stamped_decision = _stamp(decision, "closure_hash")
        self._closures[stamped_closure.case_id] = stamped_closure
        self._closure_decisions[stamped_decision.decision_id] = stamped_decision
        if stamped_decision.verdict == "allow":
            self._cases[work_case.case_id] = _stamp(
                replace(work_case, status=resulting_status, closure_certificate_ref=certificate_ref),
                "case_hash",
            )
        return stamped_decision

    def apply_closure_projection(
        self,
        closure: EffectClosureBinding,
        decision: CaseClosureDecision,
    ) -> tuple[EffectClosureBinding, CaseClosureDecision]:
        """Project a recorded closure decision without re-running closure checks."""
        work_case = self._require_case(closure.case_id)
        if decision.case_id != work_case.case_id:
            raise ValueError("closure_decision_case_mismatch")
        stamped_closure = _stamp(closure, "closure_hash")
        stamped_decision = _stamp(decision, "closure_hash")
        self._closures[stamped_closure.case_id] = stamped_closure
        self._closure_decisions[stamped_decision.decision_id] = stamped_decision
        if stamped_decision.verdict == "allow":
            certificate_ref = closure.terminal_certificate_ref or _terminal_ref_from_evidence(stamped_decision.evidence_refs)
            self._cases[work_case.case_id] = _stamp(
                replace(
                    work_case,
                    status=stamped_decision.resulting_status,
                    closure_certificate_ref=certificate_ref,
                ),
                "case_hash",
            )
        return stamped_closure, stamped_decision

    def bind_learning_admission(self, case_id: str, decision: LearningAdmissionDecision) -> LearningAdmissionBinding:
        """Bind a terminal case closure to a learning admission decision."""
        work_case = self._require_case(case_id)
        if work_case.status != "closed":
            raise ValueError("learning_requires_closed_case")
        reusable = decision.status is LearningAdmissionStatus.ADMIT
        evidence_refs = (
            f"case:{case_id}",
            f"closure:{work_case.closure_certificate_ref}",
            f"learning_admission:{decision.admission_id}",
        )
        binding = LearningAdmissionBinding(
            binding_id=_stable_id(
                "orgos-learning",
                {"case_id": case_id, "admission_id": decision.admission_id, "status": decision.status.value},
            ),
            case_id=case_id,
            admission_id=decision.admission_id,
            knowledge_id=decision.knowledge_id,
            reusable=reusable,
            evidence_refs=evidence_refs,
            metadata={
                "learning_status": decision.status.value,
                "only_admitted_learning_is_reusable": True,
            },
        )
        stamped = _stamp(binding, "binding_hash")
        self._learning_bindings[stamped.binding_id] = stamped
        self._cases[work_case.case_id] = _stamp(
            replace(work_case, learning_admission_ref=decision.admission_id),
            "case_hash",
        )
        return stamped

    def project_case(self, work_case: OrgCase) -> OrgCase:
        """Project a case snapshot from an already admitted event."""
        if work_case.org_id not in self._organizations:
            raise ValueError("case_organization_unknown")
        if work_case.department_id not in {department.department_id for department in self.department_registry.list()}:
            raise ValueError("department_unknown")
        if work_case.owner_role_id not in self._roles:
            raise ValueError("case_owner_role_unknown")
        stamped = _stamp(work_case, "case_hash")
        self._cases[stamped.case_id] = stamped
        return stamped

    def project_learning_binding(self, binding: LearningAdmissionBinding) -> LearningAdmissionBinding:
        """Project a learning binding from an already admitted event."""
        self._require_case(binding.case_id)
        stamped = _stamp(binding, "binding_hash")
        self._learning_bindings[stamped.binding_id] = stamped
        return stamped

    def get_case(self, case_id: str) -> OrgCase:
        """Return one case by id or fail closed."""
        return self._require_case(case_id)

    def get_plan_step(self, step_id: str) -> OrgPlanStep:
        """Return one plan step by id or fail closed."""
        return self._require_step(step_id)

    def read_model(self) -> dict[str, Any]:
        """Return the seven OrgOS graphs plus case loop counters."""
        departments = self.department_registry.list()
        cases = tuple(self._cases[key] for key in sorted(self._cases))
        plan_steps = tuple(self._plan_steps[key] for key in sorted(self._plan_steps))
        closures = tuple(self._closures[key] for key in sorted(self._closures))
        learning_bindings = tuple(self._learning_bindings[key] for key in sorted(self._learning_bindings))
        evidence_refs = sorted({
            ref
            for record in (*cases, *self._gate_decisions.values(), *closures, *learning_bindings)
            for ref in getattr(record, "evidence_refs", ())
        })
        certified_capabilities = sorted({
            capability
            for department in departments
            for capability in department.allowed_capabilities
        })
        return {
            "org_graph": {
                "organizations": [
                    self._organizations[key].to_json_dict()
                    for key in sorted(self._organizations)
                ],
                "departments": [item.to_json_dict() for item in departments],
                "roles": [
                    self._roles[key].to_json_dict()
                    for key in sorted(self._roles)
                ],
            },
            "authority_graph": {
                "authority_rules": [
                    self._authority_rules[key].to_json_dict()
                    for key in sorted(self._authority_rules)
                ],
                "gate_decisions": [
                    self._gate_decisions[key].to_json_dict()
                    for key in sorted(self._gate_decisions)
                ],
            },
            "work_graph": {
                "cases": [item.to_json_dict() for item in cases],
                "plan_steps": [item.to_json_dict() for item in plan_steps],
            },
            "world_graph": {
                "world_refs_observed_by_cases": [ref for ref in evidence_refs if ref.startswith("world:")],
            },
            "capability_graph": {
                "department_capability_bindings": {
                    department.department_id: list(department.allowed_capabilities)
                    for department in departments
                },
                "capabilities_declared_by_departments": certified_capabilities,
            },
            "evidence_graph": {
                "evidence_refs": evidence_refs,
                "closures": [item.to_json_dict() for item in closures],
                "closure_decisions": [
                    self._closure_decisions[key].to_json_dict()
                    for key in sorted(self._closure_decisions)
                ],
            },
            "learning_graph": {
                "learning_bindings": [item.to_json_dict() for item in learning_bindings],
                "reusable_knowledge_ids": [
                    binding.knowledge_id for binding in learning_bindings if binding.reusable
                ],
            },
            "case_loop": {
                "case_count": len(cases),
                "open_case_count": sum(1 for item in cases if item.status == "open"),
                "planned_case_count": sum(1 for item in cases if item.status == "planned"),
                "executing_case_count": sum(1 for item in cases if item.status == "executing"),
                "closed_case_count": sum(1 for item in cases if item.status == "closed"),
                "requires_review_case_count": sum(1 for item in cases if item.status == "requires_review"),
            },
        }

    def _require_case(self, case_id: str) -> OrgCase:
        _require_text(case_id, "case_id")
        work_case = self._cases.get(case_id)
        if work_case is None:
            raise ValueError("case_unknown")
        return work_case

    def _require_step(self, step_id: str) -> OrgPlanStep:
        _require_text(step_id, "step_id")
        step = self._plan_steps.get(step_id)
        if step is None:
            raise ValueError("plan_step_unknown")
        return step


def default_mullu_orgos_departments() -> tuple[DepartmentPack, ...]:
    """Return the five v0 department packs for the first OrgOS pilot."""
    return (
        DepartmentPack(
            department_id="executive",
            name="Executive",
            mission="Set objectives, risk tolerance, approval boundaries, and closure accountability.",
            owns=("objectives", "risk_tolerance", "executive_approvals"),
            allowed_case_types=("launch_gateway_pilot", "governed_invoice_review"),
            allowed_capabilities=("objective.freeze", "risk_tolerance.set", "approval.grant"),
            required_evidence=("objective_ref", "risk_tolerance_ref"),
            approval_roles=("executive_owner",),
            escalation_departments=("security_compliance", "finance"),
            metrics=("objective_change_rate", "approval_cycle_time"),
            failure_modes=("unclear_objective", "approval_deadlock"),
        ),
        DepartmentPack(
            department_id="product",
            name="Product",
            mission="Define user-facing requirements, launch boundaries, and acceptance criteria.",
            owns=("requirements", "launch_boundaries", "acceptance_criteria"),
            allowed_case_types=("launch_gateway_pilot",),
            allowed_capabilities=("requirement.define", "launch_boundary.check", "acceptance_criteria.bind"),
            required_evidence=("requirement_ref", "launch_boundary_ref"),
            approval_roles=("product_owner",),
            escalation_departments=("executive", "engineering"),
            metrics=("requirement_trace_coverage", "scope_change_count"),
            failure_modes=("scope_drift", "missing_acceptance_criteria"),
        ),
        DepartmentPack(
            department_id="engineering",
            name="Engineering",
            mission="Prepare runtime surfaces, gateway endpoints, health checks, and conformance evidence.",
            owns=("runtime", "api_gateway", "health_endpoints", "deployment_witnesses"),
            allowed_case_types=("launch_gateway_pilot",),
            allowed_capabilities=(
                "runtime.prepare",
                "gateway.health.check",
                "gateway.witness.collect",
                "runtime.conformance.collect",
            ),
            required_evidence=("runtime_health_ref", "gateway_witness_ref", "runtime_conformance_ref"),
            approval_roles=("engineering_owner",),
            escalation_departments=("security_compliance", "executive"),
            metrics=("runtime_witness_match_rate", "deployment_cycle_time"),
            failure_modes=("unreachable_runtime", "missing_conformance_witness"),
        ),
        DepartmentPack(
            department_id="security_compliance",
            name="Security Compliance",
            mission="Check authorization, secrets, evidence, contradiction, and public-claim boundaries.",
            owns=("authorization_policy", "secrets_boundary", "evidence_policy", "public_claims"),
            allowed_case_types=("launch_gateway_pilot", "governed_invoice_review"),
            allowed_capabilities=("auth.check", "secrets.scan", "evidence.review", "claim_boundary.check"),
            required_evidence=("auth_policy_ref", "secrets_scan_ref", "claim_boundary_ref"),
            approval_roles=("security_owner", "compliance_owner"),
            escalation_departments=("executive",),
            metrics=("unresolved_contradiction_count", "claim_boundary_violation_count"),
            failure_modes=("secret_exposure", "unverified_public_claim"),
        ),
        DepartmentPack(
            department_id="finance",
            name="Finance",
            mission="Control spend, budget evidence, vendor/payment risk, and financial reconciliation.",
            owns=("budgets", "invoices", "vendors", "payment_records"),
            allowed_case_types=("launch_gateway_pilot", "governed_invoice_review"),
            allowed_capabilities=(
                "budget.check",
                "provider_spend.review",
                "invoice.extract",
                "invoice.duplicate_check",
                "payment.prepare",
            ),
            required_evidence=("budget_ref", "spend_policy_ref"),
            approval_roles=("finance_owner",),
            escalation_departments=("security_compliance", "executive"),
            metrics=("budget_variance", "duplicate_payment_prevented", "unresolved_reconciliation_count"),
            failure_modes=("budget_unknown", "duplicate_payment", "vendor_identity_mismatch"),
        ),
    )


def build_orgos_case_event_log_from_env(
    *,
    clock: Callable[[], str],
    env: Mapping[str, str] | None = None,
) -> InMemoryOrgCaseEventLog | JsonlOrgCaseEventLog:
    """Build the OrgOS case event log declared by environment."""
    source = env if env is not None else os.environ
    receipt_config = _orgos_event_receipt_config_from_env(source)
    path = str(source.get("MULLU_ORGOS_CASE_EVENT_LOG_PATH", "")).strip()
    if path:
        return JsonlOrgCaseEventLog(path, clock=clock, receipt_config=receipt_config)
    return InMemoryOrgCaseEventLog(
        clock=clock,
        max_events=_int_env(source, "MULLU_ORGOS_CASE_EVENT_MEMORY_LIMIT", 1000),
        receipt_config=receipt_config,
    )


def _orgos_event_receipt_config_from_env(env: Mapping[str, str]) -> OrgCaseEventReceiptConfig:
    """Build local OrgOS event receipt policy from environment."""
    return OrgCaseEventReceiptConfig(
        signing_secret=str(
            env.get("MULLU_ORGOS_EVENT_SIGNING_SECRET", "local-orgos-event-signing-secret")
        ),
        signature_key_id=str(
            env.get("MULLU_ORGOS_EVENT_SIGNATURE_KEY_ID", "orgos-event-local")
        ),
        anchor_target=str(env.get("MULLU_ORGOS_EVENT_ANCHOR_TARGET", "audit_chain")),
        external_anchor_status=str(env.get("MULLU_ORGOS_EVENT_EXTERNAL_ANCHOR_STATUS", "not_requested")),
        external_anchor_ref=str(env.get("MULLU_ORGOS_EVENT_EXTERNAL_ANCHOR_REF", "")),
        lock_timeout_seconds=_float_env(env, "MULLU_ORGOS_CASE_EVENT_LOCK_TIMEOUT_SECONDS", 5.0),
        stale_lock_seconds=_float_env(env, "MULLU_ORGOS_CASE_EVENT_STALE_LOCK_SECONDS", 60.0),
    )


def replay_orgos_kernel_from_events(
    events: Iterable[OrgCaseEvent],
    *,
    departments: Iterable[DepartmentPack] | None = None,
) -> OrganizationKernel:
    """Rebuild an OrgOS kernel projection from append-only case events."""
    kernel = OrganizationKernel(
        departments=departments if departments is not None else default_mullu_orgos_departments()
    )
    pending_closure_by_case: dict[str, EffectClosureBinding] = {}
    for event in sorted(events, key=_event_sequence):
        if event.event_type == "department_registered":
            kernel.register_department(_department_from_event_payload(event.payload))
        elif event.event_type == "organization_registered":
            organization_payload = event.payload.get("organization", event.payload)
            role_payloads = _payload_sequence(event.payload.get("roles", ()), "roles")
            rule_payloads = _payload_sequence(event.payload.get("authority_rules", ()), "authority_rules")
            kernel.register_organization_surface(
                _organization_from_event_payload(_mapping_payload(organization_payload, "organization")),
                roles=tuple(_role_from_event_payload(item) for item in role_payloads),
                authority_rules=tuple(_authority_rule_from_event_payload(item) for item in rule_payloads),
            )
        elif event.event_type == "case_opened":
            kernel.open_case(_case_from_event_payload(event.payload))
        elif event.event_type == "case_updated":
            kernel.project_case(_case_from_event_payload(event.payload))
        elif event.event_type == "plan_step_added":
            kernel.add_plan_step(_plan_step_from_event_payload(event.payload))
        elif event.event_type == "authority_decision_recorded":
            kernel.apply_gate_decision_projection(_gate_decision_from_event_payload(event.payload))
        elif event.event_type == "closure_attempted":
            pending_closure_by_case[event.case_id] = _closure_from_event_payload(event.payload)
        elif event.event_type == "closure_decided":
            closure = pending_closure_by_case.get(event.case_id)
            if closure is None:
                raise ValueError("closure_decision_without_attempt")
            kernel.apply_closure_projection(closure, _closure_decision_from_event_payload(event.payload))
        elif event.event_type == "learning_bound":
            kernel.project_learning_binding(_learning_binding_from_event_payload(event.payload))
        elif event.event_type in {"evidence_added", "operator_note"}:
            continue
        else:
            raise ValueError(f"unsupported_orgos_event_type:{event.event_type}")
    return kernel


def _closure_rejection_reasons(
    work_case: OrgCase,
    closure: EffectClosureBinding,
    terminal_certificate: TerminalClosureCertificate | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if work_case.status not in {"executing", "awaiting_evidence", "requires_review"}:
        reasons.append("case_not_ready_for_closure")
    if not work_case.authority_decision_refs:
        reasons.append("authority_decision_not_bound_to_case")
    if not closure.terminal_certificate_ref and terminal_certificate is None:
        reasons.append("terminal_certificate_missing")
    if terminal_certificate is not None:
        if terminal_certificate.effect_reconciliation_id != closure.effect_reconciliation_ref:
            reasons.append("terminal_certificate_reconciliation_mismatch")
        if terminal_certificate.disposition.value != closure.terminal_disposition:
            reasons.append("terminal_certificate_disposition_mismatch")
        missing_certificate_evidence = tuple(
            ref for ref in terminal_certificate.evidence_refs if ref not in closure.evidence_refs
        )
        if missing_certificate_evidence:
            reasons.append("terminal_certificate_evidence_not_bound")
    if closure.terminal_disposition == "committed":
        if set(closure.expected_effects) != set(closure.observed_effects):
            reasons.append("effect_reconciliation_not_match")
        if not closure.forbidden_effects_checked:
            reasons.append("forbidden_effects_not_checked")
        if closure.compensation_ref or closure.accepted_risk_ref or closure.review_case_ref:
            reasons.append("committed_closure_has_non_committed_refs")
    elif closure.terminal_disposition == "compensated":
        if not closure.compensation_ref:
            reasons.append("compensation_ref_missing")
    elif closure.terminal_disposition == "accepted_risk":
        if not closure.accepted_risk_ref:
            reasons.append("accepted_risk_ref_missing")
    elif closure.terminal_disposition == "requires_review":
        if not closure.review_case_ref:
            reasons.append("review_case_ref_missing")
    return tuple(reasons)


def _organization_from_event_payload(payload: Mapping[str, Any]) -> Organization:
    return Organization(
        org_id=_payload_text(payload, "org_id"),
        tenant_id=_payload_text(payload, "tenant_id"),
        name=_payload_text(payload, "name"),
        owner_role_id=_payload_text(payload, "owner_role_id"),
        evidence_refs=_payload_tuple(payload, "evidence_refs"),
        metadata=_payload_metadata(payload),
    )


def _department_from_event_payload(payload: Mapping[str, Any]) -> DepartmentPack:
    return DepartmentPack(
        department_id=_payload_text(payload, "department_id"),
        name=_payload_text(payload, "name"),
        mission=_payload_text(payload, "mission"),
        owns=_payload_tuple(payload, "owns"),
        allowed_case_types=_payload_tuple(payload, "allowed_case_types"),
        allowed_capabilities=_payload_tuple(payload, "allowed_capabilities"),
        required_evidence=_payload_tuple(payload, "required_evidence"),
        approval_roles=_payload_tuple(payload, "approval_roles", allow_empty=True),
        escalation_departments=_payload_tuple(payload, "escalation_departments", allow_empty=True),
        metrics=_payload_tuple(payload, "metrics"),
        failure_modes=_payload_tuple(payload, "failure_modes"),
        metadata=_payload_metadata(payload),
    )


def _role_from_event_payload(payload: Mapping[str, Any]) -> Role:
    return Role(
        role_id=_payload_text(payload, "role_id"),
        department_id=_payload_text(payload, "department_id"),
        permissions=_payload_tuple(payload, "permissions"),
        approval_limit_risk=_payload_text(payload, "approval_limit_risk"),
        evidence_refs=_payload_tuple(payload, "evidence_refs"),
        metadata=_payload_metadata(payload),
    )


def _authority_rule_from_event_payload(payload: Mapping[str, Any]) -> AuthorityRule:
    return AuthorityRule(
        rule_id=_payload_text(payload, "rule_id"),
        role_id=_payload_text(payload, "role_id"),
        action=_payload_text(payload, "action"),
        resource_type=_payload_text(payload, "resource_type"),
        max_risk=_payload_text(payload, "max_risk"),
        requires_dual_control=bool(payload.get("requires_dual_control", False)),
        separation_of_duty=_payload_tuple(payload, "separation_of_duty", allow_empty=True),
        evidence_refs=_payload_tuple(payload, "evidence_refs"),
        metadata=_payload_metadata(payload),
    )


def _case_from_event_payload(payload: Mapping[str, Any]) -> OrgCase:
    return OrgCase(
        case_id=_payload_text(payload, "case_id"),
        org_id=_payload_text(payload, "org_id"),
        tenant_id=_payload_text(payload, "tenant_id"),
        department_id=_payload_text(payload, "department_id"),
        case_type=_payload_text(payload, "case_type"),
        goal=_payload_text(payload, "goal"),
        risk_tier=_payload_text(payload, "risk_tier"),
        owner_role_id=_payload_text(payload, "owner_role_id"),
        status=_payload_text(payload, "status"),
        evidence_refs=_payload_tuple(payload, "evidence_refs"),
        authority_decision_refs=_payload_tuple(payload, "authority_decision_refs", allow_empty=True),
        plan_certificate_ref=str(payload.get("plan_certificate_ref", "") or ""),
        closure_certificate_ref=str(payload.get("closure_certificate_ref", "") or ""),
        learning_admission_ref=str(payload.get("learning_admission_ref", "") or ""),
        metadata=_payload_metadata(payload),
    )


def _plan_step_from_event_payload(payload: Mapping[str, Any]) -> OrgPlanStep:
    rollback_plan_id = str(payload.get("rollback_plan_id", "") or "")
    return OrgPlanStep(
        step_id=_payload_text(payload, "step_id"),
        case_id=_payload_text(payload, "case_id"),
        department_id=_payload_text(payload, "department_id"),
        capability_id=_payload_text(payload, "capability_id"),
        risk_tier=_payload_text(payload, "risk_tier"),
        preconditions=_payload_tuple(payload, "preconditions"),
        postconditions=_payload_tuple(payload, "postconditions"),
        evidence_required=_payload_tuple(payload, "evidence_required"),
        approvals_required=_payload_tuple(payload, "approvals_required", allow_empty=True),
        expected_effects=_payload_tuple(payload, "expected_effects"),
        forbidden_effects=_payload_tuple(payload, "forbidden_effects"),
        rollback_plan_id=rollback_plan_id or None,
        metadata=_payload_metadata(payload),
    )


def _gate_decision_from_event_payload(payload: Mapping[str, Any]) -> PlanStepGateDecision:
    return PlanStepGateDecision(
        decision_id=_payload_text(payload, "decision_id"),
        case_id=_payload_text(payload, "case_id"),
        step_id=_payload_text(payload, "step_id"),
        verdict=_payload_text(payload, "verdict"),
        reasons=_payload_tuple(payload, "reasons"),
        required_controls=_payload_tuple(payload, "required_controls", allow_empty=True),
        evidence_refs=_payload_tuple(payload, "evidence_refs"),
        metadata=_payload_metadata(payload),
    )


def _closure_from_event_payload(payload: Mapping[str, Any]) -> EffectClosureBinding:
    return EffectClosureBinding(
        case_id=_payload_text(payload, "case_id"),
        expected_effects=_payload_tuple(payload, "expected_effects"),
        observed_effects=_payload_tuple(payload, "observed_effects"),
        forbidden_effects_checked=bool(payload.get("forbidden_effects_checked", False)),
        evidence_refs=_payload_tuple(payload, "evidence_refs"),
        effect_reconciliation_ref=_payload_text(payload, "effect_reconciliation_ref"),
        terminal_disposition=_payload_text(payload, "terminal_disposition"),
        terminal_certificate_ref=str(payload.get("terminal_certificate_ref", "") or ""),
        compensation_ref=str(payload.get("compensation_ref", "") or ""),
        accepted_risk_ref=str(payload.get("accepted_risk_ref", "") or ""),
        review_case_ref=str(payload.get("review_case_ref", "") or ""),
        metadata=_payload_metadata(payload),
    )


def _closure_decision_from_event_payload(payload: Mapping[str, Any]) -> CaseClosureDecision:
    return CaseClosureDecision(
        decision_id=_payload_text(payload, "decision_id"),
        case_id=_payload_text(payload, "case_id"),
        verdict=_payload_text(payload, "verdict"),
        resulting_status=_payload_text(payload, "resulting_status"),
        reasons=_payload_tuple(payload, "reasons"),
        evidence_refs=_payload_tuple(payload, "evidence_refs"),
        metadata=_payload_metadata(payload),
    )


def _learning_binding_from_event_payload(payload: Mapping[str, Any]) -> LearningAdmissionBinding:
    return LearningAdmissionBinding(
        binding_id=_payload_text(payload, "binding_id"),
        case_id=_payload_text(payload, "case_id"),
        admission_id=_payload_text(payload, "admission_id"),
        knowledge_id=_payload_text(payload, "knowledge_id"),
        reusable=bool(payload.get("reusable", False)),
        evidence_refs=_payload_tuple(payload, "evidence_refs"),
        metadata=_payload_metadata(payload),
    )


def _authority_decision_covers_step(
    decision: AuthorityDecision,
    *,
    work_case: OrgCase,
    step: OrgPlanStep,
    rules: Mapping[str, AuthorityRule],
) -> bool:
    matched_rules = tuple(
        rules[rule_id]
        for rule_id in decision.matched_grant_ids
        if rule_id in rules
    )
    return any(
        rule.role_id == work_case.owner_role_id
        and rule.action == step.capability_id
        and _risk_rank(rule.max_risk) >= _risk_rank(step.risk_tier)
        for rule in matched_rules
    )


def _risk_rank(risk_tier: str) -> int:
    try:
        return RISK_RANK[risk_tier]
    except KeyError as exc:
        raise ValueError("risk_tier_invalid") from exc


def _terminal_ref_from_evidence(evidence_refs: Iterable[str]) -> str:
    for evidence_ref in evidence_refs:
        if evidence_ref.startswith("terminal:") and evidence_ref != "terminal:missing":
            return evidence_ref.removeprefix("terminal:")
    return ""


def _build_case_event(
    *,
    sequence: int,
    case_id: str,
    tenant_id: str,
    event_type: str,
    actor_id: str,
    payload: Mapping[str, Any],
    evidence_refs: Iterable[str],
    occurred_at: str,
    prev_event_hash: str,
    receipt_config: OrgCaseEventReceiptConfig,
) -> OrgCaseEvent:
    event_id = f"orgos-event-{sequence}"
    evidence_ref_tuple = tuple(evidence_refs)
    receipt = _build_event_receipt(
        event_id=event_id,
        case_id=case_id,
        tenant_id=tenant_id,
        event_type=event_type,
        payload=payload,
        evidence_refs=evidence_ref_tuple,
        occurred_at=occurred_at,
        prev_event_hash=prev_event_hash,
        receipt_config=receipt_config,
    )
    event = OrgCaseEvent(
        event_id=event_id,
        case_id=case_id,
        tenant_id=tenant_id,
        event_type=event_type,
        actor_id=actor_id,
        payload=dict(payload),
        evidence_refs=evidence_ref_tuple,
        occurred_at=occurred_at,
        receipt=receipt,
        prev_event_hash=prev_event_hash,
    )
    return _stamp(event, "event_hash")


def _build_event_receipt(
    *,
    event_id: str,
    case_id: str,
    tenant_id: str,
    event_type: str,
    payload: Mapping[str, Any],
    evidence_refs: Iterable[str],
    occurred_at: str,
    prev_event_hash: str,
    receipt_config: OrgCaseEventReceiptConfig,
) -> OrgCaseEventReceipt:
    payload_hash = _event_payload_hash(payload)
    evidence_root_hash = _event_evidence_root_hash(tuple(evidence_refs))
    receipt_seed = canonical_hash({
        "event_id": event_id,
        "case_id": case_id,
        "tenant_id": tenant_id,
        "event_type": event_type,
        "prev_event_hash": prev_event_hash,
        "payload_hash": payload_hash,
        "evidence_root_hash": evidence_root_hash,
        "issued_at": occurred_at,
        "anchor_target": receipt_config.anchor_target,
        "external_anchor_status": receipt_config.external_anchor_status,
        "external_anchor_ref": receipt_config.external_anchor_ref,
    })
    unsigned = OrgCaseEventReceipt(
        receipt_id=f"orgos-event-receipt-{receipt_seed[:16]}",
        event_id=event_id,
        case_id=case_id,
        tenant_id=tenant_id,
        event_type=event_type,
        prev_event_hash=prev_event_hash,
        payload_hash=payload_hash,
        evidence_root_hash=evidence_root_hash,
        issued_at=occurred_at,
        anchor_target=receipt_config.anchor_target,
        external_anchor_status=receipt_config.external_anchor_status,
        external_anchor_ref=receipt_config.external_anchor_ref,
        signature_key_id=receipt_config.signature_key_id,
        signature="hmac-sha256:unsigned",
        receipt_hash="pending",
    )
    hashed = replace(unsigned, receipt_hash=_event_receipt_hash(unsigned))
    return replace(
        hashed,
        signature=_event_receipt_signature(hashed, signing_secret=receipt_config.signing_secret),
    )


def _event_receipt_from_payload(payload: Mapping[str, Any]) -> OrgCaseEventReceipt:
    if not isinstance(payload, Mapping):
        raise ValueError("receipt_must_be_object")
    return OrgCaseEventReceipt(
        receipt_id=_payload_text(payload, "receipt_id"),
        event_id=_payload_text(payload, "event_id"),
        case_id=_payload_text(payload, "case_id"),
        tenant_id=_payload_text(payload, "tenant_id"),
        event_type=_payload_text(payload, "event_type"),
        prev_event_hash=_payload_text(payload, "prev_event_hash"),
        payload_hash=_payload_text(payload, "payload_hash"),
        evidence_root_hash=_payload_text(payload, "evidence_root_hash"),
        issued_at=_payload_text(payload, "issued_at"),
        anchor_target=_payload_text(payload, "anchor_target"),
        external_anchor_status=_payload_text(payload, "external_anchor_status"),
        external_anchor_ref=str(payload.get("external_anchor_ref", "") or ""),
        signature_key_id=_payload_text(payload, "signature_key_id"),
        signature=_payload_text(payload, "signature"),
        receipt_hash=_payload_text(payload, "receipt_hash"),
        metadata=_payload_metadata(payload),
    )


def _verify_event_receipt_binding(
    receipt: OrgCaseEventReceipt,
    *,
    event_id: str,
    case_id: str,
    tenant_id: str,
    event_type: str,
    payload: Mapping[str, Any],
    evidence_refs: Iterable[str],
    occurred_at: str,
    prev_event_hash: str,
) -> None:
    if receipt.event_id != event_id:
        raise ValueError("orgos_event_receipt_event_id_mismatch")
    if receipt.case_id != case_id:
        raise ValueError("orgos_event_receipt_case_id_mismatch")
    if receipt.tenant_id != tenant_id:
        raise ValueError("orgos_event_receipt_tenant_id_mismatch")
    if receipt.event_type != event_type:
        raise ValueError("orgos_event_receipt_type_mismatch")
    if receipt.prev_event_hash != prev_event_hash:
        raise ValueError("orgos_event_receipt_prev_hash_mismatch")
    if receipt.issued_at != occurred_at:
        raise ValueError("orgos_event_receipt_time_mismatch")
    if receipt.payload_hash != _event_payload_hash(payload):
        raise ValueError("orgos_event_receipt_payload_hash_mismatch")
    if receipt.evidence_root_hash != _event_evidence_root_hash(tuple(evidence_refs)):
        raise ValueError("orgos_event_receipt_evidence_hash_mismatch")
    if receipt.receipt_hash != _event_receipt_hash(receipt):
        raise ValueError("orgos_event_receipt_hash_mismatch")


def _event_receipt_signature_valid(
    receipt: OrgCaseEventReceipt,
    receipt_config: OrgCaseEventReceiptConfig,
) -> bool:
    expected = _event_receipt_signature(receipt, signing_secret=receipt_config.signing_secret)
    return compare_digest(expected, receipt.signature)


def _event_payload_hash(payload: Mapping[str, Any]) -> str:
    return canonical_hash(dict(payload))


def _event_evidence_root_hash(evidence_refs: tuple[str, ...]) -> str:
    return canonical_hash({"evidence_refs": evidence_refs})


def _event_receipt_hash(receipt: OrgCaseEventReceipt) -> str:
    payload = asdict(receipt)
    payload["signature"] = ""
    payload["receipt_hash"] = ""
    return canonical_hash(payload)


def _event_receipt_signature(receipt: OrgCaseEventReceipt, *, signing_secret: str) -> str:
    payload = asdict(receipt)
    payload["signature"] = ""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    digest = hmac_new(signing_secret.encode("utf-8"), encoded, sha256).hexdigest()
    return f"hmac-sha256:{digest}"


def _event_sequence(event: OrgCaseEvent) -> int:
    try:
        return int(event.event_id.rsplit("-", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError("orgos_event_id_sequence_invalid") from exc


def _event_page(
    events: tuple[OrgCaseEvent, ...],
    *,
    case_id: str,
    tenant_id: str,
    event_type: str,
    limit: int,
    offset: int,
) -> OrgCaseEventPage:
    filtered = events
    if case_id:
        filtered = tuple(event for event in filtered if event.case_id == case_id)
    if tenant_id:
        filtered = tuple(event for event in filtered if event.tenant_id == tenant_id)
    if event_type:
        filtered = tuple(event for event in filtered if event.event_type == event_type)
    bounded_limit = _bounded_event_limit(limit)
    bounded_offset = max(0, int(offset))
    page = filtered[bounded_offset:bounded_offset + bounded_limit]
    next_offset = bounded_offset + len(page)
    return OrgCaseEventPage(
        events=page,
        total=len(filtered),
        limit=bounded_limit,
        offset=bounded_offset,
        next_offset=next_offset if next_offset < len(filtered) else None,
    )


def _mapping_payload(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name}_must_be_object")
    return value


def _payload_sequence(value: Any, field_name: str) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}_must_be_array")
    return tuple(_mapping_payload(item, field_name) for item in value)


def _payload_text(payload: Mapping[str, Any], field_name: str) -> str:
    return _require_text(str(payload.get(field_name, "") or ""), field_name)


def _payload_tuple(
    payload: Mapping[str, Any],
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    values = payload.get(field_name, ())
    if isinstance(values, str) or not isinstance(values, (list, tuple)):
        raise ValueError(f"{field_name}_must_be_array")
    return _text_tuple(tuple(str(value) for value in values), field_name, allow_empty=allow_empty)


def _payload_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata_must_be_mapping")
    return dict(metadata)


def _stamp(record: Any, hash_field: str) -> Any:
    payload = asdict(record)
    payload[hash_field] = ""
    return replace(record, **{hash_field: canonical_hash(payload)})


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}-{canonical_hash(dict(payload))[:16]}"


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}_required")
    return value.strip()


def _text_tuple(values: Iterable[str], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if isinstance(values, str):
        raise ValueError(f"{field_name}_must_be_iterable")
    normalized = tuple(_require_text(str(value), f"{field_name}_element") for value in values)
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name}_required")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name}_duplicates_forbidden")
    return normalized


def _metadata(metadata: Mapping[str, Any], defaults: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata_must_be_mapping")
    return {**dict(defaults), **dict(metadata)}


def _json_ready(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    return value


def _bounded_event_limit(value: int) -> int:
    return max(1, min(int(value), 10000))


def _int_env(env: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(env.get(name, str(default)))
    except ValueError:
        return default


def _float_env(env: Mapping[str, str], name: str, default: float) -> float:
    try:
        return float(env.get(name, str(default)))
    except ValueError:
        return default
