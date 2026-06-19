"""Produce the Universal Symbol runtime live witness input receipt.

Purpose: materialize a Foundation Mode runtime live-witness input receipt from
operator-supplied input references without probing, dispatching, appending, or
granting runtime authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime live witness input schema and foundation receipt example.
Invariants:
  - The produced receipt is not runtime authority.
  - Required live-witness inputs remain ProofState Unknown.
  - Live runtime witness acceptance, runtime admission, dispatch, connector
    calls, writes, receipt-store append, mutation, and terminal closure remain
    denied.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Mapping

try:
    import jsonschema
except ImportError:  # pragma: no cover - dependency is expected in CI/dev envs.
    jsonschema = None


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_symbol_runtime_live_witness_input_receipt.schema.json"
DEFAULT_TEMPLATE_PATH = REPO_ROOT / "examples" / "universal_symbol_runtime_live_witness_input_receipt.foundation.json"

DEFAULT_GENERATED_AT = "2026-06-19T00:00:00Z"

DEFAULT_INPUT_REFS: dict[str, str] = {
    "runtime_endpoint": "input://runtime/endpoint-url",
    "runtime_process_identity": "input://runtime/process-identity",
    "runtime_health_probe": "input://runtime/health-probe-response",
    "runtime_no_effect_dry_run": "input://runtime/no-effect-dry-run-receipt",
    "receipt_store_append_denial": "input://receipt-store/append-denial-witness",
    "operator_observation": "input://operator/runtime-observation",
    "freshness_window": "input://runtime/freshness-window",
    "proof_coverage_binding": "surface://universal_symbol_runtime_live_witness_input_receipt",
}

DENIED_AUTHORITY_FIELDS: tuple[str, ...] = (
    "live_runtime_witness_accepted",
    "runtime_admission_granted",
    "runtime_registration_performed",
    "live_dispatch_enabled",
    "connector_call_enabled",
    "filesystem_write_enabled",
    "external_write_enabled",
    "receipt_store_append_enabled",
    "raw_payload_stored",
    "raw_secret_stored",
    "state_mutation_performed",
    "terminal_closure_allowed",
)


class UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError(ValueError):
    """Raised when a generated receipt would violate the no-authority contract."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object with explicit causal context on failure."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError(f"expected object: {path}")
    return value


def build_universal_symbol_runtime_live_witness_input_receipt(
    input_refs: Mapping[str, str] | None = None,
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
    template_path: Path = DEFAULT_TEMPLATE_PATH,
) -> dict[str, Any]:
    """Return a blocked runtime live-witness input receipt.

    Input contract: `input_refs` may override known input-kind references only.
    Output contract: returned JSON object follows the foundation receipt shape.
    Error contract: unknown or empty refs raise a production error before output.
    """

    resolved_input_refs = dict(DEFAULT_INPUT_REFS)
    if input_refs:
        unknown_keys = sorted(set(input_refs) - set(DEFAULT_INPUT_REFS))
        if unknown_keys:
            raise UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError(
                f"unknown input ref kind: {', '.join(unknown_keys)}"
            )
        for input_kind, input_ref in input_refs.items():
            resolved_input_refs[input_kind] = _validate_input_ref(input_kind, input_ref)

    receipt = copy.deepcopy(load_json_object(template_path))
    receipt["generated_at"] = generated_at

    channels = receipt.get("required_input_channels")
    if not isinstance(channels, list):
        raise UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError(
            "template required_input_channels must be a list"
        )
    for channel in channels:
        if not isinstance(channel, dict):
            raise UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError("template input channel must be object")
        input_kind = channel.get("input_kind")
        if input_kind not in resolved_input_refs:
            raise UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError(
                f"template contains unknown input kind: {input_kind}"
            )
        channel["required_input_ref"] = resolved_input_refs[input_kind]
        channel["proof_state"] = "Unknown"
        channel["current_decision"] = "live_runtime_witness_blocked"

    _recompute_contract_summary(receipt)
    errors = validate_runtime_live_witness_input_receipt_object(receipt)
    if errors:
        raise UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError("; ".join(errors))
    return receipt


def validate_runtime_live_witness_input_receipt_object(
    receipt: Mapping[str, Any],
    *,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> list[str]:
    """Return validation errors for a generated receipt object."""

    schema = load_json_object(schema_path)
    errors: list[str] = []
    if jsonschema is None:
        errors.append("jsonschema dependency missing")
        return errors

    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    for error in sorted(validator.iter_errors(receipt), key=lambda item: tuple(item.path)):
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        errors.append(f"schema validation failed at {path}: {error.message}")

    if receipt.get("receipt_is_not_runtime_authority") is not True:
        errors.append("receipt_is_not_runtime_authority must remain true")
    if receipt.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence")

    denials = receipt.get("authority_denials")
    if not isinstance(denials, Mapping):
        errors.append("authority_denials must be object")
    else:
        for field in DENIED_AUTHORITY_FIELDS:
            if denials.get(field) is not False:
                errors.append(f"{field} must remain denied")

    channels = receipt.get("required_input_channels")
    if not isinstance(channels, list):
        errors.append("required_input_channels must be list")
    else:
        for channel in channels:
            if not isinstance(channel, Mapping):
                errors.append("required_input_channels item must be object")
                continue
            input_kind = channel.get("input_kind")
            if channel.get("proof_state") != "Unknown":
                errors.append(f"{input_kind} proof_state must remain Unknown")
            if channel.get("current_decision") != "live_runtime_witness_blocked":
                errors.append(f"{input_kind} current_decision must remain blocked")
            required_input_ref = channel.get("required_input_ref")
            if not isinstance(required_input_ref, str) or not required_input_ref.strip():
                errors.append(f"{input_kind} required_input_ref must be non-empty")
    return errors


def _validate_input_ref(input_kind: str, input_ref: str) -> str:
    if not isinstance(input_ref, str) or not input_ref.strip():
        raise UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError(
            f"{input_kind} input ref must be a non-empty string"
        )
    return input_ref


def _recompute_contract_summary(receipt: dict[str, Any]) -> None:
    summary = receipt.get("contract_summary")
    if not isinstance(summary, dict):
        raise UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError("template contract_summary must be object")
    summary["input_channel_count"] = _list_len(receipt.get("required_input_channels"))
    summary["consistency_constraint_count"] = _dict_len(receipt.get("input_consistency_constraints"))
    summary["authority_denial_count"] = _dict_len(receipt.get("authority_denials"))
    summary["rejection_check_count"] = _dict_len(receipt.get("rejection_policy"))
    summary["blocked_reason_count"] = _list_len(receipt.get("blocked_reasons"))
    summary["evidence_ref_count"] = _list_len(receipt.get("evidence_refs"))


def _list_len(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def _dict_len(value: object) -> int:
    return len(value) if isinstance(value, dict) else 0


def main(argv: list[str] | None = None) -> int:
    """Produce a blocked runtime live-witness input receipt."""

    parser = argparse.ArgumentParser(
        description="Produce a Universal Symbol runtime live witness input receipt without runtime authority."
    )
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--runtime-endpoint-ref", default=DEFAULT_INPUT_REFS["runtime_endpoint"])
    parser.add_argument("--runtime-process-identity-ref", default=DEFAULT_INPUT_REFS["runtime_process_identity"])
    parser.add_argument("--runtime-health-probe-ref", default=DEFAULT_INPUT_REFS["runtime_health_probe"])
    parser.add_argument("--runtime-no-effect-dry-run-ref", default=DEFAULT_INPUT_REFS["runtime_no_effect_dry_run"])
    parser.add_argument("--receipt-store-append-denial-ref", default=DEFAULT_INPUT_REFS["receipt_store_append_denial"])
    parser.add_argument("--operator-observation-ref", default=DEFAULT_INPUT_REFS["operator_observation"])
    parser.add_argument("--freshness-window-ref", default=DEFAULT_INPUT_REFS["freshness_window"])
    parser.add_argument("--proof-coverage-binding-ref", default=DEFAULT_INPUT_REFS["proof_coverage_binding"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    input_refs = {
        "runtime_endpoint": args.runtime_endpoint_ref,
        "runtime_process_identity": args.runtime_process_identity_ref,
        "runtime_health_probe": args.runtime_health_probe_ref,
        "runtime_no_effect_dry_run": args.runtime_no_effect_dry_run_ref,
        "receipt_store_append_denial": args.receipt_store_append_denial_ref,
        "operator_observation": args.operator_observation_ref,
        "freshness_window": args.freshness_window_ref,
        "proof_coverage_binding": args.proof_coverage_binding_ref,
    }
    try:
        receipt = build_universal_symbol_runtime_live_witness_input_receipt(
            input_refs,
            generated_at=args.generated_at,
        )
    except UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError as exc:
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
                    "input_channel_count": _list_len(receipt.get("required_input_channels")),
                    "authority_denial_count": _dict_len(receipt.get("authority_denials")),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
