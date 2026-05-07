"""Gateway trust ledger tests.

Purpose: verify signed evidence bundles bind terminal closure, deployment,
commit, audit root, evidence, and external anchor state.
Governance scope: trust ledger bundle issuance, signature verification,
terminal closure anchoring, tamper detection, and schema contract.
Dependencies: gateway.trust_ledger and schemas/trust_ledger_bundle.schema.json.
Invariants:
  - Bundles require terminal certificate ids and evidence refs.
  - External anchored bundles require an anchor reference.
  - Tampered bundle content fails verification.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from gateway.trust_ledger import TrustLedger, TrustLedgerBundleDraft


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_bundle.schema.json"


def test_trust_ledger_issues_and_verifies_signed_bundle() -> None:
    bundle = TrustLedger().issue(_draft(), signing_secret="secret", signature_key_id="local-key")
    verification = TrustLedger().verify(bundle, signing_secret="secret")

    assert verification.verified is True
    assert verification.reason == "verified"
    assert bundle.bundle_id.startswith("trust-bundle-")
    assert bundle.signature.startswith("hmac-sha256:")
    assert bundle.terminal_certificate_id == "terminal-closure-1"


def test_trust_ledger_detects_tampered_bundle_content() -> None:
    bundle = TrustLedger().issue(_draft(), signing_secret="secret", signature_key_id="local-key")
    tampered = replace(bundle, evidence_refs=[*bundle.evidence_refs, "proof://extra"])
    verification = TrustLedger().verify(tampered, signing_secret="secret")

    assert verification.verified is False
    assert verification.reason == "bundle_hash_mismatch"
    assert verification.expected_bundle_hash != verification.observed_bundle_hash


def test_trust_ledger_detects_wrong_secret_signature() -> None:
    bundle = TrustLedger().issue(_draft(), signing_secret="secret", signature_key_id="local-key")
    verification = TrustLedger().verify(bundle, signing_secret="wrong")

    assert verification.verified is False
    assert verification.reason == "signature_mismatch"
    assert verification.signature_key_id == "local-key"


def test_trust_ledger_requires_terminal_certificate_and_evidence() -> None:
    with pytest.raises(ValueError, match="terminal_certificate_id_required"):
        _draft(terminal_certificate_id="")
    with pytest.raises(ValueError, match="evidence_refs_required"):
        _draft(evidence_refs=())


def test_trust_ledger_requires_anchor_ref_when_anchored() -> None:
    with pytest.raises(ValueError, match="anchored_bundle_requires_external_anchor_ref"):
        _draft(external_anchor_status="anchored", external_anchor_ref="")


def test_trust_ledger_bundle_schema_exposes_signature_contract() -> None:
    bundle = TrustLedger().issue(
        _draft(external_anchor_status="anchored", external_anchor_ref="anchor://ledger/1"),
        signing_secret="secret",
        signature_key_id="local-key",
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(schema["required"]).issubset(asdict(bundle))
    assert schema["$id"] == "urn:mullusi:schema:trust-ledger-bundle:1"
    assert schema["properties"]["signature"]["pattern"] == "^hmac-sha256:.+"
    assert bundle.external_anchor_status == "anchored"
    assert bundle.external_anchor_ref == "anchor://ledger/1"


def _draft(**overrides: object) -> TrustLedgerBundleDraft:
    payload = {
        "tenant_id": "tenant-a",
        "command_id": "command-1",
        "terminal_certificate_id": "terminal-closure-1",
        "deployment_id": "deployment-2026-05-04",
        "commit_sha": "abc123",
        "hash_chain_root": "hash-root-1",
        "evidence_refs": ("proof://terminal-closure-1", "proof://audit-root-1"),
        "issued_at": "2026-05-04T16:30:00Z",
        "external_anchor_ref": "",
        "external_anchor_status": "not_requested",
        "metadata": {"surface": "trust_ledger"},
    }
    payload.update(overrides)
    return TrustLedgerBundleDraft(**payload)