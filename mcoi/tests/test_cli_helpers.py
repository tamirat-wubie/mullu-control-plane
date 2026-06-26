"""Tests for bounded CLI helper contracts."""

from __future__ import annotations

import pytest

from mcoi_runtime.app import cli
from mcoi_runtime.app.cli import CLIDemoError, _load_demo_json_object


def test_load_demo_json_object_bounds_invalid_root_type() -> None:
    with pytest.raises(CLIDemoError, match="^invalid JSON response root$") as exc_info:
        _load_demo_json_object(b"[]")
    assert "list" not in str(exc_info.value).lower()


def test_autonomous_demo_renders_local_continuation_summary(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(
        [
            "autonomous-demo",
            "--target",
            "workspace",
            "--objective",
            "prepare local change",
            "--change",
            "apply local patch",
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Autonomous Request Episode Summary" in output
    assert "automation_state:   settled_without_prompt" in output
    assert "workflow_stages:    3" in output
    assert "approval_stages:    0" in output
    assert "external_stages:    0" in output
    assert "prompt_count:       0" in output


def test_autonomous_demo_rejects_negative_retry_count(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["autonomous-demo", "--max-local-retries", "-1"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 1
    assert "max-local-retries must be non-negative" in captured.err
    assert captured.out == ""


def test_demo_command_blocks_proxy_environment_before_http(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("MULLU_ENV", "production")
    monkeypatch.setenv("HTTPS_PROXY", "http://user:secret@proxy.internal:8080")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("demo command should block before urlopen")

    monkeypatch.setattr("urllib.request.urlopen", fail_if_called)

    result = cli.demo_command(type("Args", (), {"url": "http://localhost:8000"})())
    captured = capsys.readouterr()

    assert result == 1
    assert "proxy environment blocked:HTTPS_PROXY" in captured.out
    assert "secret" not in captured.out
    assert "proxy.internal" not in captured.out
