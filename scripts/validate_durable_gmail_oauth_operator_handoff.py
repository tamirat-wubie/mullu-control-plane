#!/usr/bin/env python3
"""Validate durable Gmail OAuth operator handoff packets.

Purpose: prove the durable Gmail OAuth operator handoff is schema-valid,
redacted, and clear that recommended defaults are not observed runtime evidence.
Governance scope: OAuth provider boundary, secret redaction, live-probe
admission, and operator authority separation.
Dependencies: schemas/durable_gmail_oauth_operator_handoff.schema.json and
scripts.produce_durable_gmail_oauth_operator_handoff.
Invariants:
  - Recommended runtime defaults are not counted as observed preflight evidence.
  - Live-probe readiness requires provider authority and a passed preflight.
  - Provider and secret-store mutation flags remain false.
  - Secret-shaped values are never serialized.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_durable_gmail_oauth_runtime_preflight import (  # noqa: E402
    DURABLE_SECRET_SIGNAL_NAMES,
    NON_SECRET_CONFIG_SIGNAL_NAMES,
    WITNESS_REF_SIGNAL_NAMES,
    matched_secret_marker,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_HANDOFF = REPO_ROOT / ".change_assurance" / "durable_gmail_oauth_operator_handoff.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "durable_gmail_oauth_operator_handoff.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "durable_gmail_oauth_operator_handoff_validation.json"
RECOMMENDED_DEFAULT_NAMES = frozenset(
    {
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER",
        "EMAIL_CALENDAR_CONNECTOR_ID",
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY",
        "GMAIL_SCOPE_ID",
    }
)
REQUIRED_PROVIDER_ACTION_IDS = frozenset(
    {
        "select_google_cloud_project",
        "configure_oauth_consent_screen",
        "declare_least_privilege_gmail_scope",
        "create_oauth_client_without_secret_serialization",
        "complete_operator_consent_for_refresh_token",
        "store_runtime_secrets_by_reference",
        "record_revocation_recovery_receipt",
        "run_durable_gmail_runtime_preflight",
    }
)


@dataclass(frozen=True, slots=True)
class DurableGmailOauthOperatorHandoffValidation:
    """Validation result for one durable Gmail OAuth handoff packet."""

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


def validate_durable_gmail_oauth_operator_handoff(
    *,
    handoff_path: Path = DEFAULT_HANDOFF,
    schema_path: Path = DEFAULT_SCHEMA,
    require_blocked: bool = False,
    require_live_probe: bool = False,
) -> DurableGmailOauthOperatorHandoffValidation:
    """Validate one durable Gmail OAuth operator handoff packet."""

    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("durable Gmail OAuth operator handoff schema file missing")
    handoff = _load_json_object(handoff_path, "durable Gmail OAuth operator handoff", errors)
    if schema and handoff:
        errors.extend(_validate_schema_instance(schema, handoff))
        _validate_semantics(handoff, errors)
        if require_blocked and handoff.get("ready_for_live_probe") is True:
            errors.append("require blocked: durable Gmail OAuth handoff is ready for live probe")
        if require_live_probe and handoff.get("ready_for_live_probe") is not True:
            errors.append("require live probe: durable Gmail OAuth handoff is not ready")
    return DurableGmailOauthOperatorHandoffValidation(
        ok=not errors,
        handoff_path=_path_label(handoff_path),
        schema_path=_path_label(schema_path),
        status=str(handoff.get("status", "")) if handoff else "",
        ready_for_live_probe=handoff.get("ready_for_live_probe") is True if handoff else False,
        blocker_count=_blocker_count(handoff),
        errors=tuple(errors),
    )


def write_durable_gmail_oauth_operator_handoff_validation(
    validation: DurableGmailOauthOperatorHandoffValidation,
    output_path: Path,
) -> Path:
    """Write one durable Gmail OAuth operator handoff validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_semantics(handoff: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(handoff, sort_keys=True)
    marker = matched_secret_marker(serialized)
    if marker:
        errors.append(f"handoff must not serialize secret marker: {marker}")
    if handoff.get("external_provider_mutation_performed") is not False:
        errors.append("external_provider_mutation_performed must be false")
    if handoff.get("github_secret_mutation_performed") is not False:
        errors.append("github_secret_mutation_performed must be false")
    if handoff.get("credential_values_disclosed") is not False:
        errors.append("credential_values_disclosed must be false")
    if handoff.get("preflight_environment_basis") != "observed_environment_without_defaults":
        errors.append("preflight_environment_basis must preserve observed environment without defaults")

    ready_for_live_probe = handoff.get("ready_for_live_probe") is True
    provider_setup_authorized = handoff.get("provider_setup_authorized") is True
    preflight_summary = handoff.get("preflight_summary", {})
    preflight_ready = isinstance(preflight_summary, dict) and preflight_summary.get("ready_for_live_probe") is True
    expected_status = _expected_status(provider_setup_authorized, ready_for_live_probe)
    if handoff.get("status") != expected_status:
        errors.append(f"status must be {expected_status}")
    expected_solver_outcome = "SolvedVerified" if ready_for_live_probe else "AwaitingEvidence"
    if handoff.get("solver_outcome") != expected_solver_outcome:
        errors.append("solver_outcome must align with live-probe readiness")
    if ready_for_live_probe and not provider_setup_authorized:
        errors.append("ready_for_live_probe requires provider_setup_authorized")
    if ready_for_live_probe and not preflight_ready:
        errors.append("ready_for_live_probe requires passed preflight summary")
    if not ready_for_live_probe and not handoff.get("blocked_until"):
        errors.append("blocked handoff must list blocked_until entries")
    if ready_for_live_probe and handoff.get("blocked_until"):
        errors.append("ready handoff must not list blocked_until entries")
    if handoff.get("ready_for_provider_setup") is not (provider_setup_authorized and not ready_for_live_probe):
        errors.append("ready_for_provider_setup must equal provider authority without live-probe readiness")

    _validate_recommended_defaults(handoff, errors)
    _validate_provider_actions(handoff, errors)
    _validate_runtime_bindings(handoff, errors)
    _validate_preflight_summary(preflight_summary, errors)


def _validate_recommended_defaults(handoff: dict[str, Any], errors: list[str]) -> None:
    defaults = handoff.get("recommended_runtime_defaults", [])
    if not isinstance(defaults, list):
        errors.append("recommended_runtime_defaults must be a list")
        return
    default_names_sequence = [str(item.get("name", "")) for item in defaults if isinstance(item, dict)]
    default_names = set(default_names_sequence)
    if default_names != RECOMMENDED_DEFAULT_NAMES:
        errors.append(
            "recommended_runtime_defaults must list only durable Gmail non-secret defaults: "
            f"observed={sorted(default_names)}"
        )
    duplicate_defaults = _duplicate_values(default_names_sequence)
    if duplicate_defaults:
        errors.append(f"recommended_runtime_defaults must not duplicate names: observed={duplicate_defaults}")
    for item in defaults:
        if not isinstance(item, dict):
            continue
        if item.get("classification") != "non_secret_config":
            errors.append("recommended runtime defaults must be non_secret_config")
        if not str(item.get("recommended_value", "")).strip():
            errors.append("recommended runtime defaults must include non-empty recommended values")


def _validate_provider_actions(handoff: dict[str, Any], errors: list[str]) -> None:
    actions = handoff.get("provider_console_actions", [])
    if not isinstance(actions, list):
        errors.append("provider_console_actions must be a list")
        return
    action_id_sequence = [str(item.get("action_id", "")) for item in actions if isinstance(item, dict)]
    action_ids = set(action_id_sequence)
    if action_ids != REQUIRED_PROVIDER_ACTION_IDS:
        errors.append(f"provider action ids must match durable Gmail handoff set: observed={sorted(action_ids)}")
    duplicate_action_ids = _duplicate_values(action_id_sequence)
    if duplicate_action_ids:
        errors.append(f"provider_console_actions must not duplicate action ids: observed={duplicate_action_ids}")
    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("action_id") == "run_durable_gmail_runtime_preflight":
            if action.get("requires_explicit_operator_execution") is not False:
                errors.append("run_durable_gmail_runtime_preflight must be repository-local, not operator-executed")
            command = str(action.get("command", ""))
            if "validate_durable_gmail_oauth_runtime_preflight.py" not in command or "--require-ready" not in command:
                errors.append("run_durable_gmail_runtime_preflight command must require ready validation")
        elif action.get("requires_explicit_operator_execution") is not True:
            errors.append(f"{action.get('action_id', '')} must require explicit operator execution")


def _validate_runtime_bindings(handoff: dict[str, Any], errors: list[str]) -> None:
    bindings = handoff.get("runtime_bindings", [])
    if not isinstance(bindings, list):
        errors.append("runtime_bindings must be a list")
        return
    binding_name_sequence = [str(item.get("name", "")) for item in bindings if isinstance(item, dict)]
    binding_by_name = {str(item.get("name", "")): item for item in bindings if isinstance(item, dict)}
    required_names = set(NON_SECRET_CONFIG_SIGNAL_NAMES) | set(DURABLE_SECRET_SIGNAL_NAMES) | set(WITNESS_REF_SIGNAL_NAMES)
    observed_names = set(binding_by_name)
    missing = sorted(required_names - set(binding_by_name))
    if missing:
        errors.append(f"runtime bindings missing {missing}")
    extra = sorted(observed_names - required_names)
    if extra:
        errors.append(f"runtime bindings include unsupported names {extra}")
    duplicate_binding_names = _duplicate_values(binding_name_sequence)
    if duplicate_binding_names:
        errors.append(f"runtime_bindings must not duplicate names: observed={duplicate_binding_names}")
    for name in NON_SECRET_CONFIG_SIGNAL_NAMES:
        binding = binding_by_name.get(name, {})
        if binding and binding.get("classification") != "non_secret_config":
            errors.append(f"{name} must be classified non_secret_config")
        if binding and binding.get("store_command"):
            errors.append(f"{name} must not include a store command")
    for name in DURABLE_SECRET_SIGNAL_NAMES:
        binding = binding_by_name.get(name, {})
        if binding and binding.get("classification") != "secret":
            errors.append(f"{name} must be classified secret")
        store_command = str(binding.get("store_command", ""))
        if binding and not store_command.startswith(f"gh secret set {name} --repo "):
            errors.append(f"{name} must include a secret store command template")
        if binding and "--body" in store_command:
            errors.append(f"{name} secret store command must not inline a value")
    for name in WITNESS_REF_SIGNAL_NAMES:
        binding = binding_by_name.get(name, {})
        if binding and binding.get("classification") != "witness_ref":
            errors.append(f"{name} must be classified witness_ref")
        store_command = str(binding.get("store_command", ""))
        if binding and not store_command.startswith(f"gh variable set {name} --repo "):
            errors.append(f"{name} must include a witness ref variable command template")
        if binding and " --body <witness-ref>" not in store_command:
            errors.append(f"{name} witness ref command must use the witness-ref placeholder")


def _validate_preflight_summary(preflight_summary: Any, errors: list[str]) -> None:
    if not isinstance(preflight_summary, dict):
        errors.append("preflight_summary must be an object")
        return
    ready = preflight_summary.get("ready_for_live_probe") is True
    expected_status = "passed" if ready else "awaiting_evidence"
    expected_solver_outcome = "SolvedVerified" if ready else "AwaitingEvidence"
    if preflight_summary.get("status") != expected_status:
        errors.append("preflight_summary.status must align with ready_for_live_probe")
    if preflight_summary.get("solver_outcome") != expected_solver_outcome:
        errors.append("preflight_summary.solver_outcome must align with ready_for_live_probe")
    blocker_count = preflight_summary.get("blocker_count")
    finding_rule_ids = preflight_summary.get("finding_rule_ids", [])
    if not isinstance(blocker_count, int):
        errors.append("preflight_summary.blocker_count must be an integer")
    elif ready and blocker_count != 0:
        errors.append("ready preflight summary must have blocker_count=0")
    elif not ready and blocker_count <= 0:
        errors.append("blocked preflight summary must have blockers")
    if isinstance(blocker_count, int) and isinstance(finding_rule_ids, list) and blocker_count != len(finding_rule_ids):
        errors.append("preflight_summary.blocker_count must match finding_rule_ids count")
    if preflight_summary.get("credential_values_disclosed") is not False:
        errors.append("preflight_summary.credential_values_disclosed must be false")
    if preflight_summary.get("external_provider_mutation_performed") is not False:
        errors.append("preflight_summary.external_provider_mutation_performed must be false")
    signal_inventory = preflight_summary.get("signal_inventory", [])
    if not isinstance(signal_inventory, list):
        errors.append("preflight_summary.signal_inventory must be a list")
        return
    if any(isinstance(item, dict) and item.get("secret_value_disclosed") is not False for item in signal_inventory):
        errors.append("signal inventory must not disclose secret values")


def _expected_status(provider_setup_authorized: bool, ready_for_live_probe: bool) -> str:
    if ready_for_live_probe:
        return "ready_for_live_probe"
    if provider_setup_authorized:
        return "ready_for_provider_setup"
    return "awaiting_operator_authority"


def _duplicate_values(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


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
    """Parse durable Gmail OAuth handoff validation arguments."""

    parser = argparse.ArgumentParser(description="Validate durable Gmail OAuth operator handoff.")
    parser.add_argument("--handoff", default=str(DEFAULT_HANDOFF))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--require-blocked", action="store_true")
    parser.add_argument("--require-live-probe", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for durable Gmail OAuth handoff validation."""

    args = parse_args(argv)
    validation = validate_durable_gmail_oauth_operator_handoff(
        handoff_path=Path(args.handoff),
        schema_path=Path(args.schema),
        require_blocked=args.require_blocked,
        require_live_probe=args.require_live_probe,
    )
    write_durable_gmail_oauth_operator_handoff_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("durable Gmail OAuth operator handoff valid")
    else:
        print(f"durable Gmail OAuth operator handoff invalid errors={list(validation.errors)}")
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
