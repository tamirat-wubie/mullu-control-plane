#!/usr/bin/env python3
"""Verify Universal Symbol lifecycle evidence references without authority.

Purpose: inspect collected receipt-store lifecycle evidence references for
structural completeness while keeping lifecycle recording and runtime authority
blocked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lifecycle evidence receipt validator and Foundation Mode receipt
template.
Invariants:
  - Verification of reference shape is not lifecycle authority.
  - Template placeholder refs do not count as collected live evidence.
  - Repository-relative refs must stay inside the workspace and exist.
  - Raw secrets, connector calls, runtime dispatch, mutation, receipt append,
    and terminal closure remain denied.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.produce_universal_symbol_receipt_store_lifecycle_evidence_receipt import (  # noqa: E402
    EVIDENCE_KINDS,
    REF_PATTERN,
)
from scripts.validate_universal_symbol_receipt_store_lifecycle_evidence_receipt import (  # noqa: E402
    AUTHORITY_DENIAL_FIELDS,
    DEFAULT_RECEIPT_PATH,
    UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError,
    load_json_object,
    validate_universal_symbol_receipt_store_lifecycle_evidence_receipt,
)


EXPECTED_REF_SCHEMES: Mapping[str, tuple[str, ...]] = {
    "active_grant_identity": ("grant://",),
    "reapproval_window": ("temporal://",),
    "expiry_evidence": ("expiry://",),
    "revocation_request": ("revocation://",),
    "revocation_effect_boundary": ("effect-boundary://",),
    "replacement_decision": ("approval-decision://", "receipt://"),
    "lifecycle_audit_receipt": ("audit://", "receipt://"),
}

LOCAL_CONTENT_KIND_MARKERS: Mapping[str, tuple[str, ...]] = {
    "active_grant_identity": ("active-grant", "active_approval", "operator-approval"),
    "reapproval_window": ("reapproval", "temporal"),
    "expiry_evidence": ("expiry", "expiration"),
    "revocation_request": ("revocation",),
    "revocation_effect_boundary": ("effect-boundary", "effect_boundary", "revocation"),
    "replacement_decision": ("replacement", "approval-decision"),
    "lifecycle_audit_receipt": ("lifecycle-audit", "lifecycle_audit", "audit"),
}


class UniversalSymbolLifecycleEvidenceRefVerificationError(ValueError):
    """Raised when lifecycle evidence refs fail structural verification."""


def verify_lifecycle_evidence_refs(
    *,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    template_path: Path = DEFAULT_RECEIPT_PATH,
) -> dict[str, Any]:
    """Verify lifecycle evidence references without granting authority.

    Input contract: receipt_path points to a lifecycle evidence receipt.
    Output contract: returns a non-authorizing structural verification report.
    Error contract: malformed receipts, authority drift, raw secret-like refs,
    and missing repo-local refs raise a causal verification error.
    """

    validation_report = validate_universal_symbol_receipt_store_lifecycle_evidence_receipt(receipt_path)
    receipt = load_json_object(receipt_path)
    template = load_json_object(template_path)
    template_refs = _template_refs_by_kind(template)

    _verify_authority_denied(receipt)
    verified_kinds: list[str] = []
    placeholder_kinds: list[str] = []
    ref_reports: list[dict[str, Any]] = []

    for requirement in _requirements(receipt):
        evidence_kind = str(requirement.get("evidence_kind", ""))
        evidence_ref = str(requirement.get("required_evidence_ref", ""))
        if evidence_kind not in EVIDENCE_KINDS:
            raise UniversalSymbolLifecycleEvidenceRefVerificationError(
                f"{evidence_kind}: evidence kind is not registered"
            )
        content_verified = _verify_ref_shape(evidence_kind, evidence_ref)
        is_placeholder = evidence_ref == template_refs.get(evidence_kind, "")
        if is_placeholder:
            placeholder_kinds.append(evidence_kind)
        else:
            verified_kinds.append(evidence_kind)
        ref_reports.append(
            {
                "evidence_kind": evidence_kind,
                "evidence_ref": evidence_ref,
                "placeholder_ref": is_placeholder,
                "local_file_ref": "://" not in evidence_ref,
                "content_verified": content_verified and not is_placeholder,
                "structurally_verified": not is_placeholder,
            }
        )

    missing_kinds = sorted(set(EVIDENCE_KINDS) - {item["evidence_kind"] for item in ref_reports})
    if missing_kinds:
        raise UniversalSymbolLifecycleEvidenceRefVerificationError(
            "missing lifecycle evidence kinds: " + ", ".join(missing_kinds)
        )
    status = (
        "all_refs_structurally_verified_non_authorizing"
        if len(verified_kinds) == len(EVIDENCE_KINDS)
        else "blocked_placeholder_or_missing_lifecycle_evidence"
    )
    return {
        "valid": True,
        "status": status,
        "receipt_path": _repo_relative(receipt_path),
        "schema_validation": validation_report,
        "verified_evidence_kinds": verified_kinds,
        "placeholder_evidence_kinds": placeholder_kinds,
        "evidence_ref_reports": ref_reports,
        "proof_state_after_verification": "Unknown",
        "lifecycle_recording_allowed": False,
        "authority_granted": False,
    }


def _requirements(receipt: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    requirements = receipt.get("required_live_evidence")
    if not isinstance(requirements, list):
        raise UniversalSymbolLifecycleEvidenceRefVerificationError("required_live_evidence must be a list")
    return [item for item in requirements if isinstance(item, Mapping)]


def _template_refs_by_kind(template: Mapping[str, Any]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for requirement in _requirements(template):
        refs[str(requirement.get("evidence_kind", ""))] = str(requirement.get("required_evidence_ref", ""))
    return refs


def _verify_authority_denied(receipt: Mapping[str, Any]) -> None:
    denials = receipt.get("authority_denials")
    if not isinstance(denials, Mapping):
        raise UniversalSymbolLifecycleEvidenceRefVerificationError("authority_denials must be present")
    drifted = sorted(field_name for field_name in AUTHORITY_DENIAL_FIELDS if denials.get(field_name) is not False)
    if drifted:
        raise UniversalSymbolLifecycleEvidenceRefVerificationError(
            "authority denial drift: " + ", ".join(drifted)
        )
    if receipt.get("lifecycle_evidence_receipt_is_not_lifecycle_authority") is not True:
        raise UniversalSymbolLifecycleEvidenceRefVerificationError("lifecycle evidence receipt claims authority")


def _verify_ref_shape(evidence_kind: str, evidence_ref: str) -> bool:
    if not evidence_ref or len(evidence_ref) > 256 or not REF_PATTERN.fullmatch(evidence_ref):
        raise UniversalSymbolLifecycleEvidenceRefVerificationError(
            f"{evidence_kind}: evidence ref shape is invalid"
        )
    lowered = evidence_ref.lower()
    secret_markers = (
        "-----begin",
        "bearer",
        "access_token",
        "refresh_token",
        "password",
        "api_key",
        "private_key",
    )
    if any(marker in lowered for marker in secret_markers):
        raise UniversalSymbolLifecycleEvidenceRefVerificationError(
            f"{evidence_kind}: raw secret-like evidence ref is forbidden"
        )
    if "://" not in evidence_ref:
        _verify_repo_relative_ref(evidence_kind, evidence_ref)
        return True
    expected_prefixes = EXPECTED_REF_SCHEMES.get(evidence_kind, ())
    if expected_prefixes and not evidence_ref.startswith(expected_prefixes):
        raise UniversalSymbolLifecycleEvidenceRefVerificationError(
            f"{evidence_kind}: evidence ref scheme does not match evidence kind"
        )
    return False


def _verify_repo_relative_ref(evidence_kind: str, evidence_ref: str) -> None:
    evidence_path = Path(evidence_ref)
    if evidence_path.is_absolute():
        raise UniversalSymbolLifecycleEvidenceRefVerificationError(
            f"{evidence_kind}: evidence ref must be repository-relative"
        )
    resolved = (WORKSPACE_ROOT / evidence_path).resolve()
    root = WORKSPACE_ROOT.resolve()
    if root not in resolved.parents and resolved != root:
        raise UniversalSymbolLifecycleEvidenceRefVerificationError(
            f"{evidence_kind}: evidence ref escapes repository"
        )
    if not resolved.exists():
        raise UniversalSymbolLifecycleEvidenceRefVerificationError(
            f"{evidence_kind}: repository-relative evidence ref missing: {evidence_ref}"
        )
    _verify_local_json_content(evidence_kind, evidence_ref, resolved)


def _verify_local_json_content(evidence_kind: str, evidence_ref: str, resolved: Path) -> None:
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise UniversalSymbolLifecycleEvidenceRefVerificationError(
            f"{evidence_kind}: repository-relative evidence ref must be JSON: {evidence_ref}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise UniversalSymbolLifecycleEvidenceRefVerificationError(
            f"{evidence_kind}: repository-relative evidence ref must contain a JSON object"
        )
    content_index = _content_index(payload)
    if not any(marker in content_index for marker in LOCAL_CONTENT_KIND_MARKERS.get(evidence_kind, ())):
        raise UniversalSymbolLifecycleEvidenceRefVerificationError(
            f"{evidence_kind}: repository-relative evidence content does not match evidence kind"
        )
    denials = payload.get("authority_denials")
    if isinstance(denials, Mapping):
        drifted = sorted(field_name for field_name, field_value in denials.items() if field_value is not False)
        if drifted:
            raise UniversalSymbolLifecycleEvidenceRefVerificationError(
                f"{evidence_kind}: local evidence authority denial drift: " + ", ".join(drifted)
            )
    forbidden_keys = _forbidden_payload_keys(payload)
    if forbidden_keys:
        raise UniversalSymbolLifecycleEvidenceRefVerificationError(
            f"{evidence_kind}: local evidence contains forbidden raw material keys: "
            + ", ".join(forbidden_keys)
        )


def _content_index(payload: Mapping[str, Any]) -> str:
    fields = (
        "receipt_id",
        "witness_id",
        "grant_id",
        "evidence_id",
        "receipt_scope",
        "witness_scope",
        "evidence_kind",
    )
    values = [str(payload.get(field_name, "")).lower() for field_name in fields]
    return " ".join(values)


def _forbidden_payload_keys(value: Any, prefix: str = "") -> list[str]:
    forbidden_names = {
        "raw_payload",
        "raw_payload_value",
        "raw_secret",
        "secret_value",
        "access_token",
        "refresh_token",
        "private_key",
        "password",
    }
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_name = str(key)
            key_path = f"{prefix}.{key_name}" if prefix else key_name
            if key_name.lower() in forbidden_names:
                found.append(key_path)
            found.extend(_forbidden_payload_keys(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_payload_keys(child, f"{prefix}[{index}]"))
    return found


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for non-authorizing lifecycle evidence verification."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--template", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = verify_lifecycle_evidence_refs(receipt_path=args.receipt, template_path=args.template)
    except (
        UniversalSymbolLifecycleEvidenceRefVerificationError,
        UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError,
    ) as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_lifecycle_evidence_ref_verifier: {exc}")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    if args.strict and report["status"] != "all_refs_structurally_verified_non_authorizing":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
