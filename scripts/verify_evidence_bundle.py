"""Verify signed Mullusi trust-ledger evidence bundles.

Purpose: validate schema, bundle hash, and HMAC signature for exported
    terminal-closure evidence bundles.
Governance scope: offline trust-ledger bundle verification only.
Dependencies: gateway.trust_ledger and schemas/trust_ledger_bundle.schema.json.
Invariants:
  - Bundle JSON is schema-validated before signature verification.
  - Missing signing secret fails closed.
  - Tampered bundle content fails hash or signature verification.
  - Raw artifact payloads are not required for bundle-level verification.
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

from gateway.trust_ledger import TrustLedger, TrustLedgerBundle  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_bundle.schema.json"


def verify_bundle_file(
    *,
    bundle_path: Path,
    signing_secret: str,
    strict: bool = False,
) -> dict[str, Any]:
    """Verify one evidence bundle file and return a bounded report."""
    if not signing_secret:
        return {
            "valid": False,
            "reason": "signing_secret_required",
            "bundle_id": "",
            "schema_valid": False,
            "schema_errors": ["signing secret is required"],
        }
    try:
        raw = json.loads(bundle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {
            "valid": False,
            "reason": "bundle_read_failed",
            "bundle_id": "",
            "schema_valid": False,
            "schema_errors": [type(exc).__name__],
        }
    if not isinstance(raw, dict):
        return {
            "valid": False,
            "reason": "bundle_json_must_be_object",
            "bundle_id": "",
            "schema_valid": False,
            "schema_errors": ["bundle JSON must be an object"],
        }
    schema_errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), raw)
    if schema_errors:
        return {
            "valid": False,
            "reason": "schema_validation_failed",
            "bundle_id": str(raw.get("bundle_id", "")),
            "schema_valid": False,
            "schema_errors": schema_errors if strict else schema_errors[:10],
        }
    try:
        bundle = TrustLedgerBundle(
            bundle_id=str(raw["bundle_id"]),
            tenant_id=str(raw["tenant_id"]),
            command_id=str(raw["command_id"]),
            terminal_certificate_id=str(raw["terminal_certificate_id"]),
            deployment_id=str(raw["deployment_id"]),
            commit_sha=str(raw["commit_sha"]),
            hash_chain_root=str(raw["hash_chain_root"]),
            evidence_refs=list(raw["evidence_refs"]),
            issued_at=str(raw["issued_at"]),
            external_anchor_ref=str(raw["external_anchor_ref"]),
            external_anchor_status=str(raw["external_anchor_status"]),
            bundle_hash=str(raw["bundle_hash"]),
            signature_key_id=str(raw["signature_key_id"]),
            signature=str(raw["signature"]),
            metadata=dict(raw.get("metadata", {})),
        )
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "valid": False,
            "reason": str(exc),
            "bundle_id": str(raw.get("bundle_id", "")),
            "schema_valid": True,
            "schema_errors": [],
        }
    verification = TrustLedger().verify(bundle, signing_secret=signing_secret)
    return {
        "valid": verification.verified,
        "reason": verification.reason,
        "bundle_id": verification.bundle_id,
        "schema_valid": True,
        "schema_errors": [],
        "expected_bundle_hash": verification.expected_bundle_hash,
        "observed_bundle_hash": verification.observed_bundle_hash,
        "signature_key_id": verification.signature_key_id,
        "command_id": bundle.command_id,
        "terminal_certificate_id": bundle.terminal_certificate_id,
        "deployment_id": bundle.deployment_id,
        "commit_sha": bundle.commit_sha,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a signed Mullusi evidence bundle")
    parser.add_argument("--bundle", required=True, type=Path, help="Path to trust-ledger bundle JSON")
    parser.add_argument(
        "--signing-secret",
        default=os.environ.get("MULLU_TRUST_LEDGER_SECRET", ""),
        help="HMAC signing secret; defaults to MULLU_TRUST_LEDGER_SECRET",
    )
    parser.add_argument("--strict", action="store_true", help="Return all schema errors")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args(argv)

    report = verify_bundle_file(
        bundle_path=args.bundle,
        signing_secret=args.signing_secret,
        strict=args.strict,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "valid" if report["valid"] else "invalid"
        print(f"evidence bundle {status}: {report['reason']}")
        if report.get("bundle_id"):
            print(f"bundle_id: {report['bundle_id']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
