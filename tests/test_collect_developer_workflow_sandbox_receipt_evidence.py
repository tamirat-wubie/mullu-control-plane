"""Tests for Developer Workflow sandbox receipt evidence collection.

Purpose: prove local artifact hashes can be collected into builder-ready
evidence without running effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.collect_developer_workflow_sandbox_receipt_evidence,
the sandbox receipt bundle builder, and validator.
Invariants: only local artifacts are read, raw contents are not embedded, and
collector output can produce a validated receipt bundle.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.build_developer_workflow_sandbox_receipt_bundle import (
    build_developer_workflow_sandbox_receipt_bundle,
    write_developer_workflow_sandbox_receipt_bundle,
)
from scripts.collect_developer_workflow_sandbox_receipt_evidence import (
    collect_developer_workflow_sandbox_receipt_evidence,
    main,
    write_developer_workflow_sandbox_receipt_evidence,
)
from scripts.validate_developer_workflow_sandbox_receipt_bundle import (
    validate_developer_workflow_sandbox_receipt_bundle,
)


def _artifact(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _sha256(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def test_collector_hashes_local_artifacts_and_builds_valid_bundle(tmp_path: Path) -> None:
    before = _artifact(tmp_path / "before.txt", "before-state")
    after = _artifact(tmp_path / "after.txt", "after-state")
    diff = _artifact(tmp_path / "diff.patch", "diff-state")

    evidence = collect_developer_workflow_sandbox_receipt_evidence(
        existing_evidence=None,
        workflow_run_id="developer_workflow_v1_collected_run",
        receipt_id="sandbox_patch_receipt",
        before_file=before,
        after_file=after,
        diff_file=diff,
        command="apply_patch",
        rollback_command="git apply -R .change_assurance/sandbox_patch.diff",
        evidence_refs=("proof://developer-workflow-v1/sandbox-patch/collected",),
    )
    bundle = build_developer_workflow_sandbox_receipt_bundle(evidence)
    bundle_path = write_developer_workflow_sandbox_receipt_bundle(bundle, tmp_path / "bundle.json")
    validation = validate_developer_workflow_sandbox_receipt_bundle(bundle_path=bundle_path)
    receipt = bundle["receipts"][0]

    assert validation.ok is True
    assert evidence["workflow_run_id"] == "developer_workflow_v1_collected_run"
    assert evidence["receipts"]["sandbox_patch_receipt"]["before_state_hash"] == _sha256("before-state")
    assert evidence["receipts"]["sandbox_patch_receipt"]["after_state_hash"] == _sha256("after-state")
    assert evidence["receipts"]["sandbox_patch_receipt"]["diff_hash"] == _sha256("diff-state")
    assert receipt["status"] == "complete"
    assert "before-state" not in json.dumps(evidence)


def test_collector_preserves_existing_receipts_and_deduplicates_refs(tmp_path: Path) -> None:
    before = _artifact(tmp_path / "before.txt", "test-before")
    after = _artifact(tmp_path / "after.txt", "test-after")
    diff = _artifact(tmp_path / "diff.txt", "test-diff")
    existing = {
        "workflow_run_id": "developer_workflow_v1_existing_run",
        "receipts": {
            "sandbox_patch_receipt": {
                "before_state_hash": "sha256:before",
                "after_state_hash": "sha256:after",
                "diff_hash": "sha256:diff",
                "rollback_command": "rollback patch",
                "command": "apply_patch",
                "evidence_refs": ["proof://patch"],
            }
        },
    }

    evidence = collect_developer_workflow_sandbox_receipt_evidence(
        existing_evidence=existing,
        workflow_run_id="",
        receipt_id="test_gate_receipt",
        before_file=before,
        after_file=after,
        diff_file=diff,
        command="python -m pytest tests/test_example.py -q",
        rollback_command="no state rollback required for read-only test command",
        evidence_refs=("proof://test", "proof://test"),
    )

    assert evidence["workflow_run_id"] == "developer_workflow_v1_existing_run"
    assert sorted(evidence["receipts"]) == ["sandbox_patch_receipt", "test_gate_receipt"]
    assert evidence["receipts"]["test_gate_receipt"]["evidence_refs"] == ["proof://test"]
    assert evidence["receipts"]["sandbox_patch_receipt"]["command"] == "apply_patch"


def test_collector_rejects_missing_artifact(tmp_path: Path) -> None:
    before = tmp_path / "missing-before.txt"
    after = _artifact(tmp_path / "after.txt", "after")
    diff = _artifact(tmp_path / "diff.txt", "diff")

    try:
        collect_developer_workflow_sandbox_receipt_evidence(
            existing_evidence=None,
            workflow_run_id="developer_workflow_v1_missing_run",
            receipt_id="sandbox_patch_receipt",
            before_file=before,
            after_file=after,
            diff_file=diff,
            command="apply_patch",
            rollback_command="rollback",
            evidence_refs=("proof://missing",),
        )
    except ValueError as exc:
        observed = str(exc)
    else:
        observed = ""

    assert "artifact_file_missing" in observed
    assert "missing-before.txt" in observed


def test_collector_rejects_unknown_receipt_id(tmp_path: Path) -> None:
    before = _artifact(tmp_path / "before.txt", "before")
    after = _artifact(tmp_path / "after.txt", "after")
    diff = _artifact(tmp_path / "diff.txt", "diff")

    try:
        collect_developer_workflow_sandbox_receipt_evidence(
            existing_evidence=None,
            workflow_run_id="developer_workflow_v1_unknown_run",
            receipt_id="unknown_receipt",
            before_file=before,
            after_file=after,
            diff_file=diff,
            command="command",
            rollback_command="rollback",
            evidence_refs=("proof://unknown",),
        )
    except ValueError as exc:
        observed = str(exc)
    else:
        observed = ""

    assert observed == "unknown_receipt_id:unknown_receipt"


def test_collector_cli_writes_builder_ready_evidence(tmp_path: Path, capsys) -> None:
    before = _artifact(tmp_path / "before.txt", "cli-before")
    after = _artifact(tmp_path / "after.txt", "cli-after")
    diff = _artifact(tmp_path / "diff.txt", "cli-diff")
    output = tmp_path / "evidence.json"

    exit_code = main([
        "--input",
        str(tmp_path / "missing-existing.json"),
        "--output",
        str(output),
        "--workflow-run-id",
        "developer_workflow_v1_cli_run",
        "--receipt-id",
        "diff_review_receipt",
        "--before-file",
        str(before),
        "--after-file",
        str(after),
        "--diff-file",
        str(diff),
        "--command",
        "git diff --stat",
        "--rollback-command",
        "no state rollback required for read-only diff command",
        "--evidence-ref",
        "proof://diff-review",
        "--json",
    ])
    captured = capsys.readouterr()
    evidence = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output.exists()
    assert evidence["workflow_run_id"] == "developer_workflow_v1_cli_run"
    assert evidence["receipts"]["diff_review_receipt"]["command"] == "git diff --stat"
    assert '"diff_review_receipt"' in captured.out
