"""Produce the Universal Symbol lane runtime authority evidence value receipt.

Purpose: materialize Foundation Mode lane authority evidence refs without
verifying values, granting lane authority, admitting runtime, dispatching,
appending, or allowing terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lane evidence value schema/example and validator.
Invariants:
  - Generated receipts store refs only, never raw evidence payloads.
  - Lane authority and runtime admission remain denied.
  - Every lane evidence value remains unverified and blocking.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_universal_symbol_lane_runtime_authority_evidence_value_receipt import (
    DEFAULT_RECEIPT_PATH,
    EVIDENCE_KINDS,
    LANES,
    UniversalSymbolLaneRuntimeAuthorityEvidenceValueReceiptError,
    load_json_object,
    validate_lane_runtime_authority_evidence_value_receipt_object,
)


DEFAULT_GENERATED_AT = "2026-06-19T00:00:00Z"


class UniversalSymbolLaneRuntimeAuthorityEvidenceValueProductionError(ValueError):
    """Raised when generated lane evidence value refs would violate policy."""


def build_universal_symbol_lane_runtime_authority_evidence_value_receipt(
    value_refs: Mapping[str, str] | None = None,
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
    template_path: Path = DEFAULT_RECEIPT_PATH,
) -> dict[str, Any]:
    """Return a non-authorizing lane evidence value receipt.

    Input contract: value_refs keys use `lane_ref|evidence_kind`.
    Output contract: returned object follows the Foundation Mode template.
    Error contract: unknown keys, empty refs, or secret-shaped refs fail closed.
    """

    receipt = copy.deepcopy(load_json_object(template_path))
    receipt["generated_at"] = generated_at
    resolved_refs = dict(value_refs or {})
    _validate_override_keys(resolved_refs)

    items = receipt.get("lane_value_items")
    if not isinstance(items, list):
        raise UniversalSymbolLaneRuntimeAuthorityEvidenceValueProductionError("template lane_value_items must be list")
    for item in items:
        if not isinstance(item, dict):
            raise UniversalSymbolLaneRuntimeAuthorityEvidenceValueProductionError("template lane_value_item must be object")
        key = _value_key(str(item.get("lane_ref", "")), str(item.get("evidence_kind", "")))
        if key in resolved_refs:
            item["supplied_evidence_ref"] = _validate_ref(key, resolved_refs[key])
        item["proof_state"] = "Unknown"
        item["value_state"] = "operator_reference_recorded_not_verified"
        item["current_decision"] = "lane_runtime_authority_blocked"

    _recompute_contract_summary(receipt)
    errors = validate_lane_runtime_authority_evidence_value_receipt_object(receipt)
    if errors:
        raise UniversalSymbolLaneRuntimeAuthorityEvidenceValueProductionError("; ".join(errors))
    return receipt


def _validate_override_keys(value_refs: Mapping[str, str]) -> None:
    allowed = {_value_key(lane_ref, evidence_kind) for lane_ref in LANES for evidence_kind in EVIDENCE_KINDS}
    unknown = sorted(set(value_refs) - allowed)
    if unknown:
        raise UniversalSymbolLaneRuntimeAuthorityEvidenceValueProductionError(
            "unknown lane evidence value key: " + ", ".join(unknown)
        )
    for key, value in value_refs.items():
        _validate_ref(key, value)


def _validate_ref(key: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UniversalSymbolLaneRuntimeAuthorityEvidenceValueProductionError(f"{key}: ref must be non-empty")
    lowered = value.lower()
    if any(marker in lowered for marker in ("secret=", "token=", "password=", "private_key=", "api_key=")):
        raise UniversalSymbolLaneRuntimeAuthorityEvidenceValueProductionError(f"{key}: raw secret-like ref denied")
    return value


def _recompute_contract_summary(receipt: dict[str, Any]) -> None:
    summary = receipt.get("contract_summary")
    if not isinstance(summary, dict):
        raise UniversalSymbolLaneRuntimeAuthorityEvidenceValueProductionError("template contract_summary must be object")
    summary["lane_count"] = len(LANES)
    summary["evidence_value_kind_count"] = len(EVIDENCE_KINDS)
    summary["evidence_value_item_count"] = _list_len(receipt.get("lane_value_items"))
    summary["evidence_value_constraint_count"] = _dict_len(receipt.get("evidence_value_constraints"))
    summary["authority_denial_count"] = _dict_len(receipt.get("authority_denials"))
    summary["rejection_check_count"] = _dict_len(receipt.get("rejection_policy"))
    summary["blocked_reason_count"] = _list_len(receipt.get("blocked_reasons"))
    summary["evidence_ref_count"] = _list_len(receipt.get("evidence_refs"))


def _value_key(lane_ref: str, evidence_kind: str) -> str:
    return f"{lane_ref}|{evidence_kind}"


def _list_len(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def _dict_len(value: object) -> int:
    return len(value) if isinstance(value, dict) else 0


def main(argv: list[str] | None = None) -> int:
    """Produce a blocked lane evidence value receipt."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--value-ref", action="append", default=[], help="Override as lane_ref|evidence_kind=ref")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        value_refs = _parse_value_ref_args(args.value_ref)
        receipt = build_universal_symbol_lane_runtime_authority_evidence_value_receipt(
            value_refs,
            generated_at=args.generated_at,
        )
    except (
        UniversalSymbolLaneRuntimeAuthorityEvidenceValueProductionError,
        UniversalSymbolLaneRuntimeAuthorityEvidenceValueReceiptError,
    ) as exc:
        print(json.dumps({"valid": False, "errors": str(exc).split("; ")}, indent=2, sort_keys=True))
        return 1

    rendered = json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        try:
            args.output.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(json.dumps({"valid": False, "errors": [f"write failed: {exc}"]}, indent=2, sort_keys=True))
            return 1
        print(
            json.dumps(
                {
                    "valid": True,
                    "output": str(args.output),
                    "lane_count": len(LANES),
                    "evidence_value_item_count": _list_len(receipt.get("lane_value_items")),
                    "authority_denial_count": _dict_len(receipt.get("authority_denials")),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    print(rendered, end="")
    return 0


def _parse_value_ref_args(raw_refs: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_ref in raw_refs:
        key, separator, value = raw_ref.partition("=")
        if not separator:
            raise UniversalSymbolLaneRuntimeAuthorityEvidenceValueProductionError(
                f"value ref must use key=ref format: {raw_ref}"
            )
        parsed[key] = value
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
