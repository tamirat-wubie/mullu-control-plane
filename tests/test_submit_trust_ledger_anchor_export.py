"""Trust-ledger anchor submission tests.

Purpose: verify a portable trust-ledger anchor export can be submitted into an
    append-only external anchor ledger only after export verification.
Governance scope: operator authority, explicit submission confirmation,
    submission receipt schema validation, and ledger replay.
Dependencies: scripts.submit_trust_ledger_anchor_export, scripts.verify_anchor_receipt,
    gateway.trust_ledger, and trust-ledger submission schemas.
Invariants:
  - Submission receipts are not terminal closure certificates.
  - Unverified exports are never appended to the submission ledger.
  - The submission ledger is hash-chained and replay-verifiable.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from gateway.trust_ledger import TrustLedger, TrustLedgerBundle, TrustLedgerBundleDraft, TrustLedgerEvidenceArtifact
from scripts.submit_trust_ledger_anchor_export import main, submit_trust_ledger_anchor_export, verify_submission_ledger
from scripts.validate_schemas import _load_schema, _validate_schema_instance


SUBMISSION_SCHEMA_PATH = Path("schemas/trust_ledger_anchor_submission_receipt.schema.json")


def test_submit_trust_ledger_anchor_export_records_signed_submission(tmp_path: Path) -> None:
    export_paths = _write_anchor_export(tmp_path)
    ledger_path = tmp_path / "submissions.jsonl"
    receipt_out = tmp_path / "submission_receipt.json"

    report = submit_trust_ledger_anchor_export(
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
        receipt_out=receipt_out,
    )
    ledger_state = verify_submission_ledger(ledger_path=ledger_path, signing_secret="submission-secret")
    receipt = json.loads(receipt_out.read_text(encoding="utf-8"))

    assert report["valid"] is True
    assert report["submitted"] is True
    assert report["reason"] == "anchor_submission_recorded"
    assert report["ledger_sequence"] == 1
    assert report["submission_id"].startswith("trust-anchor-submission-")
    assert report["output_files"]["ledger"] == str(ledger_path)
    assert report["output_files"]["submission_receipt"] == str(receipt_out)
    assert ledger_state["valid"] is True
    assert ledger_state["submission_count"] == 1
    assert ledger_state["latest_submission_id"] == report["submission_id"]
    assert receipt["metadata"]["submission_is_not_terminal_closure"] is True
    assert receipt["metadata"]["requires_operator_confirmation"] is True
    assert _validate_schema_instance(_load_schema(SUBMISSION_SCHEMA_PATH), receipt) == []


def test_submit_trust_ledger_anchor_export_blocks_without_confirmation(tmp_path: Path) -> None:
    export_paths = _write_anchor_export(tmp_path)
    ledger_path = tmp_path / "submissions.jsonl"

    report = submit_trust_ledger_anchor_export(
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
        confirm_submit=False,
    )

    assert report["valid"] is False
    assert report["reason"] == "operator_confirmation_required"
    assert report["submitted"] is False
    assert report["submission_receipt"] == {}
    assert not ledger_path.exists()


def test_submit_trust_ledger_anchor_export_blocks_tampered_package(tmp_path: Path) -> None:
    export_paths = _write_anchor_export(tmp_path)
    ledger_path = tmp_path / "submissions.jsonl"
    package = json.loads(export_paths["package"].read_text(encoding="utf-8"))
    package["package_hash"] = "0" * 64
    export_paths["package"].write_text(json.dumps(package), encoding="utf-8")

    report = submit_trust_ledger_anchor_export(
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
    )

    assert report["valid"] is False
    assert report["reason"].startswith("anchor_verification_failed:")
    assert report["anchor_verification"]["valid"] is False
    assert report["submitted"] is False
    assert not ledger_path.exists()


def test_submit_trust_ledger_anchor_export_posts_remote_transparency_log(tmp_path: Path) -> None:
    export_paths = _write_anchor_export(tmp_path)
    ledger_path = tmp_path / "submissions.jsonl"
    transport = FakeTransparencyLogTransport()

    report = submit_trust_ledger_anchor_export(
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
        remote_api_token="remote-token",
        remote_timeout_seconds=3.0,
        urlopen=transport,
    )
    receipt = report["submission_receipt"]

    assert report["valid"] is True
    assert report["remote_submission"]["reason"] == "remote_submission_accepted"
    assert report["remote_submission"]["external_anchor_ref"] == "https://transparency.example/entries/1"
    assert report["remote_submission"]["status_code"] == 201
    assert receipt["external_anchor_ref"] == "https://transparency.example/entries/1"
    assert receipt["metadata"]["remote_submission_url"] == "https://transparency.example/anchors"
    assert receipt["metadata"]["remote_submission_payload_hash"] == transport.payload["submission_payload_hash"]
    assert transport.timeout == 3.0
    assert transport.request.get_header("Authorization") == "Bearer remote-token"
    assert verify_submission_ledger(ledger_path=ledger_path, signing_secret="submission-secret")["valid"] is True


def test_submit_trust_ledger_anchor_export_blocks_remote_without_confirmation(tmp_path: Path) -> None:
    export_paths = _write_anchor_export(tmp_path)
    ledger_path = tmp_path / "submissions.jsonl"

    report = submit_trust_ledger_anchor_export(
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
        allow_remote_submit=False,
        remote_api_token="remote-token",
    )

    assert report["valid"] is False
    assert report["reason"] == "remote_submission_confirmation_required"
    assert report["remote_submission"] == {}
    assert not ledger_path.exists()


def test_submit_trust_ledger_anchor_export_blocks_remote_hash_mismatch(tmp_path: Path) -> None:
    export_paths = _write_anchor_export(tmp_path)
    ledger_path = tmp_path / "submissions.jsonl"
    transport = FakeTransparencyLogTransport(observed_hash="0" * 64)

    report = submit_trust_ledger_anchor_export(
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
        remote_api_token="remote-token",
        urlopen=transport,
    )

    assert report["valid"] is False
    assert report["reason"] == "remote_submission_failed:remote_submission_payload_hash_mismatch"
    assert report["remote_submission"]["valid"] is False
    assert report["remote_submission"]["observed_submission_payload_hash"] == "0" * 64
    assert report["submission_receipt"] == {}
    assert not ledger_path.exists()


def test_verify_submission_ledger_detects_hash_drift(tmp_path: Path) -> None:
    export_paths = _write_anchor_export(tmp_path)
    ledger_path = tmp_path / "submissions.jsonl"
    report = submit_trust_ledger_anchor_export(
        bundle_path=export_paths["bundle"],
        receipt_path=export_paths["anchor_receipt"],
        artifacts_path=export_paths["artifacts"],
        package_path=export_paths["package"],
        ledger_path=ledger_path,
        operator_id="operator-1",
        authority_ref="authority://trust-ledger-submission-1",
        submitted_at="2026-05-05T12:20:00+00:00",
        verification_secret="anchor-secret",
        submission_secret="submission-secret",
        signature_key_id="submission-key",
        confirm_submit=True,
    )
    ledger_record = json.loads(ledger_path.read_text(encoding="utf-8").splitlines()[0])
    ledger_record["operator_id"] = "operator-tampered"
    ledger_path.write_text(json.dumps(ledger_record) + "\n", encoding="utf-8")

    ledger_state = verify_submission_ledger(ledger_path=ledger_path, signing_secret="submission-secret")

    assert report["valid"] is True
    assert ledger_state["valid"] is False
    assert ledger_state["reason"] == "ledger_submission_hash_mismatch"
    assert ledger_state["submission_count"] == 0


def test_submit_trust_ledger_anchor_export_cli_emits_submission_receipt(tmp_path: Path, capsys: Any) -> None:
    export_paths = _write_anchor_export(tmp_path)
    ledger_path = tmp_path / "submissions.jsonl"
    receipt_out = tmp_path / "submission_receipt.json"

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
        "--receipt-out",
        str(receipt_out),
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
        "--confirm-submit",
        "--json",
    ])
    output = json.loads(capsys.readouterr().out)
    ledger_state = verify_submission_ledger(ledger_path=ledger_path, signing_secret="submission-secret")

    assert exit_code == 0
    assert output["valid"] is True
    assert output["reason"] == "anchor_submission_recorded"
    assert output["submission_id"].startswith("trust-anchor-submission-")
    assert output["ledger_sequence"] == 1
    assert ledger_state["valid"] is True
    assert receipt_out.exists()


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
    def __init__(self, *, observed_hash: str | None = None) -> None:
        self.observed_hash = observed_hash
        self.request: Any | None = None
        self.timeout: float | None = None
        self.payload: dict[str, Any] = {}

    def __call__(self, request: Any, *, timeout: float) -> "FakeHttpResponse":
        self.request = request
        self.timeout = timeout
        self.payload = json.loads(request.data.decode("utf-8"))
        observed_hash = self.observed_hash or self.payload["submission_payload_hash"]
        return FakeHttpResponse(
            status=201,
            payload={
                "external_anchor_ref": "https://transparency.example/entries/1",
                "observed_submission_payload_hash": observed_hash,
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
