"""Tests for standalone script proxy governance.

Purpose: verify operator/evidence scripts cannot silently inherit process proxy
    routing in production-like runs.
Governance scope: script-side ProxyUsagePolicy, transport preflight, and
    credential-safe remote submission errors.
Dependencies: scripts.proxy_policy, scripts.gateway_runtime_smoke, and
    scripts.submit_trust_ledger_anchor_export.
Invariants:
  - Proxy credentials are redacted from script policy evidence.
  - Production-like script probes block before network I/O.
  - Remote submission reports bounded proxy-policy reasons.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import gateway_runtime_smoke  # noqa: E402
from scripts.proxy_policy import (  # noqa: E402
    PROXY_ENVIRONMENT_VARIABLES,
    ProxyUsagePolicy,
    active_proxy_environment,
    assert_proxy_environment_allowed,
    redact_proxy_url,
)
from scripts.submit_trust_ledger_anchor_export import _submit_remote_transparency_log  # noqa: E402


def _clear_proxy_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in PROXY_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("MULLU_PROXY_ENV_ALLOWLIST", raising=False)


def test_script_proxy_policy_redacts_and_blocks_production_proxy_environment() -> None:
    active = active_proxy_environment(
        {
            "HTTPS_PROXY": "socks5://user:secret@proxy.internal:1080",
            "NO_PROXY": "localhost,127.0.0.1",
            "MULLU_ENV": "production",
        }
    )

    with pytest.raises(RuntimeError, match="^proxy environment blocked:HTTPS_PROXY$") as excinfo:
        assert_proxy_environment_allowed(
            policy=ProxyUsagePolicy(environment="production"),
            environ={"HTTPS_PROXY": "socks5://user:secret@proxy.internal:1080"},
        )

    assert active["HTTPS_PROXY"] == "socks5://<redacted-host>:1080"
    assert active["NO_PROXY"] == "<redacted-no-proxy-list>"
    assert "secret" not in str(excinfo.value)
    assert "proxy.internal" not in str(excinfo.value)
    assert redact_proxy_url("http://user:secret@proxy.internal:8080") == "http://<redacted-host>:8080"
    assert redact_proxy_url("http://user:secret@proxy.internal:notaport") == "http://<redacted-host>"


def test_gateway_runtime_smoke_blocks_proxy_environment_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_proxy_environment(monkeypatch)
    monkeypatch.setenv("MULLU_ENV", "production")
    monkeypatch.setenv("HTTPS_PROXY", "http://user:secret@proxy.internal:8080")

    def fail_if_called(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("urlopen should not run after proxy policy rejection")

    monkeypatch.setattr("urllib.request.urlopen", fail_if_called)
    results = gateway_runtime_smoke.run_probe(
        gateway_url="https://gateway.invalid",
        worker_url="https://worker.invalid/capability/execute",
        worker_secret="worker-secret",
    )

    assert results
    assert all(result.passed is False for result in results)
    assert all("proxy environment blocked:HTTPS_PROXY" in result.detail for result in results)
    assert "secret" not in repr(results)
    assert "proxy.internal" not in repr(results)


def test_remote_trust_ledger_submit_blocks_proxy_environment_without_leaking_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_proxy_environment(monkeypatch)
    monkeypatch.setenv("MULLU_ENV", "production")
    monkeypatch.setenv("HTTP_PROXY", "http://user:secret@proxy.internal:8080")

    def fail_if_called(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("remote submit should be blocked before urlopen")

    report = _submit_remote_transparency_log(
        submit_url="https://ledger.invalid/submit",
        api_token="token-value",
        timeout_seconds=5.0,
        payload={"submission_payload_hash": "a" * 64, "payload": "bounded"},
        urlopen=fail_if_called,
    )

    assert report["valid"] is False
    assert report["reason"] == "remote_proxy_environment_blocked"
    assert report["submission_payload_hash"] == "a" * 64
    assert "secret" not in repr(report)
    assert "proxy.internal" not in repr(report)


def test_script_transport_sources_are_governed_or_disable_env_proxy() -> None:
    script_paths = (
        "scripts/collect_deployment_witness.py",
        "scripts/collect_github_teams_export.py",
        "scripts/collect_governed_swarm_staging_activation_witness.py",
        "scripts/collect_product_dashboard_production_prometheus_scrape_probe.py",
        "scripts/collect_runtime_conformance.py",
        "scripts/collect_scim_directory_export.py",
        "scripts/gateway_runtime_smoke.py",
        "scripts/preflight_deployment_witness.py",
        "scripts/preflight_finance_email_calendar_recovery.py",
        "scripts/staging_drill.py",
        "scripts/submit_trust_ledger_anchor_export.py",
    )

    for path_text in script_paths:
        content = (_ROOT / path_text).read_text(encoding="utf-8")
        assert "assert_proxy_environment_allowed()" in content, path_text

    image_skill = (_ROOT / "skills/creative/image_gen.py").read_text(encoding="utf-8")
    assert "httpx.post(" in image_skill
    assert "trust_env=False" in image_skill
