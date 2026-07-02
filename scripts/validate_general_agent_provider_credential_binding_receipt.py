#!/usr/bin/env python3
"""Validate redacted general-agent provider credential binding receipts.

Purpose: reject malformed, value-leaking, or inconsistent provider credential
binding receipts before live adapter evidence execution.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.bind_general_agent_provider_credentials.
Invariants:
  - Provider credential values are never serialized.
  - Required credential names match the live adapter provider contract.
  - The ready flag is derived from missing credentials and failed installs.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.bind_general_agent_provider_credentials import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_RECEIPT,
    REQUIRED_PROVIDER_CREDENTIALS,
    SECRET_VALUE_MARKERS,
)


RECEIPT_ID = "general-agent-provider-credential-binding-receipt-v1"
TOP_LEVEL_FIELDS = {
    "bindings",
    "checked_at",
    "external_provider_call_performed",
    "github_repo",
    "install_github_secrets",
    "missing_credentials",
    "next_action",
    "ready",
    "receipt_id",
    "secret_values_serialized",
}
BINDING_FIELDS = {
    "blocker",
    "github_secret_install_attempted",
    "github_secret_installed",
    "name",
    "present",
    "required",
    "value_serialized",
}


@dataclass(frozen=True, slots=True)
class ProviderCredentialBindingReceiptValidation:
    """Validation report for a redacted provider credential binding receipt."""

    valid: bool
    ready: bool
    receipt_id: str
    receipt_path: str
    binding_count: int
    missing_credentials: tuple[str, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""

        payload = asdict(self)
        payload["missing_credentials"] = list(self.missing_credentials)
        payload["errors"] = list(self.errors)
        return payload


def validate_general_agent_provider_credential_binding_receipt(
    *,
    receipt_path: Path = DEFAULT_RECEIPT,
    require_ready: bool = False,
) -> ProviderCredentialBindingReceiptValidation:
    """Validate one redacted provider credential binding receipt."""

    errors: list[str] = []
    receipt = _load_receipt(receipt_path, errors)
    if receipt:
        _validate_top_level(receipt, errors)
        _validate_bindings(receipt, errors)
        if require_ready and receipt.get("ready") is not True:
            errors.append("receipt ready must be true")
    return _validation_result(receipt_path, receipt, errors)


def _load_receipt(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        errors.append("provider credential binding receipt could not be read")
        return {}
    if _contains_secret_marker(raw_text):
        errors.append("provider credential binding receipt contains prohibited secret-shaped material")
        return {}
    try:
        payload = json.loads(raw_text, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append("provider credential binding receipt must be JSON")
        return {}
    if not isinstance(payload, dict):
        errors.append("provider credential binding receipt root must be an object")
        return {}
    return payload


def _validate_top_level(receipt: Mapping[str, Any], errors: list[str]) -> None:
    observed_fields = set(receipt)
    if observed_fields != TOP_LEVEL_FIELDS:
        errors.append(
            "top-level fields must match provider credential receipt contract: "
            f"missing={sorted(TOP_LEVEL_FIELDS - observed_fields)} "
            f"unexpected={sorted(observed_fields - TOP_LEVEL_FIELDS)}"
        )
    if receipt.get("receipt_id") != RECEIPT_ID:
        errors.append(f"receipt_id must be {RECEIPT_ID!r}")
    if receipt.get("secret_values_serialized") is not False:
        errors.append("secret_values_serialized must be false")
    if receipt.get("external_provider_call_performed") is not False:
        errors.append("external_provider_call_performed must be false")
    if not isinstance(receipt.get("install_github_secrets"), bool):
        errors.append("install_github_secrets must be boolean")
    if not isinstance(receipt.get("github_repo"), str):
        errors.append("github_repo must be a string")
    if not isinstance(receipt.get("next_action"), str) or not str(receipt.get("next_action", "")).strip():
        errors.append("next_action must be a non-empty string")
    _validate_timestamp(str(receipt.get("checked_at", "")), errors)


def _validate_bindings(receipt: Mapping[str, Any], errors: list[str]) -> None:
    bindings = receipt.get("bindings")
    if not isinstance(bindings, list):
        errors.append("bindings must be a list")
        return
    binding_by_name: dict[str, Mapping[str, Any]] = {}
    for binding in bindings:
        if not isinstance(binding, dict):
            errors.append("binding entries must be objects")
            continue
        observed_fields = set(binding)
        if observed_fields != BINDING_FIELDS:
            errors.append(
                "binding fields must match provider credential binding contract: "
                f"missing={sorted(BINDING_FIELDS - observed_fields)} "
                f"unexpected={sorted(observed_fields - BINDING_FIELDS)}"
            )
        name = str(binding.get("name", ""))
        if name in binding_by_name:
            errors.append(f"duplicate provider credential binding name {name}")
        binding_by_name[name] = binding
        _validate_binding(name, binding, receipt, errors)
    _validate_binding_sets(receipt, binding_by_name, errors)


def _validate_binding(
    name: str,
    binding: Mapping[str, Any],
    receipt: Mapping[str, Any],
    errors: list[str],
) -> None:
    if name not in REQUIRED_PROVIDER_CREDENTIALS:
        errors.append(f"unexpected provider credential binding name {name}")
    if binding.get("required") is not True:
        errors.append(f"{name} required must be true")
    if binding.get("value_serialized") is not False:
        errors.append(f"{name} value_serialized must be false")
    for field_name in ("present", "github_secret_install_attempted", "github_secret_installed"):
        if not isinstance(binding.get(field_name), bool):
            errors.append(f"{name} {field_name} must be boolean")
    expected_attempted = bool(receipt.get("install_github_secrets") is True and binding.get("present") is True)
    if binding.get("github_secret_install_attempted") is not expected_attempted:
        errors.append(f"{name} github_secret_install_attempted must be {expected_attempted}")
    blocker = str(binding.get("blocker", ""))
    if binding.get("present") is False and blocker != f"credential_missing:{name}":
        errors.append(f"{name} missing credential blocker mismatch")
    if binding.get("present") is True and binding.get("github_secret_installed") is True and blocker:
        errors.append(f"{name} installed credential binding must not have blocker")
    if binding.get("github_secret_installed") is True and binding.get("github_secret_install_attempted") is not True:
        errors.append(f"{name} installed secret must have an install attempt")


def _validate_binding_sets(
    receipt: Mapping[str, Any],
    binding_by_name: Mapping[str, Mapping[str, Any]],
    errors: list[str],
) -> None:
    observed_names = set(binding_by_name)
    expected_names = set(REQUIRED_PROVIDER_CREDENTIALS)
    if observed_names != expected_names:
        errors.append(
            "provider credential binding names must match required credentials: "
            f"observed_only={sorted(observed_names - expected_names)} "
            f"required_only={sorted(expected_names - observed_names)}"
        )
    missing_credentials = receipt.get("missing_credentials")
    if not isinstance(missing_credentials, list):
        errors.append("missing_credentials must be a list")
        return
    missing_set = {str(name) for name in missing_credentials}
    expected_missing = {name for name, binding in binding_by_name.items() if binding.get("present") is not True}
    if missing_set != expected_missing:
        errors.append(
            "missing_credentials must match bindings with present=false: "
            f"observed={sorted(missing_set)} expected={sorted(expected_missing)}"
        )
    failed_installs = {
        name
        for name, binding in binding_by_name.items()
        if str(binding.get("blocker", "")).startswith("github_secret_install_failed:")
    }
    expected_ready = not expected_missing and not failed_installs
    if receipt.get("ready") is not expected_ready:
        errors.append(f"ready must be {expected_ready} based on missing credentials and install blockers")


def _validate_timestamp(value: str, errors: list[str]) -> None:
    if not value:
        errors.append("checked_at timestamp is required")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append("checked_at timestamp must be ISO-8601")
        return
    if parsed.tzinfo is None:
        errors.append("checked_at timestamp must include timezone")


def _validation_result(
    receipt_path: Path,
    receipt: Mapping[str, Any],
    errors: list[str],
) -> ProviderCredentialBindingReceiptValidation:
    missing_credentials = receipt.get("missing_credentials", ())
    bindings = receipt.get("bindings", ())
    return ProviderCredentialBindingReceiptValidation(
        valid=not errors,
        ready=receipt.get("ready") is True,
        receipt_id=str(receipt.get("receipt_id", "")),
        receipt_path=_path_label(receipt_path),
        binding_count=len(bindings) if isinstance(bindings, list) else 0,
        missing_credentials=tuple(str(name) for name in missing_credentials) if isinstance(missing_credentials, list) else (),
        errors=tuple(errors),
    )


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _contains_secret_marker(raw_text: str) -> bool:
    normalized = raw_text.lower()
    return any(marker.lower() in normalized for marker in SECRET_VALUE_MARKERS)


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError(f"non-finite JSON constants are not permitted: {raw_constant}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse provider credential binding receipt validation CLI arguments."""

    parser = argparse.ArgumentParser(description="Validate redacted provider credential binding receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for redacted provider credential binding receipt validation."""

    args = parse_args(argv)
    result = validate_general_agent_provider_credential_binding_receipt(
        receipt_path=Path(args.receipt),
        require_ready=bool(args.require_ready),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"general-agent provider credential binding receipt ok ready={result.ready}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
