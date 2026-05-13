#!/usr/bin/env python3
"""Emit a redacted finance payment-provider binding receipt.

Purpose: prove whether accepted payment-provider credential bindings are
present before producing non-sandbox finance payment closure evidence.
Governance scope: payment provider binding presence, provider scope,
redacted secret handling, schema validation, and approval boundary.
Dependencies: schemas/finance_approval_payment_provider_binding_receipt.schema.json.
Invariants:
  - Credential values are never serialized.
  - Non-sandbox providers require either the shared payment connector token or
    the provider-specific token for readiness.
  - The receipt id is the provider-binding evidence ref consumed by payment
    closure receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Literal

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "finance_approval_payment_provider_binding_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_payment_provider_binding_receipt.json"
PAYMENT_PROVIDERS = ("stripe", "bank_ach", "manual_bank_portal")
ACCEPTED_PAYMENT_PROVIDER_BINDING_NAMES = (
    "PAYMENT_PROVIDER_CONNECTOR_TOKEN",
    "STRIPE_API_KEY",
    "BANK_ACH_CONNECTOR_TOKEN",
    "MANUAL_BANK_PORTAL_TOKEN",
)
PROVIDER_BINDING_NAMES = {
    "stripe": ("PAYMENT_PROVIDER_CONNECTOR_TOKEN", "STRIPE_API_KEY"),
    "bank_ach": ("PAYMENT_PROVIDER_CONNECTOR_TOKEN", "BANK_ACH_CONNECTOR_TOKEN"),
    "manual_bank_portal": ("PAYMENT_PROVIDER_CONNECTOR_TOKEN", "MANUAL_BANK_PORTAL_TOKEN"),
}
BINDING_PROVIDER_SCOPE = {
    "PAYMENT_PROVIDER_CONNECTOR_TOKEN": "shared",
    "STRIPE_API_KEY": "stripe",
    "BANK_ACH_CONNECTOR_TOKEN": "bank_ach",
    "MANUAL_BANK_PORTAL_TOKEN": "manual_bank_portal",
}
EnvReader = Callable[[str], str | None]
PaymentProvider = Literal["stripe", "bank_ach", "manual_bank_portal"]


@dataclass(frozen=True, slots=True)
class FinancePaymentProviderBindingEntry:
    """One redacted payment-provider binding entry."""

    name: str
    provider_scope: str
    present: bool
    binding_kind: str = "secret"
    risk: str = "high"
    approval_required: bool = True
    receipt_projection: str = "name_and_presence_only"
    value_serialized: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FinancePaymentProviderBindingReceipt:
    """Redacted credential presence receipt for payment provider closure."""

    schema_version: int
    receipt_id: str
    provider_binding_ref: str
    provider: PaymentProvider
    checked_at: str
    secret_serialization: str
    ready: bool
    accepted_binding_names: tuple[str, ...]
    provider_binding_names: tuple[str, ...]
    present_binding_names: tuple[str, ...]
    binding_count: int
    bindings: tuple[FinancePaymentProviderBindingEntry, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "provider_binding_ref": self.provider_binding_ref,
            "provider": self.provider,
            "checked_at": self.checked_at,
            "secret_serialization": self.secret_serialization,
            "ready": self.ready,
            "accepted_binding_names": list(self.accepted_binding_names),
            "provider_binding_names": list(self.provider_binding_names),
            "present_binding_names": list(self.present_binding_names),
            "binding_count": self.binding_count,
            "bindings": [binding.as_dict() for binding in self.bindings],
        }


def emit_finance_approval_payment_provider_binding_receipt(
    *,
    provider: PaymentProvider = "stripe",
    schema_path: Path = DEFAULT_SCHEMA,
    env_reader: EnvReader | None = None,
) -> tuple[FinancePaymentProviderBindingReceipt, tuple[str, ...]]:
    """Build and validate a redacted payment-provider binding receipt."""
    errors: list[str] = []
    if provider not in PAYMENT_PROVIDERS:
        errors.append(f"provider must be one of {PAYMENT_PROVIDERS}")
        provider = "stripe"
    schema = _load_json_object(schema_path, "finance payment provider binding receipt schema", errors)
    resolved_env_reader = env_reader or os.environ.get
    bindings = tuple(
        FinancePaymentProviderBindingEntry(
            name=name,
            provider_scope=BINDING_PROVIDER_SCOPE[name],
            present=bool((resolved_env_reader(name) or "").strip()),
        )
        for name in ACCEPTED_PAYMENT_PROVIDER_BINDING_NAMES
    )
    present_names = tuple(binding.name for binding in bindings if binding.present)
    provider_names = PROVIDER_BINDING_NAMES[provider]
    ready = any(name in present_names for name in provider_names)
    provider_binding_ref = _provider_binding_ref(provider=provider, present_names=present_names)
    receipt = FinancePaymentProviderBindingReceipt(
        schema_version=1,
        receipt_id=provider_binding_ref,
        provider_binding_ref=provider_binding_ref,
        provider=provider,
        checked_at=_validation_clock(),
        secret_serialization="forbidden",
        ready=ready,
        accepted_binding_names=ACCEPTED_PAYMENT_PROVIDER_BINDING_NAMES,
        provider_binding_names=provider_names,
        present_binding_names=present_names,
        binding_count=len(bindings),
        bindings=bindings,
    )
    if schema:
        errors.extend(_validate_schema_instance(schema, receipt.as_dict()))
    _validate_no_values_serialized(receipt, errors)
    return receipt, tuple(errors)


def write_finance_payment_provider_binding_receipt(
    receipt: FinancePaymentProviderBindingReceipt,
    output_path: Path,
) -> Path:
    """Write one redacted finance payment-provider binding receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_no_values_serialized(
    receipt: FinancePaymentProviderBindingReceipt,
    errors: list[str],
) -> None:
    if receipt.secret_serialization != "forbidden":
        errors.append("secret_serialization must be forbidden")
    for binding in receipt.bindings:
        if binding.value_serialized is not False:
            errors.append(f"{binding.name} value_serialized must be false")
        if binding.receipt_projection != "name_and_presence_only":
            errors.append(f"{binding.name} receipt_projection must be name_and_presence_only")


def _provider_binding_ref(*, provider: str, present_names: tuple[str, ...]) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "provider": provider,
                "accepted_binding_names": ACCEPTED_PAYMENT_PROVIDER_BINDING_NAMES,
                "provider_binding_names": PROVIDER_BINDING_NAMES[provider],
                "present_binding_names": present_names,
                "checked_at": _validation_clock(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"provider-binding:{provider}:{digest[:16]}"


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append(f"{label} could not be read")
        return {}
    except json.JSONDecodeError:
        errors.append(f"{label} must be JSON")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return parsed


def _validation_clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance payment-provider binding receipt arguments."""
    parser = argparse.ArgumentParser(description="Emit redacted finance payment-provider binding receipt.")
    parser.add_argument("--provider", choices=PAYMENT_PROVIDERS, default="stripe")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance payment-provider binding receipt emission."""
    args = parse_args(argv)
    receipt, errors = emit_finance_approval_payment_provider_binding_receipt(
        provider=args.provider,
        schema_path=Path(args.schema),
    )
    write_finance_payment_provider_binding_receipt(receipt, Path(args.output))
    payload = receipt.as_dict() | {"errors": list(errors)}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif receipt.ready and not errors:
        print(f"finance payment provider binding receipt ready ref={receipt.provider_binding_ref}")
    else:
        print("finance payment provider binding receipt blocked")
    return 0 if (not errors and (receipt.ready or not args.strict)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
