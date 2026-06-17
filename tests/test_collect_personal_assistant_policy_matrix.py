"""Tests for Personal Assistant policy matrix collection.

Purpose: prove policy matrix collection binds approval matrix, skill policy,
capsule policy refs, authority coverage, and capsule alignment without
granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.collect_personal_assistant_policy_matrix and checked-in
Personal Assistant Foundation Mode fixtures.
Invariants:
  - SolvedVerified requires P4/P5 approval semantics to remain closed.
  - Blocked action drift keeps the receipt AwaitingEvidence.
  - Connector payload policy must block secret values and raw private payloads.
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
    DEFAULT_APPROVAL_MATRIX,
    DEFAULT_AUTHORITY_COVERAGE,
    DEFAULT_CAPSULE,
    DEFAULT_CAPSULE_ALIGNMENT,
    DEFAULT_SKILL_POLICY,
    collect_personal_assistant_policy_matrix,
    main,
)


FIXED_NOW = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_policy_matrix_closes_from_checked_in_evidence() -> None:
    receipt = collect_personal_assistant_policy_matrix(now_utc=FIXED_NOW)
    summary = receipt["policy_matrix_summary"]  # type: ignore[index]
    p5_record = [record for record in receipt["risk_level_records"] if record["level"] == "P5"][0]  # type: ignore[index]
    connector_policy = receipt["connector_payload_policy"]  # type: ignore[index]

    assert receipt["proof_state"] == "Pass"
    assert receipt["solver_outcome"] == "SolvedVerified"
    assert summary["policy_matrix_closed"] is True
    assert summary["p4_p5_require_explicit_approval"] is True
    assert p5_record["p5_blocked"] is True
    assert connector_policy["policy_closed"] is True


def test_policy_matrix_blocks_missing_p4_approval(tmp_path: Path) -> None:
    approval_matrix = json.loads(DEFAULT_APPROVAL_MATRIX.read_text(encoding="utf-8"))
    for risk_level in approval_matrix["risk_levels"]:
        if risk_level["level"] == "P4":
            risk_level["explicit_approval_required"] = False
    approval_matrix_path = _write_json(tmp_path, "approval_matrix.json", approval_matrix)

    receipt = collect_personal_assistant_policy_matrix(
        skill_policy_path=DEFAULT_SKILL_POLICY,
        approval_matrix_path=approval_matrix_path,
        capsule_path=DEFAULT_CAPSULE,
        authority_coverage_path=DEFAULT_AUTHORITY_COVERAGE,
        capsule_alignment_path=DEFAULT_CAPSULE_ALIGNMENT,
        now_utc=FIXED_NOW,
    )

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["policy_matrix_summary"]["p4_p5_require_explicit_approval"] is False  # type: ignore[index]
    assert receipt["policy_matrix_summary"]["policy_matrix_closed"] is False  # type: ignore[index]


def test_policy_matrix_blocks_action_set_drift(tmp_path: Path) -> None:
    skill_policy = json.loads(DEFAULT_SKILL_POLICY.read_text(encoding="utf-8"))
    skill_policy["default_blocked_actions"].remove("send")
    skill_policy_path = _write_json(tmp_path, "skill_policy.json", skill_policy)

    receipt = collect_personal_assistant_policy_matrix(
        skill_policy_path=skill_policy_path,
        approval_matrix_path=DEFAULT_APPROVAL_MATRIX,
        capsule_path=DEFAULT_CAPSULE,
        authority_coverage_path=DEFAULT_AUTHORITY_COVERAGE,
        capsule_alignment_path=DEFAULT_CAPSULE_ALIGNMENT,
        now_utc=FIXED_NOW,
    )
    send_record = [record for record in receipt["blocked_action_records"] if record["action"] == "send"][0]  # type: ignore[index]

    assert receipt["proof_state"] == "Fail"
    assert send_record["in_approval_matrix"] is True
    assert send_record["in_skill_policy"] is False
    assert receipt["policy_matrix_summary"]["blocked_actions_match_policy"] is False  # type: ignore[index]


def test_policy_matrix_blocks_connector_payload_policy_drift(tmp_path: Path) -> None:
    skill_policy = json.loads(DEFAULT_SKILL_POLICY.read_text(encoding="utf-8"))
    skill_policy["connector_payload_policy"]["blocked"].remove("raw_message_body")
    skill_policy_path = _write_json(tmp_path, "skill_policy.json", skill_policy)

    receipt = collect_personal_assistant_policy_matrix(
        skill_policy_path=skill_policy_path,
        approval_matrix_path=DEFAULT_APPROVAL_MATRIX,
        capsule_path=DEFAULT_CAPSULE,
        authority_coverage_path=DEFAULT_AUTHORITY_COVERAGE,
        capsule_alignment_path=DEFAULT_CAPSULE_ALIGNMENT,
        now_utc=FIXED_NOW,
    )

    assert receipt["proof_state"] == "Fail"
    assert receipt["connector_payload_policy"]["raw_private_payloads_blocked"] is False  # type: ignore[index]
    assert receipt["connector_payload_policy"]["policy_closed"] is False  # type: ignore[index]
    assert receipt["policy_matrix_summary"]["connector_payload_policy_closed"] is False  # type: ignore[index]


def test_policy_matrix_cli_writes_receipt(tmp_path: Path, capsys: object) -> None:
    output_path = tmp_path / "policy_matrix.json"

    exit_code = main(["--output", str(output_path), "--json"], now_utc=FIXED_NOW)
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    printed = json.loads(captured.out)

    assert exit_code == 0
    assert payload["solver_outcome"] == "SolvedVerified"
    assert printed["receipt_id"] == payload["receipt_id"]
    assert payload["policy_matrix_summary"]["policy_matrix_closed"] is True
    assert output_path.exists()
