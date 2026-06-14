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
