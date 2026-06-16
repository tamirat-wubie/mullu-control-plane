"""Tests for Personal Assistant authority coverage receipt validation.

Purpose: prove the authority coverage validator rejects schema drift, approval
drift, capability overclaim, effect-boundary drift, and secret-shaped values.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_personal_assistant_authority_coverage_receipt,
scripts.collect_personal_assistant_authority_coverage, and schema fixtures.
Invariants:
  - Closed validation requires skill, risk, and capability authority coverage.
  - Effect authority remains false in Foundation Mode.
  - Secret-shaped terms are rejected even in otherwise valid JSON.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_personal_assistant_authority_coverage import (  # noqa: E402
    collect_personal_assistant_authority_coverage,
)
from scripts.validate_personal_assistant_authority_coverage_receipt import (  # noqa: E402
    main,
    validate_personal_assistant_authority_coverage_receipt,
    write_personal_assistant_authority_coverage_validation_report,
)


FIXED_NOW = datetime(2026, 6, 16, 17, 0, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_validate_authority_coverage_accepts_checked_in_shape(tmp_path: Path) -> None:
    payload = collect_personal_assistant_authority_coverage(now_utc=FIXED_NOW)
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_authority_coverage_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is True
    assert validation.receipt_id == payload["receipt_id"]
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.authority_coverage_closed is True
    assert all(step.passed for step in validation.steps)


def test_validate_authority_coverage_rejects_unclosed_summary(tmp_path: Path) -> None:
    payload = collect_personal_assistant_authority_coverage(now_utc=FIXED_NOW)
    payload["authority_summary"]["authority_coverage_closed"] = False  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_authority_coverage_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert validation.authority_coverage_closed is False
    assert any(step.name == "authority gate" and not step.passed for step in validation.steps)
    assert any(step.name == "require closed" and not step.passed for step in validation.steps)


def test_validate_authority_coverage_rejects_p4_approval_drift(tmp_path: Path) -> None:
    payload = collect_personal_assistant_authority_coverage(now_utc=FIXED_NOW)
    payload["skill_authority_records"][2]["requires_approval"] = False  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_authority_coverage_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "skill authority records" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)
    assert validation.receipt_id == payload["receipt_id"]


def test_validate_authority_coverage_rejects_capability_overclaim(tmp_path: Path) -> None:
    payload = collect_personal_assistant_authority_coverage(now_utc=FIXED_NOW)
    payload["capability_authority_records"][0]["production_ready"] = True  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_authority_coverage_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "schema contract" and not step.passed for step in validation.steps)
    assert any(step.name == "capability authority records" and not step.passed for step in validation.steps)
    assert validation.authority_coverage_closed is True


def test_validate_authority_coverage_rejects_effect_boundary_drift(tmp_path: Path) -> None:
    payload = collect_personal_assistant_authority_coverage(now_utc=FIXED_NOW)
    payload["effect_boundary"]["external_effect_allowed"] = True  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_authority_coverage_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "schema contract" and not step.passed for step in validation.steps)
    assert any(step.name == "no-effect boundary" and not step.passed for step in validation.steps)
    assert validation.receipt_id == payload["receipt_id"]


def test_validate_authority_coverage_rejects_secret_shaped_values(tmp_path: Path) -> None:
    payload = collect_personal_assistant_authority_coverage(now_utc=FIXED_NOW)
    payload["lineage"]["accepted_deltas"][0]["reason"] = "private_key must not appear"  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_authority_coverage_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "secret boundary" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)
    assert validation.authority_coverage_closed is True


def test_validate_authority_coverage_cli_writes_validation_report(tmp_path: Path, capsys: object) -> None:
    payload = collect_personal_assistant_authority_coverage(now_utc=FIXED_NOW)
    receipt_path = _write_json(tmp_path, "receipt.json", payload)
    output_path = tmp_path / "validation.json"

    exit_code = main(
        [
            "--receipt",
            str(receipt_path),
            "--output",
            str(output_path),
            "--require-closed",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    validation_payload = json.loads(output_path.read_text(encoding="utf-8"))
    printed = json.loads(captured.out)

    assert exit_code == 0
    assert validation_payload["valid"] is True
    assert printed["receipt_id"] == payload["receipt_id"]
    assert output_path.exists()


def test_write_authority_coverage_validation_report(tmp_path: Path) -> None:
    payload = collect_personal_assistant_authority_coverage(now_utc=FIXED_NOW)
    receipt_path = _write_json(tmp_path, "receipt.json", payload)
    validation = validate_personal_assistant_authority_coverage_receipt(receipt_path=receipt_path)
    output_path = tmp_path / "validation.json"

    written = write_personal_assistant_authority_coverage_validation_report(validation, output_path)
    parsed = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert parsed["valid"] is True
    assert parsed["receipt_id"] == payload["receipt_id"]
