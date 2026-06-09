"""Tests for gateway proxy usage policy.

Purpose: verify proxy environment variables cannot silently alter gateway
    outbound routing in production-like runtimes.
Governance scope: ProxyUsagePolicy, proxy URL redaction, and signed worker
    transport fail-closed behavior.
Dependencies: gateway.proxy_policy and gateway.adapter_worker_clients.
Invariants:
  - Proxy credentials are redacted from policy evidence.
  - Pilot/production block unallowlisted proxy variables before network I/O.
  - Local development policy remains non-blocking for developer machines.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.adapter_worker_clients import SignedAdapterWorkerTransport  # noqa: E402
from gateway.proxy_policy import (  # noqa: E402
    ProxyUsagePolicy,
    active_proxy_environment,
    assert_proxy_environment_allowed,
    redact_proxy_url,
)


def test_proxy_url_redaction_removes_credentials_and_host() -> None:
    redacted = redact_proxy_url("http://user:secret@proxy.internal:8080/path")
    malformed = redact_proxy_url("http://user:secret@proxy.internal:notaport/path")

    assert redacted == "http://<redacted-host>:8080"
    assert malformed == "http://<redacted-host>"
    assert "user" not in redacted
    assert "secret" not in redacted
    assert "proxy.internal" not in redacted
    assert "secret" not in malformed
    assert "proxy.internal" not in malformed


def test_active_proxy_environment_returns_only_redacted_values() -> None:
    active = active_proxy_environment(
        {
            "HTTP_PROXY": "http://user:secret@proxy.internal:8080",
            "NO_PROXY": "localhost,127.0.0.1",
            "MULLU_ENV": "production",
        }
    )

    assert active["HTTP_PROXY"] == "http://<redacted-host>:8080"
    assert active["NO_PROXY"] == "<redacted-no-proxy-list>"
    assert "secret" not in repr(active)


def test_production_proxy_environment_blocks_without_values() -> None:
    with pytest.raises(RuntimeError, match="^proxy environment blocked:HTTP_PROXY$") as excinfo:
        assert_proxy_environment_allowed(
            policy=ProxyUsagePolicy(environment="production"),
            environ={"HTTP_PROXY": "http://user:secret@proxy.internal:8080"},
        )

    message = str(excinfo.value)
    assert "HTTP_PROXY" in message
    assert "secret" not in message
    assert "proxy.internal" not in message


def test_proxy_environment_allowlist_makes_activation_explicit() -> None:
    assert_proxy_environment_allowed(
        policy=ProxyUsagePolicy(
            environment="production",
            allowed_environment_variables=("HTTP_PROXY",),
        ),
        environ={"HTTP_PROXY": "http://proxy.internal:8080"},
    )


def test_local_proxy_environment_is_non_blocking() -> None:
    assert_proxy_environment_allowed(
        policy=ProxyUsagePolicy(environment="local_dev"),
        environ={"HTTP_PROXY": "http://proxy.internal:8080"},
    )


def test_signed_transport_blocks_proxy_environment_before_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MULLU_ENV", "production")
    monkeypatch.setenv("HTTP_PROXY", "http://user:secret@proxy.internal:8080")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("network call should be blocked before urlopen")

    monkeypatch.setattr("urllib.request.urlopen", fail_if_called)
    transport = SignedAdapterWorkerTransport(
        adapter_id="browser",
        endpoint_url="https://worker.invalid/browser/execute",
        signing_secret="browser-transport-secret",
        request_signature_header="X-Mullu-Browser-Signature",
        response_signature_header="X-Mullu-Browser-Response-Signature",
    )

    with pytest.raises(RuntimeError, match="^proxy environment blocked:HTTP_PROXY") as excinfo:
        transport.submit(
            {
                "request_id": "browser-request-1",
                "tenant_id": "tenant-1",
                "capability_id": "browser.extract_text",
            },
            expected_request_id="browser-request-1",
            expected_tenant_id="tenant-1",
            expected_capability_id="browser.extract_text",
        )

    assert "secret" not in str(excinfo.value)
