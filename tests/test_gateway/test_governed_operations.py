"""Governed operations read-model tests.

Purpose: verify loop registry, gap registry, receipt records, closure
contracts, drift checks, and readiness snapshots remain non-mutating and
evidence-bound.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway.governed_operations and governed operations schema.
Invariants:
  - Missing evidence creates a gap instead of success.
  - Closure requires required evidence and aligned observed state.
  - Drift is reported as a first-class readiness blocker.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from gateway.governed_operations import (
    ClosureContract,
    DriftStatus,
    GovernedOperationsKernel,
    LoopRegistration,
    ReadinessClass,
    default_loop_registry,
    receipt_from_projection,
)
from gateway.server import _governed_operations_console_html, create_gateway_app
from scripts.validate_schemas import _load_schema, _validate_schema_instance

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "governed_operations_snapshot.schema.json"
GENERATED_AT = "2026-06-11T20:00:00+00:00"


def test_missing_evidence_becomes_blocking_gap_not_success() -> None:
    loop = _single_loop()

    snapshot = GovernedOperationsKernel().build_snapshot(
        loops=(loop,),
        observed_states={"deployment_witness": "witnessed"},
        generated_at=GENERATED_AT,
    )
    payload = snapshot.to_json_dict()

    assert snapshot.readiness_class == ReadinessClass.CLASS_D
    assert snapshot.closed_loop_count == 0
    assert snapshot.blocking_gap_count == 1
    assert payload["gaps"][0]["blocker_type"] == "evidence_missing"
    assert payload["closure_results"][0]["missing_evidence_refs"] == ["deployment_witness:current"]


def test_required_evidence_and_aligned_state_close_loop() -> None:
    loop = _single_loop()
    receipt = receipt_from_projection(
        receipt_id="receipt://deployment-witness-current",
        action="deployment_witness_read",
        actor="codex",
        authority="read_only",
        evidence_refs=("deployment_witness:current",),
        policy_result="pass",
        timestamp=GENERATED_AT,
        status="witnessed",
        input_payload={"loop_id": loop.loop_id},
        output_payload={"status": "witnessed"},
    )

    snapshot = GovernedOperationsKernel().build_snapshot(
        loops=(loop,),
        receipts=(receipt,),
        observed_states={"deployment_witness": "witnessed"},
        generated_at=GENERATED_AT,
    )
    payload = snapshot.to_json_dict()

    assert snapshot.readiness_class == ReadinessClass.CLASS_A
    assert snapshot.closed_loop_count == 1
    assert snapshot.gap_count == 0
    assert payload["closure_results"][0]["closed"] is True
    assert payload["receipts"][0]["input_hash"] != payload["receipts"][0]["output_hash"]


def test_drift_check_blocks_closure_even_with_evidence() -> None:
    loop = _single_loop(evidence_refs=("deployment_witness:current",))

    snapshot = GovernedOperationsKernel().build_snapshot(
        loops=(loop,),
        observed_states={"deployment_witness": "failed"},
        generated_at=GENERATED_AT,
    )
    payload = snapshot.to_json_dict()

    assert snapshot.drift_count == 1
    assert snapshot.readiness_status == "blocked"
    assert snapshot.drift_checks[0].status == DriftStatus.DRIFTED
    assert payload["gaps"][0]["blocker_type"] == "runtime_drift"
    assert payload["closure_results"][0]["drift_status"] == "drifted"


def test_default_registry_registers_requested_control_plane_loops() -> None:
    registry = default_loop_registry()
    loop_ids = {loop.loop_id for loop in registry}

    assert len(registry) == 7
    assert "deployment_witness" in loop_ids
    assert "runtime_conformance" in loop_ids
    assert "adapter_promotion_loop" in loop_ids
    assert all(loop.closure_contract.required_evidence_refs for loop in registry)


def test_governed_operations_snapshot_matches_schema() -> None:
    loop = _single_loop(evidence_refs=("deployment_witness:current",))
    snapshot = GovernedOperationsKernel().build_snapshot(
        loops=(loop,),
        observed_states={"deployment_witness": "witnessed"},
        generated_at=GENERATED_AT,
    )
    payload = snapshot.to_json_dict()

    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), payload)

    assert errors == []
    assert payload["snapshot_id"].startswith("governed-operations-")
    assert payload["snapshot_hash"]
    assert payload["loops"][0]["closure_contract"]["rollback_path"]
    assert payload["readiness_class"] == "class_a"


def test_governed_operations_read_model_endpoint_is_schema_backed(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_RUNTIME_CONFORMANCE_SECRET", "conformance-secret")
    monkeypatch.setenv("MULLU_RUNTIME_WITNESS_SECRET", "witness-secret")
    monkeypatch.setenv("MULLU_DEPLOYMENT_WITNESS_SECRET", "deployment-secret")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get("/governed-operations/read-model")
    payload = response.json()
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), payload)

    assert response.status_code == 200
    assert errors == []
    assert payload["loop_count"] == 7
    assert payload["readiness_class"] == "class_d"
    assert any(gap["blocker_type"] == "evidence_missing" for gap in payload["gaps"])


def test_governed_operations_console_is_read_only_projection(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_RUNTIME_CONFORMANCE_SECRET", "conformance-secret")
    monkeypatch.setenv("MULLU_RUNTIME_WITNESS_SECRET", "witness-secret")
    monkeypatch.setenv("MULLU_DEPLOYMENT_WITNESS_SECRET", "deployment-secret")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get("/governed-operations/console")
    read_model = client.get("/governed-operations/read-model").json()

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Mullu Governed Operations" in response.text
    assert "read model json" in response.text
    assert str(read_model["loop_count"]) in response.text


def test_governed_operations_console_escapes_projected_values() -> None:
    html = _governed_operations_console_html(
        {
            "readiness_class": "class_d",
            "readiness_status": "<blocked>",
            "loop_count": 1,
            "closed_loop_count": 0,
            "gap_count": 1,
            "blocking_gap_count": 1,
            "drift_count": 0,
            "snapshot_hash": "hash",
            "loops": [
                {
                    "loop_id": "loop<script>",
                    "system_ref": "gateway",
                    "owner": "ops",
                    "declared_state": "open",
                    "evidence_refs": ["ref"],
                }
            ],
            "gaps": [],
            "closure_results": [],
            "drift_checks": [],
        }
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;blocked&gt;" in html
    assert "No drift checks" in html


class StubPlatform:
    """Minimal governed platform fixture for gateway app construction."""

    def connect(self, *, identity_id: str, tenant_id: str):
        return StubSession()


class StubSession:
    """Minimal governed session fixture."""

    def llm(self, prompt: str, **kwargs):
        return type("Result", (), {"content": "ok", "succeeded": True, "error": "", "cost": 0.0})()

    def close(self) -> None:
        return None


def _single_loop(
    *,
    evidence_refs: tuple[str, ...] = (),
) -> LoopRegistration:
    return LoopRegistration(
        loop_id="deployment_witness",
        system_ref="gateway.deployment_witness",
        purpose="Bind deployment publication claims to proof.",
        owner="ops",
        declared_state="witnessed",
        evidence_refs=evidence_refs,
        closure_contract=ClosureContract(
            contract_id="deployment_witness_closure_v1",
            completion_conditions=("witness_passed",),
            required_evidence_refs=("deployment_witness:current",),
            rollback_path="block publication and keep prior witness",
            human_approval_boundary="read_only",
        ),
    )
