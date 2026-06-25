#!/usr/bin/env python3
"""Validate the Govern Cloud evaluate-route rollback witness.

Purpose: prove the public write-route rollback boundary for
    ``POST /v1/govern/evaluate`` without mutating deployment state.
Governance scope: public proxy allowlist, route rollback, API gateway health
    preservation, no outbound transport for blocked product write routes.
Dependencies: FastAPI TestClient and gateway.server.
Invariants:
  - Does not mutate DNS, Render, Cloudflare, secrets, or provider state.
  - Does not print raw secret values, host addresses, request bodies, headers,
    or response bodies.
  - Passes only when health/version stay allowlisted and evaluate stays blocked.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BLOCKED_ROUTE = "/v1/govern/evaluate"
PRESERVED_ROUTES = ("/v1/health", "/v1/version")
FALLBACK_PUBLIC_PROXY_PATHS = frozenset(PRESERVED_ROUTES)


@dataclass(frozen=True, slots=True)
class RouteProbe:
    """Bounded result for the blocked route rollback probe."""

    status_code: int
    outbound_transport_called: bool


def validate_govern_evaluate_route_rollback(
    *,
    allowlist: Iterable[str] | None = None,
    probe_runner: Callable[[], RouteProbe] | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Validate that evaluate-route rollback keeps the product write route closed."""
    observed_at = (now_utc or datetime.now(UTC)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    allowlist_set = frozenset(allowlist or _load_public_proxy_paths())
    preserved_routes_present = all(route in allowlist_set for route in PRESERVED_ROUTES)
    blocked_route_absent = BLOCKED_ROUTE not in allowlist_set
    probe = (probe_runner or _probe_blocked_evaluate_route)()
    blocked_route_returns_404 = probe.status_code == 404
    no_outbound_transport = probe.outbound_transport_called is False

    checks = {
        "preserved_routes_present": preserved_routes_present,
        "blocked_route_absent_from_allowlist": blocked_route_absent,
        "blocked_route_returns_404": blocked_route_returns_404,
        "blocked_route_no_outbound_transport": no_outbound_transport,
    }
    findings = [f"failed:{name}" for name, passed in checks.items() if not passed]
    closed = len(findings) == 0

    return {
        "schema_version": "govern_evaluate_route_rollback_witness.v1",
        "generated_at": observed_at,
        "solver_outcome": "SolvedVerified" if closed else "GovernanceBlocked",
        "proof_state": "Pass" if closed else "Fail",
        "route": f"POST {BLOCKED_ROUTE}",
        "rollback_state": "Ready" if closed else "AwaitingEvidence",
        "public_write_route_allowed": False,
        "dns_mutation": "none",
        "runtime_mutation": "none",
        "secret_values_included": False,
        "checks": checks,
        "finding_count": len(findings),
        "findings": findings,
        "rollback_action": {
            "action": "remove /v1/govern/evaluate from public proxy allowlist",
            "preserve_routes": list(PRESERVED_ROUTES),
            "verify_after_rollback": "POST /v1/govern/evaluate returns 404 without outbound transport",
        },
    }


def format_rollback_witness_report(witness: Mapping[str, Any]) -> str:
    """Format a public-safe rollback witness report."""
    checks = witness.get("checks") if isinstance(witness.get("checks"), Mapping) else {}
    findings = witness.get("findings") if isinstance(witness.get("findings"), list) else []
    return "\n".join(
        [
            f"govern_evaluate_route_rollback={witness.get('solver_outcome', 'Unknown')}",
            f"proof_state={witness.get('proof_state', 'Unknown')}",
            f"rollback_state={witness.get('rollback_state', 'Unknown')}",
            f"public_write_route_allowed={'true' if witness.get('public_write_route_allowed') else 'false'}",
            f"preserved_routes_present={'true' if checks.get('preserved_routes_present') else 'false'}",
            f"blocked_route_absent_from_allowlist={'true' if checks.get('blocked_route_absent_from_allowlist') else 'false'}",
            f"blocked_route_returns_404={'true' if checks.get('blocked_route_returns_404') else 'false'}",
            f"blocked_route_no_outbound_transport={'true' if checks.get('blocked_route_no_outbound_transport') else 'false'}",
            f"finding_count={len(findings)}",
            *[f"finding={finding}" for finding in findings],
            "secret_values=not_recorded",
            "host_addresses=not_recorded",
            "database_urls=not_recorded",
            "raw_response_bodies=not_recorded",
        ]
    )


def _probe_blocked_evaluate_route() -> RouteProbe:
    try:
        from gateway.server import create_gateway_app
    except ImportError:
        return RouteProbe(
            status_code=0,
            outbound_transport_called=False,
        )

    outbound_transport_called = False

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        nonlocal outbound_transport_called
        outbound_transport_called = True
        raise AssertionError("blocked evaluate rollback probe must not reach outbound transport")

    with _temporary_env(
        {
            "MULLU_GOVERN_CLOUD_STAGING_ENABLED": "true",
            "MULLU_GOVERN_CLOUD_PUBLIC_PROXY_ENABLED": "true",
            "MULLU_GOVERN_CLOUD_INTERNAL_URL": "http://mullusi-govern-cloud-staging:8000",
        }
    ), _temporary_urlopen(fail_if_called):
        response = TestClient(create_gateway_app()).post(BLOCKED_ROUTE, json={})
        return RouteProbe(
            status_code=response.status_code,
            outbound_transport_called=outbound_transport_called,
        )


def _load_public_proxy_paths() -> Iterable[str]:
    try:
        from gateway.server import GOVERN_CLOUD_PUBLIC_PROXY_PATHS
    except ImportError:
        return FALLBACK_PUBLIC_PROXY_PATHS
    return GOVERN_CLOUD_PUBLIC_PROXY_PATHS


@contextmanager
def _temporary_env(values: Mapping[str, str]):
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def _temporary_urlopen(replacement: Callable[..., Any]):
    original = urllib.request.urlopen
    urllib.request.urlopen = replacement  # type: ignore[assignment]
    try:
        yield
    finally:
        urllib.request.urlopen = original  # type: ignore[assignment]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of line report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    witness = validate_govern_evaluate_route_rollback()
    if args.json:
        print(json.dumps(witness, indent=2, sort_keys=False))
    else:
        print(format_rollback_witness_report(witness))
    return 0 if witness["proof_state"] == "Pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
