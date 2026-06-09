"""Tests for MCOI runtime proxy usage policy.

Purpose: verify provider/runtime network paths fail closed on ungoverned proxy
    environment variables in production-like runtimes.
Governance scope: ProxyUsagePolicy, provider transport redaction, and dry-run
    protection from process proxy inheritance.
Dependencies: mcoi_runtime.adapters.proxy_policy and multi_provider.
Invariants:
  - Proxy credentials are never surfaced in policy errors.
  - Hosted provider calls are blocked before httpx when production proxy env is active.
  - Explicit local/test proxy variables do not mutate dry-run behavior.
"""

from __future__ import annotations

from typing import Any

import pytest

from mcoi_runtime.adapters.multi_provider import GroqBackend
from mcoi_runtime.adapters.proxy_policy import (
    ProxyUsagePolicy,
    assert_proxy_environment_allowed,
    redact_proxy_url,
)
from mcoi_runtime.contracts.llm import LLMInvocationParams, LLMMessage, LLMRole


def _params() -> LLMInvocationParams:
    return LLMInvocationParams(
        model_name="test-model",
        messages=(LLMMessage(role=LLMRole.USER, content="test"),),
        max_tokens=8,
        temperature=0.0,
        tenant_id="tenant-1",
    )


def test_runtime_proxy_url_redaction_removes_credentials_and_host() -> None:
    redacted = redact_proxy_url("socks5://user:secret@proxy.internal:1080")
    malformed = redact_proxy_url("socks5://user:secret@proxy.internal:notaport")

    assert redacted == "socks5://<redacted-host>:1080"
    assert malformed == "socks5://<redacted-host>"
    assert "user" not in redacted
    assert "secret" not in redacted
    assert "proxy.internal" not in redacted
    assert "secret" not in malformed
    assert "proxy.internal" not in malformed


def test_runtime_production_proxy_environment_blocks_without_values() -> None:
    with pytest.raises(RuntimeError, match="^proxy environment blocked:HTTPS_PROXY$") as excinfo:
        assert_proxy_environment_allowed(
            policy=ProxyUsagePolicy(environment="pilot"),
            environ={"HTTPS_PROXY": "http://user:secret@proxy.internal:8080"},
        )

    assert "secret" not in str(excinfo.value)
    assert "proxy.internal" not in str(excinfo.value)
    assert "HTTPS_PROXY" in str(excinfo.value)


def test_multi_provider_blocks_proxy_environment_before_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MULLU_ENV", "production")
    monkeypatch.setenv("HTTPS_PROXY", "http://user:secret@proxy.internal:8080")

    def fail_if_called(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("httpx.post should not run after proxy policy rejection")

    monkeypatch.setattr("httpx.post", fail_if_called)
    result = GroqBackend(api_key="test-key").call(_params())

    assert result.succeeded is False
    assert result.error == "provider error (RuntimeError)"
    assert "secret" not in result.error


def test_local_proxy_environment_does_not_block_dry_run_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MULLU_ENV", "local_dev")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.internal:8080")
    assert_proxy_environment_allowed(
        policy=ProxyUsagePolicy(environment="local_dev"),
        environ={"HTTPS_PROXY": "http://proxy.internal:8080"},
    )

    assert redact_proxy_url("http://proxy.internal:8080") == "http://<redacted-host>:8080"
