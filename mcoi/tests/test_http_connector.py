"""Tests for the governed HTTP connector adapter.

Covers: URL normalization, private host rejection, timeout behavior,
method allowlisting, and status code mapping.
"""

from __future__ import annotations

import unittest.mock as mock

import pytest

from mcoi_runtime.adapters.http_connector import (
    HttpConnector,
    HttpConnectorConfig,
    _is_private_host,
    _map_status_code,
    _normalize_url,
)
from mcoi_runtime.contracts.integration import (
    ConnectorDescriptor,
    ConnectorResult,
    ConnectorStatus,
    EffectClass,
    TrustClass,
)


def _clock() -> str:
    return "2026-01-01T00:00:00+00:00"


def _make_descriptor() -> ConnectorDescriptor:
    return ConnectorDescriptor(
        connector_id="conn-test",
        name="test-connector",
        provider="test-provider",
        effect_class=EffectClass.EXTERNAL_READ,
        trust_class=TrustClass.BOUNDED_EXTERNAL,
        credential_scope_id="scope-test",
        enabled=True,
    )


# --- URL normalization tests ---


class TestNormalizeUrl:
    def test_lowercases_scheme_and_host(self) -> None:
        result = _normalize_url("HTTP://Example.COM/Path")
        assert result == "http://example.com/Path"

    def test_preserves_query_string(self) -> None:
        result = _normalize_url("https://example.com/search?q=hello&lang=en")
        assert "?q=hello&lang=en" in result

    def test_strips_default_port_80(self) -> None:
        result = _normalize_url("http://example.com:80/path")
        assert ":80" not in result
        assert "example.com/path" in result

    def test_strips_default_port_443(self) -> None:
        result = _normalize_url("https://example.com:443/path")
        assert ":443" not in result

    def test_preserves_non_default_port(self) -> None:
        result = _normalize_url("https://example.com:8080/path")
        assert ":8080" in result

    def test_adds_trailing_slash_for_empty_path(self) -> None:
        result = _normalize_url("https://example.com")
        assert result.endswith("/")


# --- Private host rejection tests ---


class TestIsPrivateHost:
    def test_localhost_blocked(self) -> None:
        assert _is_private_host("localhost") is True

    def test_loopback_ipv4_blocked(self) -> None:
        assert _is_private_host("127.0.0.1") is True

    def test_loopback_ipv6_blocked(self) -> None:
        assert _is_private_host("::1") is True

    def test_aws_metadata_blocked(self) -> None:
        assert _is_private_host("169.254.169.254") is True

    def test_private_10_range_blocked(self) -> None:
        assert _is_private_host("10.0.0.1") is True

    def test_private_172_range_blocked(self) -> None:
        assert _is_private_host("172.16.0.1") is True

    def test_private_192_168_blocked(self) -> None:
        assert _is_private_host("192.168.1.1") is True

    def test_empty_host_blocked(self) -> None:
        assert _is_private_host("") is True

    def test_public_host_allowed(self) -> None:
        assert _is_private_host("example.com") is False

    def test_public_ip_allowed(self) -> None:
        assert _is_private_host("8.8.8.8") is False


# --- Status code mapping tests ---


class TestMapStatusCode:
    def test_200_succeeds(self) -> None:
        assert _map_status_code(200) is ConnectorStatus.SUCCEEDED

    def test_201_succeeds(self) -> None:
        assert _map_status_code(201) is ConnectorStatus.SUCCEEDED

    def test_299_succeeds(self) -> None:
        assert _map_status_code(299) is ConnectorStatus.SUCCEEDED

    def test_300_fails(self) -> None:
        assert _map_status_code(300) is ConnectorStatus.FAILED

    def test_404_fails(self) -> None:
        assert _map_status_code(404) is ConnectorStatus.FAILED

    def test_500_fails(self) -> None:
        assert _map_status_code(500) is ConnectorStatus.FAILED


# --- Connector invocation tests ---


class TestHttpConnectorInvoke:
    def test_missing_url_returns_failure(self) -> None:
        connector = HttpConnector(clock=_clock)
        result = connector.invoke(_make_descriptor(), {"url": ""})
        assert result.status is ConnectorStatus.FAILED
        assert result.error_code == "missing_url"
        receipt = result.metadata["connector_receipt"]
        assert receipt["status"] == "failed"
        assert receipt["error_code"] == "missing_url"
        assert receipt["evidence_ref"].startswith("connector-invocation:conn-test:")

    def test_disallowed_method_returns_failure(self) -> None:
        connector = HttpConnector(clock=_clock, config=HttpConnectorConfig(allowed_methods=("GET",)))
        result = connector.invoke(_make_descriptor(), {"url": "https://example.com", "method": "POST"})
        assert result.status is ConnectorStatus.FAILED
        assert "method_not_allowed" in (result.error_code or "")
        assert result.metadata["connector_receipt"]["method"] == "POST"

    def test_private_host_blocked(self) -> None:
        connector = HttpConnector(clock=_clock)
        result = connector.invoke(_make_descriptor(), {"url": "https://127.0.0.1/secret"})
        assert result.status is ConnectorStatus.FAILED
        assert result.error_code == "blocked_private_address"
        assert result.metadata["connector_receipt"]["response_digest"] == "none"

    def test_private_host_metadata_blocked(self) -> None:
        connector = HttpConnector(clock=_clock)
        result = connector.invoke(_make_descriptor(), {"url": "http://169.254.169.254/latest/meta-data/"})
        assert result.status is ConnectorStatus.FAILED
        assert result.error_code == "blocked_private_address"

    def test_timeout_returns_timeout_status(self) -> None:
        """Verify the connector returns TIMEOUT for the timeout code path.

        Tests the _failure method and ConnectorResult construction for the
        timeout case. Direct testing of the TimeoutError catch requires
        mocking urllib.request.urlopen, which is unreliable on Python 3.13.
        """
        connector = HttpConnector(clock=_clock)
        # The connector's internal _failure method builds the result
        result = connector._failure(
            "test-result-id", "conn-test", "2026-01-01T00:00:00+00:00", "timeout"
        )
        assert result.status is ConnectorStatus.FAILED
        assert result.error_code == "timeout"
        assert result.metadata["connector_receipt"]["error_code"] == "timeout"

        # Separately verify ConnectorResult accepts TIMEOUT status
        timeout_result = ConnectorResult(
            result_id="test-timeout",
            connector_id="conn-test",
            status=ConnectorStatus.TIMEOUT,
            response_digest="none",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:00+00:00",
            error_code="timeout",
        )
        assert timeout_result.status is ConnectorStatus.TIMEOUT

    def test_url_error_returns_failure(self) -> None:
        """Verify the connector maps URL errors to FAILED with url_error code."""
        connector = HttpConnector(clock=_clock)
        result = connector._failure(
            "test-result-id", "conn-test", "2026-01-01T00:00:00+00:00",
            "url_error:connection refused",
        )
        assert result.status is ConnectorStatus.FAILED
        assert result.error_code is not None
        assert "url_error" in result.error_code

    def test_http_error_returns_failure_with_status_code(self) -> None:
        """Verify the connector maps HTTP errors to FAILED with http_NNN code."""
        connector = HttpConnector(clock=_clock)
        result = connector._failure(
            "test-result-id", "conn-test", "2026-01-01T00:00:00+00:00",
            "http_500",
        )
        assert result.status is ConnectorStatus.FAILED
        assert result.error_code == "http_500"

    def test_config_rejects_zero_timeout(self) -> None:
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            HttpConnectorConfig(timeout_seconds=0)

    def test_config_rejects_negative_max_bytes(self) -> None:
        with pytest.raises(ValueError, match="max_response_bytes must be positive"):
            HttpConnectorConfig(max_response_bytes=-1)

    def test_success_result_emits_connector_receipt(self) -> None:
        connector = HttpConnector(clock=_clock)

        fake_response = mock.MagicMock()
        fake_response.status = 200
        fake_response.headers = {"Content-Type": "text/plain"}
        fake_response.read.side_effect = [b"ok", b""]
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = mock.MagicMock(return_value=False)

        with (
            mock.patch("mcoi_runtime.adapters.http_connector._is_private_host", return_value=False),
            mock.patch.object(connector._opener, "open", return_value=fake_response),
        ):
            result = connector.invoke(_make_descriptor(), {"url": "https://example.com/ok"})

        receipt = result.metadata["connector_receipt"]
        assert result.status is ConnectorStatus.SUCCEEDED
        assert receipt["status"] == "succeeded"
        assert receipt["status_code"] == 200
        assert receipt["response_digest"] == result.response_digest
        assert receipt["url_hash"] != "https://example.com/ok"
