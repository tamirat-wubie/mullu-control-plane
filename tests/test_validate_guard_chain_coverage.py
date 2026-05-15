"""Purpose: verify the guard-chain coverage validator.
Governance scope: closes the GovernanceMiddleware route-coverage CI gap.
Dependencies: scripts.validate_guard_chain_coverage.
Invariants: /api/v1 routes are discovered, non-exempt, and covered by middleware.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from validate_guard_chain_coverage import (  # noqa: E402
    build_guard_chain_coverage_report,
    validate_report,
)


def test_guard_chain_coverage_report_is_closed() -> None:
    report = build_guard_chain_coverage_report()

    assert report["status"] == "closed"
    assert report["governance_middleware_installed"] is True
    assert report["api_v1_route_count"] > 0
    assert report["exempt_api_v1_route_count"] == 0
    assert report["uncovered_api_v1_route_count"] == 0
    assert report["open_issue"] == "none"
    assert validate_report(report) == []


def test_guard_chain_coverage_report_contains_known_routes() -> None:
    report = build_guard_chain_coverage_report()
    route_keys = {
        (record["method"], record["path"])
        for record in report["route_records"]
    }

    assert ("POST", "/api/v1/chat") in route_keys
    assert ("GET", "/api/v1/engineering-puzzle/goal-delta") not in route_keys
    assert ("POST", "/api/v1/engineering-puzzle/goal-delta") in route_keys
    assert ("POST", "/api/v1/coordination/checkpoint") in route_keys
    assert ("GET", "/api/v1/flags") in route_keys
    assert all(path.startswith("/api/v1") for _, path in route_keys)


def test_guard_chain_coverage_validator_detects_open_report() -> None:
    report = build_guard_chain_coverage_report()
    report["governance_middleware_installed"] = False
    report["status"] = "open"

    errors = validate_report(report)

    assert len(errors) >= 2
    assert "GovernanceMiddleware is not installed on the assembled app" in errors
    assert "guard-chain coverage report status is not closed" in errors


def test_guard_chain_coverage_cli_strict_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "validate_guard_chain_coverage.py"), "--strict"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Scanned /api/v1 routes:" in result.stdout
    assert "Status: closed" in result.stdout
    assert result.stderr == ""
