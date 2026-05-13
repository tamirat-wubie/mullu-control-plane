"""Offline trust-ledger anchor receipt verifier tests.

Purpose: verify exported trust-ledger bundles, anchor receipts, and typed
evidence artifacts can be checked outside the live gateway.
Governance scope: proof-anchor CLI verification, schema gating, and tamper
detection.
Dependencies: scripts.verify_anchor_receipt and gateway.trust_ledger.
Invariants:
  - Valid exports verify through the canonical trust ledger.
  - Schema-invalid receipts stop before signature verification.
  - Artifact mutation is detected through artifact-root verification.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from gateway.trust_ledger import (
    TrustLedger,
    TrustLedgerBundle,
    TrustLedgerBundleDraft,
    TrustLedgerEvidenceArtifact,
)
from scripts.verify_anchor_receipt import main, verify_anchor_receipt_files
from scripts.validate_schemas import _load_schema, _validate_schema_instance


REPORT_SCHEMA_PATH = Path("schemas/trust_ledger_anchor_verification_report.schema.json")


def test_verify_anchor_receipt_files_accepts_valid_export(tmp_path: Path) -> None:
    paths = _write_export(tmp_path)

    report = verify_anchor_receipt_files(
        bundle_path=paths["bundle"],
        receipt_path=paths["receipt"],
        artifacts_path=paths["artifacts"],
        package_path=paths["package"],
        signing_secret="anchor-secret",
    )

    assert report["valid"] is True
    assert report["reason"] == "anchor_verified"
    assert report["schema_valid"] is True
    assert report["schema_errors"] == []
    assert report["anchor_receipt_id"].startswith("trust-anchor-receipt-")
    assert report["bundle_id"].startswith("trust-bundle-")
    assert report["command_id"] == "command-1"
    assert report["terminal_certificate_id"] == "terminal-closure-1"
    assert report["artifact_count"] == 7
    assert report["package_present"] is True
    assert report["package_valid"] is True
    assert report["package_id"].startswith("trust-export-")
    assert len(report["package_hash"]) == 64
    _assert_report_schema(report)


def test_verify_anchor_receipt_files_detects_tampered_artifact_root(tmp_path: Path) -> None:
    paths = _write_export(tmp_path)
    artifacts = json.loads(paths["artifacts"].read_text(encoding="utf-8"))
    artifacts[0]["artifact_hash"] = _hash("mutated-command-1")
    paths["artifacts"].write_text(json.dumps(artifacts), encoding="utf-8")

    report = verify_anchor_receipt_files(
        bundle_path=paths["bundle"],
        receipt_path=paths["receipt"],
        artifacts_path=paths["artifacts"],
        package_path=paths["package"],
        signing_secret="anchor-secret",
    )

    assert report["valid"] is False
    assert report["reason"] == "package_artifacts_hash_mismatch"
    assert report["schema_valid"] is True
    assert report["bundle_id"].startswith("trust-bundle-")
    assert report["anchor_receipt_id"].startswith("trust-anchor-receipt-")
    assert report["signature_key_id"] == ""
    assert report["package_present"] is True
    assert report["package_valid"] is False
    assert report["package_id"].startswith("trust-export-")
    _assert_report_schema(report)


def test_verify_anchor_receipt_files_rejects_schema_invalid_receipt(tmp_path: Path) -> None:
    paths = _write_export(tmp_path)
    receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    receipt["bundle_id"] = "bundle-placeholder"
    paths["receipt"].write_text(json.dumps(receipt), encoding="utf-8")

    report = verify_anchor_receipt_files(
        bundle_path=paths["bundle"],
        receipt_path=paths["receipt"],
        artifacts_path=paths["artifacts"],
        signing_secret="anchor-secret",
    )

    assert report["valid"] is False
    assert report["reason"] == "schema_validation_failed"
    assert report["schema_valid"] is False
    assert report["bundle_id"].startswith("trust-bundle-")
    assert report["anchor_receipt_id"].startswith("trust-anchor-receipt-")
    assert any("anchor_receipt:" in error for error in report["schema_errors"])
    _assert_report_schema(report)


def test_verify_anchor_receipt_files_rejects_schema_invalid_artifacts(tmp_path: Path) -> None:
    paths = _write_export(tmp_path)
    artifacts = json.loads(paths["artifacts"].read_text(encoding="utf-8"))
    artifacts[0]["artifact_hash"] = "sha256:not-a-digest"
    paths["artifacts"].write_text(json.dumps(artifacts), encoding="utf-8")

    report = verify_anchor_receipt_files(
        bundle_path=paths["bundle"],
        receipt_path=paths["receipt"],
        artifacts_path=paths["artifacts"],
        signing_secret="anchor-secret",
    )

    assert report["valid"] is False
    assert report["reason"] == "schema_validation_failed"
    assert report["schema_valid"] is False
    assert report["bundle_id"].startswith("trust-bundle-")
    assert report["anchor_receipt_id"].startswith("trust-anchor-receipt-")
    assert any("artifacts:" in error for error in report["schema_errors"])
    _assert_report_schema(report)


def test_verify_anchor_receipt_files_detects_package_bundle_hash_mismatch(tmp_path: Path) -> None:
    paths = _write_export(tmp_path)
    bundle = json.loads(paths["bundle"].read_text(encoding="utf-8"))
    bundle["metadata"]["tampered"] = True
    paths["bundle"].write_text(json.dumps(bundle), encoding="utf-8")

    report = verify_anchor_receipt_files(
        bundle_path=paths["bundle"],
        receipt_path=paths["receipt"],
        artifacts_path=paths["artifacts"],
        package_path=paths["package"],
        signing_secret="anchor-secret",
    )

    assert report["valid"] is False
    assert report["reason"] == "package_bundle_hash_mismatch"
    assert report["schema_valid"] is True
    assert report["schema_errors"] == []
    assert report["package_present"] is True
    assert report["package_valid"] is False
    _assert_report_schema(report)


def test_verify_anchor_receipt_files_rejects_schema_invalid_package(tmp_path: Path) -> None:
    paths = _write_export(tmp_path)
    package = json.loads(paths["package"].read_text(encoding="utf-8"))
    package["package_id"] = "package-placeholder"
    paths["package"].write_text(json.dumps(package), encoding="utf-8")

    report = verify_anchor_receipt_files(
        bundle_path=paths["bundle"],
        receipt_path=paths["receipt"],
        artifacts_path=paths["artifacts"],
        package_path=paths["package"],
        signing_secret="anchor-secret",
    )

    assert report["valid"] is False
    assert report["reason"] == "schema_validation_failed"
    assert report["schema_valid"] is False
    assert any("package:" in error for error in report["schema_errors"])
    assert report["package_present"] is True
    assert report["package_valid"] is False
    assert report["package_id"] == "package-placeholder"
    _assert_report_schema(report)


def test_verify_anchor_receipt_files_rejects_package_hash_mismatch(tmp_path: Path) -> None:
    paths = _write_export(tmp_path)
    package = json.loads(paths["package"].read_text(encoding="utf-8"))
    package["metadata"]["operator_note"] = "changed after packaging"
    paths["package"].write_text(json.dumps(package), encoding="utf-8")

    report = verify_anchor_receipt_files(
        bundle_path=paths["bundle"],
        receipt_path=paths["receipt"],
        artifacts_path=paths["artifacts"],
        package_path=paths["package"],
        signing_secret="anchor-secret",
    )

    assert report["valid"] is False
    assert report["reason"] == "package_hash_mismatch"
    assert report["schema_valid"] is True
    assert report["package_present"] is True
    assert report["package_valid"] is False
    assert report["package_id"].startswith("trust-export-")
    _assert_report_schema(report)


def test_verify_anchor_receipt_cli_reports_valid_export(tmp_path: Path, capsys: Any) -> None:
    paths = _write_export(tmp_path)

    exit_code = main([
        "--bundle",
        str(paths["bundle"]),
        "--receipt",
        str(paths["receipt"]),
        "--artifacts",
        str(paths["artifacts"]),
        "--package",
        str(paths["package"]),
        "--signing-secret",
        "anchor-secret",
        "--json",
    ])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["valid"] is True
    assert output["reason"] == "anchor_verified"
    assert output["artifact_count"] == 7
    assert output["schema_errors"] == []
    assert output["package_present"] is True
    assert output["package_valid"] is True
    assert output["package_id"].startswith("trust-export-")
    _assert_report_schema(output)


def test_verify_anchor_receipt_report_contract_allows_missing_secret_report() -> None:
    report = verify_anchor_receipt_files(
        bundle_path=Path("missing-bundle.json"),
        receipt_path=Path("missing-receipt.json"),
        artifacts_path=Path("missing-artifacts.json"),
        signing_secret="",
    )

    assert report["valid"] is False
    assert report["reason"] == "signing_secret_required"
    assert report["schema_valid"] is False
    assert report["package_present"] is False
    _assert_report_schema(report)


def _write_export(tmp_path: Path) -> dict[str, Path]:
    ledger = TrustLedger()
    bundle = _bundle()
    artifacts = _artifacts()
    receipt = ledger.anchor_bundle(
        bundle,
        artifacts=artifacts,
        anchor_target="transparency_log",
        external_anchor_ref="anchor://transparency-log/1",
        external_anchor_status="anchored",
        anchored_at="2026-05-05T12:00:00+00:00",
        signing_secret="anchor-secret",
        signature_key_id="anchor-key",
    )
    paths = {
        "bundle": tmp_path / "bundle.json",
        "receipt": tmp_path / "anchor_receipt.json",
        "artifacts": tmp_path / "artifacts.json",
        "package": tmp_path / "package.json",
    }
    package = ledger.package_anchor_export(
        bundle=bundle,
        receipt=receipt,
        artifacts=artifacts,
        created_at="2026-05-05T12:05:00+00:00",
    )
    paths["bundle"].write_text(json.dumps(bundle.to_json_dict()), encoding="utf-8")
    paths["receipt"].write_text(json.dumps(receipt.to_json_dict()), encoding="utf-8")
    paths["artifacts"].write_text(
        json.dumps([artifact.to_json_dict() for artifact in artifacts]),
        encoding="utf-8",
    )
    paths["package"].write_text(json.dumps(package.to_json_dict()), encoding="utf-8")
    return paths


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


def _assert_report_schema(report: dict[str, Any]) -> None:
    assert _validate_schema_instance(_load_schema(REPORT_SCHEMA_PATH), report) == []
