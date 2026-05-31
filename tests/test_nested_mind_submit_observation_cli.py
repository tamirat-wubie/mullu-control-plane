"""Tests for the nested-mind observation submit CLI.

Purpose: verify operator-facing dry-run and fail-closed submit behavior.
Governance scope: P2.6 CLI/script only; no public API route.
Dependencies: scripts/nested_mind_submit_observation.py and runtime contracts.
Invariants: default mode performs no network call; submit requires explicit env
flag; printed output does not contain bearer tokens.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from mcoi_runtime.contracts.nested_mind_observation_submission import (
    NestedMindObservationProposalPlan,
    NestedMindObservationProposalPlanStatus,
    NestedMindProposalEvidence,
    stable_json_hash,
)

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "nested_mind_submit_observation.py"


def _script_module():
    spec = importlib.util.spec_from_file_location("nested_mind_submit_observation", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _clock() -> str:
    return "2026-05-31T00:00:00+00:00"


def _payload() -> dict:
    return {
        "kind": "record_observation",
        "ops": (
            {
                "op": "set",
                "key": "observations/obs-1",
                "value": {"observation_id": "obs-1"},
            },
        ),
        "metadata": {"proposal_evidence_hash": "proposal-evidence-hash-1"},
    }


def _plan() -> NestedMindObservationProposalPlan:
    payload = _payload()
    return NestedMindObservationProposalPlan(
        plan_id="plan-1",
        proposal_evidence_id="evidence-1",
        mind_id="root",
        method="POST",
        target_route="/minds/root/proposals",
        proposal_payload=payload,
        payload_hash=stable_json_hash(payload),
        mullu_receipt_hash="mullu-receipt-hash-1",
        authority_receipt_hash="authority-receipt-hash-1",
        status=NestedMindObservationProposalPlanStatus.PLANNED,
        planned_at=_clock(),
    )


def _evidence(*, evidence_id: str = "evidence-1") -> NestedMindProposalEvidence:
    return NestedMindProposalEvidence(
        evidence_id=evidence_id,
        mind_id="root",
        evidence_hash="proposal-evidence-hash-1",
        mullu_receipt_hash="mullu-receipt-hash-1",
        authority_receipt_hash="authority-receipt-hash-1",
    )


def _write_inputs(tmp_path, *, evidence_id: str = "evidence-1") -> tuple[Path, Path]:
    plan_path = tmp_path / "plan.json"
    evidence_path = tmp_path / "evidence.json"
    plan_path.write_text(_plan().to_json(), encoding="utf-8")
    evidence_path.write_text(_evidence(evidence_id=evidence_id).to_json(), encoding="utf-8")
    return plan_path, evidence_path


def test_cli_defaults_to_dry_run_and_prints_report_json(tmp_path, capsys) -> None:
    module = _script_module()
    plan_path, evidence_path = _write_inputs(tmp_path)

    exit_code = module.main(["--plan", str(plan_path), "--evidence", str(evidence_path)])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["status"] == "disabled"
    assert output["blockers"] == ["dry_run_no_network_call"]
    assert output["connector_result_id"] is None


def test_cli_evidence_mismatch_blocks_before_output(tmp_path) -> None:
    module = _script_module()
    plan_path, evidence_path = _write_inputs(tmp_path, evidence_id="other-evidence")

    with pytest.raises(RuntimeError, match="proposal_evidence_id"):
        module.main(["--plan", str(plan_path), "--evidence", str(evidence_path)])


def test_cli_submit_requires_submit_env_flag(tmp_path, monkeypatch) -> None:
    module = _script_module()
    plan_path, evidence_path = _write_inputs(tmp_path)
    monkeypatch.delenv("MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED", raising=False)

    with pytest.raises(RuntimeError, match="MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED"):
        module.main(["--plan", str(plan_path), "--evidence", str(evidence_path), "--submit"])
