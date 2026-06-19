"""Purpose: TeamOps shared-inbox planning facade for personal assistant.
Governance scope: operator handoff packets, live-probe gate summaries, receipt
emission, and no-effect guarantees for shared-inbox workflows.
Dependencies: personal-assistant registry contracts and TeamOps handoff scripts.
Invariants:
  - This module does not call Gmail, read mailboxes, draft or send messages.
  - Live-probe readiness is represented as evidence state, not execution.
  - Provider mutation, mailbox mutation, secret serialization, and external
    communication are always recorded as actions not taken.
  - Existing TeamOps handoff contracts remain the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import re
from typing import Any, Mapping, Sequence

from scripts.produce_team_ops_shared_inbox_operator_handoff import (
    DEFAULT_REPOSITORY,
    produce_team_ops_shared_inbox_operator_handoff,
)

from .contracts import PersonalAssistantInvariantError
from .intake import ConnectorProofRef, GovernedIntent, RequestExecutionMode
from .skill_registry import PersonalAssistantSkillRegistry, load_default_skill_registry


TEAMOPS_SHARED_INBOX_PLAN_SKILL_ID = "teamops.shared_inbox.plan"

_TEAMOPS_ACTIONS_NOT_TAKEN = (
    "gmail_not_called",
    "shared_inbox_not_read",
    "email_not_sent",
    "email_not_drafted",
    "mailbox_not_mutated",
    "provider_configuration_not_mutated",
    "secret_values_not_serialized",
    "live_probe_not_executed",
)
_TEAMOPS_LIVE_PROBE_ACTIONS_NOT_TAKEN = (
    "gmail_full_mailbox_not_read",
    "gmail_send_not_called",
    "gmail_draft_not_created",
    "gmail_delete_not_called",
    "gmail_archive_not_called",
    "gmail_label_not_called",
    "provider_state_not_mutated",
    "mailbox_state_not_mutated",
    "raw_token_value_not_serialized",
    "raw_message_payload_not_serialized",
)
_GMAIL_READONLY_SCOPE_MARKERS = (
    "gmail.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
)
_TOKEN_PRESENCE_SIGNAL_NAMES = (
    "EMAIL_CALENDAR_CONNECTOR_TOKEN",
    "GMAIL_ACCESS_TOKEN",
    "GMAIL_REFRESH_TOKEN",
    "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF",
)
_CREDENTIAL_FIELD_FRAGMENTS = (
    "token",
    "secret",
    "credential",
)
_SAFE_PRESENCE_VALUES = frozenset({"present", "configured", "redacted", "stored", "bound", "true", "1"})
_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)
_RAW_PRIVATE_FIELD_FRAGMENTS = (
    "raw",
    "body",
    "payload",
    "private_key",
    "cookie",
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxProjection:
    """TeamOps shared-inbox plan plus governed receipt."""

    request_id: str
    skill_id: str
    plan: Mapping[str, Any]
    receipt: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _require_text(self.request_id, "request_id"))
        object.__setattr__(self, "skill_id", _require_text(self.skill_id, "skill_id"))
        if not isinstance(self.plan, Mapping):
            raise PersonalAssistantInvariantError("plan must be a mapping")
        if not isinstance(self.receipt, Mapping):
            raise PersonalAssistantInvariantError("receipt must be a mapping")
        object.__setattr__(self, "plan", MappingProxyType(dict(self.plan)))
        object.__setattr__(self, "receipt", MappingProxyType(dict(self.receipt)))

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready TeamOps projection."""
        return {
            "request_id": self.request_id,
            "skill_id": self.skill_id,
            "plan": dict(self.plan),
            "receipt": dict(self.receipt),
        }


@dataclass(frozen=True, slots=True)
class TeamOpsGmailLiveProbeProjection:
    """Presence-only TeamOps/Gmail live-probe readiness plus receipt."""

    request_id: str
    skill_id: str
    probe: Mapping[str, Any]
    receipt: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _require_text(self.request_id, "request_id"))
        object.__setattr__(self, "skill_id", _require_text(self.skill_id, "skill_id"))
        if not isinstance(self.probe, Mapping):
            raise PersonalAssistantInvariantError("probe must be a mapping")
        if not isinstance(self.receipt, Mapping):
            raise PersonalAssistantInvariantError("receipt must be a mapping")
        object.__setattr__(self, "probe", MappingProxyType(dict(self.probe)))
        object.__setattr__(self, "receipt", MappingProxyType(dict(self.receipt)))

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready TeamOps/Gmail probe projection."""
        return {
            "request_id": self.request_id,
            "skill_id": self.skill_id,
            "probe": dict(self.probe),
            "receipt": dict(self.receipt),
        }


def plan_teamops_shared_inbox(
    intent: GovernedIntent,
    *,
    generated_at: str,
    environment: Mapping[str, str] | None = None,
    github_secret_names: set[str] | None = None,
    operator_approval_ref: str = "",
    repository: str = DEFAULT_REPOSITORY,
    registry: PersonalAssistantSkillRegistry | None = None,
) -> TeamOpsSharedInboxProjection:
    """Prepare a TeamOps shared-inbox plan without connector execution."""
    skill_registry = registry or load_default_skill_registry()
    skill = skill_registry.get(TEAMOPS_SHARED_INBOX_PLAN_SKILL_ID)
    _assert_intent_admits_teamops_plan(intent)
    _scan_private_or_secret_payload(environment or {}, path="environment")
    _scan_secret_names(github_secret_names or set())
    handoff = _json_ready(
        produce_team_ops_shared_inbox_operator_handoff(
            environment=environment,
            github_secret_names=github_secret_names,
            operator_approval_ref=operator_approval_ref,
            repository=repository,
        )
    )
    plan = {
        "plan_type": "teamops_shared_inbox_foundation",
        "handoff": handoff,
        "live_probe_gate": _live_probe_gate(handoff),
        "next_actions": list(handoff.get("blocked_until", ())) or [
            "bind redacted live-probe approval before any read-only provider probe"
        ],
        "effect_boundary": "teamops_shared_inbox_plan_only_no_provider_call",
        "execution_allowed": False,
        "live_probe_executed": False,
        "mailbox_mutation_allowed": False,
        "external_message_allowed": False,
    }
    receipt = _teamops_receipt(
        intent=intent,
        skill_id=skill.skill_id,
        risk_level=skill.risk_level.value,
        generated_at=generated_at,
        handoff=handoff,
    )
    return TeamOpsSharedInboxProjection(intent.request_id, skill.skill_id, plan, receipt)


def preview_teamops_gmail_live_probe(
    intent: GovernedIntent,
    *,
    generated_at: str,
    environment: Mapping[str, str] | None = None,
    github_secret_names: set[str] | None = None,
    operator_approval_ref: str = "",
    repository: str = DEFAULT_REPOSITORY,
    registry: PersonalAssistantSkillRegistry | None = None,
) -> TeamOpsGmailLiveProbeProjection:
    """Prepare a presence-only TeamOps/Gmail live-probe receipt preview."""
    skill_registry = registry or load_default_skill_registry()
    skill = skill_registry.get(TEAMOPS_SHARED_INBOX_PLAN_SKILL_ID)
    _assert_intent_admits_teamops_plan(intent)
    env = dict(environment or {})
    secret_names = set(github_secret_names or set())
    _scan_live_probe_environment(env)
    _scan_secret_names(secret_names)
    handoff = _json_ready(
        produce_team_ops_shared_inbox_operator_handoff(
            environment=env,
            github_secret_names=secret_names,
            operator_approval_ref=operator_approval_ref,
            repository=repository,
        )
    )
    connector_ref = _gmail_connector_ref(intent)
    connector_ready = _connector_ready_for_gmail_probe(connector_ref)
    token_ready = _token_presence_ready(env, secret_names, handoff)
    boundary_ready = connector_ready and _handoff_reports_ready(handoff)
    probe_ready = connector_ready and token_ready and boundary_ready
    blocked_until = [] if probe_ready else _live_probe_blockers(
        connector_ready=connector_ready,
        token_ready=token_ready,
        boundary_ready=boundary_ready,
        handoff=handoff,
    )
    probe = {
        "probe_type": "teamops_gmail_presence_only_live_probe",
        "status": "ready_for_live_probe" if probe_ready else "awaiting_evidence",
        "solver_outcome": "SolvedVerified" if probe_ready else "AwaitingEvidence",
        "provider": "gmail",
        "connector_readiness": {
            "connector_id": connector_ref.connector_id,
            "connector_name": connector_ref.connector_name,
            "proof_state": connector_ref.proof_state,
            "private_data_allowed": connector_ref.private_data_allowed,
            "scopes": list(connector_ref.scopes),
            "readonly_scope_present": _has_readonly_scope(connector_ref.scopes),
            "ready": connector_ready,
            "external_provider_call_performed": False,
        },
        "token_presence": {
            "status": "present" if token_ready else "awaiting_evidence",
            "checked_by": "presence_markers_only",
            "signal_names_checked": list(_TOKEN_PRESENCE_SIGNAL_NAMES),
            "raw_token_value_serialized": False,
            "raw_token_value_inspected": False,
            "ready": token_ready,
        },
        "mailbox_access_boundary": {
            "boundary": "readonly_scope_and_operator_witness_only",
            "full_mailbox_read_allowed": False,
            "message_body_read_allowed": False,
            "message_search_allowed_by_this_route": False,
            "send_allowed": False,
            "draft_allowed": False,
            "delete_allowed": False,
            "archive_allowed": False,
            "provider_mutation_allowed": False,
            "ready": boundary_ready,
        },
        "handoff_summary": {
            "handoff_id": handoff.get("handoff_id", ""),
            "status": handoff.get("status", "missing"),
            "solver_outcome": handoff.get("solver_outcome", "AwaitingEvidence"),
            "ready_for_live_probe": handoff.get("ready_for_live_probe") is True,
            "blocked_until": list(handoff.get("blocked_until", ()))
            if isinstance(handoff.get("blocked_until", ()), list)
            else [],
        },
        "blocked_until": blocked_until,
        "execution_allowed": False,
        "provider_call_performed": False,
        "mailbox_mutation_performed": False,
        "external_message_sent": False,
    }
    receipt = _teamops_live_probe_receipt(
        intent=intent,
        skill_id=skill.skill_id,
        risk_level=skill.risk_level.value,
        generated_at=generated_at,
        handoff=handoff,
        probe=probe,
    )
    return TeamOpsGmailLiveProbeProjection(intent.request_id, skill.skill_id, probe, receipt)


def _assert_intent_admits_teamops_plan(intent: GovernedIntent) -> None:
    if TEAMOPS_SHARED_INBOX_PLAN_SKILL_ID not in intent.requested_skill_ids:
        raise PersonalAssistantInvariantError(
            f"{TEAMOPS_SHARED_INBOX_PLAN_SKILL_ID} is not requested by intent {intent.request_id}"
        )
    if intent.execution_mode is RequestExecutionMode.BLOCKED or intent.missing_bindings:
        raise PersonalAssistantInvariantError(f"{intent.request_id}: missing bindings block TeamOps plan")
    connector_ref = next(
        (connector for connector in intent.connector_refs if connector.connector_name == "gmail"),
        None,
    )
    if connector_ref is None:
        raise PersonalAssistantInvariantError(f"{intent.request_id}: missing gmail connector proof")
    _assert_connector_proof(connector_ref)


def _gmail_connector_ref(intent: GovernedIntent) -> ConnectorProofRef:
    connector_ref = next(
        (connector for connector in intent.connector_refs if connector.connector_name == "gmail"),
        None,
    )
    if connector_ref is None:
        raise PersonalAssistantInvariantError(f"{intent.request_id}: missing gmail connector proof")
    return connector_ref


def _assert_connector_proof(connector_ref: ConnectorProofRef) -> None:
    if connector_ref.proof_state != "Pass" or not connector_ref.private_data_allowed:
        raise PersonalAssistantInvariantError("TeamOps shared inbox planning requires passing gmail proof")


def _live_probe_gate(handoff: Mapping[str, Any]) -> dict[str, Any]:
    ready = handoff.get("ready_for_live_probe") is True
    blocked_until = handoff.get("blocked_until", ())
    blockers = list(blocked_until) if isinstance(blocked_until, list) else []
    return {
        "ready_for_live_probe": ready,
        "solver_outcome": handoff.get("solver_outcome", "AwaitingEvidence"),
        "handoff_status": handoff.get("status", "missing"),
        "blocked_until": blockers,
        "approval_binding_required": True,
        "authority_receipt_required": True,
        "operator_input_request_required": True,
        "live_probe_executed": False,
        "external_provider_call_performed": False,
        "mailbox_write_performed": False,
        "external_message_sent": False,
    }


def _teamops_receipt(
    *,
    intent: GovernedIntent,
    skill_id: str,
    risk_level: str,
    generated_at: str,
    handoff: Mapping[str, Any],
) -> dict[str, Any]:
    timestamp = _require_text(generated_at, "generated_at")
    suffix = _request_suffix(intent.request_id)
    return {
        "receipt_id": f"pa_receipt_{suffix}_{_safe_identifier(skill_id)}",
        "request_id": intent.request_id,
        "skill_id": skill_id,
        "mode": "preview",
        "risk_level": risk_level,
        "inputs_used": ["teamops_shared_inbox_goal", "gmail_connector_proof_ref", "operator_handoff_projection"],
        "connectors_used": ["gmail"],
        "decision": "allowed",
        "approval_required": False,
        "approval_ref": "",
        "actions_taken": ["teamops_handoff_plan_prepared", "live_probe_gate_classified", "receipt_created"],
        "actions_not_taken": list(_TEAMOPS_ACTIONS_NOT_TAKEN),
        "redactions": ["secret_values_not_serialized", "approval_refs_redacted", "connector_payload_not_serialized"],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "body_projection": "none",
        },
        "timestamp": timestamp,
        "evidence_refs": _evidence_refs(intent, handoff),
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/teamops/shared-inbox/{suffix}"],
        "outcome": "SolvedVerified",
        "metadata": {
            "handoff_id": handoff.get("handoff_id", ""),
            "handoff_status": handoff.get("status", "missing"),
            "handoff_solver_outcome": handoff.get("solver_outcome", "AwaitingEvidence"),
            "ready_for_live_probe": handoff.get("ready_for_live_probe") is True,
            "blocked_until": list(handoff.get("blocked_until", ()))
            if isinstance(handoff.get("blocked_until", ()), list)
            else [],
            "live_connector_execution_allowed": False,
            "live_probe_executed": False,
            "connector_mutation_allowed": False,
            "external_write_allowed": False,
            "system_of_record_write_allowed": False,
        },
    }


def _teamops_live_probe_receipt(
    *,
    intent: GovernedIntent,
    skill_id: str,
    risk_level: str,
    generated_at: str,
    handoff: Mapping[str, Any],
    probe: Mapping[str, Any],
) -> dict[str, Any]:
    timestamp = _require_text(generated_at, "generated_at")
    suffix = _request_suffix(intent.request_id)
    ready = probe.get("status") == "ready_for_live_probe"
    return {
        "receipt_id": f"pa_receipt_{suffix}_{_safe_identifier(skill_id)}_gmail_live_probe",
        "request_id": intent.request_id,
        "skill_id": skill_id,
        "mode": "preview",
        "risk_level": risk_level,
        "inputs_used": [
            "gmail_connector_proof_ref",
            "teamops_presence_markers",
            "operator_handoff_projection",
        ],
        "connectors_used": ["gmail"],
        "decision": "allowed" if ready else "deferred",
        "approval_required": False,
        "approval_ref": "",
        "actions_taken": [
            "connector_readiness_checked",
            "token_presence_checked_by_marker",
            "mailbox_access_boundary_classified",
            "receipt_created",
        ],
        "actions_not_taken": list(_TEAMOPS_LIVE_PROBE_ACTIONS_NOT_TAKEN),
        "redactions": [
            "secret_values_not_serialized",
            "token_values_not_serialized",
            "mailbox_payload_not_serialized",
            "message_bodies_not_serialized",
        ],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "token_values_serialized": False,
            "message_body_projection": "none",
            "connector_payload_projection": "presence_only",
        },
        "timestamp": timestamp,
        "evidence_refs": _evidence_refs(intent, handoff),
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/teamops/gmail-live-probe/{suffix}"],
        "outcome": "SolvedVerified" if ready else "AwaitingEvidence",
        "metadata": {
            "probe_status": probe.get("status", "awaiting_evidence"),
            "connector_ready": _nested_bool(probe, "connector_readiness", "ready"),
            "token_presence_ready": _nested_bool(probe, "token_presence", "ready"),
            "mailbox_access_boundary_ready": _nested_bool(probe, "mailbox_access_boundary", "ready"),
            "live_connector_execution_allowed": False,
            "external_provider_call_performed": False,
            "full_mailbox_read_allowed": False,
            "draft_creation_allowed": False,
            "external_send_allowed": False,
            "delete_allowed": False,
            "archive_allowed": False,
            "provider_mutation_allowed": False,
            "system_of_record_write_allowed": False,
        },
    }


def _evidence_refs(intent: GovernedIntent, handoff: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for evidence_ref in intent.evidence_refs:
        if evidence_ref not in refs:
            refs.append(evidence_ref)
    handoff_id = str(handoff.get("handoff_id", "missing"))
    refs.append(f"proof://personal-assistant/teamops/shared-inbox/{_safe_identifier(handoff_id)}")
    return refs


def _scan_secret_names(values: set[str]) -> None:
    for value in values:
        _require_text(value, "github_secret_name")


def _scan_live_probe_environment(environment: Mapping[str, str]) -> None:
    _scan_private_or_secret_payload(environment, path="environment")
    for key, value in environment.items():
        normalized_key = str(key).lower()
        if not any(fragment in normalized_key for fragment in _CREDENTIAL_FIELD_FRAGMENTS):
            continue
        text = str(value).strip()
        if not text:
            continue
        if text.lower() in _SAFE_PRESENCE_VALUES:
            continue
        if text.startswith(("proof://", "receipt:", "witness:", "policy:", "secret-ref:")):
            continue
        raise PersonalAssistantInvariantError(f"environment.{key}: credential values must be presence markers or refs")


def _scan_private_or_secret_payload(payload: Any, *, path: str) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if any(fragment in normalized_key for fragment in _RAW_PRIVATE_FIELD_FRAGMENTS):
                raise PersonalAssistantInvariantError(f"{path}.{key}: raw private field is forbidden")
            _scan_private_or_secret_payload(value, path=f"{path}.{key}")
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, path=f"{path}[{index}]")
    elif isinstance(payload, str) and _contains_secret_like_value(payload):
        raise PersonalAssistantInvariantError(f"{path}: secret-like value must not be serialized")


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    if _contains_secret_like_value(value):
        raise PersonalAssistantInvariantError(f"{field_name} must not contain secret-like values")
    return value


def _contains_secret_like_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS)


def _connector_ready_for_gmail_probe(connector_ref: ConnectorProofRef) -> bool:
    return (
        connector_ref.connector_name == "gmail"
        and connector_ref.proof_state == "Pass"
        and connector_ref.private_data_allowed is True
        and _has_readonly_scope(connector_ref.scopes)
    )


def _has_readonly_scope(scopes: Sequence[str]) -> bool:
    return any(any(marker in scope for marker in _GMAIL_READONLY_SCOPE_MARKERS) for scope in scopes)


def _token_presence_ready(
    environment: Mapping[str, str],
    github_secret_names: set[str],
    handoff: Mapping[str, Any],
) -> bool:
    signal_ready = any(_has_presence_signal(environment, github_secret_names, name) for name in _TOKEN_PRESENCE_SIGNAL_NAMES)
    gmail_summary = handoff.get("gmail_oauth_preflight_summary", {})
    return signal_ready and isinstance(gmail_summary, Mapping) and gmail_summary.get("ready_for_live_probe") is True


def _has_presence_signal(environment: Mapping[str, str], github_secret_names: set[str], name: str) -> bool:
    return bool(str(environment.get(name, "")).strip()) or name in github_secret_names


def _handoff_reports_ready(handoff: Mapping[str, Any]) -> bool:
    gmail_summary = handoff.get("gmail_oauth_preflight_summary", {})
    teamops_summary = handoff.get("team_ops_preflight_summary", {})
    return (
        handoff.get("ready_for_live_probe") is True
        and isinstance(gmail_summary, Mapping)
        and gmail_summary.get("ready_for_live_probe") is True
        and isinstance(teamops_summary, Mapping)
        and teamops_summary.get("ready_for_live_probe") is True
    )


def _live_probe_blockers(
    *,
    connector_ready: bool,
    token_ready: bool,
    boundary_ready: bool,
    handoff: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if not connector_ready:
        blockers.append("gmail_connector_readonly_proof_required")
    if not token_ready:
        blockers.append("gmail_token_presence_witness_required")
    if not boundary_ready:
        blockers.append("teamops_mailbox_access_boundary_witness_required")
    handoff_blockers = handoff.get("blocked_until", ())
    if isinstance(handoff_blockers, list):
        blockers.extend(str(blocker) for blocker in handoff_blockers if str(blocker).strip())
    return list(dict.fromkeys(blockers))


def _nested_bool(payload: Mapping[str, Any], section: str, field_name: str) -> bool:
    value = payload.get(section, {})
    return isinstance(value, Mapping) and value.get(field_name) is True


def _request_suffix(request_id: str) -> str:
    return _safe_identifier(request_id.removeprefix("pa_request_"))


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _safe_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9_:-]+", "_", value.lower()).strip("_") or "teamops"
