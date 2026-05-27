"""Trust-ledger remote submission preflight tests.

Purpose: prove remote anchor submission readiness is checked without posting to
the transparency log or appending to the local submission ledger.
Governance scope: operator authority, remote configuration, export replay,
ledger replay, schema-backed preflight receipts, and strict CLI behavior.
Dependencies: scripts.preflight_trust_ledger_remote_submission and
gateway.trust_ledger.
Invariants:
  - Ready preflight emits SolvedVerified without mutating the ledger.
  - Missing live token remains AwaitingEvidence.
  - Tampered exports are GovernanceBlocked.
  - CLI output is schema-valid and strict mode fails for blocked preflight.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from gateway.trust_ledger import TrustLedger, TrustLedgerBundle, TrustLedgerBundleDraft, TrustLedgerEvidenceArtifact
from scripts.preflight_trust_ledger_remote_submission import (
    PREFLIGHT_SCHEMA_PATH,
    main,
    preflight_trust_ledger_remote_submission,
    write_trust_ledger_remote_submission_preflight_report,
)
from scripts.submit_trust_ledger_anchor_export import _remote_preflight_receipt_id, submit_trust_ledger_anchor_export
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_trust_ledger_remote_submission_preflight_accepts_ready_export(tmp_path: Path) -> None:
    export_paths = _write_anchor_export(tmp_path)
    ledger_path = tmp_path / "submissions.jsonl"

    report = preflight_trust_ledger_remote_submission(
        bundle_path=export_paths["bundle"],
        receipt_path=export_paths["anchor_receipt"],
        artifacts_path=export_paths["artifacts"],
        package_path=export_paths["package"],
        ledger_path=ledger_path,
        operator_id="operator-1",
        authority_ref="proof://approval-submit-anchor-1",
        submitted_at="2026-05-05T12:20:00+00:00",
        verification_secret="anchor-secret",
        submission_secret="submission-secret",
        signature_key_id="submission-key",
        remote_submit_url="https://transparency.example/anchors",
        remote_api_token="remote-token",
        remote_timeout_seconds=3.0,
    )
    payload = report.as_dict()

    assert report.ready is True
    assert report.outcome == "SolvedVerified"
    assert report.blockers == ()
    assert report.hard_blockers == ()
    assert report.step_count == 12
    assert report.anchor_verification["valid"] is True
    assert report.ledger_state["valid"] is True
    assert report.remote_submit_host == "transparency.example"
    assert report.next_ledger_sequence == 1
    assert report.previous_submission_hash == "0" * 64
    assert len(report.expected_remote_submission_payload_hash) == 64
    assert report.expected_remote_idempotency_key == report.expected_remote_submission_payload_hash
    assert payload["metadata"]["remote_submit_executed"] is False
    assert payload["metadata"]["ledger_append_executed"] is False
    assert not ledger_path.exists()
    assert _validate_schema_instance(_load_schema(PREFLIGHT_SCHEMA_PATH), payload) == []


def test_trust_ledger_remote_submission_preflight_projects_final_submit_payload_hash(tmp_path: Path) -> None:
    export_paths = _write_anchor_export(tmp_path)
    ledger_path = tmp_path / "submissions.jsonl"
    preflight = preflight_trust_ledger_remote_submission(
        bundle_path=export_paths["bundle"],
        receipt_path=export_paths["anchor_receipt"],
        artifacts_path=export_paths["artifacts"],
        package_path=export_paths["package"],
        ledger_path=ledger_path,
        operator_id="operator-1",
        authority_ref="proof://approval-submit-anchor-1",
        submitted_at="2026-05-05T12:20:00+00:00",
        verification_secret="anchor-secret",
        submission_secret="submission-secret",
        signature_key_id="submission-key",
        remote_submit_url="https://transparency.example/anchors",
        remote_api_token="remote-token",
    )
    preflight_path = tmp_path / "remote_preflight.json"
    write_trust_ledger_remote_submission_preflight_report(preflight, preflight_path)
    transport = FakeTransparencyLogTransport()

    submission = submit_trust_ledger_anchor_export(
        bundle_path=export_paths["bundle"],
        receipt_path=export_paths["anchor_receipt"],
        artifacts_path=export_paths["artifacts"],
        package_path=export_paths["package"],
        ledger_path=ledger_path,
        operator_id="operator-1",
        authority_ref="proof://approval-submit-anchor-1",
        submitted_at="2026-05-05T12:20:00+00:00",
        verification_secret="anchor-secret",
        submission_secret="submission-secret",
        signature_key_id="submission-key",
        confirm_submit=True,
        remote_submit_url="https://transparency.example/anchors",
        allow_remote_submit=True,
        remote_preflight_receipt_path=preflight_path,
        remote_api_token="remote-token",
        urlopen=transport,
    )

    assert preflight.ready is True
    assert submission["valid"] is True
    assert preflight.next_ledger_sequence == submission["ledger_sequence"]
    assert preflight.previous_submission_hash == submission["previous_submission_hash"]
    assert preflight.expected_remote_submission_payload_hash == submission["remote_submission"]["submission_payload_hash"]
    assert preflight.expected_remote_idempotency_key == transport.request.get_header("Idempotency-key")


def test_trust_ledger_remote_submission_preflight_blocks_missing_remote_token(tmp_path: Path) -> None:
    export_paths = _write_anchor_export(tmp_path)
    ledger_path = tmp_path / "submissions.jsonl"

    report = preflight_trust_ledger_remote_submission(
        bundle_path=export_paths["bundle"],
        receipt_path=export_paths["anchor_receipt"],
        artifacts_path=export_paths["artifacts"],
        package_path=export_paths["package"],
        ledger_path=ledger_path,
        operator_id="operator-1",
        authority_ref="proof://approval-submit-anchor-1",
        submitted_at="2026-05-05T12:20:00+00:00",
        verification_secret="anchor-secret",
        submission_secret="submission-secret",
        signature_key_id="submission-key",
        remote_submit_url="https://transparency.example/anchors",
        remote_api_token="",
    )

    assert report.ready is False
    assert report.outcome == "AwaitingEvidence"
    assert report.blockers == ("remote_api_token",)
    assert report.hard_blockers == ()
    assert report.remote_api_token_present is False
    assert report.anchor_verification["valid"] is True
    assert report.ledger_state["valid"] is True
    assert report.next_ledger_sequence == 1
    assert len(report.expected_remote_submission_payload_hash) == 64
    assert not ledger_path.exists()


def test_trust_ledger_remote_submission_preflight_blocks_tampered_package(tmp_path: Path) -> None:
    export_paths = _write_anchor_export(tmp_path)
    ledger_path = tmp_path / "submissions.jsonl"
    package = json.loads(export_paths["package"].read_text(encoding="utf-8"))
    package["package_hash"] = "0" * 64
    export_paths["package"].write_text(json.dumps(package), encoding="utf-8")

    report = preflight_trust_ledger_remote_submission(
        bundle_path=export_paths["bundle"],
        receipt_path=export_paths["anchor_receipt"],
        artifacts_path=export_paths["artifacts"],
        package_path=export_paths["package"],
        ledger_path=ledger_path,
        operator_id="operator-1",
        authority_ref="proof://approval-submit-anchor-1",
        submitted_at="2026-05-05T12:20:00+00:00",
        verification_secret="anchor-secret",
        submission_secret="submission-secret",
        signature_key_id="submission-key",
        remote_submit_url="https://transparency.example/anchors",
        remote_api_token="remote-token",
    )

    assert report.ready is False
    assert report.outcome == "GovernanceBlocked"
    assert "anchor_export_verification" in report.blockers
    assert "remote_payload_projection" in report.blockers
    assert "anchor_export_verification" in report.hard_blockers
    assert report.anchor_verification["valid"] is False
    assert report.anchor_verification["reason"] == "package_hash_mismatch"
    assert report.expected_remote_submission_payload_hash == ""
    assert not ledger_path.exists()


def test_trust_ledger_remote_submission_preflight_cli_writes_schema_checked_receipt(
    tmp_path: Path,
    capsys: Any,
    monkeypatch: Any,
) -> None:
    export_paths = _write_anchor_export(tmp_path)
    ledger_path = tmp_path / "submissions.jsonl"
    output_path = tmp_path / "remote_preflight.json"
    monkeypatch.delenv("MULLU_TRUST_LEDGER_REMOTE_SUBMISSION_TOKEN", raising=False)

    exit_code = main([
        "--bundle",
        str(export_paths["bundle"]),
        "--receipt",
        str(export_paths["anchor_receipt"]),
        "--artifacts",
        str(export_paths["artifacts"]),
        "--package",
        str(export_paths["package"]),
        "--ledger-path",
        str(ledger_path),
        "--operator-id",
        "operator-1",
        "--authority-ref",
        "proof://approval-submit-anchor-1",
        "--submitted-at",
        "2026-05-05T12:20:00+00:00",
        "--verification-secret",
        "anchor-secret",
        "--submission-secret",
        "submission-secret",
        "--signature-key-id",
        "submission-key",
        "--remote-submit-url",
        "https://transparency.example/anchors",
        "--output",
        str(output_path),
        "--strict",
        "--json",
    ])
    stdout_payload = json.loads(capsys.readouterr().out)
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert stdout_payload["ready"] is False
    assert written_payload == stdout_payload
    assert written_payload["outcome"] == "AwaitingEvidence"
    assert written_payload["blockers"] == ["remote_api_token"]
    assert len(written_payload["expected_remote_submission_payload_hash"]) == 64
    assert _validate_schema_instance(_load_schema(PREFLIGHT_SCHEMA_PATH), written_payload) == []
    assert not ledger_path.exists()


def test_trust_ledger_remote_submission_preflight_writer_validates_schema(tmp_path: Path) -> None:
    export_paths = _write_anchor_export(tmp_path)
    output_path = tmp_path / "ready_preflight.json"
    report = preflight_trust_ledger_remote_submission(
        bundle_path=export_paths["bundle"],
        receipt_path=export_paths["anchor_receipt"],
        artifacts_path=export_paths["artifacts"],
        package_path=export_paths["package"],
        ledger_path=tmp_path / "submissions.jsonl",
        operator_id="operator-1",
        authority_ref="proof://approval-submit-anchor-1",
        submitted_at="2026-05-05T12:20:00+00:00",
        verification_secret="anchor-secret",
        submission_secret="submission-secret",
        signature_key_id="submission-key",
        remote_submit_url="https://transparency.example/anchors",
        remote_api_token="remote-token",
    )

    written = write_trust_ledger_remote_submission_preflight_report(report, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert payload["ready"] is True
    assert payload["receipt_id"].startswith("trust-ledger-remote-submission-preflight-")
    assert payload["receipt_id"] == _remote_preflight_receipt_id(payload)
    assert payload["next_ledger_sequence"] == 1
    assert payload["expected_remote_idempotency_key"] == payload["expected_remote_submission_payload_hash"]
    assert _validate_schema_instance(_load_schema(PREFLIGHT_SCHEMA_PATH), payload) == []


def _write_anchor_export(tmp_path: Path) -> dict[str, Path]:
    ledger = TrustLedger()
    bundle = _bundle()
    artifacts = _artifacts()
    receipt = ledger.anchor_bundle(
        bundle,
        artifacts=artifacts,
        anchor_target="transparency_log",
        external_anchor_ref="anchor://transparency-log/1",
        external_anchor_status="anchored",
        anchored_at="2026-05-05T12:10:00+00:00",
        signing_secret="anchor-secret",
        signature_key_id="anchor-key",
    )
    package = ledger.package_anchor_export(
        bundle=bundle,
        receipt=receipt,
        artifacts=artifacts,
        created_at="2026-05-05T12:11:00+00:00",
    )
    paths = {
        "bundle": tmp_path / "bundle.json",
        "anchor_receipt": tmp_path / "anchor_receipt.json",
        "artifacts": tmp_path / "artifacts.json",
        "package": tmp_path / "package.json",
    }
    paths["bundle"].write_text(json.dumps(bundle.to_json_dict()), encoding="utf-8")
    paths["anchor_receipt"].write_text(json.dumps(receipt.to_json_dict()), encoding="utf-8")
    paths["artifacts"].write_text(
        json.dumps([artifact.to_json_dict() for artifact in artifacts]),
        encoding="utf-8",
    )
    paths["package"].write_text(json.dumps(package.to_json_dict()), encoding="utf-8")
    return paths


class FakeTransparencyLogTransport:
    def __init__(self) -> None:
        self.request: Any | None = None
        self.payload: dict[str, Any] = {}

    def __call__(self, request: Any, *, timeout: float) -> "FakeHttpResponse":
        self.request = request
        self.payload = json.loads(request.data.decode("utf-8"))
        return FakeHttpResponse(
            status=201,
            payload={
                "external_anchor_ref": "https://transparency.example/entries/1",
                "observed_submission_payload_hash": self.payload["submission_payload_hash"],
                "remote_receipt_hash": _hash("remote-receipt-1"),
            },
        )


class FakeHttpResponse:
    def __init__(self, *, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self._payload = payload

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        encoded = json.dumps(self._payload).encode("utf-8")
        return encoded if size < 0 else encoded[:size]


def _bundle() -> TrustLedgerBundle:
    return TrustLedger().issue(
        TrustLedgerBundleDraft(
            tenant_id="tenant-a",
            command_id="command-1",
            terminal_certificate_id="terminal-closure-1",
            deployment_id="deployment-2026-05-05",
            commit_sha="abc123",
            hash_chain_root="hash-root-1",
            evidence_refs=("proof://terminal-closure-1", "proof://audit-root-1"),
            issued_at="2026-05-05T12:00:00+00:00",
            metadata={"surface": "trust_ledger"},
        ),
        signing_secret="bundle-secret",
        signature_key_id="bundle-key",
    )


def _artifacts() -> tuple[TrustLedgerEvidenceArtifact, ...]:
    return (
        TrustLedgerEvidenceArtifact(
            artifact_type="command",
            artifact_id="command-1",
            artifact_hash=_hash("command-1"),
            evidence_ref="proof://command-1",
        ),
        TrustLedgerEvidenceArtifact(
            artifact_type="approval",
            artifact_id="approval-1",
            artifact_hash=_hash("approval-1"),
            evidence_ref="proof://approval-1",
        ),
        TrustLedgerEvidenceArtifact(
            artifact_type="execution_receipt",
            artifact_id="execution-1",
            artifact_hash=_hash("execution-1"),
            evidence_ref="proof://execution-1",
        ),
        TrustLedgerEvidenceArtifact(
            artifact_type="verification_result",
            artifact_id="verification-1",
            artifact_hash=_hash("verification-1"),
            evidence_ref="proof://verification-1",
        ),
        TrustLedgerEvidenceArtifact(
            artifact_type="effect_reconciliation",
            artifact_id="effect-reconciliation-1",
            artifact_hash=_hash("effect-reconciliation-1"),
            evidence_ref="proof://effect-reconciliation-1",
        ),
        TrustLedgerEvidenceArtifact(
            artifact_type="terminal_certificate",
            artifact_id="terminal-closure-1",
            artifact_hash=_hash("terminal-closure-1"),
            evidence_ref="proof://terminal-closure-1",
        ),
        TrustLedgerEvidenceArtifact(
            artifact_type="learning_decision",
            artifact_id="learning-admission-1",
            artifact_hash=_hash("learning-admission-1"),
            evidence_ref="proof://learning-admission-1",
        ),
    )


def _hash(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"
