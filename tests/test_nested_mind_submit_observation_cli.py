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

from mcoi_runtime.contracts import (
    NestedMindCommitWitness,
    NestedMindCommitWitnessStatus,
    NestedMindObservationProposalPlan,
    NestedMindObservationProposalPlanStatus,
    NestedMindObservationSubmissionReport,
    NestedMindObservationSubmissionStatus,
    NestedMindProposalEvidence,
    stable_json_hash,
)
from mcoi_runtime.persistence import NestedMindEvidenceStore

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


def test_cli_rejects_plan_with_unexpected_field_before_output(tmp_path, capsys) -> None:
    module = _script_module()
    plan_path, evidence_path = _write_inputs(tmp_path)
    plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_payload["unexpected_plan_field"] = "ignored"
    plan_path.write_text(json.dumps(plan_payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(RuntimeError, match="plan JSON has unexpected fields"):
        module.main(["--plan", str(plan_path), "--evidence", str(evidence_path)])
    assert capsys.readouterr().out == ""


def test_cli_rejects_evidence_with_missing_required_field_before_output(tmp_path, capsys) -> None:
    module = _script_module()
    plan_path, evidence_path = _write_inputs(tmp_path)
    evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    del evidence_payload["authority_receipt_hash"]
    evidence_path.write_text(json.dumps(evidence_payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(RuntimeError, match="evidence JSON missing required fields"):
        module.main(["--plan", str(plan_path), "--evidence", str(evidence_path)])
    assert capsys.readouterr().out == ""


def test_cli_rejects_non_object_plan_metadata_before_output(tmp_path, capsys) -> None:
    module = _script_module()
    plan_path, evidence_path = _write_inputs(tmp_path)
    plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_payload["metadata"] = ["not", "object"]
    plan_path.write_text(json.dumps(plan_payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(RuntimeError, match="plan metadata must be a JSON object"):
        module.main(["--plan", str(plan_path), "--evidence", str(evidence_path)])
    assert capsys.readouterr().out == ""


def test_cli_rejects_non_text_plan_id_before_output(tmp_path, capsys) -> None:
    module = _script_module()
    plan_path, evidence_path = _write_inputs(tmp_path)
    plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_payload["plan_id"] = 123
    plan_path.write_text(json.dumps(plan_payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="plan_id must be a non-empty string"):
        module.main(["--plan", str(plan_path), "--evidence", str(evidence_path)])
    assert capsys.readouterr().out == ""


def test_cli_rejects_non_text_plan_blocker_before_output(tmp_path, capsys) -> None:
    module = _script_module()
    plan_path, evidence_path = _write_inputs(tmp_path)
    plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_payload["blockers"] = ["ready", 7]
    plan_path.write_text(json.dumps(plan_payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"plan blockers\[1\] must be a non-empty string"):
        module.main(["--plan", str(plan_path), "--evidence", str(evidence_path)])
    assert capsys.readouterr().out == ""


def test_cli_rejects_empty_plan_blocker_before_output(tmp_path, capsys) -> None:
    module = _script_module()
    plan_path, evidence_path = _write_inputs(tmp_path)
    plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_payload["blockers"] = [""]
    plan_path.write_text(json.dumps(plan_payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"plan blockers\[0\] must be a non-empty string"):
        module.main(["--plan", str(plan_path), "--evidence", str(evidence_path)])
    assert capsys.readouterr().out == ""


def test_cli_rejects_non_finite_plan_json_before_output(tmp_path, capsys) -> None:
    module = _script_module()
    plan_path, evidence_path = _write_inputs(tmp_path)
    plan_path.write_text('{"plan_id": NaN}', encoding="utf-8")

    with pytest.raises(RuntimeError, match="failed to parse strict JSON"):
        module.main(["--plan", str(plan_path), "--evidence", str(evidence_path)])
    assert capsys.readouterr().out == ""


def test_cli_submit_requires_submit_env_flag(tmp_path, monkeypatch) -> None:
    module = _script_module()
    plan_path, evidence_path = _write_inputs(tmp_path)
    monkeypatch.delenv("MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED", raising=False)

    with pytest.raises(RuntimeError, match="MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED"):
        module.main(["--plan", str(plan_path), "--evidence", str(evidence_path), "--submit"])


def test_cli_submit_store_records_plan_report_and_witness(tmp_path, monkeypatch, capsys) -> None:
    module = _script_module()
    plan_path, evidence_path = _write_inputs(tmp_path)
    store_path = tmp_path / "evidence.jsonl"
    monkeypatch.setenv("MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED", "true")
    monkeypatch.setattr(
        module,
        "mount_nested_mind_observation_submitter_from_env",
        lambda **_: FakeBootstrap(FakeSubmitter()),
    )

    exit_code = module.main(
        [
            "--plan",
            str(plan_path),
            "--evidence",
            str(evidence_path),
            "--submit",
            "--store",
            str(store_path),
        ]
    )
    output = json.loads(capsys.readouterr().out)
    entries = NestedMindEvidenceStore(store_path).list_by_mind_id("root")

    assert exit_code == 0
    assert output["status"] == "accepted"
    assert [entry.record_type for entry in entries] == ["plan", "submission_report", "commit_witness"]
    assert "secret-token" not in store_path.read_text(encoding="utf-8")


class FakeBootstrap:
    def __init__(self, submitter: object) -> None:
        self.submitter = submitter


class FakeSubmitter:
    def submit_observation_plan_with_witness(
        self,
        plan: NestedMindObservationProposalPlan,
        *,
        submit_enabled: bool,
    ):
        assert submit_enabled is True
        report = NestedMindObservationSubmissionReport(
            report_id="submission-1",
            plan_id=plan.plan_id,
            mind_id=plan.mind_id,
            proposal_evidence_id=plan.proposal_evidence_id,
            payload_hash=plan.payload_hash,
            connector_result_id="connector-result-1",
            connector_response_digest="d" * 64,
            response_envelope_hash="envelope-hash-1",
            commit_witness_id="witness-1",
            status=NestedMindObservationSubmissionStatus.ACCEPTED,
            submitted_at=_clock(),
        )
        witness = NestedMindCommitWitness(
            witness_id="witness-1",
            proposal_evidence_id=plan.proposal_evidence_id,
            mind_id=plan.mind_id,
            mullu_receipt_hash=plan.mullu_receipt_hash,
            nested_mind_commit_hash="commit-hash-1",
            nested_mind_history_hash="history-hash-1",
            witnessed_at=_clock(),
            status=NestedMindCommitWitnessStatus.VERIFIED,
        )
        return type("Outcome", (), {"report": report, "commit_witness": witness})()
