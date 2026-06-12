#!/usr/bin/env python3
"""Produce a durable Gmail OAuth operator handoff packet.

Purpose: convert the durable Gmail OAuth runtime blockers into a redacted,
machine-readable operator checklist before any Google Cloud or secret-store
mutation occurs.
Governance scope: OAuth provider boundary, least-privilege scope selection,
secret-reference handling, witness refs, revocation recovery, and live-probe
admission.
Dependencies: scripts.validate_durable_gmail_oauth_runtime_preflight and
docs/64_durable_gmail_connector_runtime_plan.md.
Invariants:
  - This producer does not call Google Cloud, Gmail, or GitHub secret mutation.
  - Token, refresh-token, OAuth client-secret, and private-key values are never
    serialized.
  - Missing provider witnesses remain AwaitingEvidence.
  - A live probe is admitted only from presence-only preflight evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts import validate_durable_gmail_oauth_runtime_preflight as preflight  # noqa: E402


DEFAULT_OUTPUT = WORKSPACE_ROOT / ".change_assurance" / "durable_gmail_oauth_operator_handoff.json"
DEFAULT_REPOSITORY = "tamirat-wubie/mullu-control-plane"
DEFAULT_OPERATION_FAMILY = "read_only_search"
DEFAULT_ADAPTER_MODE = "google"
DEFAULT_CONNECTOR_ID = "gmail"
PROVIDER_ACTION_IDS = (
    "select_google_cloud_project",
    "configure_oauth_consent_screen",
    "declare_least_privilege_gmail_scope",
    "create_oauth_client_without_secret_serialization",
    "complete_operator_consent_for_refresh_token",
    "store_runtime_secrets_by_reference",
    "record_revocation_recovery_receipt",
    "run_durable_gmail_runtime_preflight",
)


def produce_durable_gmail_oauth_operator_handoff(
    environment: Mapping[str, str] | None = None,
    *,
    github_secret_names: set[str] | None = None,
    operator_approval_ref: str = "",
    repository: str = DEFAULT_REPOSITORY,
) -> dict[str, Any]:
    """Return a redacted operator handoff packet for durable Gmail OAuth setup."""

    env = dict(os.environ if environment is None else environment)
    secret_names = set(github_secret_names or set())
    configured_operation_family = env.get(
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY",
        DEFAULT_OPERATION_FAMILY,
    )
    operation_family = (
        configured_operation_family
        if configured_operation_family in preflight.OPERATION_FAMILY_MINIMUM_SCOPES
        else DEFAULT_OPERATION_FAMILY
    )
    scope_set = sorted(preflight.OPERATION_FAMILY_MINIMUM_SCOPES[operation_family])
    normalized_env = _environment_with_defaults(env, operation_family=operation_family, scope_set=scope_set)
    preflight_report = preflight.build_preflight_report(
        normalized_env,
        github_secret_names=secret_names,
    )
    ready_for_live_probe = bool(preflight_report["ready_for_live_probe"]) and bool(operator_approval_ref.strip())
    ready_for_provider_setup = bool(operator_approval_ref.strip()) and not ready_for_live_probe
    packet = {
        "handoff_id": _stable_handoff_id(
            operation_family=operation_family,
            scope_set=scope_set,
            operator_approval_ref=operator_approval_ref,
            preflight_report=preflight_report,
        ),
        "schema_version": 1,
        "status": _handoff_status(
            provider_setup_authorized=bool(operator_approval_ref.strip()),
            ready_for_live_probe=ready_for_live_probe,
        ),
        "solver_outcome": "SolvedVerified" if ready_for_live_probe else "AwaitingEvidence",
        "repository": repository,
        "connector_id": DEFAULT_CONNECTOR_ID,
        "operation_family": operation_family,
        "provider_setup_authorized": bool(operator_approval_ref.strip()),
        "operator_approval_ref": _redacted_ref(operator_approval_ref),
        "external_provider_mutation_performed": False,
        "github_secret_mutation_performed": False,
        "credential_values_disclosed": False,
        "ready_for_provider_setup": ready_for_provider_setup,
        "ready_for_live_probe": ready_for_live_probe,
        "scope_decision": _scope_decision(operation_family, scope_set),
        "provider_console_actions": _provider_console_actions(scope_set),
        "runtime_bindings": _runtime_bindings(repository),
        "preflight_summary": _preflight_summary(preflight_report),
        "blocked_until": _blocked_until(
            provider_setup_authorized=bool(operator_approval_ref.strip()),
            preflight_report=preflight_report,
        ),
        "verification_commands": (
            "python scripts\\validate_durable_gmail_oauth_runtime_preflight.py --json --require-ready",
            "python scripts\\validate_durable_gmail_connector_runtime_plan.py",
            "python -m pytest tests\\test_gateway\\test_gmail_oauth_lifecycle.py "
            "tests\\test_validate_durable_gmail_oauth_runtime_preflight.py -q",
        ),
    }
    _assert_redacted(packet)
    return packet


def write_durable_gmail_oauth_operator_handoff(packet: dict[str, Any], output_path: Path) -> Path:
    """Write one redacted durable Gmail OAuth handoff packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _environment_with_defaults(
    environment: Mapping[str, str],
    *,
    operation_family: str,
    scope_set: Sequence[str],
) -> dict[str, str]:
    normalized = dict(environment)
    normalized.setdefault("MULLU_EMAIL_CALENDAR_WORKER_ADAPTER", DEFAULT_ADAPTER_MODE)
    normalized.setdefault("EMAIL_CALENDAR_CONNECTOR_ID", DEFAULT_CONNECTOR_ID)
    normalized.setdefault("MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY", operation_family)
    normalized.setdefault("GMAIL_SCOPE_ID", " ".join(scope_set))
    return normalized


def _scope_decision(operation_family: str, scope_set: Sequence[str]) -> dict[str, Any]:
    sensitivity = "none"
    for scope in scope_set:
        scope_sensitivity = preflight.SCOPE_SENSITIVITY.get(scope, "none")
        if preflight.SENSITIVITY_ORDER[scope_sensitivity] > preflight.SENSITIVITY_ORDER[sensitivity]:
            sensitivity = scope_sensitivity
    return {
        "operation_family": operation_family,
        "minimum_scopes": list(scope_set),
        "scope_sensitivity": sensitivity,
        "least_privilege_required": True,
        "full_mail_scope_allowed": False,
        "metadata_scope_search_compatible": operation_family != "read_only_search",
    }


def _provider_console_actions(scope_set: Sequence[str]) -> list[dict[str, Any]]:
    return [
        {
            "action_id": "select_google_cloud_project",
            "effect_boundary": "external_provider_configuration",
            "requires_explicit_operator_execution": True,
            "evidence_ref_env": "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF",
        },
        {
            "action_id": "configure_oauth_consent_screen",
            "effect_boundary": "external_provider_configuration",
            "requires_explicit_operator_execution": True,
            "required_evidence": (
                "app identity",
                "support contact",
                "authorized domain",
                "privacy/support links when public",
            ),
            "evidence_ref_env": "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF",
        },
        {
            "action_id": "declare_least_privilege_gmail_scope",
            "effect_boundary": "external_provider_configuration",
            "requires_explicit_operator_execution": True,
            "scope_set": list(scope_set),
            "evidence_ref_env": "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF",
        },
        {
            "action_id": "create_oauth_client_without_secret_serialization",
            "effect_boundary": "external_provider_configuration",
            "requires_explicit_operator_execution": True,
            "secret_outputs": ("GMAIL_OAUTH_CLIENT_ID", "GMAIL_OAUTH_CLIENT_SECRET"),
            "evidence_ref_env": "MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF",
        },
        {
            "action_id": "complete_operator_consent_for_refresh_token",
            "effect_boundary": "external_provider_authorization",
            "requires_explicit_operator_execution": True,
            "secret_outputs": ("GMAIL_REFRESH_TOKEN",),
            "evidence_ref_env": "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF",
        },
        {
            "action_id": "store_runtime_secrets_by_reference",
            "effect_boundary": "secret_store_mutation",
            "requires_explicit_operator_execution": True,
            "evidence_ref_env": "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF",
        },
        {
            "action_id": "record_revocation_recovery_receipt",
            "effect_boundary": "recovery_evidence",
            "requires_explicit_operator_execution": True,
            "evidence_ref_env": "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF",
        },
        {
            "action_id": "run_durable_gmail_runtime_preflight",
            "effect_boundary": "repository_local_validation",
            "requires_explicit_operator_execution": False,
            "command": "python scripts\\validate_durable_gmail_oauth_runtime_preflight.py --json --require-ready",
        },
    ]


def _runtime_bindings(repository: str) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for name in preflight.NON_SECRET_CONFIG_SIGNAL_NAMES:
        bindings.append(
            {
                "name": name,
                "classification": "non_secret_config",
                "secret_store_command": "",
                "value_must_not_be_committed": True,
            }
        )
    for name in (*preflight.DURABLE_SECRET_SIGNAL_NAMES, *preflight.WITNESS_REF_SIGNAL_NAMES):
        bindings.append(
            {
                "name": name,
                "classification": "secret" if name in preflight.DURABLE_SECRET_SIGNAL_NAMES else "witness_ref",
                "secret_store_command": f"gh secret set {name} --repo {repository}",
                "value_must_not_be_committed": True,
            }
        )
    return bindings


def _preflight_summary(preflight_report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "receipt_id": preflight_report.get("receipt_id"),
        "status": preflight_report.get("status"),
        "solver_outcome": preflight_report.get("solver_outcome"),
        "blocker_count": preflight_report.get("blocker_count"),
        "ready_for_live_probe": preflight_report.get("ready_for_live_probe"),
        "credential_values_disclosed": preflight_report.get("credential_values_disclosed"),
        "external_provider_mutation_performed": preflight_report.get("external_provider_mutation_performed"),
        "finding_rule_ids": [
            str(finding.get("rule_id", ""))
            for finding in preflight_report.get("findings", [])
            if isinstance(finding, Mapping)
        ],
        "signal_inventory": preflight_report.get("signal_inventory", []),
        "scope_analysis": preflight_report.get("scope_analysis", {}),
    }


def _blocked_until(
    *,
    provider_setup_authorized: bool,
    preflight_report: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if not provider_setup_authorized:
        blockers.append("operator_approval_ref")
    blockers.extend(
        str(finding.get("rule_id", ""))
        for finding in preflight_report.get("findings", [])
        if isinstance(finding, Mapping)
    )
    return list(dict.fromkeys(blocker for blocker in blockers if blocker))


def _handoff_status(*, provider_setup_authorized: bool, ready_for_live_probe: bool) -> str:
    if ready_for_live_probe:
        return "ready_for_live_probe"
    if provider_setup_authorized:
        return "ready_for_provider_setup"
    return "awaiting_operator_authority"


def _stable_handoff_id(
    *,
    operation_family: str,
    scope_set: Sequence[str],
    operator_approval_ref: str,
    preflight_report: Mapping[str, Any],
) -> str:
    material = {
        "operation_family": operation_family,
        "scope_set": list(scope_set),
        "operator_approval_ref": _redacted_ref(operator_approval_ref),
        "preflight_status": preflight_report.get("status"),
        "blocker_count": preflight_report.get("blocker_count"),
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"durable-gmail-oauth-operator-handoff-{digest}"


def _redacted_ref(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    for marker in preflight.SECRET_VALUE_MARKERS:
        if marker in stripped:
            raise ValueError(f"durable Gmail OAuth handoff reference contains prohibited secret marker: {marker}")
    return f"ref:{hashlib.sha256(stripped.encode('utf-8')).hexdigest()[:12]}"


def _assert_redacted(packet: Mapping[str, Any]) -> None:
    serialized_packet = json.dumps(packet, sort_keys=True)
    for marker in preflight.SECRET_VALUE_MARKERS:
        if marker in serialized_packet:
            raise ValueError(f"durable Gmail OAuth handoff contains prohibited secret marker: {marker}")


def _parse_github_secret_names(values: Sequence[str]) -> set[str]:
    return {value.strip() for value in values if value.strip()}


def main(argv: list[str] | None = None) -> int:
    """Produce a durable Gmail OAuth operator handoff packet."""

    parser = argparse.ArgumentParser(description="Produce durable Gmail OAuth operator handoff packet.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repo", default=DEFAULT_REPOSITORY)
    parser.add_argument("--operator-approval-ref", default=os.environ.get("MULLU_GMAIL_OPERATOR_APPROVAL_REF", ""))
    parser.add_argument(
        "--github-secret-name",
        action="append",
        default=[],
        help="presence-only GitHub secret name; value is never accepted",
    )
    parser.add_argument(
        "--require-live-probe",
        action="store_true",
        help="return nonzero unless the handoff is ready for the live Gmail probe",
    )
    parser.add_argument("--json", action="store_true", help="print the generated handoff packet")
    args = parser.parse_args(argv)

    packet = produce_durable_gmail_oauth_operator_handoff(
        repository=args.repo,
        operator_approval_ref=args.operator_approval_ref,
        github_secret_names=_parse_github_secret_names(args.github_secret_name),
    )
    write_durable_gmail_oauth_operator_handoff(packet, args.output)
    if args.json:
        sys.stdout.write(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    if args.require_live_probe and not packet["ready_for_live_probe"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
