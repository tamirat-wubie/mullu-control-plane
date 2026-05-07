"""Tests for one-command gateway publication orchestration.

Purpose: verify readiness evidence is written before optional workflow dispatch
and that dispatch uses the readiness-report handoff path.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.publish_gateway_publication.
Invariants:
  - Workflow dispatch requires an explicit dispatch request.
  - Unready reports never trigger workflow dispatch.
  - The same readiness report can feed the dispatcher handoff contract.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.publish_gateway_publication import main, publish_gateway_publication


class FakeRunner:
    """Deterministic gh command runner for publish orchestration."""

    def __init__(
        self,
        *,
        runtime_secret_present: bool = True,
        conformance_secret_present: bool = True,
        deployment_witness_secret_present: bool = True,
        kubeconfig_secret_present: bool = True,
        workflow_state: str = "active",
        run_conclusion: str = "success",
    ) -> None:
        self.runtime_secret_present = runtime_secret_present
        self.conformance_secret_present = conformance_secret_present
        self.deployment_witness_secret_present = deployment_witness_secret_present
        self.kubeconfig_secret_present = kubeconfig_secret_present
        self.workflow_state = workflow_state
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

        if command[:3] == ["gh", "secret", "list"]:
            payload = []
            if self.runtime_secret_present:
                payload.append({"name": "MULLU_RUNTIME_WITNESS_SECRET"})
            if self.conformance_secret_present:
                payload.append({"name": "MULLU_RUNTIME_CONFORMANCE_SECRET"})
            if self.deployment_witness_secret_present:
                payload.append({"name": "MULLU_DEPLOYMENT_WITNESS_SECRET"})
            if self.kubeconfig_secret_present:
                payload.append({"name": "MULLU_KUBECONFIG_B64"})
            return _completed(command, payload)
        if command[:3] == ["gh", "workflow", "list"]:
            return _completed(
                command,
                [
                    {
                        "name": "Gateway Publication Orchestration",
                        "path": ".github/workflows/gateway-publication.yml",
                        "state": self.workflow_state,
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
                        "databaseId": 4567,
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
                    "databaseId": 4567,
                    "status": "completed",
                    "conclusion": self.run_conclusion,
                    "url": "https://github.com/run/4567",
                },
            )
        if command[:3] == ["gh", "run", "download"]:
            return _completed(command, "")
        raise AssertionError(f"unexpected command: {command}")


def test_publish_writes_ready_report_without_dispatch(tmp_path: Path) -> None:
    runner = FakeRunner(kubeconfig_secret_present=False)
    report_path = tmp_path / "readiness.json"
    receipt_path = tmp_path / "receipt.json"

    result = publish_gateway_publication(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        readiness_report_path=report_path,
        receipt_output_path=receipt_path,
        runner=runner,
        resolver=_resolve_ok,
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert result.readiness.ready is True
    assert result.dispatch_requested is False
    assert result.dispatch is None
    assert result.receipt_path == receipt_path
    assert payload["ready"] is True
    assert payload["gateway_host"] == "gateway.mullusi.com"
    assert receipt["resolution_state"] == "ready-only"
    assert receipt["dispatch_performed"] is False
    assert receipt["readiness_ready"] is True
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def test_publish_dispatches_from_written_readiness_report(tmp_path: Path) -> None:
    runner = FakeRunner()
    report_path = tmp_path / "readiness.json"
    receipt_path = tmp_path / "receipt.json"

    result = publish_gateway_publication(
        gateway_host="gateway.mullusi.com",
        gateway_url="https://gateway.mullusi.com",
        expected_environment="production",
        dispatch_witness=True,
        skip_preflight_endpoint_probes=True,
        dispatch=True,
        readiness_report_path=report_path,
        receipt_output_path=receipt_path,
        download_dir=tmp_path / "artifact",
        poll_seconds=1,
        runner=runner,
        resolver=_resolve_ok,
    )
    workflow_run_command = next(
        command for command in runner.commands if command[:3] == ["gh", "workflow", "run"]
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert result.readiness.ready is True
    assert result.dispatch_requested is True
    assert result.dispatch is not None
    assert result.dispatch.conclusion == "success"
    assert result.receipt_path == receipt_path
    assert "gateway_host=gateway.mullusi.com" in workflow_run_command
    assert "gateway_url=https://gateway.mullusi.com" in workflow_run_command
    assert "expected_environment=production" in workflow_run_command
    assert "dispatch_witness=true" in workflow_run_command
    assert "skip_preflight_endpoint_probes=true" in workflow_run_command
    assert report_path.exists()
    assert receipt["resolution_state"] == "dispatched"
    assert receipt["dispatch_performed"] is True
    assert receipt["dispatch_run_id"] == 4567
    assert receipt["dispatch_conclusion"] == "success"


def test_publish_blocks_dispatch_when_readiness_fails(tmp_path: Path) -> None:
    runner = FakeRunner(runtime_secret_present=False)
    report_path = tmp_path / "readiness.json"
    receipt_path = tmp_path / "receipt.json"

    result = publish_gateway_publication(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        dispatch=True,
        readiness_report_path=report_path,
        receipt_output_path=receipt_path,
        runner=runner,
        resolver=_resolve_ok,
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert result.readiness.ready is False
    assert result.dispatch_requested is True
    assert result.dispatch is None
    assert result.receipt_path == receipt_path
    assert payload["ready"] is False
    assert "missing=MULLU_RUNTIME_WITNESS_SECRET" in [
        step["detail"] for step in payload["steps"]
    ]
    assert receipt["resolution_state"] == "blocked-not-ready"
    assert receipt["dispatch_requested"] is True
    assert receipt["dispatch_performed"] is False
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def test_publish_blocks_dispatch_without_deployment_witness_secret(tmp_path: Path) -> None:
    runner = FakeRunner(deployment_witness_secret_present=False)
    report_path = tmp_path / "readiness.json"
    receipt_path = tmp_path / "receipt.json"

    result = publish_gateway_publication(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        dispatch=True,
        readiness_report_path=report_path,
        receipt_output_path=receipt_path,
        runner=runner,
        resolver=_resolve_ok,
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert result.readiness.ready is False
    assert result.dispatch is None
    assert "missing=MULLU_DEPLOYMENT_WITNESS_SECRET" in [
        step["detail"] for step in payload["steps"]
    ]
    assert receipt["resolution_state"] == "blocked-not-ready"
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def test_cli_returns_success_for_ready_report_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runner = FakeRunner()
    report_path = tmp_path / "readiness.json"
    receipt_path = tmp_path / "receipt.json"
    monkeypatch.setattr("scripts.publish_gateway_publication.subprocess.run", runner)
    monkeypatch.setattr(
        "scripts.report_gateway_publication_readiness.socket.getaddrinfo",
        _fake_getaddrinfo,
    )

    exit_code = main(
        [
            "--gateway-host",
            "gateway.mullusi.com",
            "--expected-environment",
            "pilot",
            "--readiness-report-output",
            str(report_path),
            "--receipt-output",
            str(receipt_path),
        ]
    )
    captured = capsys.readouterr()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "ready: true" in captured.out
    assert f"receipt: {receipt_path}" in captured.out
    assert "dispatch_requested: false" in captured.out
    assert "handoff_command:" in captured.out
    assert receipt["resolution_state"] == "ready-only"
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def _resolve_ok(host: str) -> tuple[str, ...]:
    assert host == "gateway.mullusi.com"
    return ("203.0.113.10",)


def _fake_getaddrinfo(host: str, port: object) -> list[tuple[object, ...]]:
    assert host == "gateway.mullusi.com"
    assert port is None
    return [(None, None, None, None, ("203.0.113.10", 0))]


def _completed(command: list[str], payload: object) -> subprocess.CompletedProcess[str]:
    stdout = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
