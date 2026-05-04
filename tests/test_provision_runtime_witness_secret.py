"""Tests for runtime witness secret provisioning.

Purpose: verify governed secret binding without exposing the secret value.
Governance scope: [OCE, CDCV, UWMA, PRS]
Dependencies: scripts.provision_runtime_witness_secret.
Invariants:
  - GitHub secret updates receive the secret through stdin.
  - Supplied secrets are validated before GitHub mutation.
  - CLI output contains only a fingerprint, never the secret value.
"""

from __future__ import annotations

import subprocess

import pytest

from scripts.provision_runtime_witness_secret import (
    main,
    provision_runtime_witness_secret,
)


class FakeRunner:
    """Deterministic gh secret set runner fixture."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.inputs: list[str | None] = []

    def __call__(
        self,
        command: list[str],
        *,
        input: str | None,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        self.inputs.append(input)
        assert check is True
        assert capture_output is True
        assert text is True
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


class FailingRunner(FakeRunner):
    """Runner that fails with untrusted CLI text."""

    def __call__(
        self,
        command: list[str],
        *,
        input: str | None,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        self.inputs.append(input)
        raise subprocess.CalledProcessError(
            returncode=7,
            cmd=command,
            output="stdout-secret-token",
            stderr="stderr-secret-token",
        )


def test_provision_runtime_witness_secret_sets_github_secret_from_stdin() -> None:
    runner = FakeRunner()
    secret_value = "x" * 40

    result = provision_runtime_witness_secret(
        supplied_secret=secret_value,
        runner=runner,
        clock=lambda: "2026-04-25T02:00:00Z",
    )

    assert result.github_secret_set is True
    assert result.secret_source == "stdin"
    assert result.fingerprint
    assert result.provisioned_at == "2026-04-25T02:00:00Z"
    assert result.runtime_env_output is None
    assert runner.commands == [
        [
            "gh",
            "secret",
            "set",
            "MULLU_RUNTIME_WITNESS_SECRET",
            "--repo",
            "tamirat-wubie/mullu-control-plane",
        ]
    ]
    assert runner.inputs == [secret_value]


def test_provision_runtime_witness_secret_rejects_short_supplied_secret() -> None:
    runner = FakeRunner()

    with pytest.raises(RuntimeError, match="at least 32 characters"):
        provision_runtime_witness_secret(supplied_secret="too-short", runner=runner)

    assert runner.commands == []
    assert runner.inputs == []


def test_provision_runtime_witness_secret_can_skip_github_mutation() -> None:
    runner = FakeRunner()

    result = provision_runtime_witness_secret(
        supplied_secret="y" * 40,
        set_github_secret=False,
        runner=runner,
        clock=lambda: "2026-04-25T02:00:00Z",
    )

    assert result.github_secret_set is False
    assert result.secret_name == "MULLU_RUNTIME_WITNESS_SECRET"
    assert "same value" in result.runtime_export_hint
    assert runner.commands == []


def test_generated_secret_requires_runtime_env_output() -> None:
    runner = FakeRunner()

    with pytest.raises(RuntimeError, match="requires --runtime-env-output"):
        provision_runtime_witness_secret(
            set_github_secret=False,
            runner=runner,
        )

    assert runner.commands == []
    assert runner.inputs == []


def test_generated_secret_writes_runtime_env_output(tmp_path) -> None:
    runner = FakeRunner()
    output_path = tmp_path / "runtime_witness_secret.env"

    result = provision_runtime_witness_secret(
        runtime_env_output=output_path,
        runner=runner,
        clock=lambda: "2026-04-25T02:00:00Z",
    )
    written = output_path.read_text(encoding="utf-8")

    assert result.github_secret_set is True
    assert result.secret_source == "generated"
    assert result.runtime_env_output == output_path
    assert written.startswith("MULLU_RUNTIME_WITNESS_SECRET=")
    assert runner.inputs
    assert runner.inputs[0] in written


def test_cli_output_redacts_supplied_secret(monkeypatch, capsys) -> None:
    secret_value = "z" * 40
    runner = FakeRunner()

    monkeypatch.setattr(
        "scripts.provision_runtime_witness_secret.subprocess.run",
        runner,
    )
    monkeypatch.setattr("sys.stdin.read", lambda: secret_value)

    exit_code = main(["--secret-stdin"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "secret_fingerprint:" in captured.out
    assert "github_secret_set: true" in captured.out
    assert secret_value not in captured.out
    assert runner.inputs == [secret_value]


def test_provision_runtime_witness_secret_command_failure_is_bounded() -> None:
    runner = FailingRunner()
    secret_value = "s" * 40

    with pytest.raises(RuntimeError) as exc_info:
        provision_runtime_witness_secret(
            supplied_secret=secret_value,
            runner=runner,
        )

    message = str(exc_info.value)
    assert message == "failed to set GitHub secret MULLU_RUNTIME_WITNESS_SECRET: exit_code=7"
    assert "stdout-secret-token" not in message
    assert "stderr-secret-token" not in message
    assert secret_value not in message
    assert runner.inputs == [secret_value]
