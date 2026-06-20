"""Tests for Personal Assistant skill readiness catalog validation.

Purpose: prove skill readiness catalog validation rejects schema drift, lane
drift, approval drift, execution overclaim, and secret-shaped values.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: skill readiness catalog collector, validator, and schema.
Invariants:
  - Closed catalogs require lane-bound, authority-covered skill records.
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

from scripts.collect_personal_assistant_skill_readiness_catalog import (  # noqa: E402
    collect_personal_assistant_skill_readiness_catalog,
)
from scripts.validate_personal_assistant_skill_readiness_catalog import (  # noqa: E402
    main,
    validate_personal_assistant_skill_readiness_catalog,
    write_personal_assistant_skill_readiness_catalog_validation_report,
)


FIXED_NOW = datetime(2026, 6, 20, 12, 30, tzinfo=UTC)


def _closed_catalog() -> dict[str, object]:
    return collect_personal_assistant_skill_readiness_catalog(now_utc=FIXED_NOW)


def _write_catalog(tmp_path: Path, payload: dict[str, object]) -> Path:
    catalog_path = tmp_path / "personal_assistant_skill_readiness_catalog.json"
    catalog_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return catalog_path


def test_validation_accepts_schema_valid_closed_catalog(tmp_path: Path) -> None:
    payload = _closed_catalog()
    catalog_path = _write_catalog(tmp_path, payload)

    validation = validate_personal_assistant_skill_readiness_catalog(
        catalog_path=catalog_path,
        require_closed=True,
    )

    assert validation.valid is True
    assert validation.catalog_id == payload["catalog_id"]
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.catalog_closed is True
    assert all(step.passed for step in validation.steps)


def test_validation_rejects_missing_skill_record(tmp_path: Path) -> None:
    payload = _closed_catalog()
    payload["skill_records"] = payload["skill_records"][:-1]  # type: ignore[index]
    catalog_path = _write_catalog(tmp_path, payload)

    validation = validate_personal_assistant_skill_readiness_catalog(catalog_path=catalog_path)

    assert validation.valid is False
    assert validation.catalog_closed is True
    assert any(step.name == "summary gate" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)


def test_validation_rejects_lane_drift(tmp_path: Path) -> None:
    payload = _closed_catalog()
    payload["skill_records"][0]["readiness_bound"] = False  # type: ignore[index]
    payload["skill_records"][0]["readiness_lane_state"] = "AwaitingEvidence"  # type: ignore[index]
    catalog_path = _write_catalog(tmp_path, payload)

    validation = validate_personal_assistant_skill_readiness_catalog(catalog_path=catalog_path)

    assert validation.valid is False
    assert any(step.name == "skill records" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)
    assert validation.catalog_id == payload["catalog_id"]


def test_validation_rejects_execution_overclaim(tmp_path: Path) -> None:
    payload = _closed_catalog()
    payload["skill_records"][0]["execution_enabled"] = True  # type: ignore[index]
    payload["effect_boundary"]["execution_authority_granted"] = True  # type: ignore[index]
    catalog_path = _write_catalog(tmp_path, payload)

    validation = validate_personal_assistant_skill_readiness_catalog(catalog_path=catalog_path)

    assert validation.valid is False
    assert any(step.name == "schema contract" and not step.passed for step in validation.steps)
    assert any(step.name == "skill records" and not step.passed for step in validation.steps)
    assert any(step.name == "no-effect boundary" and not step.passed for step in validation.steps)


def test_validation_rejects_p4_approval_drift(tmp_path: Path) -> None:
    payload = _closed_catalog()
    payload["skill_records"][2]["requires_approval"] = False  # type: ignore[index]
    payload["skill_records"][2]["p4_p5_approval_guarded"] = False  # type: ignore[index]
    catalog_path = _write_catalog(tmp_path, payload)

    validation = validate_personal_assistant_skill_readiness_catalog(catalog_path=catalog_path)

    assert validation.valid is False
    assert any(step.name == "skill records" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)
    assert validation.catalog_closed is True


def test_validation_rejects_secret_shaped_values(tmp_path: Path) -> None:
    payload = _closed_catalog()
    payload["lineage"]["accepted_deltas"][0]["reason"] = "client_secret marker"  # type: ignore[index]
    catalog_path = _write_catalog(tmp_path, payload)

    validation = validate_personal_assistant_skill_readiness_catalog(catalog_path=catalog_path)

    assert validation.valid is False
    assert any(step.name == "secret boundary" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)
    assert validation.catalog_closed is True


def test_validation_cli_writes_report(tmp_path: Path, capsys: object) -> None:
    payload = _closed_catalog()
    catalog_path = _write_catalog(tmp_path, payload)
    output_path = tmp_path / "validation.json"

    exit_code = main(
        [
            "--catalog",
            str(catalog_path),
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
    assert output_path.exists()
    assert validation_payload["valid"] is True
    assert printed["catalog_id"] == payload["catalog_id"]
    assert printed["catalog_closed"] is True


def test_validation_report_writer_outputs_bounded_summary(tmp_path: Path) -> None:
    payload = _closed_catalog()
    catalog_path = _write_catalog(tmp_path, payload)
    validation = validate_personal_assistant_skill_readiness_catalog(catalog_path=catalog_path)
    output_path = tmp_path / "validation.json"

    written = write_personal_assistant_skill_readiness_catalog_validation_report(validation, output_path)
    parsed = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert parsed["valid"] is True
    assert parsed["catalog_id"] == payload["catalog_id"]
    assert len(parsed["steps"]) == 8
