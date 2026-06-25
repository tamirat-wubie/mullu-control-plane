#!/usr/bin/env python3
"""Verify lane runtime authority evidence value refs without authority.

Purpose: structurally verify supplied lane evidence refs against their evidence
kind contracts while keeping lane runtime authority, runtime admission,
dispatch, receipt append, mutation, and terminal closure blocked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lane evidence value receipt validator and Foundation Mode
receipt template.
Invariants:
  - Verification of reference shape is not lane authority.
  - Template placeholder refs do not count as collected live evidence.
  - Repository-relative refs must stay inside the workspace and exist.
  - Raw secrets, connector calls, runtime dispatch, mutation, receipt append,
    and terminal closure remain denied.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_universal_symbol_lane_runtime_authority_evidence_value_receipt import (  # noqa: E402
    AUTHORITY_DENIAL_FIELDS,
    DEFAULT_RECEIPT_PATH,
    EVIDENCE_KINDS,
    LANES,
    UniversalSymbolLaneRuntimeAuthorityEvidenceValueReceiptError,
    load_json_object,
    validate_universal_symbol_lane_runtime_authority_evidence_value_receipt,
)


REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]*$")

EXPECTED_REF_SCHEMES: Mapping[str, tuple[str, ...]] = {
    "operator_approval": ("approval://", "receipt://"),
    "receipt_store_authority": ("receipt-store-authority://", "witness://", "receipt://"),
    "recovery_evidence": ("recovery://", "receipt://"),
    "audit_receipt": ("audit://", "receipt://"),
    "live_runtime_witness": ("witness://", "runtime-witness://", "receipt://"),
    "blocked_action_refs": ("blocked://", "receipt://"),
}

LOCAL_CONTENT_KIND_MARKERS: Mapping[str, tuple[str, ...]] = {
    "operator_approval": ("operator-approval", "operator_approval", "approval"),
    "receipt_store_authority": ("receipt-store-authority", "receipt_store_authority"),
    "recovery_evidence": ("recovery", "rollback"),
    "audit_receipt": ("audit",),
    "live_runtime_witness": ("live-runtime", "runtime-witness", "live_runtime"),
    "blocked_action_refs": ("blocked-action", "blocked_action", "denial"),
}


class UniversalSymbolLaneEvidenceValueRefVerificationError(ValueError):
    """Raised when lane evidence value refs fail structural verification."""


def verify_lane_evidence_value_refs(
    *,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    template_path: Path = DEFAULT_RECEIPT_PATH,
) -> dict[str, Any]:
    """Verify lane evidence refs without granting authority.

    Input contract: receipt_path points to a lane evidence value receipt.
    Output contract: returns a non-authorizing structural verification report.
    Error contract: malformed receipts, authority drift, raw secret-like refs,
    wrong evidence-kind schemes, and missing repo-local refs fail closed.
    """

    validation_report = validate_universal_symbol_lane_runtime_authority_evidence_value_receipt(receipt_path)
    receipt = load_json_object(receipt_path)
    template = load_json_object(template_path)
    template_refs = _template_refs_by_pair(template)

    _verify_authority_denied(receipt)
    verified_pairs: list[str] = []
    placeholder_pairs: list[str] = []
    value_ref_reports: list[dict[str, Any]] = []

    for item in _lane_value_items(receipt):
        lane_ref = str(item.get("lane_ref", ""))
        evidence_kind = str(item.get("evidence_kind", ""))
        supplied_ref = str(item.get("supplied_evidence_ref", ""))
        pair_key = _pair_key(lane_ref, evidence_kind)
        if lane_ref not in LANES:
            raise UniversalSymbolLaneEvidenceValueRefVerificationError(f"{lane_ref}: lane is not registered")
        if evidence_kind not in EVIDENCE_KINDS:
            raise UniversalSymbolLaneEvidenceValueRefVerificationError(
                f"{pair_key}: evidence kind is not registered"
            )
        is_placeholder = supplied_ref == template_refs.get(pair_key, "")
        content_verified = _verify_ref_shape(evidence_kind, supplied_ref, allow_input_placeholder=is_placeholder)
        if is_placeholder:
            placeholder_pairs.append(pair_key)
        else:
            verified_pairs.append(pair_key)
        value_ref_reports.append(
            {
                "lane_ref": lane_ref,
                "evidence_kind": evidence_kind,
                "supplied_evidence_ref": supplied_ref,
                "placeholder_ref": is_placeholder,
                "local_file_ref": "://" not in supplied_ref,
                "content_verified": content_verified and not is_placeholder,
                "structurally_verified": not is_placeholder,
            }
        )

    missing_pairs = sorted(_expected_pairs() - { _pair_key(item["lane_ref"], item["evidence_kind"]) for item in value_ref_reports })
    if missing_pairs:
        raise UniversalSymbolLaneEvidenceValueRefVerificationError(
            "missing lane evidence value refs: " + ", ".join(missing_pairs)
        )
    status = (
        "all_refs_structurally_verified_non_authorizing"
        if len(verified_pairs) == len(LANES) * len(EVIDENCE_KINDS)
        else "blocked_placeholder_or_missing_lane_evidence_values"
    )
    return {
        "valid": True,
        "status": status,
        "receipt_path": _repo_relative(receipt_path),
        "schema_validation": validation_report,
        "verified_value_pairs": verified_pairs,
        "placeholder_value_pairs": placeholder_pairs,
        "value_ref_reports": value_ref_reports,
        "proof_state_after_verification": "Unknown",
        "lane_runtime_authority_allowed": False,
        "runtime_admission_allowed": False,
        "receipt_append_allowed": False,
        "terminal_closure_allowed": False,
    }


def _lane_value_items(receipt: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    items = receipt.get("lane_value_items")
    if not isinstance(items, list):
        raise UniversalSymbolLaneEvidenceValueRefVerificationError("lane_value_items must be a list")
    return [item for item in items if isinstance(item, Mapping)]


def _template_refs_by_pair(template: Mapping[str, Any]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for item in _lane_value_items(template):
        refs[_pair_key(str(item.get("lane_ref", "")), str(item.get("evidence_kind", "")))] = str(
            item.get("supplied_evidence_ref", "")
        )
    return refs


def _verify_authority_denied(receipt: Mapping[str, Any]) -> None:
    denials = receipt.get("authority_denials")
    if not isinstance(denials, Mapping):
        raise UniversalSymbolLaneEvidenceValueRefVerificationError("authority_denials must be present")
    drifted = sorted(field_name for field_name in AUTHORITY_DENIAL_FIELDS if denials.get(field_name) is not False)
    if drifted:
        raise UniversalSymbolLaneEvidenceValueRefVerificationError(
            "authority denial drift: " + ", ".join(drifted)
        )
    if receipt.get("receipt_is_not_lane_authority") is not True:
        raise UniversalSymbolLaneEvidenceValueRefVerificationError("lane evidence value receipt claims authority")


def _verify_ref_shape(evidence_kind: str, evidence_ref: str, *, allow_input_placeholder: bool) -> bool:
    if not evidence_ref or len(evidence_ref) > 256 or not REF_PATTERN.fullmatch(evidence_ref):
        raise UniversalSymbolLaneEvidenceValueRefVerificationError(
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
        "token=",
        "secret=",
    )
    if any(marker in lowered for marker in secret_markers):
        raise UniversalSymbolLaneEvidenceValueRefVerificationError(
            f"{evidence_kind}: raw secret-like evidence ref is forbidden"
        )
    if "://" not in evidence_ref:
        _verify_repo_relative_ref(evidence_kind, evidence_ref)
        return True
    if allow_input_placeholder and evidence_ref.startswith("input://"):
        return False
    expected_prefixes = EXPECTED_REF_SCHEMES.get(evidence_kind, ())
    if expected_prefixes and not evidence_ref.startswith(expected_prefixes):
        raise UniversalSymbolLaneEvidenceValueRefVerificationError(
            f"{evidence_kind}: evidence ref scheme does not match evidence kind"
        )
    return False


def _verify_repo_relative_ref(evidence_kind: str, evidence_ref: str) -> None:
    evidence_path = Path(evidence_ref)
    if evidence_path.is_absolute():
        raise UniversalSymbolLaneEvidenceValueRefVerificationError(
            f"{evidence_kind}: evidence ref must be repository-relative"
        )
    resolved = (WORKSPACE_ROOT / evidence_path).resolve()
    root = WORKSPACE_ROOT.resolve()
    if root not in resolved.parents and resolved != root:
        raise UniversalSymbolLaneEvidenceValueRefVerificationError(
            f"{evidence_kind}: evidence ref escapes repository"
        )
    if not resolved.exists():
        raise UniversalSymbolLaneEvidenceValueRefVerificationError(
            f"{evidence_kind}: repository-relative evidence ref missing: {evidence_ref}"
        )
    _verify_local_json_content(evidence_kind, evidence_ref, resolved)


def _verify_local_json_content(evidence_kind: str, evidence_ref: str, resolved: Path) -> None:
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise UniversalSymbolLaneEvidenceValueRefVerificationError(
            f"{evidence_kind}: repository-relative evidence ref must be JSON: {evidence_ref}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise UniversalSymbolLaneEvidenceValueRefVerificationError(
            f"{evidence_kind}: repository-relative evidence ref must contain a JSON object"
        )
    content_index = _content_index(payload)
    if not any(marker in content_index for marker in LOCAL_CONTENT_KIND_MARKERS.get(evidence_kind, ())):
        raise UniversalSymbolLaneEvidenceValueRefVerificationError(
            f"{evidence_kind}: repository-relative evidence content does not match evidence kind"
        )
    denials = payload.get("authority_denials")
    if isinstance(denials, Mapping):
        drifted = sorted(field_name for field_name, field_value in denials.items() if field_value is not False)
        if drifted:
            raise UniversalSymbolLaneEvidenceValueRefVerificationError(
                f"{evidence_kind}: local evidence authority denial drift: " + ", ".join(drifted)
            )
    forbidden_keys = _forbidden_payload_keys(payload)
    if forbidden_keys:
        raise UniversalSymbolLaneEvidenceValueRefVerificationError(
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


def _expected_pairs() -> set[str]:
    return {_pair_key(lane_ref, evidence_kind) for lane_ref in LANES for evidence_kind in EVIDENCE_KINDS}


def _pair_key(lane_ref: str, evidence_kind: str) -> str:
    return f"{lane_ref}|{evidence_kind}"


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for non-authorizing lane evidence ref verification."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--template", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = verify_lane_evidence_value_refs(receipt_path=args.receipt, template_path=args.template)
    except (
        UniversalSymbolLaneEvidenceValueRefVerificationError,
        UniversalSymbolLaneRuntimeAuthorityEvidenceValueReceiptError,
    ) as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_lane_evidence_value_ref_verifier: {exc}")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    if args.strict and report["status"] != "all_refs_structurally_verified_non_authorizing":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
