#!/usr/bin/env python3
"""Validate the finance email/calendar recovery env example.

Purpose: keep the redacted operator template complete, name-stable, and free
of concrete secret values.
Governance scope: finance email/calendar recovery bindings, read-only scope
evidence, and secret serialization prevention.
Dependencies: examples/finance_email_calendar_recovery.env.example.
Invariants:
  - Required worker, token, connector, and scope names are present.
  - Secret-like bindings use placeholders or remain empty.
  - Scope examples are read-only and do not carry write-capable hints.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = REPO_ROOT / "examples" / "finance_email_calendar_recovery.env.example"
REQUIRED_BINDINGS = (
    "MULLU_EMAIL_CALENDAR_WORKER_URL",
    "MULLU_EMAIL_CALENDAR_WORKER_SECRET",
    "EMAIL_CALENDAR_CONNECTOR_TOKEN",
    "EMAIL_CALENDAR_CONNECTOR_ID",
    "EMAIL_CALENDAR_CONNECTOR_SCOPE_ID",
    "GMAIL_ACCESS_TOKEN",
    "GMAIL_SCOPE_ID",
    "GOOGLE_CALENDAR_ACCESS_TOKEN",
    "GOOGLE_CALENDAR_SCOPE_ID",
    "MICROSOFT_GRAPH_ACCESS_TOKEN",
    "MICROSOFT_GRAPH_SCOPE_ID",
)
SECRET_BINDINGS = (
    "MULLU_EMAIL_CALENDAR_WORKER_SECRET",
    "EMAIL_CALENDAR_CONNECTOR_TOKEN",
    "GMAIL_ACCESS_TOKEN",
    "GOOGLE_CALENDAR_ACCESS_TOKEN",
    "MICROSOFT_GRAPH_ACCESS_TOKEN",
)
SCOPE_BINDINGS = (
    "EMAIL_CALENDAR_CONNECTOR_SCOPE_ID",
    "GMAIL_SCOPE_ID",
    "GOOGLE_CALENDAR_SCOPE_ID",
    "MICROSOFT_GRAPH_SCOPE_ID",
)
READ_ONLY_SCOPE_HINTS = ("read", "readonly", "metadata", "calendar.events.readonly", "gmail.readonly")
WRITE_SCOPE_HINTS = ("write", "send", "modify", "compose", "insert", "delete")
SECRET_PLACEHOLDER = "<secret-from-secret-manager>"


@dataclass(frozen=True, slots=True)
class FinanceEmailCalendarRecoveryEnvExampleValidation:
    """Validation result for the recovery env example."""

    valid: bool
    template_path: str
    binding_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_finance_email_calendar_recovery_env_example(
    *,
    template_path: Path = DEFAULT_TEMPLATE,
) -> FinanceEmailCalendarRecoveryEnvExampleValidation:
    """Validate the redacted finance recovery env example."""
    errors: list[str] = []
    bindings = _load_env_bindings(template_path, errors)
    if bindings:
        _validate_required_bindings(bindings, errors)
        _validate_secret_placeholders(bindings, errors)
        _validate_read_only_scopes(bindings, errors)
    return FinanceEmailCalendarRecoveryEnvExampleValidation(
        valid=not errors,
        template_path=str(template_path),
        binding_count=len(bindings),
        errors=tuple(errors),
    )


def _load_env_bindings(path: Path, errors: list[str]) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        errors.append("finance email/calendar recovery env example could not be read")
        return {}
    bindings: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            errors.append("env example contains non-assignment line")
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        if not name:
            errors.append("env example contains empty binding name")
            continue
        if name in bindings:
            errors.append(f"duplicate binding name {name}")
        bindings[name] = value.strip()
    return bindings


def _validate_required_bindings(bindings: dict[str, str], errors: list[str]) -> None:
    missing = [name for name in REQUIRED_BINDINGS if name not in bindings]
    if missing:
        errors.append(f"missing required bindings {missing}")


def _validate_secret_placeholders(bindings: dict[str, str], errors: list[str]) -> None:
    for name in SECRET_BINDINGS:
        value = bindings.get(name, "")
        if value and value != SECRET_PLACEHOLDER:
            errors.append(f"{name} must be empty or {SECRET_PLACEHOLDER}")


def _validate_read_only_scopes(bindings: dict[str, str], errors: list[str]) -> None:
    for name in SCOPE_BINDINGS:
        value = bindings.get(name, "").lower()
        if not value:
            continue
        if _scope_has_write_hint(value):
            errors.append(f"{name} must not contain write-capable hints")
            continue
        if not any(hint in value for hint in READ_ONLY_SCOPE_HINTS):
            errors.append(f"{name} must include a read-only hint")


def _scope_has_write_hint(scope: str) -> bool:
    if "calendar.events" in scope and "calendar.events.readonly" not in scope:
        return True
    return any(hint in scope for hint in WRITE_SCOPE_HINTS)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate finance email/calendar recovery env example.")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = validate_finance_email_calendar_recovery_env_example(template_path=Path(args.template))
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print("finance email/calendar recovery env example valid")
    else:
        print(f"finance email/calendar recovery env example invalid errors={list(result.errors)}")
    return 0 if result.valid or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
