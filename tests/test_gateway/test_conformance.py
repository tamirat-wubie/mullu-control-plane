"""Runtime conformance endpoint tests.

Purpose: verify that the gateway exposes signed conformance certificates
without hiding missing runtime evidence.
Governance scope: runtime witness binding, conformance gaps, and schema
compatibility.
Dependencies: FastAPI TestClient, gateway server, schema validator.
Invariants:
  - `/runtime/conformance` is read-only and signed.
  - Missing closure or fabric evidence is surfaced as a named gap.
  - The endpoint payload conforms to the shared certificate schema.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import gateway.conformance as conformance  # noqa: E402
from gateway.conformance import (  # noqa: E402
    ConformanceClass,
    ConformanceStatus,
    ProofCoverageStatus,
    _collect_gaps,
    _decide_class,
    _has_stale_limitation_claim,
    _known_limitations_aligned,
    issue_conformance_certificate,
)
from gateway.capability_isolation import CapabilityExecutionReceipt  # noqa: E402
from gateway.server import create_gateway_app  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

RUNTIME_WITNESS_SCHEMA = _ROOT / "schemas" / "runtime_witness.schema.json"


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


def test_runtime_conformance_endpoint_returns_signed_gap_certificate(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_RUNTIME_CONFORMANCE_SECRET", "conformance-secret")
    monkeypatch.setenv("MULLU_RUNTIME_WITNESS_SECRET", "witness-secret")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get("/runtime/conformance")
    payload = response.json()

    assert response.status_code == 200
    assert payload["certificate_id"].startswith("conf-")
    assert payload["gateway_witness_valid"] is True
    assert payload["runtime_witness_valid"] is True
    assert payload["authority_responsibility_debt_clear"] is True
    assert payload["mcp_capability_manifest_configured"] is False
    assert payload["mcp_capability_manifest_valid"] is True
    assert payload["mcp_capability_manifest_capability_count"] == 0
    assert payload["capability_plan_bundle_canary_passed"] is True
    assert payload["capability_plan_bundle_count"] == 0
    assert payload["authority_overdue_obligation_count"] == 0
    assert payload["authority_unowned_high_risk_capability_count"] == 0
    assert payload["terminal_status"] == "degraded"
    assert "command_closure_canary_missing_terminal_success" in payload["open_conformance_gaps"]
    assert "capability_fabric_admission_not_live" in payload["open_conformance_gaps"]
    assert payload["signature"].startswith("hmac-sha256:")
    assert _signature_valid(payload, "conformance-secret") is True


def test_runtime_witness_endpoints_match_public_schema(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_RUNTIME_WITNESS_SECRET", "witness-secret")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)
    schema = json.loads(RUNTIME_WITNESS_SCHEMA.read_text(encoding="utf-8"))

    gateway_payload = client.get("/gateway/witness").json()
    runtime_payload = client.get("/runtime/witness").json()

    assert gateway_payload["witness_id"].startswith("runtime-witness-")
    assert runtime_payload["witness_id"].startswith("runtime-witness-")
    assert gateway_payload["signature"].startswith("hmac-sha256:")
    assert runtime_payload["signature"].startswith("hmac-sha256:")
    assert _signature_valid(gateway_payload, "witness-secret") is True
    assert _signature_valid(runtime_payload, "witness-secret") is True
    assert _validate_schema_instance(schema, gateway_payload) == []
    assert _validate_schema_instance(schema, runtime_payload) == []


def test_runtime_conformance_certificate_matches_schema(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_RUNTIME_CONFORMANCE_SECRET", "conformance-secret")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)
    payload = client.get("/runtime/conformance").json()
    schema_path = _ROOT / "schemas" / "runtime_conformance_certificate.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert payload["checks"]
    assert all(check["evidence_ref"] for check in payload["checks"])


def test_isolation_canary_passes_locally_without_worker(monkeypatch) -> None:
    monkeypatch.delenv("MULLU_CAPABILITY_WORKER_URL", raising=False)
    monkeypatch.delenv("MULLU_CAPABILITY_WORKER_SECRET", raising=False)

    result = conformance._isolation_canary("test")

    assert result.passed is True
    assert "local/test" in result.detail
    assert "restricted worker" in result.detail


def test_isolation_canary_fails_closed_when_worker_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("MULLU_CAPABILITY_WORKER_URL", raising=False)
    monkeypatch.delenv("MULLU_CAPABILITY_WORKER_SECRET", raising=False)

    result = conformance._isolation_canary("pilot")

    assert result.passed is False
    assert "URL" in result.detail
    assert "signing secret" in result.detail


def test_isolation_canary_requires_live_isolated_worker_receipt(monkeypatch) -> None:
    class StubExecutor:
        def execute(self, *, intent, tenant_id, identity_id, boundary, command_id="", conversation_id="", metadata=None):
            receipt = CapabilityExecutionReceipt(
                receipt_id="capability-receipt-live-canary",
                capability_id=boundary.capability_id,
                execution_plane=boundary.execution_plane,
                isolation_required=boundary.isolation_required,
                worker_id="restricted-worker-live-canary",
                input_hash="input-hash-live-canary",
                output_hash="output-hash-live-canary",
                evidence_refs=("restricted_worker:live_canary",),
            )
            return {"status": "succeeded", "governed": True}, receipt

    monkeypatch.setenv("MULLU_CAPABILITY_WORKER_URL", "https://worker.example/capability/execute")
    monkeypatch.setenv("MULLU_CAPABILITY_WORKER_SECRET", "worker-secret")
    monkeypatch.setattr(conformance, "build_isolated_capability_executor_from_env", lambda: StubExecutor())

    result = conformance._isolation_canary("pilot")

    assert result.passed is True
    assert "isolated_worker receipt" in result.detail
    assert "restricted-worker-live-canary" in result.detail


def test_runtime_conformance_surfaces_unclassified_proof_routes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        conformance,
        "_proof_coverage_status",
        lambda _repo_root: ProofCoverageStatus(
            matrix_current=True,
            declared_route_count=12,
            unclassified_route_count=3,
        ),
    )

    certificate = _issue_test_conformance(repo_root=tmp_path)
    payload = certificate.to_json_dict()
    route_check = next(
        check for check in payload["checks"]
        if check["check_id"] == "proof_coverage_declared_routes_classified"
    )

    assert payload["proof_coverage_declared_route_count"] == 12
    assert payload["proof_coverage_unclassified_route_count"] == 3
    assert payload["proof_coverage_declared_routes_classified"] is False
    assert route_check["passed"] is False
    assert "unclassified_route_count=3" in route_check["detail"]
    assert "proof_coverage_declared_routes_unclassified" in payload["open_conformance_gaps"]


def test_runtime_conformance_accepts_fully_classified_proof_routes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        conformance,
        "_proof_coverage_status",
        lambda _repo_root: ProofCoverageStatus(
            matrix_current=True,
            declared_route_count=12,
            unclassified_route_count=0,
        ),
    )

    certificate = _issue_test_conformance(repo_root=tmp_path)
    payload = certificate.to_json_dict()
    route_check = next(
        check for check in payload["checks"]
        if check["check_id"] == "proof_coverage_declared_routes_classified"
    )

    assert payload["proof_coverage_declared_routes_classified"] is True
    assert payload["proof_coverage_unclassified_route_count"] == 0
    assert route_check["passed"] is True
    assert "route_count=12" in route_check["detail"]
    assert "proof_coverage_declared_routes_unclassified" not in payload["open_conformance_gaps"]


def test_runtime_conformance_keeps_route_classification_independent_from_matrix_currency(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        conformance,
        "_proof_coverage_status",
        lambda _repo_root: ProofCoverageStatus(
            matrix_current=False,
            declared_route_count=12,
            unclassified_route_count=0,
        ),
    )

    certificate = _issue_test_conformance(repo_root=tmp_path)
    payload = certificate.to_json_dict()
    matrix_check = next(
        check for check in payload["checks"]
        if check["check_id"] == "proof_coverage_matrix_current"
    )
    route_check = next(
        check for check in payload["checks"]
        if check["check_id"] == "proof_coverage_declared_routes_classified"
    )

    assert payload["proof_coverage_matrix_current"] is False
    assert payload["proof_coverage_declared_routes_classified"] is True
    assert matrix_check["passed"] is False
    assert route_check["passed"] is True
    assert "proof_coverage_matrix_not_current" in payload["open_conformance_gaps"]
    assert "proof_coverage_declared_routes_unclassified" not in payload["open_conformance_gaps"]


def test_runtime_conformance_fails_route_classification_without_route_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        conformance,
        "_proof_coverage_status",
        lambda _repo_root: ProofCoverageStatus(
            matrix_current=False,
            declared_route_count=0,
            unclassified_route_count=0,
        ),
    )

    certificate = _issue_test_conformance(repo_root=tmp_path)
    payload = certificate.to_json_dict()
    route_check = next(
        check for check in payload["checks"]
        if check["check_id"] == "proof_coverage_declared_routes_classified"
    )

    assert payload["proof_coverage_declared_route_count"] == 0
    assert payload["proof_coverage_unclassified_route_count"] == 0
    assert payload["proof_coverage_declared_routes_classified"] is False
    assert route_check["passed"] is False
    assert "proof_coverage_declared_routes_unclassified" in payload["open_conformance_gaps"]


def test_proof_coverage_status_accepts_deployment_missing_witness_integrity(
    tmp_path,
    monkeypatch,
) -> None:
    import scripts.proof_coverage_matrix as proof_matrix

    canonical = {
        "schema_version": 1,
        "generated_by": "scripts/proof_coverage_matrix.py",
        "coverage_levels": ["gap", "read_model", "request_proof", "action_proof", "audit_chain"],
        "coverage_states": ["proven", "witnessed", "unproven"],
        "coverage_summary": {"surface_count": 1},
        "evidence_quality": {"quality_gap_count": 0},
        "surfaces": [{"surface_id": "gateway_webhook_ingress"}],
        "route_coverage": {
            "route_count": 2,
            "unclassified_route_count": 0,
            "routes": [
                {
                    "route": "/webhook/web",
                    "surface_id": "gateway_webhook_ingress",
                    "coverage_state": "witnessed",
                },
            ],
        },
        "closure_actions": [{"action_id": "closed", "status": "closed"}],
        "witness_integrity": {
            "runtime_witness_count": 1,
            "exact_test_anchor_count": 1,
            "unanchored_witness_count": 0,
        },
    }
    generated = {
        **canonical,
        "witness_integrity": {
            "runtime_witness_count": 1,
            "exact_test_anchor_count": 0,
            "unanchored_witness_count": 1,
        },
    }
    canonical_path = tmp_path / "proof_coverage_matrix.json"
    canonical_path.write_text(json.dumps(canonical), encoding="utf-8")
    monkeypatch.setattr(proof_matrix, "CANONICAL_OUTPUT", canonical_path)
    monkeypatch.setattr(proof_matrix, "proof_coverage_matrix", lambda: generated)

    status = conformance._proof_coverage_status(tmp_path)

    assert status.matrix_current is True
    assert status.declared_route_count == 2
    assert status.unclassified_route_count == 0
    assert status.declared_routes_classified is True


def test_proof_coverage_status_rejects_deployment_runtime_section_drift(
    tmp_path,
    monkeypatch,
) -> None:
    import scripts.proof_coverage_matrix as proof_matrix

    canonical = {
        "schema_version": 1,
        "generated_by": "scripts/proof_coverage_matrix.py",
        "coverage_levels": ["gap", "read_model", "request_proof", "action_proof", "audit_chain"],
        "coverage_states": ["proven", "witnessed", "unproven"],
        "coverage_summary": {"surface_count": 1},
        "evidence_quality": {"quality_gap_count": 0},
        "surfaces": [{"surface_id": "gateway_webhook_ingress"}],
        "route_coverage": {
            "route_count": 1,
            "unclassified_route_count": 0,
            "routes": [
                {
                    "route": "/webhook/web",
                    "surface_id": "gateway_webhook_ingress",
                    "coverage_state": "witnessed",
                },
            ],
        },
        "closure_actions": [{"action_id": "closed", "status": "closed"}],
        "witness_integrity": {
            "runtime_witness_count": 1,
            "exact_test_anchor_count": 1,
            "unanchored_witness_count": 0,
        },
    }
    generated = {
        **canonical,
        "route_coverage": {
            "route_count": 2,
            "unclassified_route_count": 1,
            "routes": [
                *canonical["route_coverage"]["routes"],
                {
                    "route": "/runtime/conformance",
                    "surface_id": "unclassified_declared_route",
                    "coverage_state": "unproven",
                },
            ],
        },
        "witness_integrity": {
            "runtime_witness_count": 1,
            "exact_test_anchor_count": 0,
            "unanchored_witness_count": 1,
        },
    }
    canonical_path = tmp_path / "proof_coverage_matrix.json"
    canonical_path.write_text(json.dumps(canonical), encoding="utf-8")
    monkeypatch.setattr(proof_matrix, "CANONICAL_OUTPUT", canonical_path)
    monkeypatch.setattr(proof_matrix, "proof_coverage_matrix", lambda: generated)

    status = conformance._proof_coverage_status(tmp_path)

    assert status.matrix_current is False
    assert status.declared_route_count == 2
    assert status.unclassified_route_count == 1
    assert status.declared_routes_classified is False


def test_runtime_conformance_certificate_schema_gate_fails_closed(tmp_path, monkeypatch) -> None:
    def reject_schema(_schema, _payload):
        return ["$.signature: forced schema failure"]

    monkeypatch.setattr(conformance, "_validate_schema_instance", reject_schema)

    with pytest.raises(RuntimeError) as exc:
        _issue_test_conformance(repo_root=tmp_path)

    assert "runtime conformance certificate schema validation failed" in str(exc.value)
    assert "1 schema error(s)" in str(exc.value)
    assert "$.signature" not in str(exc.value)


def test_runtime_conformance_reports_missing_authority_directory_sync_receipt(tmp_path) -> None:
    certificate = _issue_test_conformance(repo_root=tmp_path)
    payload = certificate.to_json_dict()
    receipt_check = next(check for check in payload["checks"] if check["check_id"] == "authority_directory_sync_receipt")

    assert payload["authority_directory_sync_receipt_valid"] is False
    assert receipt_check["passed"] is False
    assert "authority_directory_sync_receipt_not_witnessed" in payload["open_conformance_gaps"]


def test_runtime_conformance_accepts_valid_authority_directory_sync_receipt(tmp_path) -> None:
    (tmp_path / ".change_assurance").mkdir()
    (tmp_path / ".change_assurance" / "authority_directory_sync.json").write_text(
        json.dumps({
            "receipt_id": "authority-directory-sync-0123456789abcdef",
            "tenant_id": "tenant-1",
            "batch_id": "directory-batch-0123456789abcdef",
            "source_system": "static_yaml",
            "source_ref": "file://authority-directory.yaml",
            "source_hash": "sha256:" + "0" * 64,
            "applied_ownership_count": 1,
            "applied_approval_policy_count": 1,
            "applied_escalation_policy_count": 1,
            "rejected_record_count": 0,
            "apply_mode": "apply",
            "persisted": True,
            "rejected_records": [],
            "evidence_refs": [
                "authority:ownership_read_model",
                "authority:policy_read_model",
                "runtime_conformance:authority_configuration",
            ],
        }),
        encoding="utf-8",
    )

    certificate = _issue_test_conformance(repo_root=tmp_path)
    payload = certificate.to_json_dict()
    receipt_check = next(check for check in payload["checks"] if check["check_id"] == "authority_directory_sync_receipt")

    assert payload["authority_directory_sync_receipt_valid"] is True
    assert receipt_check["passed"] is True
    assert "authority_directory_sync_receipt_not_witnessed" not in payload["open_conformance_gaps"]


def test_runtime_conformance_degrades_when_responsibility_debt_is_present(tmp_path) -> None:
    certificate = _issue_test_conformance(
        repo_root=tmp_path,
        authority_obligation_mesh=StubAuthorityObligationMesh(overdue_obligation_count=1),
    )
    payload = certificate.to_json_dict()
    debt_check = next(check for check in payload["checks"] if check["check_id"] == "authority_responsibility_debt_clear")

    assert payload["authority_responsibility_debt_clear"] is False
    assert payload["authority_overdue_obligation_count"] == 1
    assert debt_check["passed"] is False
    assert "overdue_obligation_count=1" in debt_check["detail"]
    assert "authority_responsibility_debt_present" in payload["open_conformance_gaps"]
    assert payload["terminal_status"] == "degraded"


def test_runtime_conformance_degrades_when_mcp_manifest_is_invalid(tmp_path, monkeypatch) -> None:
    manifest_path = tmp_path / "invalid_mcp_manifest.json"
    manifest_path.write_text(json.dumps({"tools": []}), encoding="utf-8")
    monkeypatch.setenv("MULLU_MCP_CAPABILITY_MANIFEST_PATH", str(manifest_path))

    certificate = _issue_test_conformance(repo_root=tmp_path)
    payload = certificate.to_json_dict()
    manifest_check = next(
        check for check in payload["checks"]
        if check["check_id"] == "mcp_capability_manifest"
    )

    assert payload["mcp_capability_manifest_configured"] is True
    assert payload["mcp_capability_manifest_valid"] is False
    assert payload["mcp_capability_manifest_capability_count"] == 0
    assert manifest_check["passed"] is False
    assert "MCP manifest requires at least one tool" in manifest_check["detail"]
    assert "mcp_capability_manifest_invalid" in payload["open_conformance_gaps"]
    assert payload["terminal_status"] == "degraded"


def test_runtime_conformance_witnesses_valid_mcp_manifest(tmp_path, monkeypatch) -> None:
    manifest_path = _ROOT / "examples" / "mcp_capability_manifest.json"
    monkeypatch.setenv("MULLU_MCP_CAPABILITY_MANIFEST_PATH", str(manifest_path))

    certificate = _issue_test_conformance(repo_root=tmp_path)
    payload = certificate.to_json_dict()
    manifest_check = next(
        check for check in payload["checks"]
        if check["check_id"] == "mcp_capability_manifest"
    )

    assert payload["mcp_capability_manifest_configured"] is True
    assert payload["mcp_capability_manifest_valid"] is True
    assert payload["mcp_capability_manifest_capability_count"] == 1
    assert manifest_check["passed"] is True
    assert "mcp_capability_manifest_invalid" not in payload["open_conformance_gaps"]


def test_runtime_conformance_witnesses_capability_plan_bundle(tmp_path) -> None:
    certificate = _issue_test_conformance(repo_root=tmp_path, plan_ledger=StubPlanLedger())
    payload = certificate.to_json_dict()
    bundle_check = next(
        check for check in payload["checks"]
        if check["check_id"] == "capability_plan_evidence_bundle"
    )

    assert payload["capability_plan_bundle_canary_passed"] is True
    assert payload["capability_plan_bundle_count"] == 1
    assert bundle_check["passed"] is True
    assert "certificate_count=1" in bundle_check["detail"]
    assert "capability_plan_evidence_bundle_not_witnessed" not in payload["open_conformance_gaps"]


def test_runtime_conformance_degrades_when_plan_bundle_export_is_unavailable(tmp_path) -> None:
    certificate = _issue_test_conformance(
        repo_root=tmp_path,
        plan_ledger=StubPlanLedger(bundle_ready=False),
    )
    payload = certificate.to_json_dict()
    bundle_check = next(
        check for check in payload["checks"]
        if check["check_id"] == "capability_plan_evidence_bundle"
    )

    assert payload["capability_plan_bundle_canary_passed"] is False
    assert payload["capability_plan_bundle_count"] == 1
    assert bundle_check["passed"] is False
    assert "invalid_bundle_plan_id=plan-1" in bundle_check["detail"]
    assert "capability_plan_evidence_bundle_not_witnessed" in payload["open_conformance_gaps"]
    assert payload["terminal_status"] == "degraded"


def test_known_limitations_alignment_rejects_stale_directory_adapter_claim(tmp_path) -> None:
    gateway_dir = tmp_path / "gateway"
    scripts_dir = tmp_path / "scripts"
    gateway_dir.mkdir()
    scripts_dir.mkdir()
    (gateway_dir / "server.py").write_text(
        '"/authority/approval-chains" "/authority/obligations" "/authority/escalations"',
        encoding="utf-8",
    )
    for script_name in (
        "scim_authority_directory_adapter.py",
        "github_teams_authority_directory_adapter.py",
        "ldap_authority_directory_adapter.py",
        "saml_groups_authority_directory_adapter.py",
        "workspace_groups_authority_directory_adapter.py",
    ):
        (scripts_dir / script_name).write_text("# adapter present\n", encoding="utf-8")
    limitations_path = tmp_path / "KNOWN_LIMITATIONS_v0.1.md"
    limitations_path.write_text("External directory adapters are not yet implemented.\n", encoding="utf-8")

    stale = _known_limitations_aligned(tmp_path)
    limitations_path.write_text(
        "External directory sync adapters are implemented; scheduling UI is not yet implemented.\n",
        encoding="utf-8",
    )
    aligned = _known_limitations_aligned(tmp_path)

    assert stale is False
    assert aligned is True
    assert (scripts_dir / "github_teams_authority_directory_adapter.py").exists()
    assert (scripts_dir / "ldap_authority_directory_adapter.py").exists()


def test_known_limitations_alignment_ignores_unrelated_not_implemented_text(tmp_path) -> None:
    gateway_dir = tmp_path / "gateway"
    scripts_dir = tmp_path / "scripts"
    gateway_dir.mkdir()
    scripts_dir.mkdir()
    (gateway_dir / "server.py").write_text(
        '"/authority/approval-chains" "/authority/obligations" "/authority/escalations"',
        encoding="utf-8",
    )
    for script_name in (
        "scim_authority_directory_adapter.py",
        "github_teams_authority_directory_adapter.py",
        "ldap_authority_directory_adapter.py",
        "saml_groups_authority_directory_adapter.py",
        "workspace_groups_authority_directory_adapter.py",
    ):
        (scripts_dir / script_name).write_text("# adapter present\n", encoding="utf-8")
    (tmp_path / "KNOWN_LIMITATIONS_v0.1.md").write_text(
        "\n".join((
            "Gateway authority includes approval-chain and escalation surfaces.",
            "External directory sync adapters are implemented for SCIM, LDAP, SAML, and workspace directory exports.",
            "Full approval queues and scheduling UI are not yet implemented.",
        )),
        encoding="utf-8",
    )

    assert _known_limitations_aligned(tmp_path) is True
    assert _has_stale_limitation_claim(
        "External directory adapters are not yet implemented.",
        ("external directory adapters",),
    ) is True
    assert _has_stale_limitation_claim(
        "External directory adapters are implemented; scheduling UI is not yet implemented.",
        ("external directory adapters",),
    ) is False
    assert _has_stale_limitation_claim(
        "GitHub Teams adapter is not yet implemented.",
        ("github teams",),
    ) is True


def _signature_valid(payload: dict, secret: str) -> bool:
    signature = payload["signature"].removeprefix("hmac-sha256:")
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    expected = hmac.new(secret.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


class StubRouter:
    """Runtime witness fixture for direct conformance issuance."""

    def runtime_witness(self, **kwargs):
        unsigned = {
            "witness_id": "wit-0123456789abcdef",
            "environment": kwargs["environment"],
            "runtime_status": "live",
            "gateway_status": "live",
            "latest_command_event_hash": "hash-1",
            "latest_anchor_id": "anchor-1",
            "latest_terminal_certificate_id": "terminal-1",
            "signed_at": "2026-04-29T12:00:00+00:00",
            "signature_key_id": kwargs["signature_key_id"],
        }
        signature = hmac.new(
            kwargs["signing_secret"].encode("utf-8"),
            _stable_hash(unsigned).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {**unsigned, "signature": f"hmac-sha256:{signature}"}


class StubCommandLedger:
    """Closure summary fixture for direct conformance issuance."""

    def summary(self):
        return {
            "terminal_certificates": 1,
            "closure_memory_entries": 1,
            "closure_learning_decisions": 1,
        }


class StubAuthorityObligationMesh:
    """Authority responsibility witness fixture."""

    def __init__(self, *, overdue_obligation_count: int = 0) -> None:
        self._overdue_obligation_count = overdue_obligation_count

    def responsibility_witness(self):
        from gateway.authority_obligation_mesh import ResponsibilityWitness

        return ResponsibilityWitness(
            responsibility_debt_clear=self._overdue_obligation_count == 0,
            pending_approval_chain_count=0,
            overdue_approval_chain_count=0,
            expired_approval_chain_count=0,
            open_obligation_count=self._overdue_obligation_count,
            overdue_obligation_count=self._overdue_obligation_count,
            escalated_obligation_count=0,
            active_accepted_risk_count=0,
            active_compensation_review_count=0,
            requires_review_count=0,
            unowned_high_risk_capability_count=0,
        )


class StubCapabilityAdmissionGate:
    """Capability fabric read-model fixture."""

    def read_model(self):
        return {
            "require_certified": True,
            "capsule_count": 1,
            "capability_count": 1,
            "artifact_count": 1,
        }


class StubPlanLedger:
    """Capability plan ledger fixture for evidence bundle canary checks."""

    def __init__(self, *, bundle_ready: bool = True) -> None:
        self._bundle_ready = bundle_ready

    def read_model(self):
        return {"certificates": [{"plan_id": "plan-1"}]}

    def export_evidence_bundle(self, *, plan_id: str):
        if not self._bundle_ready:
            return {
                "bundle_id": "invalid",
                "bundle_hash": "hash",
                "plan_id": plan_id,
                "certificate_id": "cert-1",
                "step_command_ids": (),
                "step_terminal_certificate_ids": (),
                "evidence_refs": (),
            }
        return {
            "bundle_id": "plan-evidence-bundle-0123456789abcdef",
            "bundle_hash": "hash",
            "plan_id": plan_id,
            "certificate_id": "cert-1",
            "step_command_ids": ("cmd-1",),
            "step_terminal_certificate_ids": ("terminal-1",),
            "evidence_refs": ("plan_terminal_certificate:cert-1",),
        }


def _stable_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _issue_test_conformance(*, repo_root: Path, authority_obligation_mesh=None, plan_ledger=None, command_ledger=None):
    return issue_conformance_certificate(
        router=StubRouter(),
        command_ledger=command_ledger or StubCommandLedger(),
        authority_obligation_mesh=authority_obligation_mesh or StubAuthorityObligationMesh(),
        capability_admission_gate=StubCapabilityAdmissionGate(),
        environment="test",
        signing_secret="conformance-secret",
        signature_key_id="runtime-conformance-test",
        runtime_witness_key_id="runtime-witness-test",
        runtime_witness_secret="witness-secret",
        plan_ledger=plan_ledger,
        repo_root=repo_root,
        clock=lambda: "2026-04-29T12:00:00+00:00",
    )


def _real_command_ledger():
    from gateway.command_spine import (
        CommandLedger,
        CommandState,
        InMemoryCommandLedgerStore,
    )

    ledger = CommandLedger(
        clock=lambda: "2026-04-29T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conv-conformance",
        idempotency_key="idem-conformance",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    ledger.transition(command.command_id, CommandState.ALLOWED, risk_tier="low")
    return ledger


def _write_deployment_status(
    repo_root: Path,
    *,
    witness_state: str = "published",
    public_health_endpoint: str = "https://mullu-gateway.onrender.com/health",
) -> None:
    repo_root.joinpath("DEPLOYMENT_STATUS.md").write_text(
        "\n".join(
            (
                "# Deployment Status Witness",
                f"**Deployment witness state:** `{witness_state}`",
                f"**Public production health endpoint:** `{public_health_endpoint}`",
                "**API health endpoint:** `not-declared`",
                "Public production health is declared from the exact field above.",
            )
        ),
        encoding="utf-8",
    )


def test_collect_gaps_uses_exact_public_health_declaration_field(tmp_path) -> None:
    _write_deployment_status(tmp_path)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    docs_dir.joinpath("42_lineage_query_api.md").write_text(
        "The policy-version index is implemented by the policy-version read model.",
        encoding="utf-8",
    )

    gaps = _collect_gaps([], repository_root=tmp_path)

    assert "public_production_health_not_declared" not in gaps
    assert "deployment_witness_not_published" not in gaps
    assert "lineage_policy_version_index_projected_only" not in gaps


def test_collect_gaps_flags_specific_public_health_field_when_not_declared(tmp_path) -> None:
    _write_deployment_status(tmp_path, public_health_endpoint="not-declared")

    gaps = _collect_gaps([], repository_root=tmp_path)

    assert "public_production_health_not_declared" in gaps
    assert "deployment_witness_not_published" not in gaps
    assert len(gaps) == 1


def test_collect_gaps_flags_stale_lineage_policy_index_claim(tmp_path) -> None:
    _write_deployment_status(tmp_path)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    docs_dir.joinpath("42_lineage_query_api.md").write_text(
        "The policy-version index is not yet implemented.",
        encoding="utf-8",
    )

    gaps = _collect_gaps([], repository_root=tmp_path)

    assert "lineage_policy_version_index_projected_only" in gaps
    assert "public_production_health_not_declared" not in gaps
    assert len(gaps) == 1


def test_decide_class_is_strict_function_of_status() -> None:
    # The declared class is derived from terminal status, never hand-set,
    # so a deployment cannot over-claim:
    #   conformant           -> CLASS_A (full)
    #   conformant_with_gaps -> CLASS_B (partial)
    #   degraded             -> CLASS_C (reference)
    #   non_conformant       -> CLASS_C (reference)
    assert _decide_class(ConformanceStatus.CONFORMANT) is ConformanceClass.CLASS_A
    assert _decide_class(ConformanceStatus.CONFORMANT_WITH_GAPS) is ConformanceClass.CLASS_B
    assert _decide_class(ConformanceStatus.DEGRADED) is ConformanceClass.CLASS_C
    assert _decide_class(ConformanceStatus.NON_CONFORMANT) is ConformanceClass.CLASS_C


def test_conformance_certificate_declares_class_consistent_with_status(tmp_path) -> None:
    # The issued certificate carries a conformance_class field whose value is
    # the strict derivation of its own terminal_status. The class is part of
    # the signed payload (tamper-evident).
    certificate = _issue_test_conformance(repo_root=tmp_path)
    payload = certificate.to_json_dict()

    assert "conformance_class" in payload
    status = ConformanceStatus(payload["terminal_status"])
    expected_class = _decide_class(status).value
    assert payload["conformance_class"] == expected_class
    # Signed payload includes the class — re-deriving the signature over a
    # payload missing the class would not match.
    assert _signature_valid(payload, "conformance-secret") is True


def test_conformance_class_class_a_for_intact_clean_deployment(tmp_path, monkeypatch) -> None:
    # Force every gap-producing surface to clean so the stub deployment can
    # reach CONFORMANT -> CLASS_A. This proves Class A is actually reachable,
    # not merely defined.
    monkeypatch.setattr(conformance, "_collect_gaps", lambda checks, *, repository_root: [])
    monkeypatch.setattr(
        conformance,
        "_decide_status",
        lambda *args, **kwargs: ConformanceStatus.CONFORMANT,
    )

    certificate = _issue_test_conformance(repo_root=tmp_path)
    payload = certificate.to_json_dict()

    assert payload["terminal_status"] == "conformant"
    assert payload["conformance_class"] == "class_a"


def test_conformance_class_class_c_when_core_canary_fails(tmp_path) -> None:
    # A tampered audit chain fails a core canary -> DEGRADED -> CLASS_C.
    # The class downgrade is driven by the verifier canary wired in #851.
    from dataclasses import replace as dc_replace

    ledger = _real_command_ledger()
    ledger._events[1] = dc_replace(ledger._events[1], prev_event_hash="0" * 64)

    certificate = _issue_test_conformance(repo_root=tmp_path, command_ledger=ledger)
    payload = certificate.to_json_dict()

    assert payload["terminal_status"] in {"degraded", "non_conformant"}
    assert payload["conformance_class"] == "class_c"


def test_conformance_certificate_with_class_matches_schema(monkeypatch) -> None:
    # The conformance_class field is a required, enum-constrained property in
    # the public schema; the live endpoint payload must validate.
    monkeypatch.setenv("MULLU_RUNTIME_CONFORMANCE_SECRET", "conformance-secret")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)
    payload = client.get("/runtime/conformance").json()
    schema_path = _ROOT / "schemas" / "runtime_conformance_certificate.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert payload["conformance_class"] in {"class_a", "class_b", "class_c"}


def test_audit_trace_verifier_canary_passes_with_intact_real_ledger(tmp_path) -> None:
    # A real ledger with an intact event chain produces a passing
    # audit_trace_verifier_canary check that reports the event count.
    ledger = _real_command_ledger()
    certificate = _issue_test_conformance(repo_root=tmp_path, command_ledger=ledger)
    payload = certificate.to_json_dict()

    check = next(
        c for c in payload["checks"] if c["check_id"] == "audit_trace_verifier_canary"
    )
    assert check["passed"] is True
    assert "global_event_chain_intact" in check["detail"]
    assert "audit_trace_verifier_event_chain_broken" not in payload["open_conformance_gaps"]


def test_audit_trace_verifier_canary_surfaces_tampered_chain_as_gap(tmp_path) -> None:
    # Tamper the ledger's event chain (break a prev_event_hash link). The
    # canary must fail, surface a named gap, and force a non-conformant-grade
    # terminal status — the verifier is now load-bearing in the cert.
    from dataclasses import replace as dc_replace

    ledger = _real_command_ledger()
    # Break the global chain at the second event.
    ledger._events[1] = dc_replace(ledger._events[1], prev_event_hash="0" * 64)

    certificate = _issue_test_conformance(repo_root=tmp_path, command_ledger=ledger)
    payload = certificate.to_json_dict()

    check = next(
        c for c in payload["checks"] if c["check_id"] == "audit_trace_verifier_canary"
    )
    assert check["passed"] is False
    assert "global_event_chain_broken" in check["detail"]
    assert "audit_trace_verifier_event_chain_broken" in payload["open_conformance_gaps"]
    # A broken audit chain is a core-canary failure -> degraded (or worse).
    assert payload["terminal_status"] in {"degraded", "non_conformant"}


def test_audit_trace_verifier_canary_not_applicable_for_summary_only_ledger(tmp_path) -> None:
    # The summary-only stub ledger lacks the event-chain surface; the canary
    # reports not_applicable and passes, preserving backward compatibility.
    certificate = _issue_test_conformance(repo_root=tmp_path)
    payload = certificate.to_json_dict()

    check = next(
        c for c in payload["checks"] if c["check_id"] == "audit_trace_verifier_canary"
    )
    assert check["passed"] is True
    assert "not_applicable" in check["detail"]
