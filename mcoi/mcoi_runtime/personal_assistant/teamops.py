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
import hashlib
import json
from types import MappingProxyType
import re
from typing import Any, Mapping, Sequence

from scripts.produce_team_ops_shared_inbox_operator_handoff import (
    DEFAULT_REPOSITORY,
    produce_team_ops_shared_inbox_operator_handoff,
)
from scripts.validate_durable_gmail_oauth_runtime_preflight import build_preflight_report

from .contracts import PersonalAssistantInvariantError
from .intake import ConnectorProofRef, GovernedIntent, RequestExecutionMode
from .skill_registry import PersonalAssistantSkillRegistry, load_default_skill_registry


TEAMOPS_SHARED_INBOX_PLAN_SKILL_ID = "teamops.shared_inbox.plan"
TEAMOPS_GMAIL_LIVE_PROBE_READINESS_ROUTE = "/api/v1/personal-assistant/teamops/gmail/live-probe/readiness"

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
_TEAMOPS_GMAIL_PROBE_BLOCKED_ACTIONS = (
    "read_full_mailbox",
    "read_message_body",
    "send_email",
    "draft_email",
    "delete_email",
    "archive_email",
    "label_email",
    "mutate_provider_state",
    "serialize_raw_mailbox_payload",
    "serialize_secret_values",
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


def build_teamops_gmail_live_probe_readiness(
    *,
    generated_at: str,
    environment: Mapping[str, str] | None = None,
    github_secret_names: set[str] | None = None,
) -> dict[str, Any]:
    """Return a no-effect TeamOps/Gmail live-probe readiness receipt.

    Input contract: optional environment and GitHub secret-name inventory are
    inspected for presence only. Output contract: JSON-safe readiness evidence.
    Error contract: raises PersonalAssistantInvariantError when a redaction
    invariant would be violated before returning the payload.
    """

    timestamp = _require_text(generated_at, "generated_at")
    _scan_secret_names(github_secret_names or set())
    preflight = build_preflight_report(environment, github_secret_names=github_secret_names)
    _assert_preflight_report_redacted(preflight)
    signal_inventory = list(preflight.get("signal_inventory", ()))
    token_presence = _signal_presence(
        signal_inventory,
        ("EMAIL_CALENDAR_CONNECTOR_TOKEN", "GMAIL_ACCESS_TOKEN"),
    )
    durable_oauth_presence = _signal_presence(
        signal_inventory,
        ("GMAIL_OAUTH_CLIENT_ID", "GMAIL_OAUTH_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"),
    )
    witness_presence = _signal_presence(
        signal_inventory,
        (
            "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF",
            "MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF",
            "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF",
            "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF",
            "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF",
        ),
    )
    scope_analysis = dict(preflight.get("scope_analysis", {})) if isinstance(preflight.get("scope_analysis"), Mapping) else {}
    ready_for_live_probe = preflight.get("ready_for_live_probe") is True
    status = "passed" if ready_for_live_probe else "blocked"
    receipt = {
        "receipt_id": _teamops_gmail_probe_receipt_id(timestamp=timestamp, preflight=preflight),
        "route": TEAMOPS_GMAIL_LIVE_PROBE_READINESS_ROUTE,
        "workflow_id": "team_ops.shared_inbox_triage",
        "mode": "readiness_probe",
        "status": status,
        "solver_outcome": preflight.get("solver_outcome", "AwaitingEvidence"),
        "proof_state": "Pass" if ready_for_live_probe else "Unknown",
        "generated_at": timestamp,
        "connector_id": preflight.get("connector_id", "gmail"),
        "operation_family": preflight.get("operation_family", "missing"),
        "allowed_checks": [
            "connector_readiness",
            "token_presence",
            "durable_oauth_secret_presence",
            "gmail_scope_boundary",
            "mailbox_access_boundary",
        ],
        "blocked_actions": list(_TEAMOPS_GMAIL_PROBE_BLOCKED_ACTIONS),
        "actions_taken": [
            "durable_gmail_oauth_preflight_evaluated",
            "token_presence_checked_by_name",
            "mailbox_access_boundary_classified",
            "receipt_created",
        ],
        "actions_not_taken": [
            "gmail_provider_not_called",
            "full_mailbox_not_read",
            "message_body_not_read",
            "email_not_drafted",
            "email_not_sent",
            "email_not_deleted",
            "email_not_archived",
            "provider_state_not_mutated",
            "secret_values_not_serialized",
        ],
        "effect_boundary": {
            "readiness_probe_performed": True,
            "external_provider_call_performed": False,
            "mailbox_access_verified_by_scope_only": True,
            "mailbox_read_performed": False,
            "full_mailbox_read_performed": False,
            "message_body_read_performed": False,
            "draft_performed": False,
            "send_performed": False,
            "delete_performed": False,
            "archive_performed": False,
            "provider_mutation_performed": False,
            "external_mailbox_write_performed": False,
            "credential_values_disclosed": False,
            "production_ready_claimed": False,
        },
        "connector_readiness": {
            "ready_for_live_probe": ready_for_live_probe,
            "preflight_status": preflight.get("status", "awaiting_evidence"),
            "blocker_count": preflight.get("blocker_count", 0),
            "finding_count": preflight.get("finding_count", 0),
            "adapter_mode": preflight.get("adapter_mode", "missing"),
        },
        "token_presence": token_presence,
        "durable_oauth_presence": durable_oauth_presence,
        "witness_presence": witness_presence,
        "mailbox_access_boundary": {
            "scope_env_present": scope_analysis.get("scope_env_present", False),
            "recognized_scopes": list(scope_analysis.get("recognized_scopes", ()))
            if isinstance(scope_analysis.get("recognized_scopes", ()), list)
            else [],
            "recognized_scope_count": scope_analysis.get("recognized_scope_count", 0),
            "scope_sensitivity": scope_analysis.get("scope_sensitivity", "none"),
            "least_privilege_satisfied": scope_analysis.get("least_privilege_satisfied", False),
            "metadata_scope_search_compatible": scope_analysis.get("metadata_scope_search_compatible", False),
            "mailbox_read_allowed": False,
            "mailbox_mutation_allowed": False,
            "provider_operation_allowed_after_approval": "email.search"
            if ready_for_live_probe
            else "",
        },
        "preflight_ref": "receipt://durable_gmail_oauth_runtime_preflight",
        "preflight_findings": list(preflight.get("findings", ()))
        if isinstance(preflight.get("findings", ()), list)
        else [],
        "next_action": "bind approval and authority before any read-only provider observation"
        if ready_for_live_probe
        else "close Gmail OAuth preflight blockers before live connector probing",
    }
    _assert_preflight_report_redacted(receipt)
    return receipt


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


def _signal_presence(
    signal_inventory: Sequence[Any],
    signal_names: Sequence[str],
) -> dict[str, Any]:
    names = tuple(signal_names)
    records: list[dict[str, Any]] = []
    present_count = 0
    for name in names:
        record = _signal_record(signal_inventory, name)
        present = record.get("env_present") is True or record.get("github_secret_present") is True
        if present:
            present_count += 1
        records.append(
            {
                "name": name,
                "present": present,
                "env_present": record.get("env_present") is True,
                "github_secret_present": record.get("github_secret_present") is True,
                "secret_value_disclosed": False,
            }
        )
    return {
        "required_count": len(names),
        "present_count": present_count,
        "all_present": present_count == len(names),
        "records": records,
    }


def _signal_record(signal_inventory: Sequence[Any], signal_name: str) -> Mapping[str, Any]:
    for item in signal_inventory:
        if isinstance(item, Mapping) and item.get("name") == signal_name:
            return item
    return {}


def _teamops_gmail_probe_receipt_id(*, timestamp: str, preflight: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "timestamp": timestamp,
                "status": preflight.get("status", ""),
                "connector_id": preflight.get("connector_id", ""),
                "operation_family": preflight.get("operation_family", ""),
                "blocker_count": preflight.get("blocker_count", 0),
                "scope_analysis": preflight.get("scope_analysis", {}),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"pa_teamops_gmail_live_probe_readiness_{digest[:16]}"


def _assert_preflight_report_redacted(payload: Any) -> None:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    for marker in _SECRET_VALUE_PATTERNS:
        if marker.search(serialized):
            raise PersonalAssistantInvariantError("TeamOps Gmail probe receipt would serialize a secret-like value")
    for marker in ("client_secret=", "refresh_token=", "-----BEGIN PRIVATE KEY-----", "ya29."):
        if marker.lower() in serialized.lower():
            raise PersonalAssistantInvariantError("TeamOps Gmail probe receipt would serialize a secret marker")


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
