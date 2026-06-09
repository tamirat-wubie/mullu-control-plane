"""Tests for bounded CLI helper contracts."""

from __future__ import annotations

import pytest

from mcoi_runtime.app import cli
from mcoi_runtime.app.cli import CLIDemoError, _load_demo_json_object


def test_load_demo_json_object_bounds_invalid_root_type() -> None:
    with pytest.raises(CLIDemoError, match="^invalid JSON response root$") as exc_info:
        _load_demo_json_object(b"[]")
    assert "list" not in str(exc_info.value).lower()


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
