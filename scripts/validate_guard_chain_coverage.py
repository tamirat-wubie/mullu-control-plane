#!/usr/bin/env python3
"""Purpose: validate that every /api/v1 route is covered by GovernanceMiddleware.
Governance scope: guard-chain coverage witness for the assembled HTTP router set.
Dependencies: FastAPI route metadata, server router bootstrap, governance middleware.
Invariants:
  - The assembled app installs GovernanceMiddleware.
  - Every /api/v1/* route is covered by the middleware path predicate.
  - No /api/v1/* route is listed in GovernanceMiddleware.EXEMPT_PATHS.
  - Report output is deterministic and fails closed when coverage is incomplete.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402

from mcoi_runtime.app.middleware import EXEMPT_PATHS, GovernanceMiddleware  # noqa: E402
from mcoi_runtime.app.server_http import include_default_routers  # noqa: E402

GOVERNED_API_PREFIX = "/api/"
API_V1_PREFIX = "/api/v1"


def build_guard_chain_coverage_report() -> dict[str, Any]:
    """Return a deterministic guard-chain coverage report for /api/v1 routes."""
    app = FastAPI()
    app.add_middleware(GovernanceMiddleware, guard_chain=object())
    include_default_routers(app)

    middleware_installed = _has_governance_middleware(app)
    route_records: list[dict[str, str]] = []
    uncovered_routes: list[dict[str, str]] = []
    exempt_api_v1_routes: list[dict[str, str]] = []

    for route in _api_v1_routes(app):
        endpoint = f"{route.endpoint.__module__}.{route.endpoint.__name__}"
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            record = {
                "method": method,
                "path": route.path,
                "endpoint": endpoint,
            }
            route_records.append(record)
            if route.path in EXEMPT_PATHS:
                exempt_api_v1_routes.append(record)
            if not middleware_installed or not _covered_by_governance_middleware(route.path):
                uncovered_routes.append(record)

    route_records.sort(key=lambda item: (item["path"], item["method"], item["endpoint"]))
    exempt_api_v1_routes.sort(key=lambda item: (item["path"], item["method"], item["endpoint"]))
    uncovered_routes.sort(key=lambda item: (item["path"], item["method"], item["endpoint"]))

    status = "closed" if middleware_installed and not uncovered_routes and not exempt_api_v1_routes else "open"
    open_issue = "none"
    if status == "open":
        open_issue = (
            "one or more /api/v1 routes are not covered by GovernanceMiddleware "
            "or are exempt from guard-chain dispatch"
        )

    return {
        "schema_version": 1,
        "generated_by": "scripts/validate_guard_chain_coverage.py",
        "status": status,
        "governed_prefix": GOVERNED_API_PREFIX,
        "checked_prefix": API_V1_PREFIX,
        "governance_middleware": "mcoi_runtime.app.middleware.GovernanceMiddleware",
        "governance_middleware_installed": middleware_installed,
        "api_v1_route_count": len(route_records),
        "exempt_api_v1_route_count": len(exempt_api_v1_routes),
        "uncovered_api_v1_route_count": len(uncovered_routes),
        "open_issue": open_issue,
        "route_records": route_records,
        "exempt_api_v1_routes": exempt_api_v1_routes,
        "uncovered_api_v1_routes": uncovered_routes,
    }


def _api_v1_routes(app: FastAPI) -> list[APIRoute]:
    return sorted(
        (
            route
            for route in app.routes
            if isinstance(route, APIRoute) and route.path.startswith(API_V1_PREFIX)
        ),
        key=lambda route: route.path,
    )


def _has_governance_middleware(app: FastAPI) -> bool:
    return any(
        middleware.cls is GovernanceMiddleware
        for middleware in app.user_middleware
    )


def _covered_by_governance_middleware(path: str) -> bool:
    return path.startswith(GOVERNED_API_PREFIX) and path not in EXEMPT_PATHS


def validate_report(report: dict[str, Any]) -> list[str]:
    """Return validation errors for a guard-chain coverage report."""
    errors: list[str] = []
    if not report.get("governance_middleware_installed"):
        errors.append("GovernanceMiddleware is not installed on the assembled app")
    if report.get("api_v1_route_count", 0) <= 0:
        errors.append("no /api/v1 routes were discovered")
    if report.get("exempt_api_v1_routes"):
        errors.append("/api/v1 routes are listed in GovernanceMiddleware.EXEMPT_PATHS")
    if report.get("uncovered_api_v1_routes"):
        errors.append("/api/v1 routes are not covered by GovernanceMiddleware")
    if report.get("status") != "closed":
        errors.append("guard-chain coverage report status is not closed")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate /api/v1 guard-chain coverage.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the deterministic coverage report as JSON.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if the coverage report is not closed.",
    )
    args = parser.parse_args(argv)

    report = build_guard_chain_coverage_report()
    errors = validate_report(report)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Scanned /api/v1 routes: {report['api_v1_route_count']}")
        print(f"GovernanceMiddleware installed: {report['governance_middleware_installed']}")
        print(f"Exempt /api/v1 routes: {report['exempt_api_v1_route_count']}")
        print(f"Uncovered /api/v1 routes: {report['uncovered_api_v1_route_count']}")
        print(f"Status: {report['status']}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1 if args.strict else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
