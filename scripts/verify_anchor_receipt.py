"""Verify signed Mullusi trust-ledger external anchor receipts.

Purpose: validate exported trust-ledger bundle, external anchor receipt, and
typed evidence artifacts before running canonical anchor verification.
Governance scope: offline proof-anchor verification only.
Dependencies: gateway.trust_ledger and trust-ledger JSON schemas.
Invariants:
  - Bundle and anchor receipt JSON are schema-validated before signature checks.
  - Evidence artifacts are reconstructed through typed trust-ledger contracts.
  - Missing signing secret fails closed.
  - Artifact root, receipt id, receipt hash, and HMAC drift are reported explicitly.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.trust_ledger import (  # noqa: E402
    ExternalProofAnchorReceipt,
    TrustLedger,
    TrustLedgerBundle,
    TrustLedgerEvidenceArtifact,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


BUNDLE_SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_bundle.schema.json"
ANCHOR_RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_anchor_receipt.schema.json"


def verify_anchor_receipt_files(
    *,
    bundle_path: Path,
    receipt_path: Path,
    artifacts_path: Path,
    signing_secret: str,
    strict: bool = False,
) -> dict[str, Any]:
    """Verify one exported anchor receipt and return a bounded report."""
    if not signing_secret:
        return _report(
            valid=False,
            reason="signing_secret_required",
            schema_valid=False,
            schema_errors=["signing secret is required"],
        )
    bundle_raw = _read_json_object(bundle_path, "bundle")
    if bundle_raw["reason"]:
        return _report(**bundle_raw)
    receipt_raw = _read_json_object(receipt_path, "anchor_receipt")
    if receipt_raw["reason"]:
        return _report(**receipt_raw)
    artifacts_raw = _read_json_array(artifacts_path, "artifacts")
    if artifacts_raw["reason"]:
        return _report(**artifacts_raw)

    bundle_payload = bundle_raw["payload"]
    receipt_payload = receipt_raw["payload"]
    bundle_errors = _validate_schema_instance(_load_schema(BUNDLE_SCHEMA_PATH), bundle_payload)
    receipt_errors = _validate_schema_instance(_load_schema(ANCHOR_RECEIPT_SCHEMA_PATH), receipt_payload)
    schema_errors = [f"bundle:{error}" for error in bundle_errors]
    schema_errors.extend(f"anchor_receipt:{error}" for error in receipt_errors)
    if schema_errors:
        return _report(
            valid=False,
            reason="schema_validation_failed",
            bundle_id=str(bundle_payload.get("bundle_id", "")),
            anchor_receipt_id=str(receipt_payload.get("anchor_receipt_id", "")),
            schema_valid=False,
            schema_errors=schema_errors if strict else schema_errors[:10],
        )

    try:
        bundle = _bundle_from_payload(bundle_payload)
        receipt = _receipt_from_payload(receipt_payload)
        artifacts = _artifacts_from_payload(artifacts_raw["payload"])
    except (KeyError, TypeError, ValueError) as exc:
        return _report(
            valid=False,
            reason=str(exc),
            bundle_id=str(bundle_payload.get("bundle_id", "")),
            anchor_receipt_id=str(receipt_payload.get("anchor_receipt_id", "")),
            schema_valid=True,
            schema_errors=[],
        )

    verification = TrustLedger().verify_anchor_receipt(
        receipt,
        bundle=bundle,
        artifacts=artifacts,
        signing_secret=signing_secret,
    )
    return _report(
        valid=verification.verified,
        reason=verification.reason,
        bundle_id=verification.bundle_id,
        anchor_receipt_id=receipt.anchor_receipt_id,
        schema_valid=True,
        schema_errors=[],
        expected_bundle_hash=verification.expected_bundle_hash,
        observed_bundle_hash=verification.observed_bundle_hash,
        signature_key_id=verification.signature_key_id,
        command_id=bundle.command_id,
        terminal_certificate_id=bundle.terminal_certificate_id,
        artifact_count=len(artifacts),
    )


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    loaded = _read_json(path, label)
    if loaded["reason"]:
        return loaded
    if not isinstance(loaded["payload"], dict):
        return {
            "valid": False,
            "reason": f"{label}_json_must_be_object",
            "schema_valid": False,
            "schema_errors": [f"{label} JSON must be an object"],
        }
    return loaded


def _read_json_array(path: Path, label: str) -> dict[str, Any]:
    loaded = _read_json(path, label)
    if loaded["reason"]:
        return loaded
    if not isinstance(loaded["payload"], list):
        return {
            "valid": False,
            "reason": f"{label}_json_must_be_array",
            "schema_valid": False,
            "schema_errors": [f"{label} JSON must be an array"],
        }
    return loaded


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        return {"reason": "", "payload": json.loads(path.read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {
            "valid": False,
            "reason": f"{label}_read_failed",
            "schema_valid": False,
            "schema_errors": [type(exc).__name__],
        }


def _bundle_from_payload(payload: dict[str, Any]) -> TrustLedgerBundle:
    return TrustLedgerBundle(
        bundle_id=str(payload["bundle_id"]),
        tenant_id=str(payload["tenant_id"]),
        command_id=str(payload["command_id"]),
        terminal_certificate_id=str(payload["terminal_certificate_id"]),
        deployment_id=str(payload["deployment_id"]),
        commit_sha=str(payload["commit_sha"]),
        hash_chain_root=str(payload["hash_chain_root"]),
        evidence_refs=list(payload["evidence_refs"]),
        issued_at=str(payload["issued_at"]),
        external_anchor_ref=str(payload["external_anchor_ref"]),
        external_anchor_status=str(payload["external_anchor_status"]),
        bundle_hash=str(payload["bundle_hash"]),
        signature_key_id=str(payload["signature_key_id"]),
        signature=str(payload["signature"]),
        metadata=dict(payload.get("metadata", {})),
    )


def _receipt_from_payload(payload: dict[str, Any]) -> ExternalProofAnchorReceipt:
    return ExternalProofAnchorReceipt(
        anchor_receipt_id=str(payload["anchor_receipt_id"]),
        bundle_id=str(payload["bundle_id"]),
        tenant_id=str(payload["tenant_id"]),
        command_id=str(payload["command_id"]),
        terminal_certificate_id=str(payload["terminal_certificate_id"]),
        anchor_target=str(payload["anchor_target"]),
        external_anchor_ref=str(payload["external_anchor_ref"]),
        external_anchor_status=str(payload["external_anchor_status"]),
        bundle_hash=str(payload["bundle_hash"]),
        artifact_root_hash=str(payload["artifact_root_hash"]),
        hash_chain_root=str(payload["hash_chain_root"]),
        artifact_count=int(payload["artifact_count"]),
        required_artifact_types=list(payload["required_artifact_types"]),
        anchored_at=str(payload["anchored_at"]),
        signature_key_id=str(payload["signature_key_id"]),
        signature=str(payload["signature"]),
        anchor_receipt_hash=str(payload["anchor_receipt_hash"]),
        metadata=dict(payload["metadata"]),
    )


def _artifacts_from_payload(payload: list[Any]) -> tuple[TrustLedgerEvidenceArtifact, ...]:
    artifacts: list[TrustLedgerEvidenceArtifact] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"artifact_{index}_json_must_be_object")
        artifacts.append(
            TrustLedgerEvidenceArtifact(
                artifact_type=str(item["artifact_type"]),
                artifact_id=str(item["artifact_id"]),
                artifact_hash=str(item["artifact_hash"]),
                evidence_ref=str(item["evidence_ref"]),
                required=bool(item.get("required", True)),
                metadata=dict(item.get("metadata", {})),
            )
        )
    return tuple(artifacts)


def _report(
    *,
    valid: bool,
    reason: str,
    bundle_id: str = "",
    anchor_receipt_id: str = "",
    schema_valid: bool,
    schema_errors: list[str],
    expected_bundle_hash: str = "",
    observed_bundle_hash: str = "",
    signature_key_id: str = "",
    command_id: str = "",
    terminal_certificate_id: str = "",
    artifact_count: int = 0,
) -> dict[str, Any]:
    return {
        "valid": valid,
        "reason": reason,
        "bundle_id": bundle_id,
        "anchor_receipt_id": anchor_receipt_id,
        "schema_valid": schema_valid,
        "schema_errors": schema_errors,
        "expected_bundle_hash": expected_bundle_hash,
        "observed_bundle_hash": observed_bundle_hash,
        "signature_key_id": signature_key_id,
        "command_id": command_id,
        "terminal_certificate_id": terminal_certificate_id,
        "artifact_count": artifact_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a signed Mullusi external anchor receipt")
    parser.add_argument("--bundle", required=True, type=Path, help="Path to trust-ledger bundle JSON")
    parser.add_argument("--receipt", required=True, type=Path, help="Path to external anchor receipt JSON")
    parser.add_argument("--artifacts", required=True, type=Path, help="Path to evidence artifact array JSON")
    parser.add_argument(
        "--signing-secret",
        default=os.environ.get("MULLU_TRUST_LEDGER_ANCHOR_SECRET", ""),
        help="HMAC signing secret; defaults to MULLU_TRUST_LEDGER_ANCHOR_SECRET",
    )
    parser.add_argument("--strict", action="store_true", help="Return all schema errors")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args(argv)

    report = verify_anchor_receipt_files(
        bundle_path=args.bundle,
        receipt_path=args.receipt,
        artifacts_path=args.artifacts,
        signing_secret=args.signing_secret,
        strict=args.strict,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "valid" if report["valid"] else "invalid"
        print(f"anchor receipt {status}: {report['reason']}")
        if report.get("anchor_receipt_id"):
            print(f"anchor_receipt_id: {report['anchor_receipt_id']}")
        if report.get("bundle_id"):
            print(f"bundle_id: {report['bundle_id']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
