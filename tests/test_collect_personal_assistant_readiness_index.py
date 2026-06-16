"""Tests for personal-assistant readiness index collection.

Purpose: prove readiness index collection summarizes foundation evidence
without enabling connector, deployment, customer, or memory authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.collect_personal_assistant_readiness_index and checked-in
personal-assistant evidence fixtures.
Invariants:
  - SolvedVerified requires closed foundation evidence and all lanes solved.
  - Authority drift preserves AwaitingEvidence.
  - Production-ready capability overclaims are blocked.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_personal_assistant_readiness_index import (  # noqa: E402
    DEFAULT_CAPABILITY_PACK,
    DEFAULT_CONSOLE_READ_MODEL,
    DEFAULT_FOUNDATION_EVIDENCE,
    DEFAULT_SKILL_REGISTRY,
    collect_personal_assistant_readiness_index,
    main,
)


FIXED_NOW = datetime(2026, 6, 16, 14, 0, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_readiness_index_closes_from_checked_in_evidence() -> None:
    receipt = collect_personal_assistant_readiness_index(now_utc=FIXED_NOW)
    index = receipt["readiness_index"]  # type: ignore[index]
    summary = receipt["summary"]  # type: ignore[index]
    boundary = receipt["effect_boundary"]  # type: ignore[index]

    assert receipt["proof_state"] == "Pass"
    assert receipt["solver_outcome"] == "SolvedVerified"
    assert index["lane_count"] == 12
    assert index["solved_verified_lane_count"] == 12
    assert index["production_ready_capability_count"] == 0
    assert summary["readiness_index_closed"] is True
    assert boundary["execution_allowed"] is False
    assert boundary["production_ready_claim_allowed"] is False


def test_readiness_index_preserves_awaiting_evidence_when_foundation_opens(tmp_path: Path) -> None:
    foundation = json.loads(DEFAULT_FOUNDATION_EVIDENCE.read_text(encoding="utf-8"))
    foundation["proof_state"] = "Fail"
    foundation["solver_outcome"] = "AwaitingEvidence"
    foundation["summary"]["foundation_evidence_closed"] = False
    foundation_path = _write_json(tmp_path, "foundation.json", foundation)

    receipt = collect_personal_assistant_readiness_index(
        foundation_evidence_path=foundation_path,
        console_read_model_path=DEFAULT_CONSOLE_READ_MODEL,
        skill_registry_path=DEFAULT_SKILL_REGISTRY,
        capability_pack_path=DEFAULT_CAPABILITY_PACK,
        now_utc=FIXED_NOW,
    )

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["summary"]["foundation_evidence_closed"] is False  # type: ignore[index]
    assert receipt["summary"]["readiness_index_closed"] is False  # type: ignore[index]


def test_readiness_index_blocks_lane_authority_drift(tmp_path: Path) -> None:
    console = json.loads(DEFAULT_CONSOLE_READ_MODEL.read_text(encoding="utf-8"))
    console["lane_status"]["lanes"][0]["execution_allowed"] = True
    console_path = _write_json(tmp_path, "console.json", console)

    receipt = collect_personal_assistant_readiness_index(
        foundation_evidence_path=DEFAULT_FOUNDATION_EVIDENCE,
        console_read_model_path=console_path,
        skill_registry_path=DEFAULT_SKILL_REGISTRY,
        capability_pack_path=DEFAULT_CAPABILITY_PACK,
        now_utc=FIXED_NOW,
    )

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["lane_records"][0]["no_effect_boundary_verified"] is False  # type: ignore[index]
    assert receipt["summary"]["all_lanes_solved_verified"] is True  # type: ignore[index]
    assert receipt["summary"]["no_effect_boundary_verified"] is False  # type: ignore[index]


def test_readiness_index_blocks_production_ready_capability_overclaim(tmp_path: Path) -> None:
    capability_pack = json.loads(DEFAULT_CAPABILITY_PACK.read_text(encoding="utf-8"))
    capability_pack["capabilities"][0]["metadata"]["production_ready"] = True
    capability_pack_path = _write_json(tmp_path, "capability_pack.json", capability_pack)

    receipt = collect_personal_assistant_readiness_index(
        foundation_evidence_path=DEFAULT_FOUNDATION_EVIDENCE,
        console_read_model_path=DEFAULT_CONSOLE_READ_MODEL,
        skill_registry_path=DEFAULT_SKILL_REGISTRY,
        capability_pack_path=capability_pack_path,
        now_utc=FIXED_NOW,
    )

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["readiness_index"]["production_ready_capability_count"] == 1  # type: ignore[index]
    assert receipt["effect_boundary"]["production_ready_claim_allowed"] is True  # type: ignore[index]


def test_readiness_index_cli_writes_receipt(tmp_path: Path, capsys: object) -> None:
    output_path = tmp_path / "readiness_index.json"

    exit_code = main(["--output", str(output_path), "--json"], now_utc=FIXED_NOW)
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    printed = json.loads(captured.out)

    assert exit_code == 0
    assert payload["solver_outcome"] == "SolvedVerified"
    assert printed["receipt_id"] == payload["receipt_id"]
    assert output_path.exists()
