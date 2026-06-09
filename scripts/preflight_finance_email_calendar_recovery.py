#!/usr/bin/env python3
"""Preflight finance email/calendar live receipt recovery actions.

Purpose: map redacted recovery actions from the failed finance email/calendar
live receipt to concrete, read-only environment and worker reachability checks.
Governance scope: finance live handoff recovery, secret redaction, connector
scope review, and worker reachability evidence.
Dependencies: .change_assurance/email_calendar_live_receipt.json and operator
environment bindings.
Invariants:
  - Secret values are never serialized.
  - Recovery actions remain bounded to the live receipt contract vocabulary.
  - Worker probing is read-only reachability evidence, not a connector action.
  - A missing recovery action is reported without weakening live readiness.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.produce_capability_adapter_live_receipts import DEFAULT_EMAIL_CALENDAR_RECEIPT  # noqa: E402
from scripts.proxy_policy import ProxyEnvironmentBlocked, assert_proxy_environment_allowed  # noqa: E402

EnvReader = Callable[[str], str | None]
WorkerProbe = Callable[[str], bool]

ACCEPTED_TOKEN_ENV_NAMES = (
    "EMAIL_CALENDAR_CONNECTOR_TOKEN",
    "GMAIL_ACCESS_TOKEN",
    "GOOGLE_CALENDAR_ACCESS_TOKEN",
    "MICROSOFT_GRAPH_ACCESS_TOKEN",
)
READ_ONLY_SCOPE_HINTS = ("read", "readonly", "metadata", "calendar.events.readonly", "gmail.readonly")
WRITE_SCOPE_HINTS = ("write", "send", "modify", "compose", "insert", "delete")
RECOVERY_ACTIONS = (
    "verify_email_calendar_worker_reachable",
    "verify_connector_token_present",
    "verify_connector_scope_read_only",
    "rerun_email_calendar_live_receipt_probe",
)


@dataclass(frozen=True, slots=True)
class RecoveryActionCheck:
    """One bounded recovery-action preflight check."""

    action: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FinanceEmailCalendarRecoveryPreflight:
    """Read-only preflight result for finance email/calendar recovery."""

    ok: bool
    ready_to_rerun_probe: bool
    checked_at: str
    receipt_path: str
    receipt_status: str
    failure_class: str
    checks: tuple[RecoveryActionCheck, ...]
    blockers: tuple[str, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "ready_to_rerun_probe": self.ready_to_rerun_probe,
            "checked_at": self.checked_at,
            "receipt_path": self.receipt_path,
            "receipt_status": self.receipt_status,
            "failure_class": self.failure_class,
            "checks": [check.as_dict() for check in self.checks],
            "blockers": list(self.blockers),
            "errors": list(self.errors),
        }


def preflight_finance_email_calendar_recovery(
    *,
    receipt_path: Path = DEFAULT_EMAIL_CALENDAR_RECEIPT,
    env_reader: EnvReader | None = None,
    worker_probe: WorkerProbe | None = None,
    probe_worker: bool = False,
    clock: Callable[[], str] | None = None,
) -> FinanceEmailCalendarRecoveryPreflight:
    """Evaluate recovery actions without exposing secrets or executing connector work."""
    errors: list[str] = []
    receipt = _load_json_object(receipt_path, errors)
    resolved_env_reader = env_reader or os.environ.get
    checks = tuple(
        _check_recovery_action(
            action,
            env_reader=resolved_env_reader,
            worker_probe=worker_probe,
            probe_worker=probe_worker,
        )
        for action in _recovery_actions(receipt)
    )
    blockers = tuple(check.action for check in checks if not check.passed)
    ready_to_rerun_probe = (
        not errors
        and bool(checks)
        and all(check.passed for check in checks if check.action != "rerun_email_calendar_live_receipt_probe")
    )
    return FinanceEmailCalendarRecoveryPreflight(
        ok=not errors,
        ready_to_rerun_probe=ready_to_rerun_probe,
        checked_at=(clock or _validation_clock)(),
        receipt_path=_path_label(receipt_path),
        receipt_status=str(receipt.get("status", "")),
        failure_class=str(receipt.get("failure_class", "")),
        checks=checks,
        blockers=blockers,
        errors=tuple(errors),
    )


def _check_recovery_action(
    action: str,
    *,
    env_reader: EnvReader,
    worker_probe: WorkerProbe | None,
    probe_worker: bool,
) -> RecoveryActionCheck:
    if action == "verify_email_calendar_worker_reachable":
        return _check_worker_reachable(env_reader, worker_probe=worker_probe, probe_worker=probe_worker)
    if action == "verify_connector_token_present":
        return _check_connector_token_present(env_reader)
    if action == "verify_connector_scope_read_only":
        return _check_connector_scope_read_only(env_reader)
    if action == "rerun_email_calendar_live_receipt_probe":
        return RecoveryActionCheck(action, True, "rerun command is available after prerequisite recovery checks pass")
    return RecoveryActionCheck(action, False, "unknown recovery action")


def _check_worker_reachable(
    env_reader: EnvReader,
    *,
    worker_probe: WorkerProbe | None,
    probe_worker: bool,
) -> RecoveryActionCheck:
    endpoint_present = _env_present(env_reader, "MULLU_EMAIL_CALENDAR_WORKER_URL")
    secret_present = _env_present(env_reader, "MULLU_EMAIL_CALENDAR_WORKER_SECRET")
    if not endpoint_present or not secret_present:
        return RecoveryActionCheck(
            "verify_email_calendar_worker_reachable",
            False,
            "worker endpoint and signing secret must both be present",
        )
    if not probe_worker:
        return RecoveryActionCheck(
            "verify_email_calendar_worker_reachable",
            True,
            "worker endpoint and signing secret are present; network probe skipped",
        )
    endpoint = str(env_reader("MULLU_EMAIL_CALENDAR_WORKER_URL") or "").strip()
    probe = worker_probe or _default_worker_probe
    if probe(endpoint):
        return RecoveryActionCheck(
            "verify_email_calendar_worker_reachable",
            True,
            "worker endpoint responded to reachability probe",
        )
    return RecoveryActionCheck(
        "verify_email_calendar_worker_reachable",
        False,
        "worker endpoint did not respond to reachability probe",
    )


def _check_connector_token_present(env_reader: EnvReader) -> RecoveryActionCheck:
    present_count = sum(1 for name in ACCEPTED_TOKEN_ENV_NAMES if _env_present(env_reader, name))
    return RecoveryActionCheck(
        "verify_connector_token_present",
        present_count > 0,
        f"present accepted token bindings={present_count}",
    )


def _check_connector_scope_read_only(env_reader: EnvReader) -> RecoveryActionCheck:
    scope_env_names = (
        "EMAIL_CALENDAR_CONNECTOR_SCOPE_ID",
        "GMAIL_SCOPE_ID",
        "GOOGLE_CALENDAR_SCOPE_ID",
        "MICROSOFT_GRAPH_SCOPE_ID",
    )
    scope_values = tuple(
        str(env_reader(name) or "").strip().lower()
        for name in scope_env_names
        if _env_present(env_reader, name)
    )
    if not any(_env_present(env_reader, name) for name in ACCEPTED_TOKEN_ENV_NAMES):
        return RecoveryActionCheck(
            "verify_connector_scope_read_only",
            False,
            "connector token must be present before scope can be reviewed",
        )
    if not scope_values:
        return RecoveryActionCheck("verify_connector_scope_read_only", False, "connector scope identifier is missing")
    if any(_scope_has_write_hint(scope) for scope in scope_values):
        return RecoveryActionCheck(
            "verify_connector_scope_read_only",
            False,
            "connector scope identifier contains write-capable hint",
        )
    passed = any(any(hint in scope for hint in READ_ONLY_SCOPE_HINTS) for scope in scope_values)
    detail = "connector scope identifier is read-only" if passed else "connector scope identifier lacks read-only hint"
    return RecoveryActionCheck("verify_connector_scope_read_only", passed, detail)


def _recovery_actions(receipt: dict[str, Any]) -> tuple[str, ...]:
    actions = receipt.get("recovery_actions")
    if isinstance(actions, list) and actions:
        ordered: list[str] = []
        for action in actions:
            action_text = str(action).strip()
            if action_text and action_text not in ordered:
                ordered.append(action_text)
        for required_action in RECOVERY_ACTIONS:
            if required_action not in ordered:
                ordered.append(required_action)
        return tuple(ordered)
    return RECOVERY_ACTIONS


def _scope_has_write_hint(scope: str) -> bool:
    if "calendar.events" in scope and "calendar.events.readonly" not in scope:
        return True
    return any(hint in scope for hint in WRITE_SCOPE_HINTS)


def _load_json_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append("finance email/calendar live receipt could not be read")
        return {}
    except json.JSONDecodeError:
        errors.append("finance email/calendar live receipt must be JSON")
        return {}
    if not isinstance(parsed, dict):
        errors.append("finance email/calendar live receipt root must be an object")
        return {}
    return parsed


def _path_label(path: Path) -> str:
    """Return a preflight report path label without host-local ancestry."""
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _env_present(env_reader: EnvReader, name: str) -> bool:
    return bool(str(env_reader(name) or "").strip())


def _default_worker_probe(endpoint: str) -> bool:
    request = urllib.request.Request(endpoint, method="GET")
    try:
        assert_proxy_environment_allowed()
        with urllib.request.urlopen(request, timeout=5.0) as response:
            response.read(1)
        return True
    except urllib.error.HTTPError:
        return True
    except (OSError, urllib.error.URLError, ValueError, ProxyEnvironmentBlocked):
        return False


def _validation_clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance email/calendar recovery preflight arguments."""
    parser = argparse.ArgumentParser(description="Preflight finance email/calendar recovery actions.")
    parser.add_argument("--receipt", default=str(DEFAULT_EMAIL_CALENDAR_RECEIPT))
    parser.add_argument("--probe-worker", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance email/calendar recovery preflight."""
    args = parse_args(argv)
    result = preflight_finance_email_calendar_recovery(
        receipt_path=Path(args.receipt),
        probe_worker=args.probe_worker,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.ready_to_rerun_probe:
        print("finance email/calendar recovery preflight ready to rerun probe")
    else:
        print(f"finance email/calendar recovery preflight blocked actions={list(result.blockers)}")
    return 0 if (result.ok and (result.ready_to_rerun_probe or not args.strict)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
