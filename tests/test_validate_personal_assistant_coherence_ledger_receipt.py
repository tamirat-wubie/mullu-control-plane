"""Tests for Personal Assistant coherence ledger receipt validation.

Purpose: prove the coherence ledger validator rejects schema drift, authority
drift, evidence drift, and secret-shaped serialized values.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_personal_assistant_coherence_ledger_receipt,
scripts.collect_personal_assistant_coherence_ledger, and schema fixtures.
Invariants:
  - Closed validation requires bound lane evidence and blocked authorities.
  - Production and customer-readiness claims remain false.
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

from scripts.collect_personal_assistant_coherence_ledger import (  # noqa: E402
    collect_personal_assistant_coherence_ledger,
)
from scripts.validate_personal_assistant_coherence_ledger_receipt import (  # noqa: E402
    main,
    validate_personal_assistant_coherence_ledger_receipt,
    write_personal_assistant_coherence_ledger_validation_report,
)


FIXED_NOW = datetime(2026, 6, 16, 15, 30, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_validate_coherence_ledger_accepts_checked_in_shape(tmp_path: Path) -> None:
    payload = collect_personal_assistant_coherence_ledger(now_utc=FIXED_NOW)
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_coherence_ledger_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is True
    assert validation.receipt_id == payload["receipt_id"]
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.coherence_ledger_closed is True
    assert all(step.passed for step in validation.steps)


def test_validate_coherence_ledger_rejects_unclosed_summary(tmp_path: Path) -> None:
    payload = collect_personal_assistant_coherence_ledger(now_utc=FIXED_NOW)
    payload["coherence_summary"]["coherence_ledger_closed"] = False  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_coherence_ledger_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert validation.coherence_ledger_closed is False
    assert any(step.name == "coherence gate" and not step.passed for step in validation.steps)
    assert any(step.name == "require closed" and not step.passed for step in validation.steps)


def test_validate_coherence_ledger_rejects_missing_lane_evidence(tmp_path: Path) -> None:
    payload = collect_personal_assistant_coherence_ledger(now_utc=FIXED_NOW)
    payload["lane_ledger_records"][0]["validator_refs"] = []  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_coherence_ledger_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "schema contract" and not step.passed for step in validation.steps)
    assert any(step.name == "lane ledger records" and not step.passed for step in validation.steps)
    assert validation.receipt_id == payload["receipt_id"]


def test_validate_coherence_ledger_rejects_unblocked_authority(tmp_path: Path) -> None:
    payload = collect_personal_assistant_coherence_ledger(now_utc=FIXED_NOW)
    payload["authority_block_records"][0]["blocked"] = False  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_coherence_ledger_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "schema contract" and not step.passed for step in validation.steps)
    assert any(step.name == "authority blocks" and not step.passed for step in validation.steps)
    assert any(step.name == "coherence counts" and not step.passed for step in validation.steps)


def test_validate_coherence_ledger_rejects_secret_shaped_values(tmp_path: Path) -> None:
    payload = collect_personal_assistant_coherence_ledger(now_utc=FIXED_NOW)
    payload["lineage"]["accepted_deltas"][0]["reason"] = "client_secret must not appear"  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_coherence_ledger_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "secret boundary" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)
    assert validation.coherence_ledger_closed is True


def test_validate_coherence_ledger_cli_writes_validation_report(tmp_path: Path, capsys: object) -> None:
    payload = collect_personal_assistant_coherence_ledger(now_utc=FIXED_NOW)
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


def test_write_coherence_ledger_validation_report(tmp_path: Path) -> None:
    payload = collect_personal_assistant_coherence_ledger(now_utc=FIXED_NOW)
    receipt_path = _write_json(tmp_path, "receipt.json", payload)
    validation = validate_personal_assistant_coherence_ledger_receipt(receipt_path=receipt_path)
    output_path = tmp_path / "validation.json"

    written = write_personal_assistant_coherence_ledger_validation_report(validation, output_path)
    parsed = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert parsed["valid"] is True
    assert parsed["receipt_id"] == payload["receipt_id"]
