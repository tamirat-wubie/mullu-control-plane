#!/usr/bin/env python3
"""Produce a TeamOps shared inbox operator handoff packet.

Purpose: convert TeamOps shared inbox connector blockers into a redacted,
machine-readable operator checklist before any provider, secret-store, inbox,
or external-send mutation occurs.
Governance scope: TeamOps assistant profile admission, shared inbox connector
scope, owner queue evidence, external-send approval policy, idempotency policy,
secret-reference handling, revocation recovery, and live-probe admission.
Dependencies: scripts.validate_durable_gmail_oauth_runtime_preflight and
assistant_profiles/team_ops.default.yaml.
Invariants:
  - This producer does not call Gmail, Google Cloud, Slack, Teams, GitHub secret
    mutation, or any external message send path.
  - Secret, token, OAuth client-secret, refresh-token, private-key, and witness
    values are never serialized.
  - Missing provider or TeamOps witnesses remain AwaitingEvidence.
  - Live-probe readiness requires operator authority, Gmail OAuth preflight
    closure, and TeamOps shared inbox witness closure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts import validate_durable_gmail_oauth_runtime_preflight as gmail_preflight  # noqa: E402


DEFAULT_OUTPUT = WORKSPACE_ROOT / ".change_assurance" / "team_ops_shared_inbox_operator_handoff.json"
DEFAULT_REPOSITORY = "tamirat-wubie/mullu-control-plane"
DEFAULT_ASSISTANT_PROFILE = "team_ops.default"
DEFAULT_WORKFLOW_ID = "team_ops.shared_inbox_triage"
DEFAULT_CONNECTOR_ID = "gmail"
DEFAULT_OPERATION_FAMILY = "read_and_send_with_approval"
DEFAULT_SHARED_INBOX_PROVIDER = "gmail"
DEFAULT_OPERATION_MODE = "shared_inbox_triage"
DEFAULT_EXTERNAL_SEND_POLICY = "approval_required"

TEAM_OPS_ALLOWED_CAPABILITIES = (
    "messaging.thread.read",
    "email.read",
    "email.draft",
    "task.assign",
    "email.send.with_approval",
)
TEAM_OPS_FORBIDDEN_ACTIONS = (
    "external_send_without_approval",
    "provider_mutation_from_handoff_script",
    "secret_value_serialization",
    "cross_tenant_shared_inbox_access",
)
TEAM_OPS_NON_SECRET_CONFIG_SIGNAL_NAMES = (
    "MULLU_TEAM_OPS_ASSISTANT_PROFILE",
    "MULLU_TEAM_OPS_SHARED_INBOX_PROVIDER",
    "MULLU_TEAM_OPS_CONNECTOR_OPERATION_MODE",
    "MULLU_TEAM_OPS_EXTERNAL_SEND_POLICY",
)
TEAM_OPS_WITNESS_REF_SIGNAL_NAMES = (
    "MULLU_TEAM_OPS_TENANT_SCOPE_WITNESS_REF",
    "MULLU_TEAM_OPS_SHARED_INBOX_WITNESS_REF",
    "MULLU_TEAM_OPS_DIRECTORY_WITNESS_REF",
    "MULLU_TEAM_OPS_OWNER_QUEUE_WITNESS_REF",
    "MULLU_TEAM_OPS_EXTERNAL_SEND_APPROVAL_POLICY_REF",
    "MULLU_TEAM_OPS_IDEMPOTENCY_POLICY_REF",
    "MULLU_TEAM_OPS_REVOCATION_RECOVERY_RECEIPT_REF",
)
TEAM_OPS_OPERATOR_ACTION_IDS = (
    "authorize_team_ops_assistant_profile",
    "bind_shared_inbox_identity",
    "bind_team_directory_owner_queue",
    "declare_external_send_approval_policy",
    "bind_gmail_oauth_least_privilege_scope",
    "complete_provider_setup_without_secret_serialization",
    "record_team_ops_revocation_recovery_receipt",
    "run_team_ops_shared_inbox_preflight",
)
SECRET_VALUE_MARKERS = (
    *gmail_preflight.SECRET_VALUE_MARKERS,
    "Bearer ",
    "ghp_",
    "github_pat_",
)


@dataclass(frozen=True, slots=True)
class TeamOpsPreflightFinding:
    """One deterministic TeamOps shared inbox preflight finding."""

    rule_id: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-safe finding without secret material."""

        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
        }


def produce_team_ops_shared_inbox_operator_handoff(
    environment: Mapping[str, str] | None = None,
    *,
    github_secret_names: set[str] | None = None,
    operator_approval_ref: str = "",
    repository: str = DEFAULT_REPOSITORY,
) -> dict[str, Any]:
    """Return a redacted operator handoff packet for TeamOps shared inbox setup."""

    env = dict(os.environ if environment is None else environment)
    secret_names = set(github_secret_names or set())
    operation_family = _operation_family_for_recommendation(env)
    scope_set = sorted(gmail_preflight.OPERATION_FAMILY_MINIMUM_SCOPES[operation_family])
    gmail_report = gmail_preflight.build_preflight_report(env, github_secret_names=secret_names)
    team_ops_report = build_team_ops_shared_inbox_preflight_report(env, github_secret_names=secret_names)
    provider_setup_authorized = bool(operator_approval_ref.strip())
    ready_for_live_probe = (
        provider_setup_authorized
        and bool(gmail_report["ready_for_live_probe"])
        and bool(team_ops_report["ready_for_live_probe"])
    )
    ready_for_provider_setup = provider_setup_authorized and not ready_for_live_probe
    packet = {
        "handoff_id": _stable_handoff_id(
            operation_family=operation_family,
            scope_set=scope_set,
            operator_approval_ref=operator_approval_ref,
            gmail_report=gmail_report,
            team_ops_report=team_ops_report,
        ),
        "schema_version": 1,
        "status": _handoff_status(
            provider_setup_authorized=provider_setup_authorized,
            ready_for_live_probe=ready_for_live_probe,
        ),
        "solver_outcome": "SolvedVerified" if ready_for_live_probe else "AwaitingEvidence",
        "repository": repository,
        "assistant_profile_id": DEFAULT_ASSISTANT_PROFILE,
        "workflow_id": DEFAULT_WORKFLOW_ID,
        "connector_id": DEFAULT_CONNECTOR_ID,
        "operation_family": operation_family,
        "provider_setup_authorized": provider_setup_authorized,
        "operator_approval_ref": _redacted_ref(operator_approval_ref),
        "external_provider_mutation_performed": False,
        "github_secret_mutation_performed": False,
        "external_message_sent": False,
        "credential_values_disclosed": False,
        "ready_for_provider_setup": ready_for_provider_setup,
        "ready_for_live_probe": ready_for_live_probe,
        "capability_boundary": _capability_boundary(),
        "scope_decision": _scope_decision(operation_family, scope_set),
        "recommended_runtime_defaults": _recommended_runtime_defaults(
            operation_family=operation_family,
            scope_set=scope_set,
        ),
        "preflight_environment_basis": "observed_environment_without_defaults",
        "operator_actions": _operator_actions(scope_set),
        "runtime_bindings": _runtime_bindings(repository),
        "gmail_oauth_preflight_summary": _gmail_preflight_summary(gmail_report),
        "team_ops_preflight_summary": _team_ops_preflight_summary(team_ops_report),
        "blocked_until": _blocked_until(
            provider_setup_authorized=provider_setup_authorized,
            gmail_report=gmail_report,
            team_ops_report=team_ops_report,
        ),
        "verification_commands": (
            "python scripts\\validate_team_ops_shared_inbox_operator_handoff.py --require-blocked --json",
            "python scripts\\validate_durable_gmail_oauth_runtime_preflight.py --json --require-ready",
            "python -m pytest tests\\test_produce_team_ops_shared_inbox_operator_handoff.py "
            "tests\\test_validate_team_ops_shared_inbox_operator_handoff.py -q",
        ),
    }
    _assert_redacted(packet)
    return packet


def build_team_ops_shared_inbox_preflight_report(
    environment: Mapping[str, str],
    *,
    github_secret_names: set[str] | None = None,
) -> dict[str, Any]:
    """Build a presence-only TeamOps shared inbox preflight receipt."""

    secret_names = set(github_secret_names or set())
    findings = validate_team_ops_shared_inbox_preflight_signals(
        environment,
        github_secret_names=secret_names,
    )
    blocker_count = sum(1 for finding in findings if finding.severity == "blocker")
    ready = blocker_count == 0
    report = {
        "receipt_id": "team_ops_shared_inbox_handoff_preflight",
        "status": "passed" if ready else "awaiting_evidence",
        "solver_outcome": "SolvedVerified" if ready else "AwaitingEvidence",
        "ready_for_live_probe": ready,
        "production_ready_claimed": False,
        "credential_values_disclosed": False,
        "secret_value_markers_present": False,
        "external_provider_mutation_performed": False,
        "external_message_sent": False,
        "assistant_profile": _redacted_known_env_value(
            environment,
            "MULLU_TEAM_OPS_ASSISTANT_PROFILE",
            allowed_values=frozenset({DEFAULT_ASSISTANT_PROFILE}),
            default_value="missing",
        ),
        "shared_inbox_provider": _redacted_known_env_value(
            environment,
            "MULLU_TEAM_OPS_SHARED_INBOX_PROVIDER",
            allowed_values=frozenset({DEFAULT_SHARED_INBOX_PROVIDER}),
            default_value="missing",
        ),
        "operation_mode": _redacted_known_env_value(
            environment,
            "MULLU_TEAM_OPS_CONNECTOR_OPERATION_MODE",
            allowed_values=frozenset({DEFAULT_OPERATION_MODE}),
            default_value="missing",
        ),
        "external_send_policy": _redacted_known_env_value(
            environment,
            "MULLU_TEAM_OPS_EXTERNAL_SEND_POLICY",
            allowed_values=frozenset({DEFAULT_EXTERNAL_SEND_POLICY}),
            default_value="missing",
        ),
        "signal_inventory": build_team_ops_signal_inventory(
            environment,
            github_secret_names=secret_names,
        ),
        "blocker_count": blocker_count,
        "finding_count": len(findings),
        "findings": [finding.to_dict() for finding in findings],
    }
    _assert_redacted(report)
    return report


def validate_team_ops_shared_inbox_preflight_signals(
    environment: Mapping[str, str],
    *,
    github_secret_names: set[str] | None = None,
) -> list[TeamOpsPreflightFinding]:
    """Return blocker findings for TeamOps shared inbox preflight state."""

    secret_names = set(github_secret_names or set())
    findings: list[TeamOpsPreflightFinding] = []
    findings.extend(_validate_team_ops_config_boundary(environment))
    findings.extend(_validate_team_ops_witness_presence(environment, secret_names))
    findings.extend(_validate_no_secret_marker_leakage(environment, secret_names))
    return findings


def build_team_ops_signal_inventory(
    environment: Mapping[str, str],
    *,
    github_secret_names: set[str] | None = None,
) -> list[dict[str, object]]:
    """Return TeamOps presence-only signal inventory without raw values."""

    secret_names = set(github_secret_names or set())
    inventory: list[dict[str, object]] = []
    for name in (*TEAM_OPS_NON_SECRET_CONFIG_SIGNAL_NAMES, *TEAM_OPS_WITNESS_REF_SIGNAL_NAMES):
        inventory.append(
            {
                "name": name,
                "env_present": _has_env_value(environment, name),
                "github_secret_present": name in secret_names,
                "secret_value_disclosed": False,
            }
        )
    return inventory


def write_team_ops_shared_inbox_operator_handoff(packet: dict[str, Any], output_path: Path) -> Path:
    """Write one redacted TeamOps shared inbox handoff packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_team_ops_config_boundary(environment: Mapping[str, str]) -> list[TeamOpsPreflightFinding]:
    findings: list[TeamOpsPreflightFinding] = []
    expected = {
        "MULLU_TEAM_OPS_ASSISTANT_PROFILE": (
            DEFAULT_ASSISTANT_PROFILE,
            "team_ops_profile_missing_or_unsupported",
            "MULLU_TEAM_OPS_ASSISTANT_PROFILE must select team_ops.default.",
        ),
        "MULLU_TEAM_OPS_SHARED_INBOX_PROVIDER": (
            DEFAULT_SHARED_INBOX_PROVIDER,
            "team_ops_shared_inbox_provider_missing_or_unsupported",
            "MULLU_TEAM_OPS_SHARED_INBOX_PROVIDER must select gmail for this handoff.",
        ),
        "MULLU_TEAM_OPS_CONNECTOR_OPERATION_MODE": (
            DEFAULT_OPERATION_MODE,
            "team_ops_operation_mode_missing_or_unsupported",
            "MULLU_TEAM_OPS_CONNECTOR_OPERATION_MODE must select shared_inbox_triage.",
        ),
        "MULLU_TEAM_OPS_EXTERNAL_SEND_POLICY": (
            DEFAULT_EXTERNAL_SEND_POLICY,
            "team_ops_external_send_policy_missing_or_unsupported",
            "MULLU_TEAM_OPS_EXTERNAL_SEND_POLICY must require approval_required.",
        ),
    }
    for name, (expected_value, rule_id, message) in expected.items():
        observed = str(environment.get(name, "")).strip()
        if observed != expected_value:
            findings.append(TeamOpsPreflightFinding(rule_id, "blocker", message))
    return findings


def _validate_team_ops_witness_presence(
    environment: Mapping[str, str],
    github_secret_names: set[str],
) -> list[TeamOpsPreflightFinding]:
    findings: list[TeamOpsPreflightFinding] = []
    for name in TEAM_OPS_WITNESS_REF_SIGNAL_NAMES:
        if not _has_signal(environment, github_secret_names, name):
            findings.append(
                TeamOpsPreflightFinding(
                    "team_ops_witness_ref_missing",
                    "blocker",
                    f"{name} is required before TeamOps shared inbox probing can leave AwaitingEvidence.",
                )
            )
    return findings


def _validate_no_secret_marker_leakage(
    environment: Mapping[str, str],
    github_secret_names: set[str],
) -> list[TeamOpsPreflightFinding]:
    report_shape = {
        "signal_inventory": build_team_ops_signal_inventory(
            environment,
            github_secret_names=github_secret_names,
        )
    }
    serialized_report_shape = json.dumps(report_shape, sort_keys=True)
    leaked_markers = [marker for marker in SECRET_VALUE_MARKERS if marker in serialized_report_shape]
    if leaked_markers:
        return [
            TeamOpsPreflightFinding(
                "team_ops_secret_marker_leaked",
                "blocker",
                "TeamOps preflight report attempted to serialize a prohibited secret marker.",
            )
        ]
    return []


def _capability_boundary() -> dict[str, Any]:
    return {
        "allowed_capabilities": list(TEAM_OPS_ALLOWED_CAPABILITIES),
        "forbidden_actions": list(TEAM_OPS_FORBIDDEN_ACTIONS),
        "external_send_requires_approval": True,
        "operator_approval_queue_required": True,
        "tenant_scope_required": True,
        "idempotency_window_required": True,
        "plan_only": True,
    }


def _scope_decision(operation_family: str, scope_set: Sequence[str]) -> dict[str, Any]:
    sensitivity = "none"
    for scope in scope_set:
        scope_sensitivity = gmail_preflight.SCOPE_SENSITIVITY.get(scope, "none")
        if gmail_preflight.SENSITIVITY_ORDER[scope_sensitivity] > gmail_preflight.SENSITIVITY_ORDER[sensitivity]:
            sensitivity = scope_sensitivity
    return {
        "operation_family": operation_family,
        "minimum_scopes": list(scope_set),
        "scope_sensitivity": sensitivity,
        "least_privilege_required": True,
        "full_mail_scope_allowed": False,
        "metadata_scope_search_compatible": operation_family != "read_only_search",
        "external_send_requires_approval": True,
    }


def _recommended_runtime_defaults(*, operation_family: str, scope_set: Sequence[str]) -> list[dict[str, str]]:
    return [
        {
            "name": "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER",
            "recommended_value": "google",
            "classification": "non_secret_config",
        },
        {
            "name": "EMAIL_CALENDAR_CONNECTOR_ID",
            "recommended_value": DEFAULT_CONNECTOR_ID,
            "classification": "non_secret_config",
        },
        {
            "name": "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY",
            "recommended_value": operation_family,
            "classification": "non_secret_config",
        },
        {
            "name": "GMAIL_SCOPE_ID",
            "recommended_value": " ".join(scope_set),
            "classification": "non_secret_config",
        },
        {
            "name": "MULLU_TEAM_OPS_ASSISTANT_PROFILE",
            "recommended_value": DEFAULT_ASSISTANT_PROFILE,
            "classification": "non_secret_config",
        },
        {
            "name": "MULLU_TEAM_OPS_SHARED_INBOX_PROVIDER",
            "recommended_value": DEFAULT_SHARED_INBOX_PROVIDER,
            "classification": "non_secret_config",
        },
        {
            "name": "MULLU_TEAM_OPS_CONNECTOR_OPERATION_MODE",
            "recommended_value": DEFAULT_OPERATION_MODE,
            "classification": "non_secret_config",
        },
        {
            "name": "MULLU_TEAM_OPS_EXTERNAL_SEND_POLICY",
            "recommended_value": DEFAULT_EXTERNAL_SEND_POLICY,
            "classification": "non_secret_config",
        },
    ]


def _operator_actions(scope_set: Sequence[str]) -> list[dict[str, Any]]:
    return [
        {
            "action_id": "authorize_team_ops_assistant_profile",
            "effect_boundary": "assistant_profile_authority",
            "requires_explicit_operator_execution": True,
            "evidence_ref_env": "MULLU_TEAM_OPS_TENANT_SCOPE_WITNESS_REF",
        },
        {
            "action_id": "bind_shared_inbox_identity",
            "effect_boundary": "shared_inbox_identity",
            "requires_explicit_operator_execution": True,
            "provider": DEFAULT_SHARED_INBOX_PROVIDER,
            "evidence_ref_env": "MULLU_TEAM_OPS_SHARED_INBOX_WITNESS_REF",
        },
        {
            "action_id": "bind_team_directory_owner_queue",
            "effect_boundary": "organization_directory_and_owner_queue",
            "requires_explicit_operator_execution": True,
            "required_evidence": (
                "directory sync witness",
                "owner queue witness",
                "tenant scope witness",
            ),
            "evidence_ref_env": "MULLU_TEAM_OPS_OWNER_QUEUE_WITNESS_REF",
        },
        {
            "action_id": "declare_external_send_approval_policy",
            "effect_boundary": "external_send_policy",
            "requires_explicit_operator_execution": True,
            "required_policy": DEFAULT_EXTERNAL_SEND_POLICY,
            "evidence_ref_env": "MULLU_TEAM_OPS_EXTERNAL_SEND_APPROVAL_POLICY_REF",
        },
        {
            "action_id": "bind_gmail_oauth_least_privilege_scope",
            "effect_boundary": "external_provider_configuration",
            "requires_explicit_operator_execution": True,
            "scope_set": list(scope_set),
            "evidence_ref_env": "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF",
        },
        {
            "action_id": "complete_provider_setup_without_secret_serialization",
            "effect_boundary": "external_provider_authorization",
            "requires_explicit_operator_execution": True,
            "secret_outputs": ("GMAIL_OAUTH_CLIENT_ID", "GMAIL_OAUTH_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"),
            "evidence_ref_env": "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF",
        },
        {
            "action_id": "record_team_ops_revocation_recovery_receipt",
            "effect_boundary": "recovery_evidence",
            "requires_explicit_operator_execution": True,
            "evidence_ref_env": "MULLU_TEAM_OPS_REVOCATION_RECOVERY_RECEIPT_REF",
        },
        {
            "action_id": "run_team_ops_shared_inbox_preflight",
            "effect_boundary": "repository_local_validation",
            "requires_explicit_operator_execution": False,
            "command": "python scripts\\validate_team_ops_shared_inbox_operator_handoff.py --require-live-probe --json",
        },
    ]


def _runtime_bindings(repository: str) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for name in gmail_preflight.NON_SECRET_CONFIG_SIGNAL_NAMES:
        bindings.append(
            {
                "name": name,
                "classification": "non_secret_config",
                "secret_store_command": "",
                "value_must_not_be_committed": True,
            }
        )
    for name in (*gmail_preflight.DURABLE_SECRET_SIGNAL_NAMES, *gmail_preflight.WITNESS_REF_SIGNAL_NAMES):
        bindings.append(
            {
                "name": name,
                "classification": "secret" if name in gmail_preflight.DURABLE_SECRET_SIGNAL_NAMES else "witness_ref",
                "secret_store_command": f"gh secret set {name} --repo {repository}",
                "value_must_not_be_committed": True,
            }
        )
    for name in TEAM_OPS_NON_SECRET_CONFIG_SIGNAL_NAMES:
        bindings.append(
            {
                "name": name,
                "classification": "non_secret_config",
                "secret_store_command": "",
                "value_must_not_be_committed": True,
            }
        )
    for name in TEAM_OPS_WITNESS_REF_SIGNAL_NAMES:
        bindings.append(
            {
                "name": name,
                "classification": "witness_ref",
                "secret_store_command": f"gh secret set {name} --repo {repository}",
                "value_must_not_be_committed": True,
            }
        )
    return bindings


def _gmail_preflight_summary(gmail_report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "receipt_id": gmail_report.get("receipt_id"),
        "status": gmail_report.get("status"),
        "solver_outcome": gmail_report.get("solver_outcome"),
        "blocker_count": gmail_report.get("blocker_count"),
        "ready_for_live_probe": gmail_report.get("ready_for_live_probe"),
        "credential_values_disclosed": gmail_report.get("credential_values_disclosed"),
        "external_provider_mutation_performed": gmail_report.get("external_provider_mutation_performed"),
        "finding_rule_ids": [
            str(finding.get("rule_id", ""))
            for finding in gmail_report.get("findings", [])
            if isinstance(finding, Mapping)
        ],
        "signal_inventory": gmail_report.get("signal_inventory", []),
        "scope_analysis": gmail_report.get("scope_analysis", {}),
    }


def _team_ops_preflight_summary(team_ops_report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "receipt_id": team_ops_report.get("receipt_id"),
        "status": team_ops_report.get("status"),
        "solver_outcome": team_ops_report.get("solver_outcome"),
        "blocker_count": team_ops_report.get("blocker_count"),
        "ready_for_live_probe": team_ops_report.get("ready_for_live_probe"),
        "credential_values_disclosed": team_ops_report.get("credential_values_disclosed"),
        "external_provider_mutation_performed": team_ops_report.get("external_provider_mutation_performed"),
        "external_message_sent": team_ops_report.get("external_message_sent"),
        "finding_rule_ids": [
            str(finding.get("rule_id", ""))
            for finding in team_ops_report.get("findings", [])
            if isinstance(finding, Mapping)
        ],
        "signal_inventory": team_ops_report.get("signal_inventory", []),
    }


def _blocked_until(
    *,
    provider_setup_authorized: bool,
    gmail_report: Mapping[str, Any],
    team_ops_report: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if not provider_setup_authorized:
        blockers.append("operator_approval_ref")
    blockers.extend(
        f"gmail:{finding.get('rule_id', '')}"
        for finding in gmail_report.get("findings", [])
        if isinstance(finding, Mapping) and finding.get("severity") == "blocker"
    )
    blockers.extend(
        f"team_ops:{finding.get('rule_id', '')}"
        for finding in team_ops_report.get("findings", [])
        if isinstance(finding, Mapping) and finding.get("severity") == "blocker"
    )
    return list(dict.fromkeys(blocker for blocker in blockers if blocker))


def _handoff_status(*, provider_setup_authorized: bool, ready_for_live_probe: bool) -> str:
    if ready_for_live_probe:
        return "ready_for_live_probe"
    if provider_setup_authorized:
        return "ready_for_provider_setup"
    return "awaiting_operator_authority"


def _operation_family_for_recommendation(environment: Mapping[str, str]) -> str:
    configured_operation_family = environment.get(
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY",
        DEFAULT_OPERATION_FAMILY,
    )
    return (
        configured_operation_family
        if configured_operation_family in gmail_preflight.OPERATION_FAMILY_MINIMUM_SCOPES
        else DEFAULT_OPERATION_FAMILY
    )


def _stable_handoff_id(
    *,
    operation_family: str,
    scope_set: Sequence[str],
    operator_approval_ref: str,
    gmail_report: Mapping[str, Any],
    team_ops_report: Mapping[str, Any],
) -> str:
    material = {
        "operation_family": operation_family,
        "scope_set": list(scope_set),
        "operator_approval_ref": _redacted_ref(operator_approval_ref),
        "gmail_status": gmail_report.get("status"),
        "gmail_blocker_count": gmail_report.get("blocker_count"),
        "team_ops_status": team_ops_report.get("status"),
        "team_ops_blocker_count": team_ops_report.get("blocker_count"),
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"teamops-shared-inbox-operator-handoff-{digest}"


def _redacted_ref(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    for marker in SECRET_VALUE_MARKERS:
        if marker in stripped:
            raise ValueError(f"TeamOps handoff reference contains prohibited secret marker: {marker}")
    return f"ref:{hashlib.sha256(stripped.encode('utf-8')).hexdigest()[:12]}"


def _assert_redacted(packet: Mapping[str, Any]) -> None:
    serialized_packet = json.dumps(packet, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker in serialized_packet:
            raise ValueError(f"TeamOps shared inbox handoff contains prohibited secret marker: {marker}")


def _has_signal(environment: Mapping[str, str], github_secret_names: set[str], name: str) -> bool:
    return _has_env_value(environment, name) or name in github_secret_names


def _has_env_value(environment: Mapping[str, str], name: str) -> bool:
    return bool(str(environment.get(name, "")).strip())


def _redacted_known_env_value(
    environment: Mapping[str, str],
    name: str,
    *,
    allowed_values: frozenset[str],
    default_value: str,
) -> str:
    raw = str(environment.get(name, "")).strip()
    if not raw:
        return default_value
    return raw if raw in allowed_values else "unrecognized_redacted"


def _parse_github_secret_names(values: Sequence[str]) -> set[str]:
    return {value.strip() for value in values if value.strip()}


def main(argv: list[str] | None = None) -> int:
    """Produce a TeamOps shared inbox operator handoff packet."""

    parser = argparse.ArgumentParser(description="Produce TeamOps shared inbox operator handoff packet.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repo", default=DEFAULT_REPOSITORY)
    parser.add_argument("--operator-approval-ref", default=os.environ.get("MULLU_TEAM_OPS_OPERATOR_APPROVAL_REF", ""))
    parser.add_argument(
        "--github-secret-name",
        action="append",
        default=[],
        help="presence-only GitHub secret name; value is never accepted",
    )
    parser.add_argument(
        "--require-live-probe",
        action="store_true",
        help="return nonzero unless the handoff is ready for the live shared inbox probe",
    )
    parser.add_argument("--json", action="store_true", help="print the generated handoff packet")
    args = parser.parse_args(argv)

    packet = produce_team_ops_shared_inbox_operator_handoff(
        repository=args.repo,
        operator_approval_ref=args.operator_approval_ref,
        github_secret_names=_parse_github_secret_names(args.github_secret_name),
    )
    write_team_ops_shared_inbox_operator_handoff(packet, args.output)
    if args.json:
        sys.stdout.write(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    if args.require_live_probe and not packet["ready_for_live_probe"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
