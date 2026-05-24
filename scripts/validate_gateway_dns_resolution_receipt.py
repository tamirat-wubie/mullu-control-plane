#!/usr/bin/env python3
"""Validate gateway DNS resolution receipts.

Purpose: gate deployment publication on a schema-backed DNS resolution receipt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.collect_gateway_dns_resolution_receipt and public JSON schemas.
Invariants:
  - Receipt JSON must match the public DNS resolution contract.
  - Resolved and unresolved states have explicit, bounded next actions.
  - A require-resolved gate fails closed until at least one address is present.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.collect_gateway_dns_resolution_receipt import DEFAULT_OUTPUT  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "gateway_dns_resolution_receipt_validation.json"
)
GATEWAY_DNS_RECEIPT_SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "gateway_dns_resolution_receipt.schema.json"
)
RECEIPT_ID_PATTERN = re.compile(r"^gateway-dns-resolution-[0-9a-f]{16}$")
RESOLVED_NEXT_ACTION = "rerun deployment witness preflight with endpoint probes enabled"
UNRESOLVED_NEXT_ACTION = (
    "publish a DNS A, AAAA, or CNAME record for the gateway host, then rerun this receipt"
)


@dataclass(frozen=True, slots=True)
class GatewayDnsResolutionValidationStep:
    """One DNS receipt validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class GatewayDnsResolutionReceiptValidation:
    """Structured validation report for one DNS resolution receipt."""

    receipt_path: str
    valid: bool
    receipt_id: str
    resolved: bool
    address_count: int
    steps: tuple[GatewayDnsResolutionValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation payload."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_gateway_dns_resolution_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = GATEWAY_DNS_RECEIPT_SCHEMA_PATH,
    require_resolved: bool = False,
) -> GatewayDnsResolutionReceiptValidation:
    """Validate one gateway DNS resolution receipt and optional resolved gate."""
    payload = _read_receipt_payload(receipt_path)
    steps = (
        _check_schema_contract(payload, schema_path),
        _check_receipt_id(payload),
        _check_resolution_state(payload),
        _check_next_action(payload),
        _check_require_resolved(payload, require_resolved=require_resolved),
    )
    addresses = payload.get("addresses")
    return GatewayDnsResolutionReceiptValidation(
        receipt_path=_bounded_receipt_path(receipt_path),
        valid=all(step.passed for step in steps),
        receipt_id=_bounded_receipt_id(payload),
        resolved=payload.get("resolved") is True,
        address_count=len(addresses) if isinstance(addresses, list) else 0,
        steps=steps,
    )


def write_gateway_dns_resolution_validation_report(
    validation: GatewayDnsResolutionReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one local gateway DNS receipt validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _read_receipt_payload(receipt_path: Path) -> dict[str, Any]:
    try:
        raw_text = receipt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("failed to read gateway DNS resolution receipt") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("gateway DNS resolution receipt returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("gateway DNS resolution receipt was not a JSON object")
    return parsed


def _check_schema_contract(
    payload: dict[str, Any],
    schema_path: Path,
) -> GatewayDnsResolutionValidationStep:
    try:
        schema = _load_schema(schema_path)
    except OSError:
        return GatewayDnsResolutionValidationStep(
            "schema contract",
            False,
            "schema-read-failed",
        )
    errors = _validate_schema_instance(schema, payload)
    return GatewayDnsResolutionValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"schema-errors={len(errors)}",
    )


def _check_receipt_id(payload: dict[str, Any]) -> GatewayDnsResolutionValidationStep:
    receipt_id = payload.get("receipt_id")
    passed = RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None
    return GatewayDnsResolutionValidationStep(
        "receipt id",
        passed,
        "valid" if passed else _receipt_id_state(receipt_id),
    )


def _check_resolution_state(payload: dict[str, Any]) -> GatewayDnsResolutionValidationStep:
    resolved = payload.get("resolved")
    addresses = payload.get("addresses")
    error = payload.get("error")
    if resolved is True:
        passed = isinstance(addresses, list) and len(addresses) > 0 and error is None
        detail = f"resolved=true addresses={_address_count(addresses)} error={_error_state(error)}"
    elif resolved is False:
        passed = isinstance(addresses, list) and not addresses and error == "resolution_error"
        detail = f"resolved=false addresses={_address_count(addresses)} error={_error_state(error)}"
    else:
        passed = False
        detail = "resolved=invalid"
    return GatewayDnsResolutionValidationStep("resolution state", passed, detail)


def _check_next_action(payload: dict[str, Any]) -> GatewayDnsResolutionValidationStep:
    resolved = payload.get("resolved")
    next_action = payload.get("next_action")
    if resolved is True:
        expected_action = RESOLVED_NEXT_ACTION
    elif resolved is False:
        expected_action = UNRESOLVED_NEXT_ACTION
    else:
        expected_action = ""
    passed = isinstance(next_action, str) and next_action == expected_action
    return GatewayDnsResolutionValidationStep(
        "next action",
        passed,
        "matched" if passed else "mismatched",
    )


def _check_require_resolved(
    payload: dict[str, Any],
    *,
    require_resolved: bool,
) -> GatewayDnsResolutionValidationStep:
    if not require_resolved:
        return GatewayDnsResolutionValidationStep(
            "require resolved",
            True,
            "not-required",
        )
    resolved = payload.get("resolved") is True
    addresses = payload.get("addresses")
    passed = resolved and isinstance(addresses, list) and len(addresses) > 0
    return GatewayDnsResolutionValidationStep(
        "require resolved",
        passed,
        "resolved" if passed else "unresolved",
    )


def _bounded_receipt_path(receipt_path: Path) -> str:
    if receipt_path == DEFAULT_OUTPUT:
        return ".change_assurance/gateway_dns_resolution_receipt.json"
    return "provided_receipt"


def _bounded_receipt_id(payload: dict[str, Any]) -> str:
    receipt_id = payload.get("receipt_id")
    if RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None:
        return str(receipt_id)
    return _receipt_id_state(receipt_id)


def _receipt_id_state(receipt_id: Any) -> str:
    if receipt_id in (None, ""):
        return "missing"
    return "invalid"


def _address_count(addresses: Any) -> int:
    return len(addresses) if isinstance(addresses, list) else 0


def _error_state(error: Any) -> str:
    if error is None:
        return "none"
    if isinstance(error, str):
        return error
    return "invalid"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse gateway DNS receipt validation CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Validate a gateway DNS resolution receipt."
    )
    parser.add_argument("--receipt", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--schema", default=str(GATEWAY_DNS_RECEIPT_SCHEMA_PATH))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-resolved", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for gateway DNS resolution receipt validation."""
    args = parse_args(argv)
    try:
        validation = validate_gateway_dns_resolution_receipt(
            receipt_path=Path(args.receipt),
            schema_path=Path(args.schema),
            require_resolved=args.require_resolved,
        )
    except RuntimeError:
        print("gateway DNS resolution receipt validation failed")
        return 1

    output_path = write_gateway_dns_resolution_validation_report(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True))
    else:
        print(f"validation_report: {output_path}")
        print(f"receipt: {validation.receipt_path}")
        print(f"receipt_id: {validation.receipt_id}")
        print(f"valid: {str(validation.valid).lower()}")
        for step in validation.steps:
            print(
                f"step: {step.name} "
                f"passed={str(step.passed).lower()} "
                f"detail={step.detail}"
            )
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
