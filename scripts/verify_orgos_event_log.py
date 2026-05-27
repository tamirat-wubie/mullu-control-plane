"""Verify signed Mullu OrgOS case-event JSONL logs.

Purpose: validate OrgOS case-event schema shape, hash-chain continuity, event
    receipt binding, and HMAC receipt signatures for offline review.
Governance scope: OrgOS EvidenceGraph replay verification and trust-ledger
    optional artifact export only.
Dependencies: gateway.orgos_kernel, gateway.trust_ledger, and OrgOS JSON
    schemas.
Invariants:
  - JSONL event records are schema-validated before receipt verification.
  - Missing signing secret fails closed.
  - Payload, evidence, event hash, receipt hash, and receipt signature drift
    are reported explicitly.
  - Exported trust-ledger artifact is optional and is not terminal closure.
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

from gateway.orgos_kernel import JsonlOrgCaseEventLog, OrgCaseEvent, OrgCaseEventReceiptConfig  # noqa: E402
from gateway.trust_ledger import TrustLedgerEvidenceArtifact  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


EVENT_SCHEMA_PATH = ROOT / "schemas" / "orgos_case_event.schema.json"
REPORT_SCHEMA_PATH = ROOT / "schemas" / "orgos_case_event_log_verification_report.schema.json"


def verify_orgos_event_log_file(
    *,
    event_log_path: Path,
    signing_secret: str,
    strict: bool = False,
    signature_key_id: str = "orgos-event-offline-verifier",
) -> dict[str, Any]:
    """Verify one OrgOS JSONL event log and return a bounded report."""
    if not signing_secret:
        return _report(
            valid=False,
            reason="signing_secret_required",
            schema_valid=False,
            schema_errors=["signing secret is required"],
        )
    schema_result = _validate_jsonl_schema(event_log_path, strict=strict)
    if schema_result["reason"]:
        return _report(
            valid=False,
            reason=schema_result["reason"],
            schema_valid=False,
            schema_errors=schema_result["schema_errors"],
        )
    try:
        page = JsonlOrgCaseEventLog(
            event_log_path,
            clock=lambda: "offline-orgos-verifier",
            receipt_config=OrgCaseEventReceiptConfig(
                signing_secret=signing_secret,
                signature_key_id=signature_key_id,
            ),
        ).list(limit=10000)
    except (OSError, TypeError, ValueError, TimeoutError) as exc:
        return _report(
            valid=False,
            reason="event_log_verification_failed",
            schema_valid=True,
            schema_errors=[],
            verification_errors=[str(exc)],
        )
    events = tuple(sorted(page.events, key=_event_sequence))
    if not events:
        return _report(
            valid=False,
            reason="event_log_empty",
            schema_valid=True,
            schema_errors=[],
            verification_errors=["event log contains no events"],
        )
    first = events[0]
    latest = events[-1]
    return _report(
        valid=True,
        reason="verified",
        schema_valid=True,
        schema_errors=[],
        event_count=len(events),
        first_event_id=first.event_id,
        latest_event_id=latest.event_id,
        latest_event_hash=latest.event_hash,
        latest_receipt_id=latest.receipt.receipt_id,
        signature_key_ids=sorted({event.receipt.signature_key_id for event in events}),
        anchor_statuses=sorted({event.receipt.external_anchor_status for event in events}),
        trust_ledger_artifact=_trust_ledger_artifact(latest),
    )


def _validate_jsonl_schema(event_log_path: Path, *, strict: bool) -> dict[str, Any]:
    schema_errors: list[str] = []
    event_schema = _load_schema(EVENT_SCHEMA_PATH)
    try:
        lines = event_log_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "reason": "event_log_read_failed",
            "schema_errors": [type(exc).__name__],
        }
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            schema_errors.append(f"line_{line_number}:json:{exc.msg}")
            continue
        if not isinstance(payload, dict):
            schema_errors.append(f"line_{line_number}:event JSON must be an object")
            continue
        schema_errors.extend(
            f"line_{line_number}:{error}"
            for error in _validate_schema_instance(event_schema, payload)
        )
    if schema_errors:
        return {
            "reason": "schema_validation_failed",
            "schema_errors": schema_errors if strict else schema_errors[:10],
        }
    return {"reason": "", "schema_errors": []}


def _trust_ledger_artifact(event: OrgCaseEvent) -> dict[str, Any]:
    artifact = TrustLedgerEvidenceArtifact(
        artifact_type="orgos_event_receipt",
        artifact_id=event.receipt.receipt_id,
        artifact_hash=f"sha256:{event.receipt.receipt_hash}",
        evidence_ref=f"proof://orgos/case-events/{event.event_id}",
        required=False,
        metadata={
            "case_id": event.case_id,
            "tenant_id": event.tenant_id,
            "event_hash": event.event_hash,
            "signature_key_id": event.receipt.signature_key_id,
            "external_anchor_status": event.receipt.external_anchor_status,
            "event_receipt_is_not_terminal_closure": True,
        },
    )
    return artifact.to_json_dict()


def _report(
    *,
    valid: bool,
    reason: str,
    schema_valid: bool,
    schema_errors: list[str],
    verification_errors: list[str] | None = None,
    event_count: int = 0,
    first_event_id: str = "",
    latest_event_id: str = "",
    latest_event_hash: str = "",
    latest_receipt_id: str = "",
    signature_key_ids: list[str] | None = None,
    anchor_statuses: list[str] | None = None,
    trust_ledger_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "valid": valid,
        "reason": reason,
        "schema_valid": schema_valid,
        "schema_errors": schema_errors,
        "verification_errors": verification_errors or [],
        "event_count": event_count,
        "first_event_id": first_event_id,
        "latest_event_id": latest_event_id,
        "latest_event_hash": latest_event_hash,
        "latest_receipt_id": latest_receipt_id,
        "signature_key_ids": signature_key_ids or [],
        "anchor_statuses": anchor_statuses or [],
        "trust_ledger_artifact": trust_ledger_artifact,
    }


def _event_sequence(event: OrgCaseEvent) -> int:
    try:
        return int(event.event_id.rsplit("-", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError("orgos_event_id_sequence_invalid") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a signed Mullu OrgOS event log")
    parser.add_argument("--event-log", required=True, type=Path, help="Path to OrgOS JSONL event log")
    parser.add_argument(
        "--signing-secret",
        default=os.environ.get("MULLU_ORGOS_EVENT_SIGNING_SECRET", ""),
        help="HMAC signing secret; defaults to MULLU_ORGOS_EVENT_SIGNING_SECRET",
    )
    parser.add_argument(
        "--signature-key-id",
        default=os.environ.get("MULLU_ORGOS_EVENT_SIGNATURE_KEY_ID", "orgos-event-offline-verifier"),
        help="Verifier-local key id used to instantiate the receipt contract",
    )
    parser.add_argument("--strict", action="store_true", help="Return all schema errors")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args(argv)

    report = verify_orgos_event_log_file(
        event_log_path=args.event_log,
        signing_secret=args.signing_secret,
        signature_key_id=args.signature_key_id,
        strict=args.strict,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "valid" if report["valid"] else "invalid"
        print(f"orgos event log {status}: {report['reason']}")
        if report.get("latest_event_id"):
            print(f"latest_event_id: {report['latest_event_id']}")
        if report.get("latest_receipt_id"):
            print(f"latest_receipt_id: {report['latest_receipt_id']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
