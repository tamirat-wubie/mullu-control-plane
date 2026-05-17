"""Tests for governed swarm staging activation witness collection.

Purpose: verify the staging collector emits proof-carrying activation evidence.
Governance scope: route probes, audit receipt closure, release pin, and fail-closed output.
Dependencies: scripts.collect_governed_swarm_staging_activation_witness.
Invariants: successful collection validates against the public schema; missing audit closure is not SolvedVerified.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.collect_governed_swarm_staging_activation_witness import (
    HttpResult,
    collect_activation_witness,
    main,
)
from scripts.validate_governed_swarm_staging_activation_witness import validate_witness_payload


CONTROL_PLANE_COMMIT = "0a81ea4b21adb77e2e7f5ee9f3f5894ef48a0b5b"


def test_collect_governed_swarm_staging_activation_witness_passes(tmp_path: Path) -> None:
    audit_store = tmp_path / "swarm-runs.jsonl"
    audit_store.write_text(json.dumps({"closure_certificate": {"status": "closed"}}) + "\n", encoding="utf-8")

    witness = collect_activation_witness(
        staging_url="https://staging.example",
        control_plane_commit=CONTROL_PLANE_COMMIT,
        runtime_path="/opt/mullu/mullu-governed-swarm/mcoi",
        audit_store_path=str(audit_store),
        run_id="swarm-run-staging-001",
        opener=_successful_opener,
        clock=lambda: "2026-05-17T13:30:00Z",
    )

    assert validate_witness_payload(witness) == []
    assert witness["outcome"] == "SolvedVerified"
    assert witness["runtime_release_tag"] == "v0.1.0-governed-swarm"
    assert witness["invoice_smoke"]["run_id"] == "swarm-run-staging-001"
    assert witness["audit_store"]["latest_receipt_has_closure"] is True


def test_collect_governed_swarm_staging_activation_witness_blocks_without_audit_closure(
    tmp_path: Path,
) -> None:
    audit_store = tmp_path / "swarm-runs.jsonl"
    audit_store.write_text(json.dumps({"record": {"status": "closed"}}) + "\n", encoding="utf-8")

    witness = collect_activation_witness(
        staging_url="https://staging.example",
        control_plane_commit=CONTROL_PLANE_COMMIT,
        runtime_path="/opt/mullu/mullu-governed-swarm/mcoi",
        audit_store_path=str(audit_store),
        run_id="swarm-run-staging-001",
        opener=_successful_opener,
        clock=lambda: "2026-05-17T13:30:00Z",
    )

    assert witness["outcome"] == "AwaitingEvidence"
    assert any("latest receipt lacks closure proof" in error for error in witness["errors"])
    assert validate_witness_payload(witness)


def test_collect_governed_swarm_staging_activation_witness_cli_writes_valid_witness(
    tmp_path: Path,
    monkeypatch,
) -> None:
    audit_store = tmp_path / "swarm-runs.jsonl"
    output_path = tmp_path / "witness.json"
    audit_store.write_text(json.dumps({"closure": {"status": "closed"}}) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        "scripts.collect_governed_swarm_staging_activation_witness._http_json",
        _successful_opener,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "collect_governed_swarm_staging_activation_witness.py",
            "--staging-url",
            "https://staging.example",
            "--control-plane-commit",
            CONTROL_PLANE_COMMIT,
            "--runtime-path",
            "/opt/mullu/mullu-governed-swarm/mcoi",
            "--audit-store-path",
            str(audit_store),
            "--output",
            str(output_path),
            "--run-id",
            "swarm-run-staging-001",
        ],
    )

    exit_code = main()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert payload["outcome"] == "SolvedVerified"
    assert validate_witness_payload(payload) == []


def _successful_opener(request: Any, timeout_seconds: float) -> HttpResult:
    url = request.full_url if hasattr(request, "full_url") else str(request)
    assert timeout_seconds > 0
    if url.endswith("/api/v1/swarm/invoice-runs"):
        return HttpResult(
            status=200,
            payload={
                "run_id": "swarm-run-staging-001",
                "governed": True,
                "status": "closed",
            },
        )
    if url.endswith("/api/v1/swarm/runs/swarm-run-staging-001"):
        return HttpResult(
            status=200,
            payload={"payload": {"record": {"run_id": "swarm-run-staging-001"}}},
        )
    if url.endswith("/api/v1/swarm/runs"):
        return HttpResult(status=200, payload={"payload": {"count": 1}})
    raise AssertionError(f"unexpected URL {url}")
