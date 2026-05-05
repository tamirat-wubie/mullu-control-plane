"""Tests for governed deployment witness orchestration.

Purpose: verify the operator shortcut composes ingress rendering, repository
variable provisioning, and optional workflow dispatch.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.orchestrate_deployment_witness.
Invariants:
  - Invalid gateway hosts fail before GitHub variables are written.
  - Repository variables use the URL derived from the validated host.
  - Dispatch is opt-in and preserves the existing guarded workflow contract.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts.orchestrate_deployment_witness import (
    main,
    orchestrate_deployment_witness,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


REPO_ROOT = Path(__file__).resolve().parent.parent


class FakeRunner:
    """Deterministic kubectl and GitHub CLI runner fixture."""

    def __init__(self, *, run_conclusion: str = "success") -> None:
        self.run_conclusion = run_conclusion
        self.commands: list[list[str]] = []

    def __call__(
        self,
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        assert check is True
        assert capture_output is True
        assert text is True

        if command[:3] == ["kubectl", "apply", "-f"]:
            return _completed(command, "")
        if command[:3] == ["gh", "variable", "set"]:
            return _completed(command, "")
        if command[:3] == ["gh", "variable", "list"]:
            return _completed(
                command,
                [
                    {"name": "MULLU_GATEWAY_URL", "value": "https://gateway.mullusi.com"},
                    {"name": "MULLU_EXPECTED_RUNTIME_ENV", "value": "pilot"},
                ],
            )
        if command[:3] == ["gh", "secret", "list"]:
            return _completed(
                command,
                [
                    {"name": "MULLU_RUNTIME_WITNESS_SECRET"},
                    {"name": "MULLU_RUNTIME_CONFORMANCE_SECRET"},
                ],
            )
        if command[:3] == ["gh", "workflow", "list"]:
            return _completed(
                command,
                [
                    {
                        "name": "Deployment Witness Collection",
                        "path": ".github/workflows/deployment-witness.yml",
                        "state": "active",
                    }
                ],
            )
        if command[:3] == ["gh", "workflow", "run"]:
            return _completed(command, "")
        if command[:3] == ["gh", "run", "list"]:
            return _completed(
                command,
                [
                    {
                        "databaseId": 5678,
                        "createdAt": "2099-01-01T00:00:00Z",
                        "status": "completed",
                    }
                ],
            )
        if command[:3] == ["gh", "run", "watch"]:
            return _completed(command, "")
        if command[:3] == ["gh", "run", "view"]:
            return _completed(
                command,
                {
                    "databaseId": 5678,
                    "status": "completed",
                    "conclusion": self.run_conclusion,
                    "url": "https://github.com/run/5678",
                },
            )
        if command[:3] == ["gh", "run", "download"]:
            return _completed(command, "")
        raise AssertionError(f"unexpected command: {command}")


def test_orchestrate_deployment_witness_renders_and_provisions(tmp_path: Path) -> None:
    runner = FakeRunner()

    orchestration = orchestrate_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        rendered_ingress_output=tmp_path / "ingress.yaml",
        runner=runner,
    )

    variable_commands = [
        command for command in runner.commands if command[:3] == ["gh", "variable", "set"]
    ]
    assert orchestration.ingress.host == "gateway.mullusi.com"
    assert orchestration.ingress.applied is False
    assert orchestration.target.gateway_url == "https://gateway.mullusi.com"
    assert orchestration.target.expected_environment == "pilot"
    assert orchestration.preflight is None
    assert orchestration.dispatch is None
    assert orchestration.receipt.receipt_id.startswith("deployment-witness-orchestration-")
    assert orchestration.receipt.gateway_host == "gateway.mullusi.com"
    assert orchestration.receipt.gateway_url == "https://gateway.mullusi.com"
    assert orchestration.receipt.preflight_required is False
    assert orchestration.receipt.preflight_ready is None
    assert orchestration.receipt.dispatch_requested is False
    assert orchestration.receipt.mcp_operator_checklist_required is False
    assert orchestration.receipt.mcp_operator_checklist_valid is None
    assert "dispatch:skipped" in orchestration.receipt.evidence_refs
    assert "mcp_operator_checklist:skipped" in orchestration.receipt.evidence_refs
    assert len(variable_commands) == 2
    assert not any(command[:3] == ["kubectl", "apply", "-f"] for command in runner.commands)
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def test_orchestrate_deployment_witness_can_apply_and_dispatch(tmp_path: Path) -> None:
    runner = FakeRunner()

    orchestration = orchestrate_deployment_witness(
        gateway_host="gateway.mullusi.com",
        gateway_url="https://gateway.mullusi.com/",
        expected_environment="production",
        rendered_ingress_output=tmp_path / "ingress.yaml",
        apply_ingress=True,
        dispatch=True,
        download_dir=tmp_path / "artifact",
        poll_seconds=1,
        runner=runner,
    )

    assert orchestration.ingress.applied is True
    assert orchestration.target.gateway_url == "https://gateway.mullusi.com"
    assert orchestration.target.expected_environment == "production"
    assert orchestration.preflight is None
    assert orchestration.dispatch is not None
    assert orchestration.dispatch.run_id == 5678
    assert orchestration.dispatch.conclusion == "success"
    assert orchestration.receipt.dispatch_requested is True
    assert orchestration.receipt.dispatch_run_id == 5678
    assert orchestration.receipt.dispatch_conclusion == "success"
    assert "deployment_witness_run:5678" in orchestration.receipt.evidence_refs
    assert any(command[:3] == ["kubectl", "apply", "-f"] for command in runner.commands)
    assert any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)
    assert any(command[:3] == ["gh", "run", "download"] for command in runner.commands)


def test_orchestrate_deployment_witness_can_gate_dispatch_with_preflight(tmp_path: Path) -> None:
    runner = FakeRunner()

    orchestration = orchestrate_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        rendered_ingress_output=tmp_path / "ingress.yaml",
        require_preflight=True,
        preflight_output=tmp_path / "preflight.json",
        dispatch=True,
        download_dir=tmp_path / "artifact",
        poll_seconds=1,
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
        json_getter=_healthy_getter,
    )

    assert orchestration.preflight is not None
    assert orchestration.preflight.ready is True
    assert orchestration.dispatch is not None
    assert orchestration.receipt.preflight_required is True
    assert orchestration.receipt.preflight_ready is True
    assert "preflight:ready:true" in orchestration.receipt.evidence_refs
    assert orchestration.dispatch.conclusion == "success"
    assert (tmp_path / "preflight.json").exists()
    assert any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def test_orchestrate_deployment_witness_accepts_mounted_runtime_secret(tmp_path: Path) -> None:
    runner = FakeRunner()

    orchestration = orchestrate_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        rendered_ingress_output=tmp_path / "ingress.yaml",
        require_preflight=True,
        preflight_output=tmp_path / "preflight.json",
        dispatch=True,
        runtime_secret_present=True,
        conformance_secret_present=True,
        download_dir=tmp_path / "artifact",
        poll_seconds=1,
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
        json_getter=_healthy_getter,
    )

    assert orchestration.preflight is not None
    assert orchestration.preflight.ready is True
    assert orchestration.dispatch is not None
    assert not any(command[:3] == ["gh", "secret", "list"] for command in runner.commands)
    assert any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def test_orchestrate_deployment_witness_requires_valid_mcp_operator_checklist(tmp_path: Path) -> None:
    runner = FakeRunner()

    orchestration = orchestrate_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        rendered_ingress_output=tmp_path / "ingress.yaml",
        require_mcp_operator_checklist=True,
        runner=runner,
    )

    assert orchestration.receipt.mcp_operator_checklist_required is True
    assert orchestration.receipt.mcp_operator_checklist_valid is True
    assert orchestration.receipt.mcp_operator_checklist_path == "examples\\mcp_operator_handoff_checklist.json"
    assert "mcp_operator_checklist:valid:true" in orchestration.receipt.evidence_refs
    assert len([command for command in runner.commands if command[:3] == ["gh", "variable", "set"]]) == 2


def test_orchestrate_deployment_witness_blocks_invalid_mcp_operator_checklist(tmp_path: Path) -> None:
    runner = FakeRunner()
    checklist_path = tmp_path / "invalid_mcp_operator_checklist.json"
    checklist_path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="MCP operator checklist validation failed"):
        orchestrate_deployment_witness(
            gateway_host="gateway.mullusi.com",
            expected_environment="pilot",
            rendered_ingress_output=tmp_path / "ingress.yaml",
            require_mcp_operator_checklist=True,
            mcp_operator_checklist_path=checklist_path,
            runner=runner,
        )

    assert runner.commands == []
    assert not (tmp_path / "ingress.yaml").exists()


def test_orchestrate_deployment_witness_blocks_dispatch_when_preflight_fails(tmp_path: Path) -> None:
    runner = FakeRunner()

    with pytest.raises(RuntimeError, match="deployment witness preflight failed"):
        orchestrate_deployment_witness(
            gateway_host="gateway.mullusi.com",
            expected_environment="pilot",
            rendered_ingress_output=tmp_path / "ingress.yaml",
            require_preflight=True,
            preflight_output=tmp_path / "preflight.json",
            dispatch=True,
            runner=runner,
            resolver=lambda host: (),
            json_getter=_healthy_getter,
        )

    assert (tmp_path / "preflight.json").exists()
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def test_orchestrate_deployment_witness_rejects_host_before_provision(tmp_path: Path) -> None:
    runner = FakeRunner()

    with pytest.raises(RuntimeError, match="must not include URL scheme"):
        orchestrate_deployment_witness(
            gateway_host="https://gateway.mullusi.com",
            expected_environment="pilot",
            rendered_ingress_output=tmp_path / "ingress.yaml",
            runner=runner,
        )

    assert runner.commands == []


def test_cli_reports_invalid_host(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "scripts.orchestrate_deployment_witness.subprocess.run",
        FakeRunner(),
    )

    exit_code = main(
        [
            "--gateway-host",
            "https://gateway.mullusi.com",
            "--rendered-ingress-output",
            str(tmp_path / "ingress.yaml"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "deployment witness orchestration failed" in captured.out
    assert "must not include URL scheme" in captured.out


def test_cli_writes_orchestration_receipt(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "scripts.orchestrate_deployment_witness.subprocess.run",
        FakeRunner(),
    )
    receipt_path = tmp_path / "orchestration.json"

    exit_code = main(
        [
            "--gateway-host",
            "gateway.mullusi.com",
            "--expected-environment",
            "pilot",
            "--rendered-ingress-output",
            str(tmp_path / "ingress.yaml"),
            "--orchestration-output",
            str(receipt_path),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert receipt_path.exists()
    assert payload["receipt_id"].startswith("deployment-witness-orchestration-")
    assert payload["gateway_host"] == "gateway.mullusi.com"
    assert payload["gateway_url"] == "https://gateway.mullusi.com"
    assert payload["dispatch_requested"] is False
    assert "dispatch:skipped" in payload["evidence_refs"]
    assert "orchestration_receipt_path" in captured.out


def test_cli_uses_orchestration_receipt_output_environment(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.setattr(
        "scripts.orchestrate_deployment_witness.subprocess.run",
        FakeRunner(),
    )
    receipt_path = tmp_path / "env-orchestration.json"
    monkeypatch.setenv("MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT", str(receipt_path))

    exit_code = main(
        [
            "--gateway-host",
            "gateway.mullusi.com",
            "--expected-environment",
            "pilot",
            "--rendered-ingress-output",
            str(tmp_path / "ingress.yaml"),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["receipt_id"].startswith("deployment-witness-orchestration-")
    assert payload["preflight_required"] is False
    assert payload["preflight_ready"] is None
    assert payload["dispatch_requested"] is False
    assert payload["mcp_operator_checklist_required"] is False
    assert payload["mcp_operator_checklist_valid"] is None
    assert str(receipt_path) in captured.out


def test_orchestration_receipt_schema_matches_cli_output(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "scripts.orchestrate_deployment_witness.subprocess.run",
        FakeRunner(),
    )
    receipt_path = tmp_path / "schema-orchestration.json"
    schema_path = REPO_ROOT / "schemas" / "deployment_orchestration_receipt.schema.json"

    exit_code = main(
        [
            "--gateway-host",
            "gateway.mullusi.com",
            "--expected-environment",
            "pilot",
            "--rendered-ingress-output",
            str(tmp_path / "ingress.yaml"),
            "--orchestration-output",
            str(receipt_path),
        ]
    )
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    schema = _load_schema(schema_path)
    schema_errors = _validate_schema_instance(schema, payload)

    required_fields = set(schema["required"])
    assert exit_code == 0
    assert schema_errors == []
    assert set(payload) == required_fields
    assert set(schema["properties"]) == required_fields
    assert payload["expected_environment"] in schema["properties"]["expected_environment"]["enum"]
    assert isinstance(payload["ingress_applied"], bool)
    assert isinstance(payload["preflight_required"], bool)
    assert isinstance(payload["dispatch_requested"], bool)
    assert isinstance(payload["mcp_operator_checklist_required"], bool)
    assert payload["preflight_ready"] is None or isinstance(payload["preflight_ready"], bool)
    assert payload["dispatch_run_id"] is None or isinstance(payload["dispatch_run_id"], int)
    assert payload["mcp_operator_checklist_valid"] is None or isinstance(
        payload["mcp_operator_checklist_valid"],
        bool,
    )
    assert len(payload["evidence_refs"]) >= schema["properties"]["evidence_refs"]["minItems"]
    assert all(isinstance(item, str) and item for item in payload["evidence_refs"])


def _completed(command: list[str], payload: object) -> subprocess.CompletedProcess[str]:
    stdout = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")


def _healthy_getter(url: str) -> tuple[int, dict[str, Any]]:
    if url.endswith("/health"):
        return 200, {"status": "healthy"}
    if url.endswith("/gateway/witness"):
        return 200, {
            "witness_id": "runtime-witness-1",
            "environment": "pilot",
            "runtime_status": "healthy",
            "gateway_status": "healthy",
            "latest_command_event_hash": "abc123",
            "latest_terminal_certificate_id": "terminal-1",
            "responsibility_debt_clear": True,
            "signed_at": "2026-04-25T00:00:00Z",
            "signature_key_id": "runtime",
            "signature": "hmac-sha256:placeholder",
        }
    if url.endswith("/runtime/conformance"):
        return 200, {
            "certificate_id": "conf-0123456789abcdef",
            "environment": "pilot",
            "issued_at": "2026-04-25T00:00:00+00:00",
            "expires_at": "2099-04-25T00:30:00+00:00",
            "gateway_witness_valid": True,
            "runtime_witness_valid": True,
            "latest_anchor_valid": True,
            "command_closure_canary_passed": True,
            "capability_admission_canary_passed": True,
            "dangerous_capability_isolation_canary_passed": True,
            "streaming_budget_canary_passed": True,
            "lineage_query_canary_passed": True,
            "authority_obligation_canary_passed": True,
            "authority_responsibility_debt_clear": True,
            "authority_pending_approval_chain_count": 0,
            "authority_overdue_approval_chain_count": 0,
            "authority_open_obligation_count": 0,
            "authority_overdue_obligation_count": 0,
            "authority_escalated_obligation_count": 0,
            "authority_unowned_high_risk_capability_count": 0,
            "authority_directory_sync_receipt_valid": True,
            "mcp_capability_manifest_configured": False,
            "mcp_capability_manifest_valid": True,
            "mcp_capability_manifest_capability_count": 0,
            "capability_plan_bundle_canary_passed": True,
            "capability_plan_bundle_count": 0,
            "capsule_registry_certified": True,
            "proof_coverage_matrix_current": True,
            "proof_coverage_declared_routes_classified": True,
            "proof_coverage_declared_route_count": 301,
            "proof_coverage_unclassified_route_count": 0,
            "known_limitations_aligned": False,
            "security_model_aligned": False,
            "terminal_status": "conformant_with_gaps",
            "open_conformance_gaps": ["known_limitations_documentation_drift"],
            "evidence_refs": ["gateway_witness:test"],
            "checks": [
                {
                    "check_id": "gateway_witness_valid",
                    "passed": True,
                    "evidence_ref": "gateway_witness:test",
                    "detail": "verified",
                }
            ],
            "signature_key_id": "runtime-conformance-test",
            "signature": "hmac-sha256:placeholder",
        }
    raise AssertionError(f"unexpected url: {url}")
