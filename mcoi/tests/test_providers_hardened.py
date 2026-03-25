"""Purpose: verify hardened providers — HTTP config, SMTP config, process model, CLI.
Governance scope: provider adapter and CLI tests only.
Dependencies: provider adapters, CLI module.
Invariants: method allowlist enforced, size limits enforced, configs validated.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from mcoi_runtime.adapters.http_connector import HttpConnector, HttpConnectorConfig, _normalize_url
from mcoi_runtime.adapters.smtp_communication import SmtpConfig
from mcoi_runtime.adapters.process_model import ProcessModelAdapter, ProcessModelConfig
from mcoi_runtime.adapters.stub_model import StubModelAdapter
from mcoi_runtime.contracts.integration import (
    ConnectorDescriptor,
    ConnectorStatus,
    EffectClass,
    TrustClass,
)
from mcoi_runtime.contracts.model import ModelInvocation, ModelStatus, ValidationStatus
from mcoi_runtime.app.cli import build_parser, main


_CLOCK = "2026-03-19T00:00:00+00:00"


def _descriptor() -> ConnectorDescriptor:
    return ConnectorDescriptor(
        connector_id="http-1", name="HTTP Test", provider="test",
        effect_class=EffectClass.EXTERNAL_READ, trust_class=TrustClass.BOUNDED_EXTERNAL,
        credential_scope_id="scope-http", enabled=True,
    )


# --- HTTP Connector hardening ---


def test_http_config_validates() -> None:
    config = HttpConnectorConfig(timeout_seconds=10, max_response_bytes=1024)
    assert config.timeout_seconds == 10
    assert config.max_response_bytes == 1024


def test_http_config_rejects_bad_values() -> None:
    with pytest.raises(ValueError, match="timeout"):
        HttpConnectorConfig(timeout_seconds=-1)
    with pytest.raises(ValueError, match="max_response"):
        HttpConnectorConfig(max_response_bytes=0)


def test_url_normalization() -> None:
    assert _normalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path"
    assert _normalize_url("http://test.com") == "http://test.com/"


def test_http_method_not_allowed() -> None:
    connector = HttpConnector(
        clock=lambda: _CLOCK,
        config=HttpConnectorConfig(allowed_methods=("GET",)),
    )
    result = connector.invoke(_descriptor(), {"url": "https://example.com", "method": "POST"})
    assert result.status is ConnectorStatus.FAILED
    assert "method_not_allowed" in result.error_code


def test_http_missing_url_still_fails() -> None:
    connector = HttpConnector(clock=lambda: _CLOCK)
    result = connector.invoke(_descriptor(), {})
    assert result.status is ConnectorStatus.FAILED
    assert result.error_code == "missing_url"


# --- SMTP Config ---


def test_smtp_config_validates() -> None:
    config = SmtpConfig(host="smtp.test.com", port=587, sender_email="agent@test.com")
    assert config.host == "smtp.test.com"


def test_smtp_config_rejects_bad_port() -> None:
    with pytest.raises(ValueError, match="port"):
        SmtpConfig(host="smtp.test.com", port=-1, sender_email="a@b.com")


def test_smtp_config_rejects_empty_host() -> None:
    with pytest.raises(ValueError, match="host"):
        SmtpConfig(host="", port=587, sender_email="a@b.com")


# --- Process Model ---


def test_process_model_config_validates() -> None:
    config = ProcessModelConfig(command=(sys.executable, "-c", "print('hello')"), timeout_seconds=10)
    assert config.command == (sys.executable, "-c", "print('hello')")


def test_process_model_config_rejects_empty_command() -> None:
    with pytest.raises(ValueError, match="command"):
        ProcessModelConfig(command=())


def test_process_model_invokes_portable_python_command() -> None:
    adapter = ProcessModelAdapter(
        config=ProcessModelConfig(command=(sys.executable, "-c", "print('test-output')")),
        clock=lambda: _CLOCK,
    )
    inv = ModelInvocation(
        invocation_id="inv-1", model_id="python-model",
        prompt_hash="prompt-1", invoked_at=_CLOCK,
    )
    resp = adapter.invoke(inv)
    assert resp.status is ModelStatus.SUCCEEDED
    assert resp.validation_status is ValidationStatus.PENDING
    assert resp.output_digest != "none"
    assert resp.output_tokens is not None


def test_process_model_handles_failure() -> None:
    adapter = ProcessModelAdapter(
        config=ProcessModelConfig(command=(sys.executable, "-c", "import sys; sys.exit(1)")),
        clock=lambda: _CLOCK,
    )
    inv = ModelInvocation(
        invocation_id="inv-1", model_id="fail-model",
        prompt_hash="p-1", invoked_at=_CLOCK,
    )
    resp = adapter.invoke(inv)
    assert resp.status is ModelStatus.FAILED


# --- CLI ---


def test_cli_parser_builds() -> None:
    parser = build_parser()
    args = parser.parse_args(["status"])
    assert args.command == "status"


def test_cli_run_parses() -> None:
    parser = build_parser()
    args = parser.parse_args(["run", "request.json"])
    assert args.command == "run"
    assert args.request == "request.json"


def test_cli_status_runs() -> None:
    exit_code = main(["status"])
    assert exit_code == 0


def test_cli_run_with_inline_json(tmp_path: Path) -> None:
    request = json.dumps({
        "request_id": "cli-1",
        "subject_id": "cli-op",
        "goal_id": "cli-goal",
        "template": {
            "template_id": "tpl-1",
            "action_type": "shell_command",
            "command_argv": ["{python_executable}", "-c", "print('cli-test')"],
        },
        "bindings": {},
    })
    exit_code = main(["run", request])
    # Exit code 1 because verification is open (not complete), which is correct
    assert exit_code == 1


def test_cli_runtime_binding_allows_portable_python_template(capsys: pytest.CaptureFixture[str]) -> None:
    request = json.dumps({
        "request_id": "cli-bind-1",
        "subject_id": "cli-op",
        "goal_id": "cli-goal",
        "template": {
            "template_id": "tpl-bind-1",
            "action_type": "shell_command",
            "command_argv": ["{python_executable}", "-c", "print('binding-test')"],
        },
        "bindings": {},
    })
    exit_code = main(["run", request])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "dispatched:         True" in output
    assert "validation_error" not in output


def test_cli_shipped_examples_run_portably(capsys: pytest.CaptureFixture[str]) -> None:
    examples_root = Path(__file__).resolve().parent.parent / "examples"
    request_examples = sorted(examples_root.glob("request-*.json"))

    assert request_examples

    for example_path in request_examples:
        exit_code = main(["run", str(example_path)])
        output = capsys.readouterr().out

        assert exit_code == 1
        assert "dispatched:         True" in output
        assert "validation_error" not in output


def test_cli_rejects_malformed_inline_request_json(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["run", '{"request_id": "bad"'])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "invalid request JSON in inline input" in captured.err


def test_cli_rejects_non_object_inline_request_json(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["run", '["not", "an", "object"]'])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "request JSON root must be an object" in captured.err


def test_cli_rejects_malformed_request_file_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request_file = tmp_path / "bad-request.json"
    request_file.write_text('{"request_id": "bad"', encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(["run", str(request_file)])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "invalid request JSON" in captured.err
    assert str(request_file) in captured.err


def test_cli_no_command_returns_zero() -> None:
    exit_code = main([])
    assert exit_code == 0
