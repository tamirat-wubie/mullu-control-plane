#!/usr/bin/env python3
"""Validate durable Gmail OAuth runtime preflight signals.

Purpose: decide whether the Gmail connector runtime has enough credential,
scope, and witness signals to proceed to a governed live probe.
Governance scope: OAuth scope minimization, credential presence-only reporting,
secret redaction, witness gating, adapter compatibility, and no external effect
unless the operator explicitly requests GitHub secret-name inventory.
Dependencies: gateway.email_calendar_connector_adapters,
docs/64_durable_gmail_connector_runtime_plan.md, Google Gmail API scope rules,
and optional GitHub CLI secret-name inventory.
Invariants:
  - Secret values are never returned, printed, persisted, or compared by value.
  - Missing provider, refresh, revocation, or scope evidence remains
    AwaitingEvidence.
  - The current adapter's query-based Gmail search path is not treated as
    compatible with gmail.metadata.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]

SUPPORTED_GMAIL_ADAPTER_MODES = frozenset({"http", "google", "production"})
GMAIL_CONNECTOR_IDS = frozenset({"", "gmail"})
ACCESS_TOKEN_SIGNAL_NAMES = (
    "EMAIL_CALENDAR_CONNECTOR_TOKEN",
    "GMAIL_ACCESS_TOKEN",
)
DURABLE_SECRET_SIGNAL_NAMES = (
    "GMAIL_OAUTH_CLIENT_ID",
    "GMAIL_OAUTH_CLIENT_SECRET",
    "GMAIL_REFRESH_TOKEN",
)
WITNESS_REF_SIGNAL_NAMES = (
    "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF",
    "MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF",
    "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF",
    "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF",
    "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF",
)
NON_SECRET_CONFIG_SIGNAL_NAMES = (
    "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER",
    "EMAIL_CALENDAR_CONNECTOR_ID",
    "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY",
    "GMAIL_SCOPE_ID",
    "EMAIL_CALENDAR_CONNECTOR_SCOPE_ID",
)

GMAIL_FULL_MAIL_SCOPE = "https://mail.google.com/"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_METADATA_SCOPE = "https://www.googleapis.com/auth/gmail.metadata"
GMAIL_MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"

SCOPE_ALIASES = {
    "https://mail.google.com/": GMAIL_FULL_MAIL_SCOPE,
    "mail.google.com": GMAIL_FULL_MAIL_SCOPE,
    "gmail.full": GMAIL_FULL_MAIL_SCOPE,
    "oauth:gmail.full": GMAIL_FULL_MAIL_SCOPE,
    "https://www.googleapis.com/auth/gmail.readonly": GMAIL_READONLY_SCOPE,
    "gmail.readonly": GMAIL_READONLY_SCOPE,
    "oauth:gmail.readonly": GMAIL_READONLY_SCOPE,
    "https://www.googleapis.com/auth/gmail.compose": GMAIL_COMPOSE_SCOPE,
    "gmail.compose": GMAIL_COMPOSE_SCOPE,
    "oauth:gmail.compose": GMAIL_COMPOSE_SCOPE,
    "https://www.googleapis.com/auth/gmail.send": GMAIL_SEND_SCOPE,
    "gmail.send": GMAIL_SEND_SCOPE,
    "oauth:gmail.send": GMAIL_SEND_SCOPE,
    "https://www.googleapis.com/auth/gmail.metadata": GMAIL_METADATA_SCOPE,
    "gmail.metadata": GMAIL_METADATA_SCOPE,
    "oauth:gmail.metadata": GMAIL_METADATA_SCOPE,
    "https://www.googleapis.com/auth/gmail.modify": GMAIL_MODIFY_SCOPE,
    "gmail.modify": GMAIL_MODIFY_SCOPE,
    "oauth:gmail.modify": GMAIL_MODIFY_SCOPE,
}
SCOPE_SENSITIVITY = {
    GMAIL_FULL_MAIL_SCOPE: "restricted",
    GMAIL_READONLY_SCOPE: "restricted",
    GMAIL_COMPOSE_SCOPE: "restricted",
    GMAIL_METADATA_SCOPE: "restricted",
    GMAIL_MODIFY_SCOPE: "restricted",
    GMAIL_SEND_SCOPE: "sensitive",
}
SENSITIVITY_ORDER = {"none": 0, "sensitive": 1, "restricted": 2}
OPERATION_FAMILY_MINIMUM_SCOPES = {
    "read_only_search": frozenset({GMAIL_READONLY_SCOPE}),
    "read_only_message": frozenset({GMAIL_READONLY_SCOPE}),
    "draft_create": frozenset({GMAIL_COMPOSE_SCOPE}),
    "send_with_approval": frozenset({GMAIL_SEND_SCOPE}),
    "read_and_draft": frozenset({GMAIL_READONLY_SCOPE, GMAIL_COMPOSE_SCOPE}),
    "read_and_send_with_approval": frozenset({GMAIL_READONLY_SCOPE, GMAIL_SEND_SCOPE}),
}
SECRET_VALUE_MARKERS = (
    "ya29.",
    "refresh_token=",
    "client_secret=",
    "-----BEGIN PRIVATE KEY-----",
)


@dataclass(frozen=True, slots=True)
class RuntimePreflightFinding:
    """One deterministic Gmail OAuth runtime preflight finding."""

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


def build_preflight_report(
    environment: Mapping[str, str] | None = None,
    *,
    github_secret_names: set[str] | None = None,
) -> dict[str, Any]:
    """Build a redacted durable Gmail OAuth runtime preflight receipt."""

    env = dict(os.environ if environment is None else environment)
    secret_names = set(github_secret_names or set())
    findings = validate_preflight_signals(env, github_secret_names=secret_names)
    blocker_count = sum(1 for finding in findings if finding.severity == "blocker")
    scope_analysis = analyze_scope(env)
    signal_inventory = build_signal_inventory(env, github_secret_names=secret_names)
    ready = blocker_count == 0
    return {
        "receipt_id": "durable_gmail_oauth_runtime_preflight",
        "status": "passed" if ready else "awaiting_evidence",
        "solver_outcome": "SolvedVerified" if ready else "AwaitingEvidence",
        "ready_for_live_probe": ready,
        "production_ready_claimed": False,
        "credential_values_disclosed": False,
        "secret_value_markers_present": False,
        "external_provider_mutation_performed": False,
        "adapter_mode": _redacted_known_env_value(
            env,
            "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER",
            allowed_values=SUPPORTED_GMAIL_ADAPTER_MODES,
            default_value="missing",
        ),
        "connector_id": _redacted_known_env_value(
            env,
            "EMAIL_CALENDAR_CONNECTOR_ID",
            allowed_values=GMAIL_CONNECTOR_IDS,
            default_value="gmail",
        )
        or "gmail",
        "operation_family": _redacted_known_env_value(
            env,
            "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY",
            allowed_values=frozenset(OPERATION_FAMILY_MINIMUM_SCOPES),
            default_value="missing",
        ),
        "scope_analysis": scope_analysis,
        "signal_inventory": signal_inventory,
        "blocker_count": blocker_count,
        "finding_count": len(findings),
        "findings": [finding.to_dict() for finding in findings],
    }


def validate_preflight_signals(
    environment: Mapping[str, str],
    *,
    github_secret_names: set[str] | None = None,
) -> list[RuntimePreflightFinding]:
    """Return blocker/info findings for durable Gmail runtime preflight state."""

    secret_names = set(github_secret_names or set())
    findings: list[RuntimePreflightFinding] = []
    findings.extend(_validate_adapter_boundary(environment))
    findings.extend(_validate_durable_secret_presence(environment, secret_names))
    findings.extend(_validate_witness_presence(environment, secret_names))
    findings.extend(_validate_scope_boundary(environment))
    findings.extend(_validate_access_token_only_boundary(environment, secret_names))
    findings.extend(_validate_no_secret_marker_leakage(environment))
    return findings


def analyze_scope(environment: Mapping[str, str]) -> dict[str, Any]:
    """Return redacted Gmail OAuth scope analysis for the configured family."""

    scopes = _canonical_scope_set(environment)
    operation_family = environment.get("MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY", "").strip()
    expected = OPERATION_FAMILY_MINIMUM_SCOPES.get(operation_family, frozenset())
    observed_sensitivity = "none"
    for scope in scopes:
        sensitivity = SCOPE_SENSITIVITY.get(scope, "none")
        if SENSITIVITY_ORDER[sensitivity] > SENSITIVITY_ORDER[observed_sensitivity]:
            observed_sensitivity = sensitivity
    return {
        "scope_env_present": bool(_scope_raw_value(environment)),
        "recognized_scopes": sorted(scopes),
        "recognized_scope_count": len(scopes),
        "unknown_scope_count": _unknown_scope_count(environment),
        "scope_sensitivity": observed_sensitivity,
        "minimum_required_scopes": sorted(expected),
        "least_privilege_satisfied": bool(expected) and scopes == expected,
        "metadata_scope_search_compatible": not (
            operation_family == "read_only_search" and GMAIL_METADATA_SCOPE in scopes
        ),
    }


def build_signal_inventory(
    environment: Mapping[str, str],
    *,
    github_secret_names: set[str] | None = None,
) -> list[dict[str, object]]:
    """Return presence-only signal inventory without secret values."""

    secret_names = set(github_secret_names or set())
    inventory: list[dict[str, object]] = []
    for name in (
        *NON_SECRET_CONFIG_SIGNAL_NAMES,
        *ACCESS_TOKEN_SIGNAL_NAMES,
        *DURABLE_SECRET_SIGNAL_NAMES,
        *WITNESS_REF_SIGNAL_NAMES,
    ):
        inventory.append(
            {
                "name": name,
                "env_present": _has_env_value(environment, name),
                "github_secret_present": name in secret_names,
                "secret_value_disclosed": False,
            }
        )
    return inventory


def load_env_file(path: Path) -> dict[str, str]:
    """Load a simple dotenv-style file without variable expansion."""

    if not path.exists():
        raise FileNotFoundError(f"missing env file: {_path_label(path)}")
    if not path.is_file():
        raise IsADirectoryError(f"env path is not a file: {_path_label(path)}")
    parsed: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"env line {line_number} must use KEY=VALUE form")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError(f"env line {line_number} has invalid variable name")
        parsed[key] = _strip_optional_quotes(value.strip())
    return parsed


def collect_github_secret_names(repo: str) -> set[str]:
    """Collect GitHub Actions secret names with gh without exposing values."""

    repo_value = repo.strip()
    if not repo_value:
        raise ValueError("GitHub repository must be non-empty")
    completed = subprocess.run(
        ["gh", "secret", "list", "--repo", repo_value],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        reason = _safe_cli_error(completed.stderr or completed.stdout or "gh secret list failed")
        raise RuntimeError(f"GitHub secret inventory unavailable: {reason}")
    return parse_github_secret_list(completed.stdout)


def parse_github_secret_list(output: str) -> set[str]:
    """Parse `gh secret list` table output into secret names only."""

    names: set[str] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.upper().startswith("NAME"):
            continue
        name = line.split()[0]
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            names.add(name)
    return names


def _validate_adapter_boundary(environment: Mapping[str, str]) -> list[RuntimePreflightFinding]:
    findings: list[RuntimePreflightFinding] = []
    adapter_mode = environment.get("MULLU_EMAIL_CALENDAR_WORKER_ADAPTER", "").strip().lower()
    connector_id = environment.get("EMAIL_CALENDAR_CONNECTOR_ID", "gmail").strip().lower()
    operation_family = environment.get("MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY", "").strip()
    if not adapter_mode:
        findings.append(
            RuntimePreflightFinding(
                "gmail_oauth_adapter_mode_missing",
                "blocker",
                "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER must select http, google, or production before durable Gmail probing.",
            )
        )
    elif adapter_mode not in SUPPORTED_GMAIL_ADAPTER_MODES:
        findings.append(
            RuntimePreflightFinding(
                "gmail_oauth_adapter_mode_unsupported",
                "blocker",
                "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER is not a supported durable Gmail adapter mode.",
            )
        )
    if connector_id not in GMAIL_CONNECTOR_IDS:
        findings.append(
            RuntimePreflightFinding(
                "gmail_oauth_connector_id_not_gmail",
                "blocker",
                "EMAIL_CALENDAR_CONNECTOR_ID must be gmail for the durable Gmail preflight.",
            )
        )
    if operation_family not in OPERATION_FAMILY_MINIMUM_SCOPES:
        findings.append(
            RuntimePreflightFinding(
                "gmail_oauth_operation_family_missing_or_unsupported",
                "blocker",
                "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY must declare a supported Gmail operation family.",
            )
        )
    return findings


def _validate_durable_secret_presence(
    environment: Mapping[str, str],
    github_secret_names: set[str],
) -> list[RuntimePreflightFinding]:
    findings: list[RuntimePreflightFinding] = []
    for name in DURABLE_SECRET_SIGNAL_NAMES:
        if not _has_signal(environment, github_secret_names, name):
            findings.append(
                RuntimePreflightFinding(
                    "gmail_oauth_durable_secret_missing",
                    "blocker",
                    f"{name} presence is required for durable OAuth runtime preflight.",
                )
            )
    return findings


def _validate_witness_presence(
    environment: Mapping[str, str],
    github_secret_names: set[str],
) -> list[RuntimePreflightFinding]:
    findings: list[RuntimePreflightFinding] = []
    for name in WITNESS_REF_SIGNAL_NAMES:
        if not _has_signal(environment, github_secret_names, name):
            findings.append(
                RuntimePreflightFinding(
                    "gmail_oauth_witness_ref_missing",
                    "blocker",
                    f"{name} is required before durable Gmail runtime can leave AwaitingEvidence.",
                )
            )
    return findings


def _validate_scope_boundary(environment: Mapping[str, str]) -> list[RuntimePreflightFinding]:
    findings: list[RuntimePreflightFinding] = []
    scope_raw = _scope_raw_value(environment)
    operation_family = environment.get("MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY", "").strip()
    expected = OPERATION_FAMILY_MINIMUM_SCOPES.get(operation_family)
    scopes = _canonical_scope_set(environment)
    if not scope_raw:
        return [
            RuntimePreflightFinding(
                "gmail_oauth_scope_missing",
                "blocker",
                "GMAIL_SCOPE_ID or EMAIL_CALENDAR_CONNECTOR_SCOPE_ID must declare the selected Gmail OAuth scope.",
            )
        ]
    if _unknown_scope_count(environment):
        findings.append(
            RuntimePreflightFinding(
                "gmail_oauth_scope_unrecognized",
                "blocker",
                "Configured Gmail OAuth scope contains an unrecognized token; value is redacted.",
            )
        )
    if GMAIL_FULL_MAIL_SCOPE in scopes:
        findings.append(
            RuntimePreflightFinding(
                "gmail_oauth_full_mail_scope_prohibited",
                "blocker",
                "Full mail scope is wider than the supported durable Gmail operation families.",
            )
        )
    if operation_family == "read_only_search" and GMAIL_METADATA_SCOPE in scopes:
        findings.append(
            RuntimePreflightFinding(
                "gmail_oauth_metadata_scope_incompatible_with_search",
                "blocker",
                "Current Gmail search uses the q parameter, which is incompatible with gmail.metadata.",
            )
        )
    if expected and scopes != expected:
        findings.append(
            RuntimePreflightFinding(
                "gmail_oauth_scope_not_least_privilege",
                "blocker",
                "Configured Gmail OAuth scope set does not exactly match the minimum set for the declared operation family.",
            )
        )
    return findings


def _validate_access_token_only_boundary(
    environment: Mapping[str, str],
    github_secret_names: set[str],
) -> list[RuntimePreflightFinding]:
    has_access_token = any(_has_signal(environment, github_secret_names, name) for name in ACCESS_TOKEN_SIGNAL_NAMES)
    has_durable_secret = any(_has_signal(environment, github_secret_names, name) for name in DURABLE_SECRET_SIGNAL_NAMES)
    if has_access_token and not has_durable_secret:
        return [
            RuntimePreflightFinding(
                "gmail_oauth_access_token_only",
                "info",
                "Access-token evidence may support a bounded probe but does not prove durable OAuth refresh lifecycle readiness.",
            )
        ]
    return []


def _validate_no_secret_marker_leakage(environment: Mapping[str, str]) -> list[RuntimePreflightFinding]:
    report_shape = {
        "scope_analysis": analyze_scope(environment),
        "signal_inventory": build_signal_inventory(environment),
    }
    serialized_report_shape = json.dumps(report_shape, sort_keys=True)
    leaked_markers = [marker for marker in SECRET_VALUE_MARKERS if marker in serialized_report_shape]
    if leaked_markers:
        return [
            RuntimePreflightFinding(
                "gmail_oauth_secret_marker_leaked",
                "blocker",
                "Preflight report attempted to serialize a prohibited secret marker.",
            )
        ]
    return []


def _canonical_scope_set(environment: Mapping[str, str]) -> set[str]:
    scopes: set[str] = set()
    for token in _scope_tokens(environment):
        canonical = SCOPE_ALIASES.get(token.lower())
        if canonical:
            scopes.add(canonical)
    return scopes


def _unknown_scope_count(environment: Mapping[str, str]) -> int:
    return sum(1 for token in _scope_tokens(environment) if token.lower() not in SCOPE_ALIASES)


def _scope_raw_value(environment: Mapping[str, str]) -> str:
    return (
        environment.get("GMAIL_SCOPE_ID", "").strip()
        or environment.get("EMAIL_CALENDAR_CONNECTOR_SCOPE_ID", "").strip()
    )


def _scope_tokens(environment: Mapping[str, str]) -> list[str]:
    value = _scope_raw_value(environment)
    if not value:
        return []
    return [token for token in re.split(r"[\s,]+", value.strip()) if token]


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
    raw = str(environment.get(name, "")).strip().lower()
    if not raw:
        return default_value
    return raw if raw in allowed_values else "unrecognized_redacted"


def _strip_optional_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _safe_cli_error(message: str) -> str:
    first_line = next((line.strip() for line in message.splitlines() if line.strip()), "unknown error")
    for marker in SECRET_VALUE_MARKERS:
        first_line = first_line.replace(marker, "<redacted-secret-marker>")
    return first_line[:240]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the durable Gmail OAuth runtime preflight."""

    parser = argparse.ArgumentParser(description="Validate durable Gmail OAuth runtime preflight signals.")
    parser.add_argument("--env-file", type=Path, help="optional dotenv-style file to overlay onto process env")
    parser.add_argument("--github-repo", help="optional repo for gh secret-name inventory, e.g. owner/repo")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable preflight receipt")
    parser.add_argument("--require-ready", action="store_true", help="return non-zero unless ready_for_live_probe is true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        environment = dict(os.environ)
        if args.env_file:
            environment.update(load_env_file(args.env_file))
        github_secret_names = collect_github_secret_names(args.github_repo) if args.github_repo else set()
        report = build_preflight_report(environment, github_secret_names=github_secret_names)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        report = {
            "receipt_id": "durable_gmail_oauth_runtime_preflight",
            "status": "failed",
            "solver_outcome": "GovernanceBlocked",
            "ready_for_live_probe": False,
            "production_ready_claimed": False,
            "credential_values_disclosed": False,
            "external_provider_mutation_performed": False,
            "blocker_count": 1,
            "finding_count": 1,
            "findings": [
                RuntimePreflightFinding(
                    "gmail_oauth_preflight_load_failed",
                    "blocker",
                    _safe_cli_error(str(exc)),
                ).to_dict()
            ],
        }

    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        for finding in report["findings"]:
            prefix = "BLOCKER" if finding["severity"] == "blocker" else "INFO"
            sys.stdout.write(f"[{prefix}] {finding['rule_id']}: {finding['message']}\n")
        sys.stdout.write(f"STATUS: {report['status']}\n")

    if args.require_ready and not report["ready_for_live_probe"]:
        return 1
    return 0 if report["status"] != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
