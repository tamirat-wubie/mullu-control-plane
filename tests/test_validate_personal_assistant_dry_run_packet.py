"""Tests for Personal Assistant dry-run packet validation.

Purpose: prove the dry-run validator rejects schema drift, dangling bindings,
ungated effect paths, authority drift, and secret-shaped values.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_personal_assistant_dry_run_packet and the
dry-run packet collector.
Invariants:
  - Require-closed validation needs a closed no-effect dry-run packet.
  - P4/P5 paths need approval gates.
  - Secret-shaped values cannot be serialized into dry-run packets.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_personal_assistant_dry_run_packet import (  # noqa: E402
    collect_personal_assistant_dry_run_packet,
)
from scripts.validate_personal_assistant_dry_run_packet import (  # noqa: E402
    main,
    validate_personal_assistant_dry_run_packet,
    write_personal_assistant_dry_run_packet_validation_report,
)

FIXED_NOW = datetime(2026, 6, 20, 9, 45, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_validate_dry_run_packet_accepts_checked_in_shape(tmp_path: Path) -> None:
    packet = collect_personal_assistant_dry_run_packet(now_utc=FIXED_NOW)
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_dry_run_packet(packet_path=packet_path, require_closed=True)

    assert validation.valid is True
    assert validation.packet_id == packet["packet_id"]
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.dry_run_packet_closed is True
    assert all(step.passed for step in validation.steps)


def test_validate_dry_run_packet_rejects_dangling_binding(tmp_path: Path) -> None:
    packet = collect_personal_assistant_dry_run_packet(now_utc=FIXED_NOW)
    packet["stages"][3]["input_bindings"].append("missing_stage.output")  # type: ignore[index]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_dry_run_packet(packet_path=packet_path)

    assert validation.valid is False
    assert validation.dry_run_packet_closed is True
    assert any(step.name == "bindings" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)


def test_validate_dry_run_packet_rejects_ungated_p4_path(tmp_path: Path) -> None:
    packet = collect_personal_assistant_dry_run_packet(now_utc=FIXED_NOW)
    stages = {stage["stage_id"]: stage for stage in packet["stages"]}  # type: ignore[index]
    stages["blocked_external_send"]["predecessor_ids"] = ["draft_preview"]
    stages["blocked_external_send"]["input_bindings"] = ["draft_preview.draft_artifact_ref"]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_dry_run_packet(packet_path=packet_path)

    assert validation.valid is False
    assert validation.dry_run_packet_closed is True
    assert any(step.name == "approval gate order" and not step.passed for step in validation.steps)
    assert validation.packet_id == packet["packet_id"]


def test_validate_dry_run_packet_rejects_no_effect_drift(tmp_path: Path) -> None:
    packet = collect_personal_assistant_dry_run_packet(now_utc=FIXED_NOW)
    packet["no_effect_boundary"]["live_connector_execution_allowed"] = True  # type: ignore[index]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_dry_run_packet(packet_path=packet_path)

    assert validation.valid is False
    assert any(step.name == "schema contract" and not step.passed for step in validation.steps)
    assert any(step.name == "no-effect boundary" and not step.passed for step in validation.steps)
    assert validation.dry_run_packet_closed is True


def test_validate_dry_run_packet_rejects_secret_values(tmp_path: Path) -> None:
    packet = collect_personal_assistant_dry_run_packet(now_utc=FIXED_NOW)
    packet["lineage"]["accepted_deltas"][0]["reason"] = "api_key=value must not appear"  # type: ignore[index]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_dry_run_packet(packet_path=packet_path)

    assert validation.valid is False
    assert any(step.name == "secret value boundary" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)
    assert validation.dry_run_packet_closed is True


def test_validate_dry_run_packet_rejects_open_closure_when_required(tmp_path: Path) -> None:
    packet = collect_personal_assistant_dry_run_packet(now_utc=FIXED_NOW)
    packet["closure_summary"]["dry_run_packet_closed"] = False  # type: ignore[index]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_dry_run_packet(packet_path=packet_path, require_closed=True)

    assert validation.valid is False
    assert validation.dry_run_packet_closed is False
    assert any(step.name == "closure gate" and not step.passed for step in validation.steps)
    assert any(step.name == "require closed" and not step.passed for step in validation.steps)


def test_validate_dry_run_packet_cli_writes_report(tmp_path: Path, capsys: object) -> None:
    packet = collect_personal_assistant_dry_run_packet(now_utc=FIXED_NOW)
    packet_path = _write_json(tmp_path, "packet.json", packet)
    output_path = tmp_path / "validation.json"

    exit_code = main(
        [
            "--packet",
            str(packet_path),
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
    assert printed["packet_id"] == packet["packet_id"]


def test_write_dry_run_validation_report(tmp_path: Path) -> None:
    packet = collect_personal_assistant_dry_run_packet(now_utc=FIXED_NOW)
    packet_path = _write_json(tmp_path, "packet.json", packet)
    validation = validate_personal_assistant_dry_run_packet(packet_path=packet_path)
    output_path = tmp_path / "validation.json"

    written = write_personal_assistant_dry_run_packet_validation_report(validation, output_path)
    parsed = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert parsed["valid"] is True
    assert parsed["packet_id"] == packet["packet_id"]
