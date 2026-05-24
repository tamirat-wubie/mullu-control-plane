#!/usr/bin/env python3
"""Validate gateway DNS target binding receipts.

Purpose: fail closed until the intended gateway DNS origin target is explicitly
bound before DNS publication.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.emit_gateway_dns_target_binding_receipt and public schemas.
Invariants:
  - Receipt JSON must match the public target-binding contract.
  - Ready target binding requires provider, record type, target, and host/URL match.
  - Optional require-ready policy fails closed for missing target/provider/type.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.emit_gateway_dns_target_binding_receipt import (  # noqa: E402
    BOUND_NEXT_ACTION,
    DEFAULT_OUTPUT,
    MISSING_PROVIDER_NEXT_ACTION,
    MISSING_RECORD_TYPE_NEXT_ACTION,
    MISSING_TARGET_NEXT_ACTION,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "gateway_dns_target_binding_receipt_validation.json"
)
GATEWAY_DNS_TARGET_BINDING_SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "gateway_dns_target_binding_receipt.schema.json"
)
RECEIPT_ID_PATTERN = re.compile(r"^gateway-dns-target-binding-[0-9a-f]{16}$")


@dataclass(frozen=True, slots=True)
class GatewayDnsTargetBindingValidationStep:
    """One DNS target binding validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class GatewayDnsTargetBindingReceiptValidation:
    """Structured validation report for one DNS target binding receipt."""

    receipt_path: str
    valid: bool
    receipt_id: str
    binding_state: str
    ready: bool
    steps: tuple[GatewayDnsTargetBindingValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation payload."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_gateway_dns_target_binding_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = GATEWAY_DNS_TARGET_BINDING_SCHEMA_PATH,
    require_ready: bool = False,
    expected_gateway_host: str = "",
    expected_gateway_url: str = "",
    expected_environment: str = "",
) -> GatewayDnsTargetBindingReceiptValidation:
    """Validate one gateway DNS target binding receipt."""
    payload = _read_receipt_payload(receipt_path)
    steps = (
        _check_schema_contract(payload, schema_path),
        _check_receipt_id(payload),
        _check_gateway_host_shape(payload),
        _check_gateway_url_host_match(payload),
        _check_target_binding_state(payload),
        _check_next_action(payload),
        _check_expected("gateway_host", payload.get("gateway_host"), expected_gateway_host),
        _check_expected("gateway_url", payload.get("gateway_url"), expected_gateway_url),
        _check_expected("expected_environment", payload.get("expected_environment"), expected_environment),
        _check_require_ready(payload, require_ready=require_ready),
    )
    return GatewayDnsTargetBindingReceiptValidation(
        receipt_path=_bounded_receipt_path(receipt_path),
        valid=all(step.passed for step in steps),
        receipt_id=_bounded_receipt_id(payload),
        binding_state=_bounded_binding_state(payload),
        ready=payload.get("ready") is True,
        steps=steps,
    )


def write_gateway_dns_target_binding_validation_report(
    validation: GatewayDnsTargetBindingReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one local gateway DNS target binding validation report."""
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
        raise RuntimeError("failed to read gateway DNS target binding receipt") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("gateway DNS target binding receipt returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("gateway DNS target binding receipt was not a JSON object")
    return parsed


def _check_schema_contract(
    payload: dict[str, Any],
    schema_path: Path,
) -> GatewayDnsTargetBindingValidationStep:
    try:
        schema = _load_schema(schema_path)
    except OSError:
        return GatewayDnsTargetBindingValidationStep(
            "schema contract",
            False,
            "schema-read-failed",
        )
    errors = _validate_schema_instance(schema, payload)
    return GatewayDnsTargetBindingValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"schema-errors={len(errors)}",
    )


def _check_receipt_id(payload: dict[str, Any]) -> GatewayDnsTargetBindingValidationStep:
    receipt_id = payload.get("receipt_id")
    passed = RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None
    return GatewayDnsTargetBindingValidationStep(
        "receipt id",
        passed,
        "valid" if passed else _receipt_id_state(receipt_id),
    )


def _check_gateway_host_shape(payload: dict[str, Any]) -> GatewayDnsTargetBindingValidationStep:
    gateway_host = payload.get("gateway_host")
    passed = isinstance(gateway_host, str) and _is_hostname(gateway_host)
    return GatewayDnsTargetBindingValidationStep(
        "gateway host shape",
        passed,
        "valid" if passed else "invalid",
    )


def _check_gateway_url_host_match(payload: dict[str, Any]) -> GatewayDnsTargetBindingValidationStep:
    gateway_host = payload.get("gateway_host")
    gateway_url = payload.get("gateway_url")
    parsed = urlparse(str(gateway_url))
    passed = parsed.scheme == "https" and parsed.hostname == gateway_host
    return GatewayDnsTargetBindingValidationStep(
        "gateway URL host match",
        passed,
        "matched" if passed else "mismatched",
    )


def _check_target_binding_state(payload: dict[str, Any]) -> GatewayDnsTargetBindingValidationStep:
    binding_state = payload.get("binding_state")
    ready = payload.get("ready")
    record_type = payload.get("record_type")
    target = payload.get("target")
    target_kind = payload.get("target_kind")
    provider = payload.get("provider")
    if binding_state == "bound":
        passed = (
            ready is True
            and record_type in {"A", "AAAA", "CNAME"}
            and isinstance(target, str)
            and bool(target)
            and isinstance(provider, str)
            and bool(provider)
            and target_kind == _expected_target_kind(str(record_type), target)
        )
    elif binding_state == "missing-target":
        passed = ready is False and target == "" and target_kind == "missing"
    elif binding_state == "missing-record-type":
        passed = ready is False and record_type == "" and target_kind == "missing"
    elif binding_state == "missing-provider":
        passed = ready is False and provider == "" and target_kind == "missing"
    else:
        passed = False
    return GatewayDnsTargetBindingValidationStep(
        "target binding state",
        passed,
        f"state={binding_state}" if isinstance(binding_state, str) else "state=invalid",
    )


def _check_next_action(payload: dict[str, Any]) -> GatewayDnsTargetBindingValidationStep:
    expected_action = {
        "bound": BOUND_NEXT_ACTION,
        "missing-target": MISSING_TARGET_NEXT_ACTION,
        "missing-record-type": MISSING_RECORD_TYPE_NEXT_ACTION,
        "missing-provider": MISSING_PROVIDER_NEXT_ACTION,
    }.get(str(payload.get("binding_state")), "")
    passed = isinstance(payload.get("next_action"), str) and payload.get("next_action") == expected_action
    return GatewayDnsTargetBindingValidationStep(
        "next action",
        passed,
        "matched" if passed else "mismatched",
    )


def _check_expected(
    label: str,
    actual_value: Any,
    expected_value: str,
) -> GatewayDnsTargetBindingValidationStep:
    if not expected_value:
        return GatewayDnsTargetBindingValidationStep(
            f"expected {label}",
            True,
            "not-required",
        )
    passed = actual_value == expected_value
    return GatewayDnsTargetBindingValidationStep(
        f"expected {label}",
        passed,
        "matched" if passed else "mismatched",
    )


def _check_require_ready(
    payload: dict[str, Any],
    *,
    require_ready: bool,
) -> GatewayDnsTargetBindingValidationStep:
    if not require_ready:
        return GatewayDnsTargetBindingValidationStep("require ready", True, "not-required")
    ready = payload.get("ready") is True and payload.get("binding_state") == "bound"
    return GatewayDnsTargetBindingValidationStep(
        "require ready",
        ready,
        "ready" if ready else "not-ready",
    )


def _expected_target_kind(record_type: str, target: str) -> str:
    try:
        address = ipaddress.ip_address(target)
    except ValueError:
        address = None
    if record_type == "A" and address and address.version == 4:
        return "ipv4"
    if record_type == "AAAA" and address and address.version == 6:
        return "ipv6"
    if record_type == "CNAME" and address is None and _is_hostname(target):
        return "hostname"
    return "invalid"


def _is_hostname(value: str) -> bool:
    if not value or len(value) > 253 or "." not in value or "/" in value or ":" in value:
        return False
    labels = value.split(".")
    if any(not label or len(label) > 63 for label in labels):
        return False
    return all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)


def _bounded_receipt_path(receipt_path: Path) -> str:
    if receipt_path == DEFAULT_OUTPUT:
        return ".change_assurance/gateway_dns_target_binding_receipt.json"
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


def _bounded_binding_state(payload: dict[str, Any]) -> str:
    binding_state = payload.get("binding_state")
    if binding_state in {"bound", "missing-target", "missing-record-type", "missing-provider"}:
        return str(binding_state)
    return "invalid"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse gateway DNS target binding receipt validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate a gateway DNS target binding receipt."
    )
    parser.add_argument("--receipt", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--schema", default=str(GATEWAY_DNS_TARGET_BINDING_SCHEMA_PATH))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--expected-gateway-host", default="")
    parser.add_argument("--expected-gateway-url", default="")
    parser.add_argument("--expected-environment", default="", choices=("", "pilot", "production"))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for gateway DNS target binding receipt validation."""
    args = parse_args(argv)
    try:
        validation = validate_gateway_dns_target_binding_receipt(
            receipt_path=Path(args.receipt),
            schema_path=Path(args.schema),
            require_ready=args.require_ready,
            expected_gateway_host=args.expected_gateway_host,
            expected_gateway_url=args.expected_gateway_url,
            expected_environment=args.expected_environment,
        )
    except RuntimeError:
        print("gateway DNS target binding receipt validation failed")
        return 1

    output_path = write_gateway_dns_target_binding_validation_report(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True))
    else:
        print(f"validation_report: {output_path}")
        print(f"receipt: {validation.receipt_path}")
        print(f"receipt_id: {validation.receipt_id}")
        print(f"binding_state: {validation.binding_state}")
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
