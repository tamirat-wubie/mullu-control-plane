"""Tests for Personal Assistant authority coverage collection.

Purpose: prove authority coverage collection binds skills, risk levels,
approval policy, and capability fixtures without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.collect_personal_assistant_authority_coverage and
checked-in Personal Assistant foundation fixtures.
Invariants:
  - SolvedVerified requires P0-P5 coverage and non-executable skills.
  - P4/P5 approval drift keeps the receipt AwaitingEvidence.
  - Capability production overclaim keeps the receipt AwaitingEvidence.
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
    DEFAULT_APPROVAL_MATRIX,
    DEFAULT_CAPABILITY_PACK,
    DEFAULT_COHERENCE_LEDGER,
    DEFAULT_SKILL_POLICY,
    DEFAULT_SKILL_REGISTRY,
    collect_personal_assistant_authority_coverage,
    main,
)


FIXED_NOW = datetime(2026, 6, 16, 16, 30, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_authority_coverage_closes_from_checked_in_evidence() -> None:
    receipt = collect_personal_assistant_authority_coverage(now_utc=FIXED_NOW)
    summary = receipt["authority_summary"]  # type: ignore[index]
    first_skill = receipt["skill_authority_records"][0]  # type: ignore[index]
    first_capability = receipt["capability_authority_records"][0]  # type: ignore[index]

    assert receipt["proof_state"] == "Pass"
    assert receipt["solver_outcome"] == "SolvedVerified"
    assert summary["authority_coverage_closed"] is True
    assert summary["risk_level_count"] == 6
    assert summary["p4_p5_actions_require_explicit_approval"] is True
    assert first_skill["authority_covered"] is True
    assert first_capability["secret_scope"] == "none"


def test_authority_coverage_blocks_p4_approval_drift(tmp_path: Path) -> None:
    registry = json.loads(DEFAULT_SKILL_REGISTRY.read_text(encoding="utf-8"))
    registry["skills"][2]["requires_approval"] = False
    registry_path = _write_json(tmp_path, "skill_registry.json", registry)

    receipt = collect_personal_assistant_authority_coverage(
        skill_registry_path=registry_path,
        approval_matrix_path=DEFAULT_APPROVAL_MATRIX,
        skill_policy_path=DEFAULT_SKILL_POLICY,
        capability_pack_path=DEFAULT_CAPABILITY_PACK,
        coherence_ledger_path=DEFAULT_COHERENCE_LEDGER,
        now_utc=FIXED_NOW,
    )

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["skill_authority_records"][2]["requires_approval"] is False  # type: ignore[index]
    assert receipt["skill_authority_records"][2]["authority_covered"] is False  # type: ignore[index]
    assert receipt["authority_summary"]["p4_p5_actions_require_explicit_approval"] is False  # type: ignore[index]


def test_authority_coverage_blocks_capability_production_overclaim(tmp_path: Path) -> None:
    capability_pack = json.loads(DEFAULT_CAPABILITY_PACK.read_text(encoding="utf-8"))
    capability_pack["capabilities"][0]["metadata"]["production_ready"] = True
    capability_pack_path = _write_json(tmp_path, "capability_pack.json", capability_pack)

    receipt = collect_personal_assistant_authority_coverage(
        skill_registry_path=DEFAULT_SKILL_REGISTRY,
        approval_matrix_path=DEFAULT_APPROVAL_MATRIX,
        skill_policy_path=DEFAULT_SKILL_POLICY,
        capability_pack_path=capability_pack_path,
        coherence_ledger_path=DEFAULT_COHERENCE_LEDGER,
        now_utc=FIXED_NOW,
    )

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["capability_authority_records"][0]["production_ready"] is True  # type: ignore[index]
    assert receipt["capability_authority_records"][0]["authority_covered"] is False  # type: ignore[index]
    assert receipt["authority_summary"]["authority_coverage_closed"] is False  # type: ignore[index]


def test_authority_coverage_blocks_missing_risk_level(tmp_path: Path) -> None:
    approval_matrix = json.loads(DEFAULT_APPROVAL_MATRIX.read_text(encoding="utf-8"))
    approval_matrix["risk_levels"] = [
        record for record in approval_matrix["risk_levels"] if record["level"] != "P5"
    ]
    approval_matrix_path = _write_json(tmp_path, "approval_matrix.json", approval_matrix)

    receipt = collect_personal_assistant_authority_coverage(
        skill_registry_path=DEFAULT_SKILL_REGISTRY,
        approval_matrix_path=approval_matrix_path,
        skill_policy_path=DEFAULT_SKILL_POLICY,
        capability_pack_path=DEFAULT_CAPABILITY_PACK,
        coherence_ledger_path=DEFAULT_COHERENCE_LEDGER,
        now_utc=FIXED_NOW,
    )

    p5_record = [record for record in receipt["risk_level_records"] if record["level"] == "P5"][0]  # type: ignore[index]

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert p5_record["matrix_bound"] is False
    assert receipt["authority_summary"]["approval_matrix_levels_bound"] is False  # type: ignore[index]
    assert receipt["authority_summary"]["authority_coverage_closed"] is False  # type: ignore[index]


def test_authority_coverage_cli_writes_receipt(tmp_path: Path, capsys: object) -> None:
    output_path = tmp_path / "authority_coverage.json"

    exit_code = main(["--output", str(output_path), "--json"], now_utc=FIXED_NOW)
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    printed = json.loads(captured.out)

    assert exit_code == 0
    assert payload["solver_outcome"] == "SolvedVerified"
    assert printed["receipt_id"] == payload["receipt_id"]
    assert payload["authority_summary"]["authority_coverage_closed"] is True
    assert output_path.exists()
