"""Tests for the nested-mind evidence report CLI.

Purpose: verify read-only reporting over the append-only nested-mind evidence store.
Governance scope: P3 readiness visibility only; no nested-mind network calls.
Dependencies: report_nested_mind_evidence.py and NestedMindEvidenceStore.
Invariants: blocked stores remain blocked; ready requires one verified causal chain.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from mcoi_runtime.contracts import (
    NestedMindCommitWitness,
    NestedMindCommitWitnessStatus,
    NestedMindObservationReconciliationReport,
    NestedMindObservationReconciliationStatus,
    NestedMindObservationSubmissionReport,
    NestedMindObservationSubmissionStatus,
)
from mcoi_runtime.persistence import CorruptedDataError, NestedMindEvidenceStore

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "report_nested_mind_evidence.py"


def _module():
    spec = importlib.util.spec_from_file_location("report_nested_mind_evidence", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _clock() -> str:
    return "2026-05-31T00:00:00+00:00"


def _submission() -> NestedMindObservationSubmissionReport:
    return NestedMindObservationSubmissionReport(
        report_id="submission-1",
        plan_id="plan-1",
        mind_id="root",
        proposal_evidence_id="evidence-1",
        payload_hash="payload-hash-1",
        mullu_receipt_hash="mullu-receipt-hash-1",
        connector_result_id="connector-result-1",
        connector_response_digest="d" * 64,
        response_envelope_hash="envelope-hash-1",
        commit_witness_id="witness-1",
        status=NestedMindObservationSubmissionStatus.ACCEPTED,
        submitted_at=_clock(),
    )


def _witness() -> NestedMindCommitWitness:
    return NestedMindCommitWitness(
        witness_id="witness-1",
        proposal_evidence_id="evidence-1",
        mind_id="root",
        mullu_receipt_hash="mullu-receipt-hash-1",
        nested_mind_commit_hash="commit-hash-1",
        nested_mind_history_hash="history-hash-1",
        witnessed_at=_clock(),
        status=NestedMindCommitWitnessStatus.VERIFIED,
    )


def _reconciliation() -> NestedMindObservationReconciliationReport:
    return NestedMindObservationReconciliationReport(
        report_id="reconciliation-1",
        plan_id="plan-1",
        commit_witness_id="witness-1",
        mind_id="root",
        mullu_receipt_hash="mullu-receipt-hash-1",
        expected_commit_hash="commit-hash-1",
        expected_history_hash="history-hash-1",
        projection_connector_result_id="projection-result-1",
        audit_connector_result_id="audit-result-1",
        replay_connector_result_id=None,
        status=NestedMindObservationReconciliationStatus.VERIFIED,
        checked_at=_clock(),
    )


def test_report_blocks_empty_store(tmp_path) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    NestedMindEvidenceStore(store_path)

    report = module.build_nested_mind_evidence_report(store_path)

    assert report["status"] == "blocked"
    assert report["total_records"] == 0
    assert report["record_counts"]["submission_report"] == 0
    assert "accepted_submission_missing" in report["readiness"]["blockers"]
    assert report["next_action"] == "collect_live_record_observation_submission_witness_and_reconciliation"


def test_report_rejects_corrupted_evidence_store(tmp_path) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store_path.write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="invalid nested-mind evidence entry"):
        module.build_nested_mind_evidence_report(store_path)


def test_report_cli_rejects_corrupted_evidence_store(tmp_path, capsys) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store_path.write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="invalid nested-mind evidence entry"):
        module.main(["--store", str(store_path)])
    assert capsys.readouterr().out == ""


def test_report_cli_rejects_duplicate_evidence_ids(tmp_path, capsys) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    existing_line = store_path.read_text(encoding="utf-8")
    store_path.write_text(existing_line + existing_line, encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="duplicate nested-mind evidence id"):
        module.main(["--store", str(store_path)])
    assert capsys.readouterr().out == ""


def test_report_cli_rejects_stored_sensitive_fields(tmp_path, capsys) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    entry = json.loads(store_path.read_text(encoding="utf-8"))
    entry["payload"]["metadata"] = {"raw_response_body": "{}"}
    store_path.write_text(json.dumps(entry, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="forbidden sensitive field"):
        module.main(["--store", str(store_path)])
    assert capsys.readouterr().out == ""


def test_report_cli_rejects_unexpected_top_level_fields(tmp_path, capsys) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    entry = store_path.read_text(encoding="utf-8").strip()
    unsafe_entry = entry[:-1] + ',"authorization":"secret"}'
    store_path.write_text(unsafe_entry + "\n", encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="unexpected fields"):
        module.main(["--store", str(store_path)])
    assert capsys.readouterr().out == ""


def test_report_cli_rejects_unsupported_record_type(tmp_path, capsys) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    entry = json.loads(store_path.read_text(encoding="utf-8"))
    entry["record_type"] = "unknown_record"
    store_path.write_text(json.dumps(entry, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="unsupported nested-mind evidence record type"):
        module.main(["--store", str(store_path)])
    assert capsys.readouterr().out == ""


def test_report_cli_rejects_invalid_payload_contract(tmp_path, capsys) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    entry = json.loads(store_path.read_text(encoding="utf-8"))
    entry["payload"]["unexpected_payload_field"] = "ignored"
    store_path.write_text(json.dumps(entry, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="payload contract invalid"):
        module.main(["--store", str(store_path)])
    assert capsys.readouterr().out == ""


def test_report_cli_rejects_record_id_payload_mismatch(tmp_path, capsys) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    entry = json.loads(store_path.read_text(encoding="utf-8"))
    entry["record_id"] = "tampered-report-id"
    store_path.write_text(json.dumps(entry, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="record_id payload mismatch"):
        module.main(["--store", str(store_path)])
    assert capsys.readouterr().out == ""


def test_report_cli_rejects_mind_id_payload_mismatch(tmp_path, capsys) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    entry = json.loads(store_path.read_text(encoding="utf-8"))
    entry["mind_id"] = "tenant-other"
    store_path.write_text(json.dumps(entry, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="mind_id payload mismatch"):
        module.main(["--store", str(store_path)])
    assert capsys.readouterr().out == ""


def test_report_cli_rejects_mullu_receipt_hash_payload_mismatch(tmp_path, capsys) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_commit_witness(_witness())
    entry = json.loads(store_path.read_text(encoding="utf-8"))
    entry["mullu_receipt_hash"] = "tampered-receipt-hash"
    store_path.write_text(json.dumps(entry, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="mullu_receipt_hash payload mismatch"):
        module.main(["--store", str(store_path)])
    assert capsys.readouterr().out == ""


def test_report_cli_rejects_unexpected_top_level_fields(tmp_path, capsys) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    entry = store_path.read_text(encoding="utf-8").strip()
    unsafe_entry = entry[:-1] + ',"authorization":"secret"}'
    store_path.write_text(unsafe_entry + "\n", encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="unexpected fields"):
        module.main(["--store", str(store_path)])
    assert capsys.readouterr().out == ""


def test_report_ready_for_bound_verified_chain(tmp_path) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    store.record_commit_witness(_witness())
    store.record_reconciliation_report(_reconciliation())

    report = module.build_nested_mind_evidence_report(store_path, mind_id="root")

    assert report["status"] == "ready"
    assert report["mind_id"] == "root"
    assert report["total_records"] == 3
    assert report["accepted_submission_ids"] == ("submission-1",)
    assert report["verified_commit_witness_ids"] == ("witness-1",)
    assert report["verified_reconciliation_report_ids"] == ("reconciliation-1",)
    assert report["next_action"] == "p3_gate_ready_for_operator_review"


def test_report_mind_filter_blocks_other_mind_evidence(tmp_path) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    store.record_commit_witness(_witness())
    store.record_reconciliation_report(_reconciliation())

    report = module.build_nested_mind_evidence_report(store_path, mind_id="tenant-other")

    assert report["status"] == "blocked"
    assert report["mind_id"] == "tenant-other"
    assert report["total_records"] == 0
    assert report["accepted_submission_ids"] == ()
    assert "accepted_submission_missing" in report["readiness"]["blockers"]


def test_report_blocks_unbound_verified_records(tmp_path) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    store.record_commit_witness(_witness())
    store.record_reconciliation_report(
        NestedMindObservationReconciliationReport(
            report_id="reconciliation-1",
            plan_id="plan-1",
            commit_witness_id="witness-1",
            mind_id="root",
            mullu_receipt_hash="mullu-receipt-hash-1",
            expected_commit_hash="wrong-commit",
            expected_history_hash="history-hash-1",
            projection_connector_result_id="projection-result-1",
            audit_connector_result_id="audit-result-1",
            replay_connector_result_id=None,
            status=NestedMindObservationReconciliationStatus.VERIFIED,
            checked_at=_clock(),
        )
    )

    report = module.build_nested_mind_evidence_report(store_path, mind_id="root")

    assert report["status"] == "blocked"
    assert report["total_records"] == 3
    assert report["verified_commit_witness_ids"] == ("witness-1",)
    assert report["verified_reconciliation_report_ids"] == ("reconciliation-1",)
    assert report["readiness"]["blockers"] == ("verified_causal_chain_missing",)
    assert report["next_action"] == "reconcile_verified_submission_witness_chain"


def test_cli_prints_report_and_returns_blocked_status(tmp_path, capsys) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    NestedMindEvidenceStore(store_path)

    exit_code = module.main(["--store", str(store_path)])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert output["status"] == "blocked"
    assert output["readiness"]["status"] == "blocked"


def test_cli_prints_report_and_returns_ready_status(tmp_path, capsys) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    store.record_commit_witness(_witness())
    store.record_reconciliation_report(_reconciliation())

    exit_code = module.main(["--store", str(store_path), "--mind-id", "root"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["status"] == "ready"
    assert output["mind_id"] == "root"
    assert output["readiness"]["status"] == "ready"
    assert output["next_action"] == "p3_gate_ready_for_operator_review"


def test_cli_mind_filter_blocks_other_mind_evidence(tmp_path, capsys) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    store.record_commit_witness(_witness())
    store.record_reconciliation_report(_reconciliation())

    exit_code = module.main(["--store", str(store_path), "--mind-id", "tenant-other"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert output["status"] == "blocked"
    assert output["mind_id"] == "tenant-other"
    assert output["total_records"] == 0
    assert output["readiness"]["status"] == "blocked"
