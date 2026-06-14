"""Purpose: deterministic request intake for the personal-assistant layer.
Governance scope: convert operator text into governed intent records, skill
references, risk boundaries, connector proof gaps, and missing WHQR bindings.
Dependencies: personal-assistant skill registry contracts only.
Invariants:
  - Intake is pure and performs no connector, mailbox, calendar, memory, or
    deployment execution.
  - Missing hard bindings are explicit before any effect-bearing action.
  - Output records preserve schema-ready request fields and blocked actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError, SkillMode, SkillRiskLevel
from .skill_registry import PersonalAssistantSkillRegistry, load_default_skill_registry


DEFAULT_GOVERNANCE_REFS = (
    "docs/PERSONAL_ASSISTANT_RISK_BOUNDARY.md",
    "docs/UNIVERSAL_ACTION_ORCHESTRATION.md",
)


class RequestInterface(StrEnum):
    """Allowed personal-assistant intake interfaces."""

    OPERATOR_CONSOLE = "operator_console"
    WEB_CHAT = "web_chat"
    EMAIL_INTAKE = "email_intake"
    SLACK_ADAPTER = "slack_adapter"
    DISCORD_ADAPTER = "discord_adapter"
    TELEGRAM_ADAPTER = "telegram_adapter"
    WHATSAPP_ADAPTER = "whatsapp_adapter"
    API_ROUTE = "api_route"

    @staticmethod
    def coerce(value: str) -> "RequestInterface":
        """Coerce text into a request interface."""
        try:
            return RequestInterface(value)
        except ValueError as exc:
            raise PersonalAssistantInvariantError(f"unknown request interface: {value}") from exc


class RequestExecutionMode(StrEnum):
    """Schema-backed personal-assistant intake execution modes."""

    DRY_RUN = "dry_run"
    PREVIEW = "preview"
    DRAFT = "draft"
    EXECUTE_WITH_APPROVAL = "execute_with_approval"
    BLOCKED = "blocked"
    READ_AND_DRAFT_ONLY = "read_and_draft_only"


class ApprovalScope(StrEnum):
    """Schema-backed approval scope values."""

    NONE = "none"
    PER_REQUEST = "per_request"
    PER_PLAN = "per_plan"
    PER_SKILL = "per_skill"
    PER_ACTION = "per_action"
    PER_RECIPIENT = "per_recipient"


@dataclass(frozen=True, slots=True)
class MissingBinding:
    """One explicit WHQR or authority binding gap."""

    binding_id: str
    binding_type: str
    reason_code: str
    question: str

    def __post_init__(self) -> None:
        for field_name in ("binding_id", "binding_type", "reason_code", "question"):
            object.__setattr__(self, field_name, _require_text(getattr(self, field_name), field_name))

    def as_dict(self) -> dict[str, str]:
        """Return a schema-ready missing-binding object."""
        return {
            "binding_id": self.binding_id,
            "binding_type": self.binding_type,
            "reason_code": self.reason_code,
            "question": self.question,
        }


@dataclass(frozen=True, slots=True)
class ConnectorProofRef:
    """Connector proof projection admitted into intake without secret values."""

    connector_id: str
    connector_name: str
    proof_state: str
    private_data_allowed: bool
    scopes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("connector_id", "connector_name", "proof_state"):
            object.__setattr__(self, field_name, _require_text(getattr(self, field_name), field_name))
        if self.proof_state not in {"Pass", "Fail", "Unknown", "BudgetUnknown"}:
            raise PersonalAssistantInvariantError("proof_state must be Pass, Fail, Unknown, or BudgetUnknown")
        if not isinstance(self.private_data_allowed, bool):
            raise PersonalAssistantInvariantError("private_data_allowed must be a boolean")
        object.__setattr__(self, "scopes", _text_tuple(self.scopes, "scopes", allow_empty=True))

    def as_dict(self) -> dict[str, Any]:
        """Return a schema-ready connector proof reference."""
        return {
            "connector_id": self.connector_id,
            "connector_name": self.connector_name,
            "proof_state": self.proof_state,
            "private_data_allowed": self.private_data_allowed,
            "scopes": list(self.scopes),
        }


@dataclass(frozen=True, slots=True)
class GovernedIntent:
    """Schema-ready governed intent record produced by request intake."""

    request_id: str
    submitted_at: str
    interface: RequestInterface
    user_goal: str
    requested_capabilities: tuple[str, ...]
    requested_skill_ids: tuple[str, ...]
    risk_level: SkillRiskLevel
    requires_approval: bool
    execution_mode: RequestExecutionMode
    approval_scope: ApprovalScope
    missing_bindings: tuple[MissingBinding, ...] = ()
    connector_refs: tuple[ConnectorProofRef, ...] = ()
    governance_refs: tuple[str, ...] = DEFAULT_GOVERNANCE_REFS
    blocked_actions: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _require_text(self.request_id, "request_id"))
        object.__setattr__(self, "submitted_at", _require_text(self.submitted_at, "submitted_at"))
        object.__setattr__(self, "user_goal", _require_text(self.user_goal, "user_goal"))
        if not isinstance(self.interface, RequestInterface):
            raise PersonalAssistantInvariantError("interface must be a RequestInterface")
        if not isinstance(self.risk_level, SkillRiskLevel):
            raise PersonalAssistantInvariantError("risk_level must be a SkillRiskLevel")
        if not isinstance(self.requires_approval, bool):
            raise PersonalAssistantInvariantError("requires_approval must be a boolean")
        if not isinstance(self.execution_mode, RequestExecutionMode):
            raise PersonalAssistantInvariantError("execution_mode must be a RequestExecutionMode")
        if not isinstance(self.approval_scope, ApprovalScope):
            raise PersonalAssistantInvariantError("approval_scope must be an ApprovalScope")
        object.__setattr__(self, "requested_capabilities", _text_tuple(self.requested_capabilities, "requested_capabilities", allow_empty=True))
        object.__setattr__(self, "requested_skill_ids", _text_tuple(self.requested_skill_ids, "requested_skill_ids", allow_empty=True))
        object.__setattr__(self, "governance_refs", _text_tuple(self.governance_refs, "governance_refs"))
        object.__setattr__(self, "blocked_actions", _text_tuple(self.blocked_actions, "blocked_actions", allow_empty=True))
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "missing_bindings", _binding_tuple(self.missing_bindings))
        object.__setattr__(self, "connector_refs", _connector_tuple(self.connector_refs))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))
        if self.missing_bindings and self.execution_mode is not RequestExecutionMode.BLOCKED:
            raise PersonalAssistantInvariantError("missing bindings require blocked execution mode")

    @property
    def has_missing_bindings(self) -> bool:
        """Return whether clarification is required before planning can continue."""
        return bool(self.missing_bindings)

    def as_request_dict(self) -> dict[str, Any]:
        """Return a schema-ready personal-assistant request object."""
        return {
            "request_type": "personal_assistant.request",
            "request_id": self.request_id,
            "submitted_at": self.submitted_at,
            "interface": self.interface.value,
            "user_goal": self.user_goal,
            "requested_capabilities": list(self.requested_capabilities),
            "requested_skill_ids": list(self.requested_skill_ids),
            "risk_level": self.risk_level.value,
            "requires_approval": self.requires_approval,
            "execution_mode": self.execution_mode.value,
            "approval_scope": self.approval_scope.value,
            "missing_bindings": [binding.as_dict() for binding in self.missing_bindings],
            "connector_refs": [connector.as_dict() for connector in self.connector_refs],
            "governance_refs": list(self.governance_refs),
            "blocked_actions": list(self.blocked_actions),
            "evidence_refs": list(self.evidence_refs),
            "metadata": dict(self.metadata),
        }


def interpret_user_request(
    user_request: str,
    *,
    request_id: str,
    submitted_at: str,
    interface: RequestInterface | str = RequestInterface.OPERATOR_CONSOLE,
    connector_refs: Sequence[ConnectorProofRef | Mapping[str, Any]] = (),
    registry: PersonalAssistantSkillRegistry | None = None,
) -> GovernedIntent:
    """Interpret operator text into a governed personal-assistant request."""
    request_text = _require_text(user_request, "user_request")
    request_interface = interface if isinstance(interface, RequestInterface) else RequestInterface.coerce(str(interface))
    skill_registry = registry or load_default_skill_registry()
    admitted_connectors = tuple(_coerce_connector_ref(connector) for connector in connector_refs)
    selected_skill_ids, explicit_gaps = _select_skill_ids_and_gaps(request_text)
    selected_skills = tuple(skill_registry.get(skill_id) for skill_id in selected_skill_ids)
    missing_bindings = list(explicit_gaps)
    missing_bindings.extend(_connector_binding_gaps(selected_skills, admitted_connectors))
    risk_level = _max_risk(selected_skills, default=SkillRiskLevel.P2)
    blocked_actions = _blocked_actions(selected_skills)
    requires_approval = any(skill.requires_approval for skill in selected_skills) or risk_level.requires_explicit_approval
    approval_scope = _approval_scope_for(selected_skills, missing_bindings, requires_approval)
    execution_mode = _execution_mode_for(selected_skills, missing_bindings, requires_approval)
    return GovernedIntent(
        request_id=request_id,
        submitted_at=submitted_at,
        interface=request_interface,
        user_goal=request_text,
        requested_capabilities=_capability_refs(selected_skills),
        requested_skill_ids=tuple(skill.skill_id for skill in selected_skills),
        risk_level=risk_level,
        requires_approval=requires_approval,
        execution_mode=execution_mode,
        approval_scope=approval_scope,
        missing_bindings=tuple(missing_bindings),
        connector_refs=admitted_connectors,
        blocked_actions=blocked_actions,
        evidence_refs=(f"proof://personal-assistant/request/{request_id.removeprefix('pa_request_')}",),
        metadata={
            "intake_mode": "deterministic_foundation",
            "live_connector_execution_allowed": False,
            "system_of_record_write_allowed": False,
        },
    )


def _select_skill_ids_and_gaps(request_text: str) -> tuple[tuple[str, ...], tuple[MissingBinding, ...]]:
    normalized = request_text.lower()
    gaps: list[MissingBinding] = []
    if _looks_like_ambiguous_send(normalized):
        return (
            ("email.send.with_approval",),
            (
                MissingBinding(
                    "recipient:daniel",
                    "recipient",
                    "missing_recipient_identity",
                    "Which Daniel should receive the message?",
                ),
                MissingBinding(
                    "artifact:it",
                    "artifact",
                    "missing_artifact_binding",
                    "What should be sent?",
                ),
                MissingBinding(
                    "approval:send-boundary",
                    "approval_scope",
                    "missing_approval_scope",
                    "Should I draft only or send after explicit approval?",
                ),
            ),
        )
    if "teamops" in normalized or "team ops" in normalized or "shared inbox" in normalized:
        return ("teamops.shared_inbox.plan",), ()
    if any(term in normalized for term in ("inbox", "email", "reply", "respond")):
        skill_ids = ["email.inbox.summarize"]
        if any(term in normalized for term in ("draft", "reply", "respond", "response")):
            skill_ids.append("email.response.draft")
        return tuple(skill_ids), ()
    if "calendar" in normalized or "meeting" in normalized:
        skill_ids = ["calendar.day.brief"]
        if any(term in normalized for term in ("draft", "schedule", "event")):
            skill_ids.append("calendar.event.draft")
        if not any(term in normalized for term in ("today", "tomorrow", "day", "date", "week")):
            gaps.append(
                MissingBinding(
                    "time_window:calendar",
                    "time_window",
                    "missing_time_window",
                    "Which date or time window should the calendar request use?",
                )
            )
        return tuple(skill_ids), tuple(gaps)
    if any(term in normalized for term in ("task", "todo", "to-do", "reminder", "follow-up", "followup")):
        return ("task.create_draft",), ()
    if any(term in normalized for term in ("math", "calculate", "compare", "budget", "cost", "optimize", "scenario")):
        return ("math.reasoning.plan",), ()
    if any(term in normalized for term in ("document", "doc", "file", "summarize this")):
        return (
            ("document.summarize",),
            (
                MissingBinding(
                    "artifact:document",
                    "artifact",
                    "missing_document_ref",
                    "Which document should I use?",
                ),
            ),
        )
    return (
        (),
        (
            MissingBinding(
                "action_boundary:unknown",
                "action_boundary",
                "missing_skill_boundary",
                "Which personal-assistant skill or action boundary should handle this request?",
            ),
        ),
    )


def _looks_like_ambiguous_send(normalized: str) -> bool:
    return "send it to" in normalized or ("send" in normalized and "daniel" in normalized and "it" in normalized)


def _connector_binding_gaps(
    selected_skills: tuple[Any, ...],
    connector_refs: tuple[ConnectorProofRef, ...],
) -> tuple[MissingBinding, ...]:
    gaps: list[MissingBinding] = []
    seen_binding_ids: set[str] = set()
    connector_index = {connector.connector_name: connector for connector in connector_refs}
    for skill in selected_skills:
        if not skill.private_connector_required:
            continue
        for connector_name in skill.connectors:
            connector_ref = connector_index.get(connector_name)
            binding_id = f"connector:{connector_name}"
            if binding_id in seen_binding_ids:
                continue
            if connector_ref is None:
                gaps.append(
                    MissingBinding(
                        binding_id,
                        "connector",
                        "missing_connector_proof",
                        f"Which approved {connector_name} connector proof should this request use?",
                    )
                )
                seen_binding_ids.add(binding_id)
                continue
            if connector_ref.proof_state != "Pass" or not connector_ref.private_data_allowed:
                gaps.append(
                    MissingBinding(
                        binding_id,
                        "connector",
                        "connector_proof_not_passed",
                        f"Provide a passing private-data proof for the {connector_name} connector.",
                    )
                )
                seen_binding_ids.add(binding_id)
    return tuple(gaps)


def _max_risk(selected_skills: tuple[Any, ...], *, default: SkillRiskLevel) -> SkillRiskLevel:
    if not selected_skills:
        return default
    return max((skill.risk_level for skill in selected_skills), key=lambda risk: risk.order)


def _blocked_actions(selected_skills: tuple[Any, ...]) -> tuple[str, ...]:
    blocked: list[str] = []
    for skill in selected_skills:
        for action in skill.blocked_actions:
            if action not in blocked:
                blocked.append(action)
    return tuple(blocked)


def _capability_refs(selected_skills: tuple[Any, ...]) -> tuple[str, ...]:
    capability_refs: list[str] = []
    for skill in selected_skills:
        for capability_ref in skill.capability_refs:
            if capability_ref not in capability_refs:
                capability_refs.append(capability_ref)
    return tuple(capability_refs)


def _approval_scope_for(
    selected_skills: tuple[Any, ...],
    missing_bindings: Sequence[MissingBinding],
    requires_approval: bool,
) -> ApprovalScope:
    if any(binding.binding_type == "recipient" for binding in missing_bindings):
        return ApprovalScope.PER_RECIPIENT
    if requires_approval:
        return ApprovalScope.PER_ACTION
    if any(skill.mode is SkillMode.DRAFT_ONLY for skill in selected_skills):
        return ApprovalScope.NONE
    return ApprovalScope.NONE


def _execution_mode_for(
    selected_skills: tuple[Any, ...],
    missing_bindings: Sequence[MissingBinding],
    requires_approval: bool,
) -> RequestExecutionMode:
    if missing_bindings:
        return RequestExecutionMode.BLOCKED
    if any(skill.mode is SkillMode.BLOCKED for skill in selected_skills):
        return RequestExecutionMode.BLOCKED
    if requires_approval:
        return RequestExecutionMode.EXECUTE_WITH_APPROVAL
    if any(skill.mode is SkillMode.DRAFT_ONLY for skill in selected_skills):
        return RequestExecutionMode.READ_AND_DRAFT_ONLY
    return RequestExecutionMode.PREVIEW


def _coerce_connector_ref(value: ConnectorProofRef | Mapping[str, Any]) -> ConnectorProofRef:
    if isinstance(value, ConnectorProofRef):
        return value
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError("connector ref must be a ConnectorProofRef or mapping")
    return ConnectorProofRef(
        connector_id=_require_text(value.get("connector_id"), "connector_id"),
        connector_name=_require_text(value.get("connector_name"), "connector_name"),
        proof_state=_require_text(value.get("proof_state"), "proof_state"),
        private_data_allowed=_require_bool(value.get("private_data_allowed"), "private_data_allowed"),
        scopes=tuple(value.get("scopes", ())),
    )


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    return value


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise PersonalAssistantInvariantError(f"{field_name} must be a boolean")
    return value


def _text_tuple(values: Sequence[Any], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise PersonalAssistantInvariantError(f"{field_name}[{index}] must be a non-empty string")
        if value not in normalized:
            normalized.append(value)
    if not normalized and not allow_empty:
        raise PersonalAssistantInvariantError(f"{field_name} must contain at least one item")
    return tuple(normalized)


def _binding_tuple(values: Sequence[MissingBinding]) -> tuple[MissingBinding, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise PersonalAssistantInvariantError("missing_bindings must be a sequence")
    for value in values:
        if not isinstance(value, MissingBinding):
            raise PersonalAssistantInvariantError("missing_bindings must contain MissingBinding values")
    return tuple(values)


def _connector_tuple(values: Sequence[ConnectorProofRef]) -> tuple[ConnectorProofRef, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise PersonalAssistantInvariantError("connector_refs must be a sequence")
    for value in values:
        if not isinstance(value, ConnectorProofRef):
            raise PersonalAssistantInvariantError("connector_refs must contain ConnectorProofRef values")
    return tuple(values)


def _freeze_metadata(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError("metadata must be an object")
    return MappingProxyType(dict(value))
