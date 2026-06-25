"""Tests for the Govern Cloud evaluate-route rollback witness validator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.validate_govern_evaluate_route_rollback import (
    BLOCKED_ROUTE,
    PRESERVED_ROUTES,
    RouteProbe,
    format_rollback_witness_report,
    validate_govern_evaluate_route_rollback,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = REPO_ROOT / "scripts" / "validate_govern_evaluate_route_rollback.py"


def test_current_gateway_rollback_witness_passes() -> None:
    witness = validate_govern_evaluate_route_rollback()
    report = format_rollback_witness_report(witness)

    assert witness["solver_outcome"] == "SolvedVerified"
    assert witness["proof_state"] == "Pass"
    assert witness["rollback_state"] == "Ready"
    assert witness["public_write_route_allowed"] is False
    assert witness["checks"]["preserved_routes_present"] is True
    assert witness["checks"]["blocked_route_absent_from_allowlist"] is True
    assert witness["checks"]["blocked_route_returns_404"] is True
    assert witness["checks"]["blocked_route_no_outbound_transport"] is True
    assert witness["finding_count"] == 0
    assert "secret_values=not_recorded" in report


def test_rollback_witness_blocks_if_evaluate_route_is_allowlisted() -> None:
    witness = validate_govern_evaluate_route_rollback(
        allowlist=(*PRESERVED_ROUTES, BLOCKED_ROUTE),
        probe_runner=lambda: RouteProbe(status_code=404, outbound_transport_called=False),
    )

    assert witness["solver_outcome"] == "GovernanceBlocked"
    assert witness["proof_state"] == "Fail"
    assert witness["rollback_state"] == "AwaitingEvidence"
    assert "failed:blocked_route_absent_from_allowlist" in witness["findings"]


def test_rollback_witness_preserves_explicit_empty_allowlist() -> None:
    witness = validate_govern_evaluate_route_rollback(
        allowlist=(),
        probe_runner=lambda: RouteProbe(status_code=404, outbound_transport_called=False),
    )

    assert witness["solver_outcome"] == "GovernanceBlocked"
    assert witness["proof_state"] == "Fail"
    assert witness["checks"]["preserved_routes_present"] is False
    assert witness["checks"]["blocked_route_absent_from_allowlist"] is True
    assert "failed:preserved_routes_present" in witness["findings"]


def test_rollback_witness_blocks_if_probe_reaches_transport() -> None:
    witness = validate_govern_evaluate_route_rollback(
        probe_runner=lambda: RouteProbe(status_code=404, outbound_transport_called=True),
    )

    assert witness["proof_state"] == "Fail"
    assert "failed:blocked_route_no_outbound_transport" in witness["findings"]


def test_cli_json_output_is_public_safe() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)

    assert result.returncode in {0, 1}
    assert payload["proof_state"] in {"Pass", "Fail"}
    assert payload["secret_values_included"] is False
    assert "postgres://" not in result.stdout.lower()
    assert "traceback" not in result.stderr.lower()
