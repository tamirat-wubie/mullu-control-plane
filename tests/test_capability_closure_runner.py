"""Tests for capability debt closure runner.

Purpose: prove ranked capability debt becomes one read-only closure lane with
explicit missing refs and approval proof steps.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: mcoi/capability_closure/runner.py and capability debt report
projection fixtures.
Invariants: the runner emits planning artifacts only, keeps live execution
disabled, and does not grant repository, connector, PR, or merge authority.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parent.parent
_MCOI_ROOT = _ROOT / "mcoi"
for import_root in (_ROOT, _MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from capability_closure.runner import (  # noqa: E402
    ARTIFACT_FILENAMES,
    CapabilityClosureRunnerError,
    build_capability_closure_artifacts,
    write_capability_closure_artifacts,
)
from scripts.run_capability_debt_closure import main as run_main  # noqa: E402


def test_capability_closure_runner_selects_email_approval_lane() -> None:
    artifacts = build_capability_closure_artifacts()
    plan = artifacts["capability_closure_plan"]
    missing_refs = artifacts["missing_evidence_refs"]
    next_approval = artifacts["next_approval_action"]
    receipt = artifacts["closure_receipt"]

    assert plan["selected_capability_id"] == "email.send.with_approval"
    assert plan["selected_category"] == "approval"
    assert plan["closure_lane"]["current_gate"] == "gate.approval.required"
    assert plan["live_execution_enabled"] is False
    assert missing_refs["approval_refs"] == plan["selected_debt_item"]["missing_refs"]
    assert "approval_decision_receipt" in next_approval["required_approval_receipts"]
    assert next_approval["execution_after_approval_allowed"] is False
    assert receipt["status"] == "AwaitingEvidence"
    assert receipt["closure_claim"] == "not_closed"
    assert all(value is False for value in receipt["effect_boundary"].values())


def test_capability_closure_runner_falls_back_to_ranked_debt() -> None:
    report = {
        "debt_report_id": "capability_debt_report.test",
        "source_refs": {"passport_set_id": "test.passports"},
        "debt_rows": [
            _row(
                capability_id="demo.low",
                category="live_action",
                severity="low",
                refs=["live_action_authority"],
            ),
            _row(
                capability_id="demo.critical",
                category="promotion",
                severity="critical",
                refs=["active_capability_certification"],
            ),
        ],
    }

    artifacts = build_capability_closure_artifacts(
        debt_report=report,
        preferred_capability_ids=(),
    )
    plan = artifacts["capability_closure_plan"]
    refs = artifacts["missing_evidence_refs"]

    assert plan["selected_capability_id"] == "demo.critical"
    assert plan["selected_category"] == "promotion"
    assert plan["selection_policy"]["selection_reason"] == "highest_ranked_debt_item"
    assert plan["closure_lane"]["missing_ref_count"] == 1
    assert refs["selected_missing_refs"] == ["active_capability_certification"]
    assert refs["missing_refs_by_category"]["promotion"] == ["active_capability_certification"]


def test_capability_closure_runner_writes_all_requested_artifacts(tmp_path: Path) -> None:
    artifacts = build_capability_closure_artifacts()

    written_paths = write_capability_closure_artifacts(artifacts, tmp_path)
    payloads = {
        key: json.loads(path.read_text(encoding="utf-8"))
        for key, path in written_paths.items()
    }

    assert set(written_paths) == set(ARTIFACT_FILENAMES)
    assert {path.name for path in written_paths.values()} == set(ARTIFACT_FILENAMES.values())
    assert payloads["capability_closure_plan"]["selected_capability_id"] == "email.send.with_approval"
    assert payloads["missing_evidence_refs"]["selected_missing_ref_count"] == 6
    assert payloads["next_approval_action"]["operator_review_required"] is True
    assert payloads["closure_receipt"]["artifacts"] == ARTIFACT_FILENAMES


def test_capability_closure_runner_cli_emits_json_paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_main(["--output-dir", str(tmp_path), "--json"])
    captured = capsys.readouterr()
    output_paths = json.loads(captured.out)

    assert exit_code == 0
    assert sorted(output_paths) == sorted(ARTIFACT_FILENAMES)
    assert all(Path(path).exists() for path in output_paths.values())
    assert all(Path(path).parent == tmp_path for path in output_paths.values())
    assert "capability_closure_plan" in output_paths


def test_capability_closure_runner_rejects_empty_debt_rows() -> None:
    with pytest.raises(CapabilityClosureRunnerError) as excinfo:
        build_capability_closure_artifacts(debt_report={"debt_rows": []})

    assert "non-empty debt_rows" in str(excinfo.value)
    assert "capability closure" in str(excinfo.value)
    assert "debt_rows" in str(excinfo.value)


def _row(
    *,
    capability_id: str,
    category: str,
    severity: str,
    refs: list[str],
) -> dict[str, object]:
    return {
        "debt_row_id": f"capability_debt.{capability_id}.test",
        "capability_id": capability_id,
        "capability_name": capability_id,
        "family": "demo",
        "operator_status": "Live action disabled",
        "current_unlock_level": "C1",
        "current_stage": "local_demo",
        "debt_severity": severity,
        "debt_item_count": 1,
        "debt_items": [
            {
                "debt_id": f"{capability_id}.{category}.test",
                "category": category,
                "severity": severity,
                "description": f"{category} test debt",
                "missing_refs": refs,
                "fix": f"collect {category} refs",
            }
        ],
        "next_action": f"collect {category} refs",
        "live_action_enabled": False,
        "debt_row_is_not_execution_authority": True,
    }
