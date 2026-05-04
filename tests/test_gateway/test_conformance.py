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
from gateway.conformance import _known_limitations_aligned, issue_conformance_certificate  # noqa: E402
from gateway.server import create_gateway_app  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


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
    assert (scripts_dir / "ldap_authority_directory_adapter.py").exists()


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


def _issue_test_conformance(*, repo_root: Path, authority_obligation_mesh=None, plan_ledger=None):
    return issue_conformance_certificate(
        router=StubRouter(),
        command_ledger=StubCommandLedger(),
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
