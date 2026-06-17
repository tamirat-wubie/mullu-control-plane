"""Tests for Personal Assistant policy matrix receipt validation.

Purpose: prove the policy matrix validator rejects schema drift, unclosed
policy gates, blocked-action drift, effect-boundary drift, and secret values.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_personal_assistant_policy_matrix_receipt,
scripts.collect_personal_assistant_policy_matrix, and schema fixtures.
Invariants:
  - Closed validation requires P0-P5 policy coverage and blocked-action parity.
  - Effect authority remains false in Foundation Mode.
  - Secret values are rejected while blocked secret field names are allowed.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_personal_assistant_policy_matrix import (  # noqa: E402
    collect_personal_assistant_policy_matrix,
)
from scripts.validate_personal_assistant_policy_matrix_receipt import (  # noqa: E402
    main,
    validate_personal_assistant_policy_matrix_receipt,
    write_personal_assistant_policy_matrix_validation_report,
)


FIXED_NOW = datetime(2026, 6, 17, 12, 30, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_validate_policy_matrix_accepts_checked_in_shape(tmp_path: Path) -> None:
    payload = collect_personal_assistant_policy_matrix(now_utc=FIXED_NOW)
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_policy_matrix_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is True
    assert validation.receipt_id == payload["receipt_id"]
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.policy_matrix_closed is True
    assert all(step.passed for step in validation.steps)


def test_validate_policy_matrix_rejects_unclosed_summary(tmp_path: Path) -> None:
    payload = collect_personal_assistant_policy_matrix(now_utc=FIXED_NOW)
    payload["policy_matrix_summary"]["policy_matrix_closed"] = False  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_policy_matrix_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert validation.policy_matrix_closed is False
    assert any(step.name == "policy matrix gate" and not step.passed for step in validation.steps)
    assert any(step.name == "require closed" and not step.passed for step in validation.steps)


def test_validate_policy_matrix_rejects_blocked_action_drift(tmp_path: Path) -> None:
    payload = collect_personal_assistant_policy_matrix(now_utc=FIXED_NOW)
    payload["blocked_action_records"][0]["in_skill_policy"] = False  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_policy_matrix_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "blocked action parity" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)
    assert validation.receipt_id == payload["receipt_id"]


def test_validate_policy_matrix_rejects_effect_boundary_drift(tmp_path: Path) -> None:
    payload = collect_personal_assistant_policy_matrix(now_utc=FIXED_NOW)
    payload["effect_boundary"]["external_effect_allowed"] = True  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_policy_matrix_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "schema contract" and not step.passed for step in validation.steps)
    assert any(step.name == "no-effect boundary" and not step.passed for step in validation.steps)
    assert validation.policy_matrix_closed is True


def test_validate_policy_matrix_rejects_secret_values(tmp_path: Path) -> None:
    payload = collect_personal_assistant_policy_matrix(now_utc=FIXED_NOW)
    payload["lineage"]["accepted_deltas"][0]["reason"] = "bearer token must not appear"  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_policy_matrix_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "secret value boundary" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)
    assert validation.policy_matrix_closed is True


def test_validate_policy_matrix_cli_writes_validation_report(tmp_path: Path, capsys: object) -> None:
    payload = collect_personal_assistant_policy_matrix(now_utc=FIXED_NOW)
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


def test_write_policy_matrix_validation_report(tmp_path: Path) -> None:
    payload = collect_personal_assistant_policy_matrix(now_utc=FIXED_NOW)
    receipt_path = _write_json(tmp_path, "receipt.json", payload)
    validation = validate_personal_assistant_policy_matrix_receipt(receipt_path=receipt_path)
    output_path = tmp_path / "validation.json"

    written = write_personal_assistant_policy_matrix_validation_report(validation, output_path)
    parsed = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert parsed["valid"] is True
    assert parsed["receipt_id"] == payload["receipt_id"]
