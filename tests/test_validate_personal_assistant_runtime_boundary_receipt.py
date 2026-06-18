"""Tests for Personal Assistant runtime boundary receipt validation.

Purpose: prove the runtime boundary validator rejects schema drift, unclosed
runtime gates, module authority drift, effect-boundary drift, and secret values.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_personal_assistant_runtime_boundary_receipt,
scripts.collect_personal_assistant_runtime_boundary, and schema fixtures.
Invariants:
  - Closed validation requires runtime modules and capabilities to be non-mutating.
  - Effect authority remains false in Foundation Mode.
  - Secret values are rejected while hash-only source evidence is allowed.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_personal_assistant_runtime_boundary import (  # noqa: E402
    collect_personal_assistant_runtime_boundary,
)
from scripts.validate_personal_assistant_runtime_boundary_receipt import (  # noqa: E402
    main,
    validate_personal_assistant_runtime_boundary_receipt,
    write_personal_assistant_runtime_boundary_validation_report,
)


FIXED_NOW = datetime(2026, 6, 17, 13, 30, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_validate_runtime_boundary_accepts_checked_in_shape(tmp_path: Path) -> None:
    payload = collect_personal_assistant_runtime_boundary(now_utc=FIXED_NOW)
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_runtime_boundary_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is True
    assert validation.receipt_id == payload["receipt_id"]
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.runtime_boundary_closed is True
    assert all(step.passed for step in validation.steps)


def test_validate_runtime_boundary_rejects_unclosed_summary(tmp_path: Path) -> None:
    payload = collect_personal_assistant_runtime_boundary(now_utc=FIXED_NOW)
    payload["runtime_boundary_summary"]["runtime_boundary_closed"] = False  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_runtime_boundary_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert validation.runtime_boundary_closed is False
    assert any(step.name == "runtime boundary gate" and not step.passed for step in validation.steps)
    assert any(step.name == "require closed" and not step.passed for step in validation.steps)


def test_validate_runtime_boundary_rejects_module_authority_drift(tmp_path: Path) -> None:
    payload = collect_personal_assistant_runtime_boundary(now_utc=FIXED_NOW)
    payload["module_records"][0]["forbidden_import_count"] = 1  # type: ignore[index]
    payload["module_records"][0]["forbidden_imports"] = ["requests"]  # type: ignore[index]
    payload["module_records"][0]["module_boundary_closed"] = False  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_runtime_boundary_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "module records" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)
    assert validation.receipt_id == payload["receipt_id"]


def test_validate_runtime_boundary_rejects_effect_boundary_drift(tmp_path: Path) -> None:
    payload = collect_personal_assistant_runtime_boundary(now_utc=FIXED_NOW)
    payload["effect_boundary"]["live_connector_execution_allowed"] = True  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_runtime_boundary_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "schema contract" and not step.passed for step in validation.steps)
    assert any(step.name == "no-effect boundary" and not step.passed for step in validation.steps)
    assert validation.runtime_boundary_closed is True


def test_validate_runtime_boundary_rejects_secret_values(tmp_path: Path) -> None:
    payload = collect_personal_assistant_runtime_boundary(now_utc=FIXED_NOW)
    payload["lineage"]["accepted_deltas"][0]["reason"] = "client_secret=value must not appear"  # type: ignore[index]
    receipt_path = _write_json(tmp_path, "receipt.json", payload)

    validation = validate_personal_assistant_runtime_boundary_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "secret value boundary" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)
    assert validation.runtime_boundary_closed is True


def test_validate_runtime_boundary_cli_writes_validation_report(tmp_path: Path, capsys: object) -> None:
    payload = collect_personal_assistant_runtime_boundary(now_utc=FIXED_NOW)
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


def test_write_runtime_boundary_validation_report(tmp_path: Path) -> None:
    payload = collect_personal_assistant_runtime_boundary(now_utc=FIXED_NOW)
    receipt_path = _write_json(tmp_path, "receipt.json", payload)
    validation = validate_personal_assistant_runtime_boundary_receipt(receipt_path=receipt_path)
    output_path = tmp_path / "validation.json"

    written = write_personal_assistant_runtime_boundary_validation_report(validation, output_path)
    parsed = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert parsed["valid"] is True
    assert parsed["receipt_id"] == payload["receipt_id"]
