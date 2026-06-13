#!/usr/bin/env python3
"""Validate TeamOps shared inbox operator handoff packets.

Purpose: prove TeamOps shared inbox handoffs are schema-valid, redacted, and
explicit about observed evidence versus recommended defaults before live probe
admission.
Governance scope: TeamOps assistant authority, shared inbox scope, owner queue
binding, external-send approval separation, secret redaction, and live-probe
admission.
Dependencies: schemas/team_ops_shared_inbox_operator_handoff.schema.json and
scripts.produce_team_ops_shared_inbox_operator_handoff.
Invariants:
  - Recommended runtime defaults are not counted as observed preflight evidence.
  - Live-probe readiness requires operator authority, Gmail readiness, and
    TeamOps witness readiness.
  - Provider, secret-store, and external-message mutation flags remain false.
  - Secret-shaped values are never serialized.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import validate_durable_gmail_oauth_runtime_preflight as gmail_preflight  # noqa: E402
from scripts.produce_team_ops_shared_inbox_operator_handoff import (  # noqa: E402
    SECRET_VALUE_MARKERS,
    TEAM_OPS_ALLOWED_CAPABILITIES,
    TEAM_OPS_FORBIDDEN_ACTIONS,
    TEAM_OPS_NON_SECRET_CONFIG_SIGNAL_NAMES,
    TEAM_OPS_OPERATOR_ACTION_IDS,
    TEAM_OPS_WITNESS_REF_SIGNAL_NAMES,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_HANDOFF = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_operator_handoff.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_operator_handoff.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_operator_handoff_validation.json"
RECOMMENDED_DEFAULT_NAMES = frozenset(
    {
        "EMAIL_CALENDAR_CONNECTOR_ID",
        "GMAIL_SCOPE_ID",
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER",
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY",
        "MULLU_TEAM_OPS_ASSISTANT_PROFILE",
        "MULLU_TEAM_OPS_CONNECTOR_OPERATION_MODE",
        "MULLU_TEAM_OPS_EXTERNAL_SEND_POLICY",
        "MULLU_TEAM_OPS_SHARED_INBOX_PROVIDER",
    }
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxOperatorHandoffValidation:
    """Validation result for one TeamOps shared inbox handoff packet."""

    ok: bool
    handoff_path: str
    schema_path: str
    status: str
    ready_for_live_probe: bool
    blocker_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation receipt."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_team_ops_shared_inbox_operator_handoff(
    *,
    handoff_path: Path = DEFAULT_HANDOFF,
    schema_path: Path = DEFAULT_SCHEMA,
    require_blocked: bool = False,
    require_live_probe: bool = False,
) -> TeamOpsSharedInboxOperatorHandoffValidation:
    """Validate one TeamOps shared inbox operator handoff packet."""

    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("TeamOps shared inbox operator handoff schema file missing")
    handoff = _load_json_object(handoff_path, "TeamOps shared inbox operator handoff", errors)
    if schema and handoff:
        errors.extend(_validate_schema_instance(schema, handoff))
        _validate_semantics(handoff, errors)
        if require_blocked and handoff.get("ready_for_live_probe") is True:
            errors.append("require blocked: TeamOps shared inbox handoff is ready for live probe")
        if require_live_probe and handoff.get("ready_for_live_probe") is not True:
            errors.append("require live probe: TeamOps shared inbox handoff is not ready")
    return TeamOpsSharedInboxOperatorHandoffValidation(
        ok=not errors,
        handoff_path=_path_label(handoff_path),
        schema_path=_path_label(schema_path),
        status=str(handoff.get("status", "")) if handoff else "",
        ready_for_live_probe=handoff.get("ready_for_live_probe") is True if handoff else False,
        blocker_count=_blocker_count(handoff),
        errors=tuple(errors),
    )


def write_team_ops_shared_inbox_operator_handoff_validation(
    validation: TeamOpsSharedInboxOperatorHandoffValidation,
    output_path: Path,
) -> Path:
    """Write one TeamOps shared inbox handoff validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_semantics(handoff: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(handoff, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker in serialized:
            errors.append(f"handoff must not serialize secret marker: {marker}")
    if handoff.get("external_provider_mutation_performed") is not False:
        errors.append("external_provider_mutation_performed must be false")
    if handoff.get("github_secret_mutation_performed") is not False:
        errors.append("github_secret_mutation_performed must be false")
    if handoff.get("external_message_sent") is not False:
        errors.append("external_message_sent must be false")
    if handoff.get("credential_values_disclosed") is not False:
        errors.append("credential_values_disclosed must be false")
    if handoff.get("preflight_environment_basis") != "observed_environment_without_defaults":
        errors.append("preflight_environment_basis must preserve observed environment without defaults")

    ready_for_live_probe = handoff.get("ready_for_live_probe") is True
    provider_setup_authorized = handoff.get("provider_setup_authorized") is True
    gmail_summary = handoff.get("gmail_oauth_preflight_summary", {})
    team_ops_summary = handoff.get("team_ops_preflight_summary", {})
    gmail_ready = isinstance(gmail_summary, dict) and gmail_summary.get("ready_for_live_probe") is True
    team_ops_ready = isinstance(team_ops_summary, dict) and team_ops_summary.get("ready_for_live_probe") is True
    expected_status = _expected_status(provider_setup_authorized, ready_for_live_probe)
    if handoff.get("status") != expected_status:
        errors.append(f"status must be {expected_status}")
    expected_solver_outcome = "SolvedVerified" if ready_for_live_probe else "AwaitingEvidence"
    if handoff.get("solver_outcome") != expected_solver_outcome:
        errors.append("solver_outcome must align with live-probe readiness")
    if ready_for_live_probe and not provider_setup_authorized:
        errors.append("ready_for_live_probe requires provider_setup_authorized")
    if ready_for_live_probe and not gmail_ready:
        errors.append("ready_for_live_probe requires passed Gmail OAuth preflight summary")
    if ready_for_live_probe and not team_ops_ready:
        errors.append("ready_for_live_probe requires passed TeamOps preflight summary")
    if not ready_for_live_probe and not handoff.get("blocked_until"):
        errors.append("blocked handoff must list blocked_until entries")
    if ready_for_live_probe and handoff.get("blocked_until"):
        errors.append("ready handoff must not list blocked_until entries")
    if handoff.get("ready_for_provider_setup") is not (provider_setup_authorized and not ready_for_live_probe):
        errors.append("ready_for_provider_setup must equal provider authority without live-probe readiness")

    _validate_capability_boundary(handoff, errors)
    _validate_scope_decision(handoff, errors)
    _validate_recommended_defaults(handoff, errors)
    _validate_operator_actions(handoff, errors)
    _validate_runtime_bindings(handoff, errors)
    _validate_gmail_preflight_summary(gmail_summary, errors)
    _validate_team_ops_preflight_summary(team_ops_summary, errors)


def _validate_capability_boundary(handoff: dict[str, Any], errors: list[str]) -> None:
    boundary = handoff.get("capability_boundary", {})
    if not isinstance(boundary, dict):
        errors.append("capability_boundary must be an object")
        return
    if set(boundary.get("allowed_capabilities", [])) != set(TEAM_OPS_ALLOWED_CAPABILITIES):
        errors.append("capability_boundary.allowed_capabilities must match TeamOps shared inbox capabilities")
    if set(boundary.get("forbidden_actions", [])) != set(TEAM_OPS_FORBIDDEN_ACTIONS):
        errors.append("capability_boundary.forbidden_actions must match TeamOps hard boundaries")
    for field_name in (
        "external_send_requires_approval",
        "operator_approval_queue_required",
        "tenant_scope_required",
        "idempotency_window_required",
        "plan_only",
    ):
        if boundary.get(field_name) is not True:
            errors.append(f"capability_boundary.{field_name} must be true")


def _validate_scope_decision(handoff: dict[str, Any], errors: list[str]) -> None:
    scope_decision = handoff.get("scope_decision", {})
    if not isinstance(scope_decision, dict):
        errors.append("scope_decision must be an object")
        return
    if scope_decision.get("least_privilege_required") is not True:
        errors.append("scope_decision.least_privilege_required must be true")
    if scope_decision.get("full_mail_scope_allowed") is not False:
        errors.append("scope_decision.full_mail_scope_allowed must be false")
    if scope_decision.get("external_send_requires_approval") is not True:
        errors.append("scope_decision.external_send_requires_approval must be true")
    minimum_scopes = set(scope_decision.get("minimum_scopes", []))
    required_scopes = gmail_preflight.OPERATION_FAMILY_MINIMUM_SCOPES.get(
        str(scope_decision.get("operation_family", "")),
        frozenset(),
    )
    if minimum_scopes != set(required_scopes):
        errors.append("scope_decision.minimum_scopes must match operation family minimum scopes")


def _validate_recommended_defaults(handoff: dict[str, Any], errors: list[str]) -> None:
    defaults = handoff.get("recommended_runtime_defaults", [])
    if not isinstance(defaults, list):
        errors.append("recommended_runtime_defaults must be a list")
        return
    default_names = {str(item.get("name", "")) for item in defaults if isinstance(item, dict)}
    if default_names != RECOMMENDED_DEFAULT_NAMES:
        errors.append(
            "recommended_runtime_defaults must list only TeamOps shared inbox non-secret defaults: "
            f"observed={sorted(default_names)}"
        )
    for item in defaults:
        if not isinstance(item, dict):
            continue
        if item.get("classification") != "non_secret_config":
            errors.append("recommended runtime defaults must be non_secret_config")
        if not str(item.get("recommended_value", "")).strip():
            errors.append("recommended runtime defaults must include non-empty recommended values")


def _validate_operator_actions(handoff: dict[str, Any], errors: list[str]) -> None:
    actions = handoff.get("operator_actions", [])
    if not isinstance(actions, list):
        errors.append("operator_actions must be a list")
        return
    action_ids = {str(item.get("action_id", "")) for item in actions if isinstance(item, dict)}
    if action_ids != set(TEAM_OPS_OPERATOR_ACTION_IDS):
        errors.append(f"operator action ids must match TeamOps handoff set: observed={sorted(action_ids)}")
    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("action_id") == "run_team_ops_shared_inbox_preflight":
            if action.get("requires_explicit_operator_execution") is not False:
                errors.append("run_team_ops_shared_inbox_preflight must be repository-local")
            command = str(action.get("command", ""))
            if "validate_team_ops_shared_inbox_operator_handoff.py" not in command or "--require-live-probe" not in command:
                errors.append("run_team_ops_shared_inbox_preflight command must require ready validation")
        elif action.get("requires_explicit_operator_execution") is not True:
            errors.append(f"{action.get('action_id', '')} must require explicit operator execution")


def _validate_runtime_bindings(handoff: dict[str, Any], errors: list[str]) -> None:
    bindings = handoff.get("runtime_bindings", [])
    if not isinstance(bindings, list):
        errors.append("runtime_bindings must be a list")
        return
    binding_by_name = {str(item.get("name", "")): item for item in bindings if isinstance(item, dict)}
    required_names = (
        set(gmail_preflight.NON_SECRET_CONFIG_SIGNAL_NAMES)
        | set(gmail_preflight.DURABLE_SECRET_SIGNAL_NAMES)
        | set(gmail_preflight.WITNESS_REF_SIGNAL_NAMES)
        | set(TEAM_OPS_NON_SECRET_CONFIG_SIGNAL_NAMES)
        | set(TEAM_OPS_WITNESS_REF_SIGNAL_NAMES)
    )
    missing = sorted(required_names - set(binding_by_name))
    if missing:
        errors.append(f"runtime bindings missing {missing}")
    _validate_binding_class(
        binding_by_name,
        gmail_preflight.NON_SECRET_CONFIG_SIGNAL_NAMES,
        "non_secret_config",
        require_secret_command=False,
        errors=errors,
    )
    _validate_binding_class(
        binding_by_name,
        gmail_preflight.DURABLE_SECRET_SIGNAL_NAMES,
        "secret",
        require_secret_command=True,
        errors=errors,
    )
    _validate_binding_class(
        binding_by_name,
        gmail_preflight.WITNESS_REF_SIGNAL_NAMES,
        "witness_ref",
        require_secret_command=True,
        errors=errors,
    )
    _validate_binding_class(
        binding_by_name,
        TEAM_OPS_NON_SECRET_CONFIG_SIGNAL_NAMES,
        "non_secret_config",
        require_secret_command=False,
        errors=errors,
    )
    _validate_binding_class(
        binding_by_name,
        TEAM_OPS_WITNESS_REF_SIGNAL_NAMES,
        "witness_ref",
        require_secret_command=True,
        errors=errors,
    )


def _validate_binding_class(
    binding_by_name: dict[str, Any],
    names: tuple[str, ...],
    classification: str,
    *,
    require_secret_command: bool,
    errors: list[str],
) -> None:
    for name in names:
        binding = binding_by_name.get(name, {})
        if not binding:
            continue
        if binding.get("classification") != classification:
            errors.append(f"{name} must be classified {classification}")
        command = str(binding.get("secret_store_command", ""))
        if require_secret_command and "gh secret set" not in command:
            errors.append(f"{name} must include a secret store command template")
        if not require_secret_command and command:
            errors.append(f"{name} must not include a secret store command")
        if binding.get("value_must_not_be_committed") is not True:
            errors.append(f"{name} must not be committed")


def _validate_gmail_preflight_summary(preflight_summary: Any, errors: list[str]) -> None:
    if not isinstance(preflight_summary, dict):
        errors.append("gmail_oauth_preflight_summary must be an object")
        return
    ready = preflight_summary.get("ready_for_live_probe") is True
    expected_status = "passed" if ready else "awaiting_evidence"
    expected_solver_outcome = "SolvedVerified" if ready else "AwaitingEvidence"
    if preflight_summary.get("receipt_id") != "durable_gmail_oauth_runtime_preflight":
        errors.append("gmail_oauth_preflight_summary.receipt_id must be durable_gmail_oauth_runtime_preflight")
    if preflight_summary.get("status") != expected_status:
        errors.append("gmail_oauth_preflight_summary.status must align with ready_for_live_probe")
    if preflight_summary.get("solver_outcome") != expected_solver_outcome:
        errors.append("gmail_oauth_preflight_summary.solver_outcome must align with ready_for_live_probe")
    _validate_common_preflight_summary(
        preflight_summary,
        "gmail_oauth_preflight_summary",
        require_external_message_field=False,
        errors=errors,
    )


def _validate_team_ops_preflight_summary(preflight_summary: Any, errors: list[str]) -> None:
    if not isinstance(preflight_summary, dict):
        errors.append("team_ops_preflight_summary must be an object")
        return
    ready = preflight_summary.get("ready_for_live_probe") is True
    expected_status = "passed" if ready else "awaiting_evidence"
    expected_solver_outcome = "SolvedVerified" if ready else "AwaitingEvidence"
    if preflight_summary.get("receipt_id") != "team_ops_shared_inbox_handoff_preflight":
        errors.append("team_ops_preflight_summary.receipt_id must be team_ops_shared_inbox_handoff_preflight")
    if preflight_summary.get("status") != expected_status:
        errors.append("team_ops_preflight_summary.status must align with ready_for_live_probe")
    if preflight_summary.get("solver_outcome") != expected_solver_outcome:
        errors.append("team_ops_preflight_summary.solver_outcome must align with ready_for_live_probe")
    if preflight_summary.get("external_message_sent") is not False:
        errors.append("team_ops_preflight_summary.external_message_sent must be false")
    _validate_common_preflight_summary(
        preflight_summary,
        "team_ops_preflight_summary",
        require_external_message_field=True,
        errors=errors,
    )


def _validate_common_preflight_summary(
    preflight_summary: dict[str, Any],
    label: str,
    *,
    require_external_message_field: bool,
    errors: list[str],
) -> None:
    ready = preflight_summary.get("ready_for_live_probe") is True
    blocker_count = preflight_summary.get("blocker_count")
    finding_rule_ids = preflight_summary.get("finding_rule_ids", [])
    if not isinstance(blocker_count, int):
        errors.append(f"{label}.blocker_count must be an integer")
    elif ready and blocker_count != 0:
        errors.append(f"ready {label} must have blocker_count=0")
    elif not ready and blocker_count <= 0:
        errors.append(f"blocked {label} must have blockers")
    if isinstance(blocker_count, int) and isinstance(finding_rule_ids, list) and blocker_count != len(finding_rule_ids):
        errors.append(f"{label}.blocker_count must match finding_rule_ids count")
    if preflight_summary.get("credential_values_disclosed") is not False:
        errors.append(f"{label}.credential_values_disclosed must be false")
    if preflight_summary.get("external_provider_mutation_performed") is not False:
        errors.append(f"{label}.external_provider_mutation_performed must be false")
    if require_external_message_field and preflight_summary.get("external_message_sent") is not False:
        errors.append(f"{label}.external_message_sent must be false")
    signal_inventory = preflight_summary.get("signal_inventory", [])
    if not isinstance(signal_inventory, list):
        errors.append(f"{label}.signal_inventory must be a list")
        return
    if any(isinstance(item, dict) and item.get("secret_value_disclosed") is not False for item in signal_inventory):
        errors.append(f"{label} signal inventory must not disclose secret values")


def _expected_status(provider_setup_authorized: bool, ready_for_live_probe: bool) -> str:
    if ready_for_live_probe:
        return "ready_for_live_probe"
    if provider_setup_authorized:
        return "ready_for_provider_setup"
    return "awaiting_operator_authority"


def _blocker_count(handoff: dict[str, Any]) -> int:
    blocked_until = handoff.get("blocked_until", ())
    return len(blocked_until) if isinstance(blocked_until, list) else 0


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps shared inbox handoff validation arguments."""

    parser = argparse.ArgumentParser(description="Validate TeamOps shared inbox operator handoff.")
    parser.add_argument("--handoff", default=str(DEFAULT_HANDOFF))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--require-blocked", action="store_true")
    parser.add_argument("--require-live-probe", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps shared inbox handoff validation."""

    args = parse_args(argv)
    validation = validate_team_ops_shared_inbox_operator_handoff(
        handoff_path=Path(args.handoff),
        schema_path=Path(args.schema),
        require_blocked=args.require_blocked,
        require_live_probe=args.require_live_probe,
    )
    write_team_ops_shared_inbox_operator_handoff_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("TeamOps shared inbox operator handoff valid")
    else:
        print(f"TeamOps shared inbox operator handoff invalid errors={list(validation.errors)}")
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
