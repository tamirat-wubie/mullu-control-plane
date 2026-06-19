#!/usr/bin/env python3
"""Produce a Universal Symbol receipt-store lifecycle evidence receipt.

Purpose: admit lifecycle evidence references into the Foundation Mode receipt
without granting lifecycle authority or recording receipt-store lifecycle state.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lifecycle evidence receipt template and validator.
Invariants:
  - Collected evidence references do not become lifecycle authority.
  - Required evidence remains ProofState Unknown until a verifier validates it.
  - Raw payloads, raw secrets, connector calls, runtime dispatch, state
    mutation, receipt-store append, and terminal closure remain denied.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import sys
from collections.abc import Callable
from typing import Any, Mapping


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_universal_symbol_receipt_store_lifecycle_evidence_receipt import (  # noqa: E402
    DEFAULT_RECEIPT_PATH,
    UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError,
    load_json_object,
    validate_universal_symbol_receipt_store_lifecycle_evidence_receipt,
)


DEFAULT_OUTPUT = WORKSPACE_ROOT / ".change_assurance" / "universal_symbol_lifecycle_evidence_receipt.json"
REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]*$")

EVIDENCE_KINDS: tuple[str, ...] = (
    "active_grant_identity",
    "reapproval_window",
    "expiry_evidence",
    "revocation_request",
    "revocation_effect_boundary",
    "replacement_decision",
    "lifecycle_audit_receipt",
)

ENVIRONMENT_REF_NAMES: Mapping[str, str] = {
    "active_grant_identity": "MULLU_LIFECYCLE_ACTIVE_GRANT_REF",
    "reapproval_window": "MULLU_LIFECYCLE_REAPPROVAL_WINDOW_REF",
    "expiry_evidence": "MULLU_LIFECYCLE_EXPIRY_EVIDENCE_REF",
    "revocation_request": "MULLU_LIFECYCLE_REVOCATION_REQUEST_REF",
    "revocation_effect_boundary": "MULLU_LIFECYCLE_REVOCATION_EFFECT_BOUNDARY_REF",
    "replacement_decision": "MULLU_LIFECYCLE_REPLACEMENT_DECISION_REF",
    "lifecycle_audit_receipt": "MULLU_LIFECYCLE_AUDIT_RECEIPT_REF",
}

PRODUCER_EVIDENCE_REFS: tuple[str, ...] = (
    "scripts/produce_universal_symbol_receipt_store_lifecycle_evidence_receipt.py",
    "tests/test_produce_universal_symbol_receipt_store_lifecycle_evidence_receipt.py",
)


class UniversalSymbolLifecycleEvidenceProducerError(ValueError):
    """Raised when lifecycle evidence reference admission fails closed."""


def produce_lifecycle_evidence_receipt(
    *,
    evidence_refs: Mapping[str, str] | None = None,
    output_path: Path = DEFAULT_OUTPUT,
    template_path: Path = DEFAULT_RECEIPT_PATH,
    clock: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Write a non-authorizing lifecycle evidence receipt.

    Input contract: evidence_refs maps each required evidence kind to a
    repository-relative or governed URI reference.
    Output contract: returns the written receipt and an admission report.
    Error contract: invalid evidence kinds or raw secret-like references raise
    UniversalSymbolLifecycleEvidenceProducerError before writing output.
    """

    supplied_refs = dict(evidence_refs or _environment_evidence_refs(os.environ))
    unknown_kinds = sorted(set(supplied_refs) - set(EVIDENCE_KINDS))
    if unknown_kinds:
        raise UniversalSymbolLifecycleEvidenceProducerError(
            "unknown lifecycle evidence kinds: " + ", ".join(unknown_kinds)
        )

    template = load_json_object(template_path)
    receipt = copy.deepcopy(template)
    receipt["generated_at"] = (clock or _validation_clock)()

    collected_kinds: list[str] = []
    missing_kinds: list[str] = []
    for requirement in receipt["required_live_evidence"]:
        evidence_kind = str(requirement["evidence_kind"])
        candidate_ref = supplied_refs.get(evidence_kind, "").strip()
        if candidate_ref:
            _validate_reference(evidence_kind, candidate_ref)
            requirement["required_evidence_ref"] = candidate_ref
            collected_kinds.append(evidence_kind)
        else:
            missing_kinds.append(evidence_kind)
        requirement["proof_state"] = "Unknown"
        requirement["current_decision"] = "lifecycle_recording_blocked"

    receipt["evidence_refs"] = _with_producer_refs(receipt["evidence_refs"])
    receipt["contract_summary"]["evidence_ref_count"] = len(receipt["evidence_refs"])
    _assert_authority_denied(receipt)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    validation_report = validate_universal_symbol_receipt_store_lifecycle_evidence_receipt(output_path)
    admission_report = {
        "status": "collected_non_authorizing" if not missing_kinds else "blocked_missing_live_evidence",
        "collected_evidence_kinds": collected_kinds,
        "missing_evidence_kinds": missing_kinds,
        "proof_state_after_intake": "Unknown",
        "lifecycle_recording_allowed": False,
        "authority_granted": False,
    }
    return {
        "receipt": receipt,
        "admission_report": admission_report,
        "validation": validation_report,
    }


def _environment_evidence_refs(environment: Mapping[str, str]) -> dict[str, str]:
    return {
        evidence_kind: environment.get(env_name, "").strip()
        for evidence_kind, env_name in ENVIRONMENT_REF_NAMES.items()
        if environment.get(env_name, "").strip()
    }


def _validate_reference(evidence_kind: str, candidate_ref: str) -> None:
    lowered = candidate_ref.lower()
    secret_markers = (
        "-----begin",
        "bearer ",
        "access_token",
        "refresh_token",
        "password=",
        "api_key=",
        "private_key",
    )
    if any(marker in lowered for marker in secret_markers):
        raise UniversalSymbolLifecycleEvidenceProducerError(
            f"{evidence_kind}: raw secret-like material is not admissible"
        )
    if len(candidate_ref) > 256 or not REF_PATTERN.fullmatch(candidate_ref):
        raise UniversalSymbolLifecycleEvidenceProducerError(
            f"{evidence_kind}: evidence ref must be a governed ref, not raw payload"
        )


def _with_producer_refs(existing_refs: Any) -> list[str]:
    refs = list(existing_refs if isinstance(existing_refs, list) else [])
    for evidence_ref in PRODUCER_EVIDENCE_REFS:
        if evidence_ref not in refs:
            refs.append(evidence_ref)
    return refs


def _assert_authority_denied(receipt: Mapping[str, Any]) -> None:
    denials = receipt.get("authority_denials")
    if not isinstance(denials, Mapping):
        raise UniversalSymbolLifecycleEvidenceProducerError("authority_denials must be present")
    drifted = sorted(field_name for field_name, field_value in denials.items() if field_value is not False)
    if drifted:
        raise UniversalSymbolLifecycleEvidenceProducerError(
            "authority denial drift: " + ", ".join(drifted)
        )


def _validation_clock() -> str:
    return os.environ.get("MULLU_VALIDATION_TIMESTAMP", "1970-01-01T00:00:00Z")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for lifecycle evidence reference intake."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--template", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--evidence-ref", action="append", default=[], metavar="KIND=REF")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = produce_lifecycle_evidence_receipt(
            evidence_refs=_parse_evidence_ref_args(args.evidence_ref),
            output_path=args.output,
            template_path=args.template,
        )
    except (UniversalSymbolLifecycleEvidenceProducerError, UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError) as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_lifecycle_evidence_receipt_producer: {exc}")
        return 1

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    if args.strict and result["admission_report"]["missing_evidence_kinds"]:
        return 1
    return 0


def _parse_evidence_ref_args(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise UniversalSymbolLifecycleEvidenceProducerError(
                f"evidence-ref must use KIND=REF format: {value}"
            )
        evidence_kind, evidence_ref = value.split("=", 1)
        parsed[evidence_kind.strip()] = evidence_ref.strip()
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
