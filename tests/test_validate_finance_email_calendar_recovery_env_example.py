"""Tests for finance email/calendar recovery env example validation.

Purpose: prove the recovery env template remains complete, redacted, and
read-only before operators use it for live receipt recovery.
Governance scope: binding-name stability, secret placeholder enforcement, and
read-only scope evidence.
Dependencies: scripts.validate_finance_email_calendar_recovery_env_example.
Invariants:
  - The checked-in template validates.
  - Concrete secret values fail closed.
  - Write-capable scope examples fail closed.
"""

from __future__ import annotations

from pathlib import Path

from scripts.validate_finance_email_calendar_recovery_env_example import (
    main,
    validate_finance_email_calendar_recovery_env_example,
)


def test_finance_recovery_env_example_accepts_checked_in_template() -> None:
    result = validate_finance_email_calendar_recovery_env_example()

    assert result.valid is True
    assert result.errors == ()
    assert result.binding_count == 11


def test_finance_recovery_env_example_rejects_concrete_secret(tmp_path: Path) -> None:
    template_path = _write_template(tmp_path)
    content = template_path.read_text(encoding="utf-8")
    template_path.write_text(
        content.replace(
            "EMAIL_CALENDAR_CONNECTOR_TOKEN=<secret-from-secret-manager>",
            "EMAIL_CALENDAR_CONNECTOR_TOKEN=concrete-token-value",
        ),
        encoding="utf-8",
    )

    result = validate_finance_email_calendar_recovery_env_example(template_path=template_path)

    assert result.valid is False
    assert "EMAIL_CALENDAR_CONNECTOR_TOKEN must be empty or <secret-from-secret-manager>" in result.errors


def test_finance_recovery_env_example_rejects_write_scope(tmp_path: Path) -> None:
    template_path = _write_template(tmp_path)
    content = template_path.read_text(encoding="utf-8")
    template_path.write_text(
        content.replace("GOOGLE_CALENDAR_SCOPE_ID=calendar.events.readonly", "GOOGLE_CALENDAR_SCOPE_ID=calendar.events"),
        encoding="utf-8",
    )

    result = validate_finance_email_calendar_recovery_env_example(template_path=template_path)

    assert result.valid is False
    assert "GOOGLE_CALENDAR_SCOPE_ID must not contain write-capable hints" in result.errors


def test_finance_recovery_env_example_cli_outputs_json(capsys) -> None:
    exit_code = main(["--json", "--strict"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert '"valid": true' in captured.out
    assert '"binding_count": 11' in captured.out


def _write_template(tmp_path: Path) -> Path:
    source = Path("examples/finance_email_calendar_recovery.env.example")
    template_path = tmp_path / "finance_email_calendar_recovery.env.example"
    template_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return template_path
