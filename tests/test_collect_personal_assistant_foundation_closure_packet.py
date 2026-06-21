"""Tests for Personal Assistant foundation closure packet collection.

Purpose: prove the closure packet binds the checked-in Foundation Mode receipt
chain without granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.collect_personal_assistant_foundation_closure_packet and
checked-in Personal Assistant receipt fixtures.
Invariants:
  - Closed packets require all source receipts to be closed and non-authoritative.
  - Effect-boundary drift prevents closure.
  - Collection writes digest-only source records, not raw private payloads.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_personal_assistant_foundation_closure_packet import (  # noqa: E402
    SOURCE_RECEIPTS,
    collect_personal_assistant_foundation_closure_packet,
    main,
)

FIXED_NOW = datetime(2026, 6, 18, 1, 0, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _copy_source_receipts(tmp_path: Path) -> list[tuple[str, Path, str, str]]:
    copied: list[tuple[str, Path, str, str]] = []
    for source_kind, source_path, schema_ref, closure_field in SOURCE_RECEIPTS:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        copied.append((source_kind, _write_json(tmp_path, f"{source_kind}.json", payload), schema_ref, closure_field))
    return copied


def test_foundation_closure_packet_closes_from_checked_in_receipts() -> None:
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=FIXED_NOW)
    summary = packet["closure_summary"]  # type: ignore[index]
    source_receipts = packet["source_receipts"]  # type: ignore[index]

    assert packet["proof_state"] == "Pass"
    assert packet["solver_outcome"] == "SolvedVerified"
    assert summary["foundation_closure_packet_closed"] is True
    assert summary["source_receipt_count"] == 9
    assert all(record["closed"] is True for record in source_receipts)
    assert {record["source_kind"] for record in source_receipts} >= {"skill_readiness_catalog", "dry_run_packet"}


def test_foundation_closure_packet_opens_when_source_receipt_is_open(tmp_path: Path) -> None:
    sources = _copy_source_receipts(tmp_path)
    readiness_path = next(path for kind, path, _schema_ref, _field in sources if kind == "readiness_index")
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    readiness["summary"]["readiness_index_closed"] = False
    readiness["proof_state"] = "Fail"
    readiness["solver_outcome"] = "AwaitingEvidence"
    _write_json(tmp_path, "readiness_index.json", readiness)

    packet = collect_personal_assistant_foundation_closure_packet(
        receipt_sources=tuple(sources),
        now_utc=FIXED_NOW,
    )
    readiness_record = [record for record in packet["source_receipts"] if record["source_kind"] == "readiness_index"][0]  # type: ignore[index]

    assert packet["proof_state"] == "Fail"
    assert packet["solver_outcome"] == "AwaitingEvidence"
    assert readiness_record["closed"] is False
    assert packet["closure_summary"]["foundation_closure_packet_closed"] is False  # type: ignore[index]


def test_foundation_closure_packet_blocks_effect_boundary_drift(tmp_path: Path) -> None:
    sources = _copy_source_receipts(tmp_path)
    runtime_path = next(path for kind, path, _schema_ref, _field in sources if kind == "runtime_boundary")
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["effect_boundary"]["memory_write_allowed"] = True
    _write_json(tmp_path, "runtime_boundary.json", runtime)

    packet = collect_personal_assistant_foundation_closure_packet(
        receipt_sources=tuple(sources),
        now_utc=FIXED_NOW,
    )
    runtime_record = [record for record in packet["source_receipts"] if record["source_kind"] == "runtime_boundary"][0]  # type: ignore[index]

    assert packet["proof_state"] == "Fail"
    assert runtime_record["effect_violation_count"] == 1
    assert runtime_record["effect_violations"] == ["memory_write_allowed"]
    assert packet["closure_summary"]["all_no_effect_boundaries_clear"] is False  # type: ignore[index]


def test_foundation_closure_packet_cli_writes_packet(tmp_path: Path, capsys: object) -> None:
    output_path = tmp_path / "foundation_closure_packet.json"

    exit_code = main(["--output", str(output_path), "--json"], now_utc=FIXED_NOW)
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    printed = json.loads(captured.out)

    assert exit_code == 0
    assert output_path.exists()
    assert payload["solver_outcome"] == "SolvedVerified"
    assert printed["packet_id"] == payload["packet_id"]
    assert payload["closure_summary"]["foundation_closure_packet_closed"] is True
