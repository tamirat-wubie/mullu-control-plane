#!/usr/bin/env python3
"""Emit a gateway DNS target binding receipt.

Purpose: record the operator-selected gateway DNS origin target before DNS
publication is attempted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: argparse, JSON receipt output, and deterministic target parsing.
Invariants:
  - Emission never mutates DNS, GitHub variables, workflows, or secrets.
  - A ready receipt requires host, URL, environment, record type, provider, and target.
  - Target syntax is validated without resolving or publishing the record.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "gateway_dns_target_binding_receipt.json"
PLACEHOLDER_HOST = "gateway.example.com"
BOUND_NEXT_ACTION = "publish DNS record and rerun gateway DNS resolution receipt"
MISSING_TARGET_NEXT_ACTION = "select gateway origin target before DNS publication"
MISSING_RECORD_TYPE_NEXT_ACTION = "select DNS record type before DNS publication"
MISSING_PROVIDER_NEXT_ACTION = "record authoritative DNS provider before DNS publication"


@dataclass(frozen=True, slots=True)
class GatewayDnsTargetBindingReceipt:
    """Evidence for one intended gateway DNS binding."""

    receipt_id: str
    gateway_host: str
    gateway_url: str
    expected_environment: str
    record_type: str
    target: str
    target_kind: str
    provider: str
    binding_state: str
    ready: bool
    checked_at_utc: str
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready target binding receipt."""
        return asdict(self)


def emit_gateway_dns_target_binding_receipt(
    *,
    gateway_host: str,
    gateway_url: str,
    expected_environment: str,
    record_type: str,
    target: str,
    provider: str,
    now_utc: datetime | None = None,
) -> GatewayDnsTargetBindingReceipt:
    """Build a deterministic gateway DNS target binding receipt."""
    normalized_host = _require_gateway_host(gateway_host or _host_from_gateway_url(gateway_url))
    normalized_url = _require_gateway_url(gateway_url, normalized_host)
    normalized_environment = _require_expected_environment(expected_environment)
    normalized_record_type = record_type.strip().upper()
    normalized_target = target.strip().lower()
    normalized_provider = provider.strip()

    binding_state = _binding_state(
        record_type=normalized_record_type,
        target=normalized_target,
        provider=normalized_provider,
    )
    target_kind = "missing"
    if binding_state == "bound":
        target_kind = _target_kind(record_type=normalized_record_type, target=normalized_target)

    ready = binding_state == "bound"
    checked_at = _format_utc(now_utc or datetime.now(UTC))
    next_action = _next_action(binding_state)
    receipt_material = {
        "gateway_host": normalized_host,
        "gateway_url": normalized_url,
        "expected_environment": normalized_environment,
        "record_type": normalized_record_type,
        "target": normalized_target,
        "target_kind": target_kind,
        "provider": normalized_provider,
        "binding_state": binding_state,
        "ready": ready,
    }
    digest = hashlib.sha256(
        json.dumps(receipt_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return GatewayDnsTargetBindingReceipt(
        receipt_id=f"gateway-dns-target-binding-{digest[:16]}",
        gateway_host=normalized_host,
        gateway_url=normalized_url,
        expected_environment=normalized_environment,
        record_type=normalized_record_type,
        target=normalized_target,
        target_kind=target_kind,
        provider=normalized_provider,
        binding_state=binding_state,
        ready=ready,
        checked_at_utc=checked_at,
        next_action=next_action,
    )


def write_gateway_dns_target_binding_receipt(
    receipt: GatewayDnsTargetBindingReceipt,
    output_path: Path,
) -> Path:
    """Write one gateway DNS target binding receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _binding_state(*, record_type: str, target: str, provider: str) -> str:
    if not target:
        return "missing-target"
    if not record_type:
        return "missing-record-type"
    if not provider:
        return "missing-provider"
    return "bound"


def _target_kind(*, record_type: str, target: str) -> str:
    if record_type not in {"A", "AAAA", "CNAME"}:
        raise RuntimeError("DNS record type must be A, AAAA, or CNAME")
    if record_type == "A":
        try:
            address = ipaddress.ip_address(target)
        except ValueError as exc:
            raise RuntimeError("A record target must be an IPv4 address") from exc
        if address.version != 4:
            raise RuntimeError("A record target must be an IPv4 address")
        return "ipv4"
    if record_type == "AAAA":
        try:
            address = ipaddress.ip_address(target)
        except ValueError as exc:
            raise RuntimeError("AAAA record target must be an IPv6 address") from exc
        if address.version != 6:
            raise RuntimeError("AAAA record target must be an IPv6 address")
        return "ipv6"
    try:
        ipaddress.ip_address(target)
    except ValueError:
        pass
    else:
        raise RuntimeError("CNAME record target must be a hostname")
    _require_gateway_host(target)
    return "hostname"


def _require_gateway_host(host: str) -> str:
    normalized_host = host.strip().lower()
    if not normalized_host:
        raise RuntimeError("gateway host is required")
    if normalized_host.startswith(("https://", "http://")):
        raise RuntimeError("gateway host must not include URL scheme")
    if "/" in normalized_host or ":" in normalized_host:
        raise RuntimeError("gateway host must not include path or port")
    if normalized_host == PLACEHOLDER_HOST:
        raise RuntimeError("gateway host must replace gateway.example.com")
    if not _is_dns_name(normalized_host):
        raise RuntimeError("gateway host contains invalid DNS characters")
    if "." not in normalized_host:
        raise RuntimeError("gateway host must be a fully qualified DNS name")
    return normalized_host


def _is_dns_name(value: str) -> bool:
    if not value or len(value) > 253:
        return False
    labels = value.split(".")
    if any(not label or len(label) > 63 for label in labels):
        return False
    return all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)


def _require_gateway_url(gateway_url: str, expected_host: str) -> str:
    parsed = urlparse(gateway_url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError("gateway URL must include https scheme and host")
    if parsed.port or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise RuntimeError("gateway URL must not include port, path, query, or fragment")
    normalized_host = _require_gateway_host(parsed.hostname)
    if normalized_host != expected_host:
        raise RuntimeError("gateway URL host must match gateway host")
    return f"https://{normalized_host}"


def _host_from_gateway_url(gateway_url: str) -> str:
    parsed = urlparse(gateway_url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError("gateway host or gateway URL is required")
    return parsed.hostname


def _require_expected_environment(expected_environment: str) -> str:
    normalized_environment = expected_environment.strip().lower()
    if normalized_environment not in {"pilot", "production"}:
        raise RuntimeError("expected environment must be pilot or production")
    return normalized_environment


def _next_action(binding_state: str) -> str:
    if binding_state == "bound":
        return BOUND_NEXT_ACTION
    if binding_state == "missing-target":
        return MISSING_TARGET_NEXT_ACTION
    if binding_state == "missing-record-type":
        return MISSING_RECORD_TYPE_NEXT_ACTION
    if binding_state == "missing-provider":
        return MISSING_PROVIDER_NEXT_ACTION
    raise RuntimeError("unsupported gateway DNS binding state")


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse gateway DNS target binding receipt arguments."""
    parser = argparse.ArgumentParser(description="Emit a gateway DNS target binding receipt.")
    parser.add_argument("--gateway-host", default=os.environ.get("MULLU_GATEWAY_HOST", ""))
    parser.add_argument("--gateway-url", default=os.environ.get("MULLU_GATEWAY_URL", ""))
    parser.add_argument(
        "--expected-environment",
        default=os.environ.get("MULLU_EXPECTED_RUNTIME_ENV", "pilot"),
        choices=("pilot", "production"),
    )
    parser.add_argument("--record-type", default=os.environ.get("MULLU_GATEWAY_DNS_RECORD_TYPE", ""))
    parser.add_argument("--target", default=os.environ.get("MULLU_GATEWAY_DNS_TARGET", ""))
    parser.add_argument("--provider", default=os.environ.get("MULLU_DNS_PROVIDER", ""))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    *,
    now_utc: datetime | None = None,
) -> int:
    """CLI entry point for gateway DNS target binding receipt emission."""
    args = parse_args(argv)
    try:
        receipt = emit_gateway_dns_target_binding_receipt(
            gateway_host=args.gateway_host,
            gateway_url=args.gateway_url,
            expected_environment=args.expected_environment,
            record_type=args.record_type,
            target=args.target,
            provider=args.provider,
            now_utc=now_utc,
        )
    except RuntimeError as exc:
        print(f"gateway DNS target binding receipt emission failed: {exc}", file=sys.stderr)
        return 1
    output_path = write_gateway_dns_target_binding_receipt(receipt, Path(args.output))
    if args.json:
        print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"target_binding_receipt: {output_path}")
        print(f"gateway_host: {receipt.gateway_host}")
        print(f"binding_state: {receipt.binding_state}")
        print(f"ready: {str(receipt.ready).lower()}")
    return 0 if receipt.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
