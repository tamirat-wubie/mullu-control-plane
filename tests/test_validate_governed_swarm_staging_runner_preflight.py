"""Tests for governed swarm staging runner preflight validation.

Purpose: keep saved runner preflight receipts proof-carrying before staging witness collection.
Governance scope: runner local surfaces, readiness outcome, and required check-set completeness.
Dependencies: governed swarm staging runner preflight schema, example receipt, and validator script.
Invariants: ready receipts require every required check to pass; blocked receipts cannot claim SolvedVerified.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.validate_governed_swarm_staging_runner_preflight import (
    validate_runner_preflight_file,
    validate_runner_preflight_payload,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = ROOT / "docs" / "governed-swarm-staging-runner-preflight-example.json"


def test_example_governed_swarm_staging_runner_preflight_passes() -> None:
    errors = validate_runner_preflight_file(EXAMPLE_PATH)

    assert errors == []
    assert EXAMPLE_PATH.exists()
    assert EXAMPLE_PATH.name == "governed-swarm-staging-runner-preflight-example.json"


def test_runner_preflight_rejects_missing_required_check() -> None:
    payload = _example_payload()
    payload["checks"] = [check for check in payload["checks"] if check["name"] != "audit_store_readable"]

    errors = validate_runner_preflight_payload(payload)

    assert len(errors) == 1
    assert "$.checks missing required checks" in errors[0]
    assert "audit_store_readable" in errors[0]


def test_runner_preflight_rejects_ready_with_failed_check() -> None:
    payload = _example_payload()
    payload["checks"][2]["passed"] = False

    errors = validate_runner_preflight_payload(payload)

    assert len(errors) == 1
    assert "$.ready cannot be true" in errors[0]
    assert "all checks passed" in errors[0]


def test_runner_preflight_rejects_not_ready_solved() -> None:
    payload = _example_payload()
    payload["ready"] = False

    errors = validate_runner_preflight_payload(payload)

    assert len(errors) == 1
    assert "$.outcome cannot be SolvedVerified" in errors[0]
    assert "ready is false" in errors[0]


def test_runner_preflight_rejects_runtime_bridge_detail_mismatch() -> None:
    payload = _example_payload()
    payload["checks"][2]["detail"] = "/opt/mullu/mullu-control-plane/mcoi"

    errors = validate_runner_preflight_payload(payload)

    assert len(errors) == 1
    assert "$.checks[runtime_bridge].detail" in errors[0]
    assert "/mcoi_runtime/swarm" in errors[0]


def _example_payload() -> dict[str, Any]:
    import json

    return deepcopy(json.loads(EXAMPLE_PATH.read_text(encoding="utf-8")))
