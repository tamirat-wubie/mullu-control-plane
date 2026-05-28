"""Tests for governed swarm staging activation witness validation.

Purpose: keep staging activation evidence proof-carrying and bundled-runtime-bound.
Governance scope: bundled runtime witness, route probes, audit persistence, rollback proof.
Dependencies: governed swarm staging witness schema, example witness, and validator script.
Invariants: malformed runtime labels, missing routes, and missing audit closure fail closed.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.validate_governed_swarm_staging_activation_witness import (
    validate_witness_file,
    validate_witness_payload,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = ROOT / "docs" / "governed-swarm-staging-activation-witness-example.json"


def test_example_governed_swarm_staging_activation_witness_passes() -> None:
    errors = validate_witness_file(EXAMPLE_PATH)

    assert errors == []
    assert EXAMPLE_PATH.exists()
    assert EXAMPLE_PATH.name == "governed-swarm-staging-activation-witness-example.json"


def test_governed_swarm_staging_witness_rejects_wrong_runtime_tag() -> None:
    payload = _example_payload()
    payload["runtime_release_tag"] = "latest"

    errors = validate_witness_payload(payload)

    assert len(errors) == 1
    assert "$.runtime_release_tag" in errors[0]
    assert "control-plane-bundled-runtime" in errors[0]


def test_governed_swarm_staging_witness_rejects_runtime_commit_mismatch() -> None:
    payload = _example_payload()
    payload["runtime_commit"] = "0" * 40

    errors = validate_witness_payload(payload)

    assert len(errors) == 1
    assert "$.runtime_commit" in errors[0]
    assert "$.control_plane_commit" in errors[0]


def test_governed_swarm_staging_witness_rejects_missing_route_probe() -> None:
    payload = _example_payload()
    payload["route_probes"][2] = payload["route_probes"][1]

    errors = validate_witness_payload(payload)

    assert len(errors) == 1
    assert "$.route_probes" in errors[0]
    assert "/api/v1/swarm/runs" in errors[0]


def test_governed_swarm_staging_witness_rejects_unmounted_extension_health() -> None:
    payload = _example_payload()
    payload["extension_health"]["governed_swarm"]["mounted"] = False
    payload["extension_health"]["governed_swarm"]["state"] = "enabled_unmounted"

    errors = validate_witness_payload(payload)

    assert len(errors) == 1
    assert "$.extension_health.governed_swarm" in errors[0]
    assert "mounted" in errors[0]


def test_governed_swarm_staging_witness_rejects_audit_path_mismatch() -> None:
    payload = _example_payload()
    payload["audit_store"]["path"] = "/tmp/not-the-configured-audit.jsonl"

    errors = validate_witness_payload(payload)

    assert len(errors) == 1
    assert "$.feature_flags.MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH" in errors[0]
    assert "$.audit_store.path" in errors[0]


def test_governed_swarm_staging_witness_rejects_solved_with_errors() -> None:
    payload = _example_payload()
    payload["errors"] = ["route probe failed"]

    errors = validate_witness_payload(payload)

    assert len(errors) == 1
    assert "$.errors" in errors[0]
    assert "SolvedVerified" in errors[0]


def _example_payload() -> dict[str, Any]:
    import json

    return deepcopy(json.loads(EXAMPLE_PATH.read_text(encoding="utf-8")))
