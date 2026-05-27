"""OrgOS trust-ledger anchor export packager tests.

Purpose: verify optional OrgOS event-receipt artifacts can be merged into a
    real terminal trust-ledger anchor export.
Governance scope: terminal closure anchoring, optional OrgOS evidence binding,
    duplicate prevention, and offline anchor verification.
Dependencies: scripts.package_orgos_anchor_export, scripts.verify_orgos_event_log,
    scripts.verify_anchor_receipt, gateway.orgos_kernel, and gateway.trust_ledger.
Invariants:
  - OrgOS event receipts remain optional supporting evidence.
  - Terminal command artifacts remain required for anchor issuance.
  - Produced exports verify through the canonical offline anchor verifier.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from gateway.orgos_kernel import JsonlOrgCaseEventLog, OrgCaseEventReceiptConfig
from gateway.trust_ledger import TrustLedger, TrustLedgerBundle, TrustLedgerBundleDraft, TrustLedgerEvidenceArtifact
from scripts.package_orgos_anchor_export import main, package_orgos_anchor_export
from scripts.validate_schemas import _load_schema, _validate_schema_instance
from scripts.verify_anchor_receipt import verify_anchor_receipt_files
from scripts.verify_orgos_event_log import verify_orgos_event_log_file


NOW = "2026-05-05T12:00:00+00:00"
PACKAGE_SCHEMA_PATH = Path("schemas/trust_ledger_export_package.schema.json")


def test_package_orgos_anchor_export_merges_optional_orgos_artifact(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    output_dir = tmp_path / "anchor-export"

    report = package_orgos_anchor_export(
        bundle_path=inputs["bundle"],
        base_artifacts_path=inputs["base_artifacts"],
        orgos_artifacts_path=inputs["orgos_artifacts"],
        output_dir=output_dir,
        anchor_target="transparency_log",
        external_anchor_ref="",
        external_anchor_status="pending",
        anchored_at="2026-05-05T12:10:00+00:00",
        signing_secret="anchor-secret",
        signature_key_id="anchor-key",
        created_at="2026-05-05T12:11:00+00:00",
    )
    verification = verify_anchor_receipt_files(
        bundle_path=output_dir / "bundle.json",
        receipt_path=output_dir / "anchor_receipt.json",
        artifacts_path=output_dir / "artifacts.json",
        package_path=output_dir / "package.json",
        signing_secret="anchor-secret",
    )
    artifacts = json.loads((output_dir / "artifacts.json").read_text(encoding="utf-8"))
    package = json.loads((output_dir / "package.json").read_text(encoding="utf-8"))

    assert report["valid"] is True
    assert report["reason"] == "packaged"
    assert report["artifact_count"] == 8
    assert report["orgos_artifact_count"] == 1
    assert report["package_id"].startswith("trust-export-")
    assert report["anchor_receipt_id"].startswith("trust-anchor-receipt-")
    assert report["output_files"]["package"].endswith("package.json")
    assert verification["valid"] is True
    assert verification["reason"] == "anchor_verified"
    assert verification["artifact_count"] == 8
    assert any(item["artifact_type"] == "orgos_event_receipt" for item in artifacts)
    assert package["artifact_count"] == 8
    assert _validate_schema_instance(_load_schema(PACKAGE_SCHEMA_PATH), package) == []


def test_package_orgos_anchor_export_rejects_required_orgos_artifact(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    orgos_artifacts = json.loads(inputs["orgos_artifacts"].read_text(encoding="utf-8"))
    orgos_artifacts[0]["required"] = True
    inputs["orgos_artifacts"].write_text(json.dumps(orgos_artifacts), encoding="utf-8")

    report = package_orgos_anchor_export(
        bundle_path=inputs["bundle"],
        base_artifacts_path=inputs["base_artifacts"],
        orgos_artifacts_path=inputs["orgos_artifacts"],
        output_dir=tmp_path / "anchor-export",
        anchor_target="transparency_log",
        external_anchor_ref="",
        external_anchor_status="pending",
        anchored_at="2026-05-05T12:10:00+00:00",
        signing_secret="anchor-secret",
        signature_key_id="anchor-key",
        created_at="2026-05-05T12:11:00+00:00",
    )

    assert report["valid"] is False
    assert report["reason"] == "orgos_event_receipt_must_be_optional"
    assert report["artifact_count"] == 0
    assert report["output_files"] == {}


def test_package_orgos_anchor_export_rejects_missing_terminal_artifact(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    base_artifacts = [
        item
        for item in json.loads(inputs["base_artifacts"].read_text(encoding="utf-8"))
        if item["artifact_type"] != "terminal_certificate"
    ]
    inputs["base_artifacts"].write_text(json.dumps(base_artifacts), encoding="utf-8")

    report = package_orgos_anchor_export(
        bundle_path=inputs["bundle"],
        base_artifacts_path=inputs["base_artifacts"],
        orgos_artifacts_path=inputs["orgos_artifacts"],
        output_dir=tmp_path / "anchor-export",
        anchor_target="transparency_log",
        external_anchor_ref="",
        external_anchor_status="pending",
        anchored_at="2026-05-05T12:10:00+00:00",
        signing_secret="anchor-secret",
        signature_key_id="anchor-key",
        created_at="2026-05-05T12:11:00+00:00",
    )

    assert report["valid"] is False
    assert report["reason"] == "anchor_required_artifacts_missing:terminal_certificate"
    assert report["schema_valid"] is True
    assert report["schema_errors"] == []


def test_package_orgos_anchor_export_cli_emits_verifiable_package(tmp_path: Path, capsys: Any) -> None:
    inputs = _write_inputs(tmp_path)
    output_dir = tmp_path / "anchor-export"

    exit_code = main([
        "--bundle",
        str(inputs["bundle"]),
        "--base-artifacts",
        str(inputs["base_artifacts"]),
        "--orgos-artifacts",
        str(inputs["orgos_artifacts"]),
        "--output-dir",
        str(output_dir),
        "--anchor-target",
        "transparency_log",
        "--external-anchor-status",
        "pending",
        "--anchored-at",
        "2026-05-05T12:10:00+00:00",
        "--created-at",
        "2026-05-05T12:11:00+00:00",
        "--signing-secret",
        "anchor-secret",
        "--signature-key-id",
        "anchor-key",
        "--json",
    ])
    output = json.loads(capsys.readouterr().out)
    verification = verify_anchor_receipt_files(
        bundle_path=output_dir / "bundle.json",
        receipt_path=output_dir / "anchor_receipt.json",
        artifacts_path=output_dir / "artifacts.json",
        package_path=output_dir / "package.json",
        signing_secret="anchor-secret",
    )

    assert exit_code == 0
    assert output["valid"] is True
    assert output["reason"] == "packaged"
    assert output["orgos_artifact_count"] == 1
    assert verification["valid"] is True
    assert verification["package_valid"] is True
    assert Path(output["output_files"]["artifacts"]).exists()


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    bundle = _bundle()
    base_artifacts = _base_artifacts()
    orgos_artifacts = _orgos_artifacts(tmp_path)
    paths = {
        "bundle": tmp_path / "bundle.json",
        "base_artifacts": tmp_path / "base_artifacts.json",
        "orgos_artifacts": tmp_path / "orgos_artifacts.json",
    }
    paths["bundle"].write_text(json.dumps(bundle.to_json_dict()), encoding="utf-8")
    paths["base_artifacts"].write_text(
        json.dumps([artifact.to_json_dict() for artifact in base_artifacts]),
        encoding="utf-8",
    )
    paths["orgos_artifacts"].write_text(json.dumps(orgos_artifacts), encoding="utf-8")
    return paths


def _orgos_artifacts(tmp_path: Path) -> list[dict[str, Any]]:
    event_log_path = tmp_path / "orgos-events.jsonl"
    log = JsonlOrgCaseEventLog(
        event_log_path,
        clock=lambda: NOW,
        receipt_config=OrgCaseEventReceiptConfig(
            signing_secret="orgos-secret",
            signature_key_id="orgos-event-test",
            lock_timeout_seconds=1.0,
            stale_lock_seconds=1.0,
        ),
    )
    log.record(
        case_id="case-launch-gateway",
        tenant_id="tenant-a",
        event_type="closure_decided",
        actor_id="engineering_owner",
        payload={"case_id": "case-launch-gateway", "terminal_certificate_ref": "terminal-closure-1"},
        evidence_refs=("terminal:terminal-closure-1",),
    )
    report = verify_orgos_event_log_file(event_log_path=event_log_path, signing_secret="orgos-secret")
    assert report["valid"] is True
    return [report["trust_ledger_artifact"]]


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


def _base_artifacts() -> tuple[TrustLedgerEvidenceArtifact, ...]:
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
            required=False,
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
            required=False,
        ),
    )


def _hash(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"
