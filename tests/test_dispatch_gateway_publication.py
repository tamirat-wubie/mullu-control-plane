"""Tests for governed gateway publication workflow dispatch.

Purpose: verify the CLI shortcut validates publication inputs, secret presence,
workflow state, and artifact download without reading secret values.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.dispatch_gateway_publication.
Invariants:
  - Runtime witness secret presence is checked by name only.
  - Kubeconfig secret is required only when ingress apply is requested.
  - Workflow dispatch happens only after validation succeeds.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.dispatch_gateway_publication import (
    DEFAULT_REPOSITORY,
    dispatch_gateway_publication,
    main,
)


class FakeRunner:
    """Deterministic gh command runner fixture."""

    def __init__(
        self,
        *,
        runtime_secret_present: bool = True,
        kubeconfig_secret_present: bool = True,
        workflow_state: str = "active",
        run_conclusion: str = "success",
    ) -> None:
        self.runtime_secret_present = runtime_secret_present
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


def test_dispatch_gateway_publication_runs_workflow_and_downloads_artifact(tmp_path: Path) -> None:
    runner = FakeRunner()

    result = dispatch_gateway_publication(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        dispatch_witness=True,
        download_dir=tmp_path / "artifact",
        poll_seconds=1,
        runner=runner,
    )
    workflow_run_command = next(
        command for command in runner.commands if command[:3] == ["gh", "workflow", "run"]
    )

    assert result.run_id == 4567
    assert result.conclusion == "success"
    assert result.artifact_dir == tmp_path / "artifact"
    assert "gateway_host=gateway.mullusi.com" in workflow_run_command
    assert "expected_environment=pilot" in workflow_run_command
    assert "apply_ingress=false" in workflow_run_command
    assert "dispatch_witness=true" in workflow_run_command
    assert "skip_preflight_endpoint_probes=false" in workflow_run_command
    assert any(command[:3] == ["gh", "run", "download"] for command in runner.commands)


def test_dispatch_gateway_publication_requires_kubeconfig_for_apply(tmp_path: Path) -> None:
    runner = FakeRunner(kubeconfig_secret_present=False)

    with pytest.raises(RuntimeError, match="MULLU_KUBECONFIG_B64"):
        dispatch_gateway_publication(
            gateway_host="gateway.mullusi.com",
            expected_environment="pilot",
            apply_ingress=True,
            download_dir=tmp_path / "artifact",
            runner=runner,
        )

    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)
    assert not (tmp_path / "artifact").exists()


def test_dispatch_gateway_publication_skips_kubeconfig_when_not_applying(tmp_path: Path) -> None:
    runner = FakeRunner(kubeconfig_secret_present=False)

    result = dispatch_gateway_publication(
        gateway_host="gateway.mullusi.com",
        gateway_url="https://gateway.mullusi.com/",
        expected_environment="production",
        skip_preflight_endpoint_probes=True,
        download_dir=tmp_path / "artifact",
        poll_seconds=1,
        runner=runner,
    )
    workflow_run_command = next(
        command for command in runner.commands if command[:3] == ["gh", "workflow", "run"]
    )

    assert result.conclusion == "success"
    assert "gateway_url=https://gateway.mullusi.com" in workflow_run_command
    assert "expected_environment=production" in workflow_run_command
    assert "skip_preflight_endpoint_probes=true" in workflow_run_command


def test_dispatch_gateway_publication_fails_before_dispatch_without_runtime_secret() -> None:
    runner = FakeRunner(runtime_secret_present=False)

    with pytest.raises(RuntimeError, match="MULLU_RUNTIME_WITNESS_SECRET"):
        dispatch_gateway_publication(
            gateway_host="gateway.mullusi.com",
            expected_environment="pilot",
            runner=runner,
        )

    assert runner.commands[0][:3] == ["gh", "secret", "list"]
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def test_dispatch_gateway_publication_fails_before_dispatch_when_workflow_inactive() -> None:
    runner = FakeRunner(workflow_state="disabled_manually")

    with pytest.raises(RuntimeError, match="not active"):
        dispatch_gateway_publication(
            gateway_host="gateway.mullusi.com",
            expected_environment="pilot",
            runner=runner,
        )

    assert len(runner.commands) == 2
    assert runner.commands[1][:3] == ["gh", "workflow", "list"]
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def test_dispatch_gateway_publication_rejects_invalid_host() -> None:
    runner = FakeRunner()

    with pytest.raises(RuntimeError, match="must not include URL scheme"):
        dispatch_gateway_publication(
            gateway_host="https://gateway.mullusi.com",
            expected_environment="pilot",
            runner=runner,
        )

    assert runner.commands == []


def test_cli_reports_missing_host(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "scripts.dispatch_gateway_publication.subprocess.run",
        FakeRunner(),
    )

    exit_code = main(["--gateway-host", ""])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "gateway publication dispatch failed" in captured.out
    assert "gateway host is required" in captured.out


def test_cli_dispatches_from_ready_readiness_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runner = FakeRunner(kubeconfig_secret_present=False)
    report_path = tmp_path / "readiness.json"
    _write_readiness_report(
        report_path,
        expected_environment="production",
        dispatch_witness=True,
        skip_preflight_endpoint_probes=True,
    )
    monkeypatch.setattr(
        "scripts.dispatch_gateway_publication.subprocess.run",
        runner,
    )

    exit_code = main(
        [
            "--readiness-report",
            str(report_path),
            "--download-dir",
            str(tmp_path / "artifact"),
        ]
    )
    workflow_run_command = next(
        command for command in runner.commands if command[:3] == ["gh", "workflow", "run"]
    )

    assert exit_code == 0
    assert "gateway_host=gateway.mullusi.com" in workflow_run_command
    assert "gateway_url=https://gateway.mullusi.com" in workflow_run_command
    assert "expected_environment=production" in workflow_run_command
    assert "dispatch_witness=true" in workflow_run_command
    assert "skip_preflight_endpoint_probes=true" in workflow_run_command


def test_cli_refuses_unready_readiness_report(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    runner = FakeRunner()
    report_path = tmp_path / "readiness.json"
    _write_readiness_report(report_path, ready=False)
    monkeypatch.setattr(
        "scripts.dispatch_gateway_publication.subprocess.run",
        runner,
    )

    exit_code = main(["--readiness-report", str(report_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert runner.commands == []
    assert "readiness report is not ready" in captured.out
    assert "gateway publication dispatch failed" in captured.out


def test_cli_refuses_readiness_report_repository_mismatch(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    runner = FakeRunner()
    report_path = tmp_path / "readiness.json"
    _write_readiness_report(report_path, repository="tamirat-wubie/other")
    monkeypatch.setattr(
        "scripts.dispatch_gateway_publication.subprocess.run",
        runner,
    )

    exit_code = main(["--readiness-report", str(report_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert runner.commands == []
    assert "repository mismatch" in captured.out
    assert "tamirat-wubie/other" in captured.out


def _completed(command: list[str], payload: object) -> subprocess.CompletedProcess[str]:
    stdout = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")


def _write_readiness_report(
    report_path: Path,
    *,
    repository: str = DEFAULT_REPOSITORY,
    ready: bool = True,
    expected_environment: str = "pilot",
    apply_ingress: bool = False,
    dispatch_witness: bool = False,
    skip_preflight_endpoint_probes: bool = False,
) -> None:
    report_path.write_text(
        json.dumps(
            {
                "repository": repository,
                "gateway_host": "gateway.mullusi.com",
                "gateway_url": "https://gateway.mullusi.com",
                "expected_environment": expected_environment,
                "apply_ingress": apply_ingress,
                "dispatch_witness": dispatch_witness,
                "skip_preflight_endpoint_probes": skip_preflight_endpoint_probes,
                "ready": ready,
                "steps": [],
            }
        ),
        encoding="utf-8",
    )
