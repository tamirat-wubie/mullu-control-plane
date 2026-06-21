"""Tests for Personal Assistant foundation closure packet validation.

Purpose: prove the foundation closure packet validator rejects schema drift,
open closure gates, authority drift, effect drift, and secret-shaped values.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_personal_assistant_foundation_closure_packet and
the closure packet collector.
Invariants:
  - Require-closed validation needs every source receipt closed.
  - Packet IDs must bind to the packet body.
  - Source receipt kinds must keep canonical source, schema, and closure bindings.
  - Source payload closure fields must match the recorded closed source receipts.
  - Source receipt digests must match current checked-in source refs.
  - Source receipt serialized lengths must match current checked-in source payloads.
  - Authority denials must remain complete.
  - Secret-shaped values cannot be serialized into closure packets.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.validate_personal_assistant_foundation_closure_packet as closure_validator  # noqa: E402
from scripts.collect_personal_assistant_foundation_closure_packet import (  # noqa: E402
    collect_personal_assistant_foundation_closure_packet,
)
from scripts.validate_personal_assistant_foundation_closure_packet import (  # noqa: E402
    _file_sha256,
    main,
    validate_personal_assistant_foundation_closure_packet,
    write_personal_assistant_foundation_closure_validation_report,
)

FIXED_NOW = datetime(2026, 6, 18, 1, 30, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_validate_foundation_closure_packet_accepts_checked_in_shape(tmp_path: Path) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_foundation_closure_packet(
        packet_path=packet_path,
        require_closed=True,
    )

    assert validation.valid is True
    assert validation.packet_id == packet["packet_id"]
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.foundation_closure_packet_closed is True
    assert all(step.passed for step in validation.steps)
    assert packet["closure_summary"]["source_receipt_count"] == 9  # type: ignore[index]
    assert {record["source_kind"] for record in packet["source_receipts"]} >= {"skill_readiness_catalog", "dry_run_packet"}  # type: ignore[index]


def test_validate_foundation_closure_packet_rejects_open_source(tmp_path: Path) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    packet["source_receipts"][0]["closed"] = False  # type: ignore[index]
    packet["closure_summary"]["all_source_closure_flags_pass"] = False  # type: ignore[index]
    packet["closure_summary"]["foundation_closure_packet_closed"] = False  # type: ignore[index]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_foundation_closure_packet(
        packet_path=packet_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert validation.foundation_closure_packet_closed is False
    assert any(step.name == "source receipts" and not step.passed for step in validation.steps)
    assert any(step.name == "require closed" and not step.passed for step in validation.steps)


def test_validate_foundation_closure_packet_rejects_source_digest_drift(tmp_path: Path) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    packet["source_receipts"][0]["source_sha256"] = "0" * 64  # type: ignore[index]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_foundation_closure_packet(
        packet_path=packet_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert validation.foundation_closure_packet_closed is True
    assert any(step.name == "source receipt digests" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)


def test_validate_foundation_closure_packet_rejects_source_ref_escape(tmp_path: Path) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    packet["source_receipts"][0]["source_ref"] = "../outside.json"  # type: ignore[index]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_foundation_closure_packet(packet_path=packet_path)

    assert validation.valid is False
    assert any(step.name == "source receipt digests" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)
    assert validation.packet_id == packet["packet_id"]


def test_validate_foundation_closure_packet_rejects_packet_id_body_drift(tmp_path: Path) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    packet["lineage"]["accepted_deltas"][0]["reason"] = "Bound source receipts with an amended local note."  # type: ignore[index]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_foundation_closure_packet(
        packet_path=packet_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert validation.packet_id == packet["packet_id"]
    assert validation.foundation_closure_packet_closed is True
    assert any(step.name == "packet id binding" and not step.passed for step in validation.steps)
    assert any(step.name == "packet id" and step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)


def test_validate_foundation_closure_packet_rejects_canonical_source_binding_drift(tmp_path: Path) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    foundation_record = next(
        record
        for record in packet["source_receipts"]  # type: ignore[index]
        if record["source_kind"] == "foundation_evidence"
    )
    replacement_ref = "examples/personal_assistant_readiness_index_receipt.json"
    foundation_record["source_ref"] = replacement_ref
    foundation_record["schema_ref"] = "schemas/personal_assistant_readiness_index_receipt.schema.json"
    foundation_record["source_sha256"] = _file_sha256(_ROOT / replacement_ref)
    foundation_record["closure_field"] = "readiness_index_closed"
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_foundation_closure_packet(
        packet_path=packet_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert validation.foundation_closure_packet_closed is True
    assert any(step.name == "source receipt bindings" and not step.passed for step in validation.steps)
    assert any(step.name == "source receipt digests" and step.passed for step in validation.steps)
    assert any(step.name == "source receipt schemas" and step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)


def test_validate_foundation_closure_packet_rejects_source_payload_closure_drift(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    fixture_root = tmp_path / "repo"
    source_ref = "examples/personal_assistant_foundation_evidence_receipt.json"
    patched_sources = []
    for source_kind, source_path, schema_ref, closure_field in closure_validator.SOURCE_RECEIPTS:
        source_relative_ref = source_path.relative_to(_ROOT).as_posix()
        fixture_source_path = fixture_root / source_relative_ref
        fixture_schema_path = fixture_root / schema_ref
        fixture_source_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_schema_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_source_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        fixture_schema_path.write_text((_ROOT / schema_ref).read_text(encoding="utf-8"), encoding="utf-8")
        patched_sources.append((source_kind, fixture_source_path, schema_ref, closure_field))
    source_payload = json.loads((fixture_root / source_ref).read_text(encoding="utf-8"))
    source_payload["summary"]["foundation_evidence_closed"] = False
    (fixture_root / source_ref).write_text(
        json.dumps(source_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    packet["source_receipts"][0]["source_sha256"] = _file_sha256(fixture_root / source_ref)  # type: ignore[index]
    monkeypatch.setattr(closure_validator, "REPO_ROOT", fixture_root)  # type: ignore[attr-defined]
    monkeypatch.setattr(closure_validator, "SOURCE_RECEIPTS", tuple(patched_sources))  # type: ignore[attr-defined]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_foundation_closure_packet(
        packet_path=packet_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert validation.foundation_closure_packet_closed is True
    assert any(
        step.name == "source receipt source closure fields" and not step.passed
        for step in validation.steps
    )
    assert any(step.name == "source receipt bindings" and step.passed for step in validation.steps)
    assert any(step.name == "source receipt digests" and step.passed for step in validation.steps)
    assert any(step.name == "source receipt schemas" and step.passed for step in validation.steps)


def test_validate_foundation_closure_packet_rejects_source_serialized_length_drift(
    tmp_path: Path,
) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    packet["source_receipts"][0]["serialized_length"] += 1  # type: ignore[index]
    packet["packet_id"] = closure_validator._expected_packet_id(packet)  # type: ignore[attr-defined]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_foundation_closure_packet(
        packet_path=packet_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert validation.foundation_closure_packet_closed is True
    assert any(
        step.name == "source receipt serialized lengths" and not step.passed
        for step in validation.steps
    )
    assert any(step.name == "packet id binding" and step.passed for step in validation.steps)
    assert any(step.name == "source receipt digests" and step.passed for step in validation.steps)
    assert any(step.name == "source receipt schemas" and step.passed for step in validation.steps)


def test_validate_foundation_closure_packet_rejects_schema_ref_shape_drift(tmp_path: Path) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    dry_run_record = next(
        record
        for record in packet["source_receipts"]  # type: ignore[index]
        if record["source_kind"] == "dry_run_packet"
    )
    dry_run_record["schema_ref"] = "schemas/personal_assistant_receipt.schema.json"
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_foundation_closure_packet(
        packet_path=packet_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert validation.foundation_closure_packet_closed is True
    assert any(step.name == "source receipt schemas" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and not step.passed for step in validation.steps)


def test_validate_foundation_closure_packet_rejects_schema_ref_escape(tmp_path: Path) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    packet["source_receipts"][0]["schema_ref"] = "../outside.schema.json"  # type: ignore[index]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_foundation_closure_packet(packet_path=packet_path)

    assert validation.valid is False
    assert any(step.name == "source receipt schemas" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and not step.passed for step in validation.steps)
    assert validation.packet_id == packet["packet_id"]


def test_validate_foundation_closure_packet_rejects_missing_schema_ref(tmp_path: Path) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    del packet["source_receipts"][0]["schema_ref"]  # type: ignore[index]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_foundation_closure_packet(packet_path=packet_path)

    assert validation.valid is False
    assert any(step.name == "source receipt schemas" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and not step.passed for step in validation.steps)
    assert validation.packet_id == packet["packet_id"]


def test_foundation_closure_source_digest_is_line_ending_stable(tmp_path: Path) -> None:
    lf_source = tmp_path / "source-lf.json"
    crlf_source = tmp_path / "source-crlf.json"
    lf_source.write_bytes(b'{\n  "proof_state": "Pass"\n}\n')
    crlf_source.write_bytes(b'{\r\n  "proof_state": "Pass"\r\n}\r\n')

    assert _file_sha256(lf_source) == _file_sha256(crlf_source)
    assert len(_file_sha256(lf_source)) == 64
    assert len(_file_sha256(crlf_source)) == 64


def test_validate_foundation_closure_packet_rejects_missing_authority_denial(tmp_path: Path) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    packet["authority_denials"] = packet["authority_denials"][:-1]  # type: ignore[index]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_foundation_closure_packet(packet_path=packet_path)

    assert validation.valid is False
    assert any(step.name == "schema contract" and not step.passed for step in validation.steps)
    assert any(step.name == "authority denials" and not step.passed for step in validation.steps)
    assert validation.packet_id == packet["packet_id"]


def test_validate_foundation_closure_packet_rejects_no_effect_drift(tmp_path: Path) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    packet["no_effect_boundary"]["live_connector_execution_allowed"] = True  # type: ignore[index]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_foundation_closure_packet(packet_path=packet_path)

    assert validation.valid is False
    assert any(step.name == "schema contract" and not step.passed for step in validation.steps)
    assert any(step.name == "no-effect boundary" and not step.passed for step in validation.steps)
    assert validation.foundation_closure_packet_closed is True


def test_validate_foundation_closure_packet_rejects_secret_values(tmp_path: Path) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    packet["lineage"]["accepted_deltas"][0]["reason"] = "client_secret=value must not appear"  # type: ignore[index]
    packet_path = _write_json(tmp_path, "packet.json", packet)

    validation = validate_personal_assistant_foundation_closure_packet(packet_path=packet_path)

    assert validation.valid is False
    assert any(step.name == "secret value boundary" and not step.passed for step in validation.steps)
    assert any(step.name == "schema contract" and step.passed for step in validation.steps)
    assert validation.foundation_closure_packet_closed is True


def test_validate_foundation_closure_packet_cli_writes_report(tmp_path: Path, capsys: object) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
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


def test_write_foundation_closure_validation_report(tmp_path: Path) -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    packet_path = _write_json(tmp_path, "packet.json", packet)
    validation = validate_personal_assistant_foundation_closure_packet(packet_path=packet_path)
    output_path = tmp_path / "validation.json"

    written = write_personal_assistant_foundation_closure_validation_report(validation, output_path)
    parsed = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert parsed["valid"] is True
    assert parsed["packet_id"] == packet["packet_id"]
