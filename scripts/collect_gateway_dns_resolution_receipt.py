#!/usr/bin/env python3
"""Collect a gateway DNS resolution receipt.

Purpose: turn gateway DNS resolution into a bounded evidence artifact for
deployment publication closure plans.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: Python socket resolution, argparse, and JSON receipt output.
Invariants:
  - Collection never mutates DNS, deployment status, workflows, or secrets.
  - Resolver exception details are bounded before serialization.
  - A non-resolving host writes a receipt and returns a non-zero gate status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "gateway_dns_resolution_receipt.json"
PLACEHOLDER_HOST = "gateway.example.com"

ResolvedAddress = tuple[int, str]
Resolver = Callable[[str], Iterable[ResolvedAddress]]


@dataclass(frozen=True, slots=True)
class GatewayDnsResolutionReceipt:
    """Evidence from one gateway DNS resolution attempt."""

    receipt_id: str
    host: str
    checked_at_utc: str
    resolved: bool
    addresses: tuple[str, ...]
    error: str | None
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready DNS resolution receipt."""
        payload = asdict(self)
        payload["addresses"] = list(self.addresses)
        return payload


def collect_gateway_dns_resolution_receipt(
    *,
    host: str,
    resolver: Resolver = None,
    now_utc: datetime | None = None,
) -> GatewayDnsResolutionReceipt:
    """Resolve one gateway host and return a bounded receipt."""
    normalized_host = _require_gateway_host(host)
    effective_resolver = resolver or _socket_resolver
    checked_at = _format_utc(now_utc or datetime.now(UTC))
    try:
        addresses = _resolved_addresses(normalized_host, effective_resolver)
        error = None
    except OSError:
        addresses = ()
        error = "resolution_error"
    resolved = bool(addresses)
    receipt_material = {
        "host": normalized_host,
        "resolved": resolved,
        "addresses": addresses,
        "error": error,
    }
    digest = hashlib.sha256(
        json.dumps(receipt_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return GatewayDnsResolutionReceipt(
        receipt_id=f"gateway-dns-resolution-{digest[:16]}",
        host=normalized_host,
        checked_at_utc=checked_at,
        resolved=resolved,
        addresses=addresses,
        error=error,
        next_action=(
            "rerun deployment witness preflight with endpoint probes enabled"
            if resolved
            else "publish a DNS A, AAAA, or CNAME record for the gateway host, then rerun this receipt"
        ),
    )


def write_gateway_dns_resolution_receipt(
    receipt: GatewayDnsResolutionReceipt,
    output_path: Path,
) -> Path:
    """Write one DNS resolution receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _resolved_addresses(host: str, resolver: Resolver) -> tuple[str, ...]:
    addresses = {
        address
        for family, address in resolver(host)
        if family in {socket.AF_INET, socket.AF_INET6} and address
    }
    return tuple(sorted(addresses))


def _socket_resolver(host: str) -> tuple[ResolvedAddress, ...]:
    return tuple(
        (result[0], str(result[4][0]))
        for result in socket.getaddrinfo(host, None)
        if result[4] and result[4][0]
    )


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
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", normalized_host):
        raise RuntimeError("gateway host contains invalid DNS characters")
    if "." not in normalized_host:
        raise RuntimeError("gateway host must be a fully qualified DNS name")
    return normalized_host


def _host_from_gateway_url(gateway_url: str) -> str:
    parsed = urlparse(gateway_url.strip())
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise RuntimeError("gateway URL must include http or https scheme and host")
    return parsed.hostname


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse DNS resolution receipt CLI arguments."""
    parser = argparse.ArgumentParser(description="Collect a gateway DNS resolution receipt.")
    parser.add_argument("--host", default=os.environ.get("MULLU_GATEWAY_HOST", ""))
    parser.add_argument("--gateway-url", default=os.environ.get("MULLU_GATEWAY_URL", ""))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    *,
    resolver: Resolver = None,
    now_utc: datetime | None = None,
) -> int:
    """CLI entry point for DNS resolution receipt collection."""
    args = parse_args(argv)
    try:
        host = args.host or _host_from_gateway_url(args.gateway_url)
        receipt = collect_gateway_dns_resolution_receipt(
            host=host,
            resolver=resolver,
            now_utc=now_utc,
        )
    except RuntimeError as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "error": str(exc),
                        "receipt_written": False,
                        "resolved": False,
                        "status": "failed",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print("gateway DNS resolution receipt failed")
        return 1
    write_gateway_dns_resolution_receipt(receipt, Path(args.output))
    if args.json:
        print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    elif receipt.resolved:
        print(f"gateway DNS resolved: {receipt.host}")
    else:
        print(f"gateway DNS unresolved: {receipt.host}")
    return 0 if receipt.resolved else 1


if __name__ == "__main__":
    raise SystemExit(main())
