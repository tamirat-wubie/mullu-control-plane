"""Gateway trust ledger external anchor receipt tests.

Purpose: verify trust bundles can emit signed external proof anchor receipts
that bind command, execution, verification, terminal closure, and optional
supporting evidence artifacts.
Governance scope: external proof anchoring, typed artifact roots, terminal
closure binding, signature verification, tamper detection, and schema contract.
Dependencies: gateway.trust_ledger and schemas/trust_ledger_anchor_receipt.schema.json.
Invariants:
  - Anchor receipts are not terminal closure certificates.
  - Required artifact classes are present before anchoring.
  - Artifact roots and HMAC signatures detect post-issue mutation.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from gateway.trust_ledger import (
    ExternalProofAnchorReceipt,
    TrustLedger,
    TrustLedgerBundle,
    TrustLedgerBundleDraft,
    TrustLedgerEvidenceArtifact,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_anchor_receipt.schema.json"


def test_trust_ledger_anchor_receipt_binds_required_artifacts() -> None:
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
    verification = ledger.verify_anchor_receipt(
        receipt,
        bundle=bundle,
        artifacts=artifacts,
        signing_secret="anchor-secret",
    )

    assert verification.verified is True
    assert verification.reason == "anchor_verified"
    assert receipt.anchor_receipt_id.startswith("trust-anchor-receipt-")
    assert receipt.artifact_count == len(artifacts)
    assert receipt.signature.startswith("hmac-sha256:")
    assert receipt.bundle_hash == bundle.bundle_hash
    assert receipt.artifact_root_hash != bundle.bundle_hash
    assert receipt.metadata["anchor_receipt_is_not_terminal_closure"] is True


def test_trust_ledger_anchor_receipt_detects_tampered_artifact_root() -> None:
    ledger = TrustLedger()
    bundle = _bundle()
    artifacts = _artifacts()
    receipt = _anchor_receipt(ledger, bundle, artifacts)
    tampered_artifacts = (
        replace(artifacts[0], artifact_hash="sha256:mutated-command"),
        *artifacts[1:],
    )

    verification = ledger.verify_anchor_receipt(
        receipt,
        bundle=bundle,
        artifacts=tampered_artifacts,
        signing_secret="anchor-secret",
    )

    assert verification.verified is False
    assert verification.reason == "artifact_root_hash_mismatch"
    assert verification.expected_bundle_hash != verification.observed_bundle_hash
    assert verification.signature_key_id == "anchor-key"


def test_trust_ledger_anchor_receipt_rejects_missing_terminal_artifact() -> None:
    ledger = TrustLedger()
    bundle = _bundle()
    artifacts = tuple(
        artifact
        for artifact in _artifacts()
        if artifact.artifact_type != "terminal_certificate"
    )

    try:
        _anchor_receipt(ledger, bundle, artifacts)
    except ValueError as exc:
        error = str(exc)
    else:
        error = ""

    assert error == "anchor_required_artifacts_missing:terminal_certificate"
    assert len(artifacts) == 6
    assert all(artifact.artifact_type != "terminal_certificate" for artifact in artifacts)


def test_trust_ledger_anchor_receipt_rejects_command_identity_drift() -> None:
    ledger = TrustLedger()
    bundle = _bundle()
    artifacts = _artifacts()
    receipt = _anchor_receipt(ledger, bundle, artifacts)
    drifted_artifacts = (
        replace(artifacts[0], artifact_id="command-2"),
        *artifacts[1:],
    )

    verification = ledger.verify_anchor_receipt(
        receipt,
        bundle=bundle,
        artifacts=drifted_artifacts,
        signing_secret="anchor-secret",
    )

    assert verification.verified is False
    assert verification.reason == "command_artifact_id_mismatch"
    assert verification.signature_key_id == "anchor-key"


def test_trust_ledger_anchor_receipt_validates_against_schema() -> None:
    ledger = TrustLedger()
    bundle = _bundle()
    receipt = _anchor_receipt(ledger, bundle, _artifacts())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), receipt.to_json_dict())

    assert errors == []
    assert receipt.to_json_dict()["metadata"]["anchor_receipt_is_not_terminal_closure"] is True
    assert receipt.to_json_dict()["external_anchor_status"] == "anchored"
    assert receipt.to_json_dict()["external_anchor_ref"] == "anchor://transparency-log/1"


def _anchor_receipt(
    ledger: TrustLedger,
    bundle: TrustLedgerBundle,
    artifacts: tuple[TrustLedgerEvidenceArtifact, ...],
) -> ExternalProofAnchorReceipt:
    return ledger.anchor_bundle(
        bundle,
        artifacts=artifacts,
        anchor_target="transparency_log",
        external_anchor_ref="anchor://transparency-log/1",
        external_anchor_status="anchored",
        anchored_at="2026-05-05T12:00:00+00:00",
        signing_secret="anchor-secret",
        signature_key_id="anchor-key",
    )


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
            artifact_hash="sha256:command-1",
            evidence_ref="proof://command-1",
        ),
        TrustLedgerEvidenceArtifact(
            artifact_type="approval",
            artifact_id="approval-1",
            artifact_hash="sha256:approval-1",
            evidence_ref="proof://approval-1",
        ),
        TrustLedgerEvidenceArtifact(
            artifact_type="execution_receipt",
            artifact_id="execution-1",
            artifact_hash="sha256:execution-1",
            evidence_ref="proof://execution-1",
        ),
        TrustLedgerEvidenceArtifact(
            artifact_type="verification_result",
            artifact_id="verification-1",
            artifact_hash="sha256:verification-1",
            evidence_ref="proof://verification-1",
        ),
        TrustLedgerEvidenceArtifact(
            artifact_type="effect_reconciliation",
            artifact_id="effect-reconciliation-1",
            artifact_hash="sha256:effect-reconciliation-1",
            evidence_ref="proof://effect-reconciliation-1",
        ),
        TrustLedgerEvidenceArtifact(
            artifact_type="terminal_certificate",
            artifact_id="terminal-closure-1",
            artifact_hash="sha256:terminal-closure-1",
            evidence_ref="proof://terminal-closure-1",
        ),
        TrustLedgerEvidenceArtifact(
            artifact_type="learning_decision",
            artifact_id="learning-admission-1",
            artifact_hash="sha256:learning-admission-1",
            evidence_ref="proof://learning-admission-1",
        ),
    )
