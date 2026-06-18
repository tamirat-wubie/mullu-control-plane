"""Tests for Personal Assistant coherence ledger collection.

Purpose: prove coherence ledger collection binds foundation lanes to evidence
without enabling connector, deployment, customer, or memory authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.collect_personal_assistant_coherence_ledger and checked-in
Personal Assistant evidence fixtures.
Invariants:
  - SolvedVerified requires a closed readiness index and bound lane evidence.
  - Authority drift preserves AwaitingEvidence.
  - Missing lane evidence prevents coherence closure.
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
    DEFAULT_CAPABILITY_PACK,
    DEFAULT_CONSOLE_READ_MODEL,
    DEFAULT_READINESS_INDEX,
    DEFAULT_SKILL_REGISTRY,
    collect_personal_assistant_coherence_ledger,
    main,
)


FIXED_NOW = datetime(2026, 6, 16, 15, 0, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_coherence_ledger_closes_from_checked_in_evidence() -> None:
    receipt = collect_personal_assistant_coherence_ledger(now_utc=FIXED_NOW)
    summary = receipt["coherence_summary"]  # type: ignore[index]
    first_lane = receipt["lane_ledger_records"][0]  # type: ignore[index]
    boundary = receipt["effect_boundary"]  # type: ignore[index]

    assert receipt["proof_state"] == "Pass"
    assert receipt["solver_outcome"] == "SolvedVerified"
    assert summary["coherence_ledger_closed"] is True
    assert summary["lane_count"] == 12
    assert summary["blocked_authority_count"] == 8
    assert first_lane["source_receipt_ids"] == [receipt["source_receipts"][0]["receipt_id"]]  # type: ignore[index]
    assert first_lane["dependency_edge_count"] >= 2
    assert boundary["execution_allowed"] is False


def test_coherence_ledger_preserves_awaiting_evidence_when_readiness_opens(tmp_path: Path) -> None:
    readiness = json.loads(DEFAULT_READINESS_INDEX.read_text(encoding="utf-8"))
    readiness["proof_state"] = "Fail"
    readiness["solver_outcome"] = "AwaitingEvidence"
    readiness["summary"]["readiness_index_closed"] = False
    readiness_path = _write_json(tmp_path, "readiness.json", readiness)

    receipt = collect_personal_assistant_coherence_ledger(
        readiness_index_path=readiness_path,
        console_read_model_path=DEFAULT_CONSOLE_READ_MODEL,
        skill_registry_path=DEFAULT_SKILL_REGISTRY,
        capability_pack_path=DEFAULT_CAPABILITY_PACK,
        now_utc=FIXED_NOW,
    )

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["coherence_summary"]["readiness_index_closed"] is False  # type: ignore[index]
    assert receipt["coherence_summary"]["coherence_ledger_closed"] is False  # type: ignore[index]


def test_coherence_ledger_blocks_lane_evidence_drift(tmp_path: Path) -> None:
    console = json.loads(DEFAULT_CONSOLE_READ_MODEL.read_text(encoding="utf-8"))
    console["lane_status"]["lanes"][0]["schema_refs"] = []
    console_path = _write_json(tmp_path, "console.json", console)

    receipt = collect_personal_assistant_coherence_ledger(
        readiness_index_path=DEFAULT_READINESS_INDEX,
        console_read_model_path=console_path,
        skill_registry_path=DEFAULT_SKILL_REGISTRY,
        capability_pack_path=DEFAULT_CAPABILITY_PACK,
        now_utc=FIXED_NOW,
    )

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["lane_ledger_records"][0]["schema_refs"] == []  # type: ignore[index]
    assert receipt["coherence_summary"]["all_lanes_bound_to_sources"] is False  # type: ignore[index]
    assert receipt["coherence_summary"]["coherence_ledger_closed"] is False  # type: ignore[index]


def test_coherence_ledger_blocks_authority_drift(tmp_path: Path) -> None:
    readiness = json.loads(DEFAULT_READINESS_INDEX.read_text(encoding="utf-8"))
    readiness["authority_blocks"]["live_execution_blocked"] = False
    readiness_path = _write_json(tmp_path, "readiness.json", readiness)

    receipt = collect_personal_assistant_coherence_ledger(
        readiness_index_path=readiness_path,
        console_read_model_path=DEFAULT_CONSOLE_READ_MODEL,
        skill_registry_path=DEFAULT_SKILL_REGISTRY,
        capability_pack_path=DEFAULT_CAPABILITY_PACK,
        now_utc=FIXED_NOW,
    )

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["authority_block_records"][0]["blocked"] is False  # type: ignore[index]
    assert receipt["coherence_summary"]["blocked_authority_count"] == 7  # type: ignore[index]
    assert receipt["coherence_summary"]["all_edges_no_effect"] is False  # type: ignore[index]


def test_coherence_ledger_cli_writes_receipt(tmp_path: Path, capsys: object) -> None:
    output_path = tmp_path / "coherence_ledger.json"

    exit_code = main(["--output", str(output_path), "--json"], now_utc=FIXED_NOW)
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    printed = json.loads(captured.out)

    assert exit_code == 0
    assert payload["solver_outcome"] == "SolvedVerified"
    assert printed["receipt_id"] == payload["receipt_id"]
    assert output_path.exists()
