"""Purpose: verify SSRF hardening in the governed HTTP connector.
Governance scope: HTTP connector security tests only.
Dependencies: pytest, unittest.mock, http_connector module.
Invariants:
  - DNS rebinding to private IPs is blocked.
  - Redirect following is blocked.
  - HttpProviderPolicy is enforced when provided.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import urllib.error

import pytest

from mcoi_runtime.adapters.http_connector import (
    HttpConnector,
    HttpConnectorConfig,
    _is_private_host,
    _is_private_ip,
    _NoRedirectHandler,
)
from mcoi_runtime.contracts.integration import (
    ConnectorDescriptor,
    ConnectorStatus,
    EffectClass,
    TrustClass,
)
from mcoi_runtime.contracts.provider_policy import HttpProviderPolicy


def _make_connector_descriptor() -> ConnectorDescriptor:
    return ConnectorDescriptor(
        connector_id="test-connector",
        name="Test",
        provider="test-provider",
        effect_class=EffectClass.EXTERNAL_READ,
        trust_class=TrustClass.BOUNDED_EXTERNAL,
        credential_scope_id="scope-1",
        enabled=True,
    )


CLOCK = lambda: "2026-03-19T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Issue A-1: DNS rebinding — hostname resolving to private IP
# ---------------------------------------------------------------------------

class TestDnsRebindingProtection:
    """Verify that hostnames resolving to private IPs are blocked."""

    @patch("mcoi_runtime.adapters.http_connector.socket.getaddrinfo")
    def test_hostname_resolving_to_127_0_0_1_is_blocked(self, mock_getaddrinfo):
        """A hostname like evil.com that resolves to 127.0.0.1 must be blocked."""
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("127.0.0.1", 0)),
        ]
        assert _is_private_host("evil.example.com") is True

    @patch("mcoi_runtime.adapters.http_connector.socket.getaddrinfo")
    def test_hostname_resolving_to_10_x_is_blocked(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("10.0.0.1", 0)),
        ]
        assert _is_private_host("internal.example.com") is True

    @patch("mcoi_runtime.adapters.http_connector.socket.getaddrinfo")
    def test_hostname_resolving_to_192_168_x_is_blocked(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("192.168.1.1", 0)),
        ]
        assert _is_private_host("home.example.com") is True

    @patch("mcoi_runtime.adapters.http_connector.socket.getaddrinfo")
    def test_hostname_resolving_to_ipv6_loopback_is_blocked(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (10, 1, 6, "", ("::1", 0, 0, 0)),
        ]
        assert _is_private_host("ipv6loop.example.com") is True

    @patch("mcoi_runtime.adapters.http_connector.socket.getaddrinfo")
    def test_hostname_resolving_to_public_ip_is_allowed(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("93.184.216.34", 0)),
        ]
        assert _is_private_host("example.com") is False

    @patch("mcoi_runtime.adapters.http_connector.socket.getaddrinfo")
    def test_dns_failure_blocks_host(self, mock_getaddrinfo):
        """Unresolvable hostnames are blocked (fail closed)."""
        import socket as _socket
        mock_getaddrinfo.side_effect = _socket.gaierror("Name resolution failed")
        assert _is_private_host("nonexistent.example.com") is True

    @patch("mcoi_runtime.adapters.http_connector.socket.getaddrinfo")
    def test_mixed_public_and_private_blocks(self, mock_getaddrinfo):
        """If any resolved address is private, the host is blocked."""
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("93.184.216.34", 0)),
            (2, 1, 6, "", ("127.0.0.1", 0)),
        ]
        assert _is_private_host("dual.example.com") is True

    def test_is_private_ip_loopback(self):
        assert _is_private_ip("127.0.0.1") is True

    def test_is_private_ip_private_range(self):
        assert _is_private_ip("10.0.0.1") is True
        assert _is_private_ip("172.16.0.1") is True
        assert _is_private_ip("192.168.0.1") is True

    def test_is_private_ip_public(self):
        assert _is_private_ip("8.8.8.8") is False

    def test_is_private_ip_link_local(self):
        assert _is_private_ip("169.254.169.254") is True

    def test_is_private_ip_ipv6_loopback(self):
        assert _is_private_ip("::1") is True

    @patch("mcoi_runtime.adapters.http_connector.socket.getaddrinfo")
    def test_connector_blocks_dns_rebinding(self, mock_getaddrinfo):
        """Full integration: HttpConnector.invoke blocks DNS-rebinding hostname."""
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("127.0.0.1", 0)),
        ]
        connector = HttpConnector(clock=CLOCK)
        desc = _make_connector_descriptor()
        result = connector.invoke(desc, {"url": "http://evil.example.com/secret"})
        assert result.status is ConnectorStatus.FAILED
        assert result.error_code == "blocked_private_address"


# ---------------------------------------------------------------------------
# Issue A-2: Redirect following
# ---------------------------------------------------------------------------

class TestRedirectBlocking:
    """Verify that HTTP redirects are blocked."""

    @patch("mcoi_runtime.adapters.http_connector._is_private_host", return_value=False)
    def test_redirect_to_private_url_is_blocked(self, _mock_priv):
        """A redirect response must not be followed; it should produce a redirect_blocked error."""
        connector = HttpConnector(clock=CLOCK)
        desc = _make_connector_descriptor()

        # The _NoRedirectHandler raises HTTPError with redirect_blocked message
        # We test via the opener which uses _NoRedirectHandler
        handler = _NoRedirectHandler()
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            handler.redirect_request(
                MagicMock(), MagicMock(), 302, "Found", {},
                "http://127.0.0.1/admin",
            )
        assert "redirect_blocked" in str(exc_info.value.msg)

    def test_connector_surfaces_redirect_blocked_error(self):
        """When opener raises redirect_blocked HTTPError, connector returns it.

        v4.29.0 (audit F10): the connector now uses ``_resolve_and_check``
        plus a per-request pinned opener. Mock both layers — SSRF
        resolution returns ``(False, public_ip)`` so the request flow
        proceeds, and the pinned opener's ``open`` raises the simulated
        redirect-blocked error.
        """
        fake_opener = MagicMock()
        fake_opener.open.side_effect = urllib.error.HTTPError(
            "http://evil.com/internal", 302,
            "redirect_blocked:302:http://127.0.0.1/admin",
            {}, None,
        )
        with (
            patch(
                "mcoi_runtime.adapters.http_connector._resolve_and_check",
                return_value=(False, "93.184.216.34"),
            ),
            patch(
                "mcoi_runtime.adapters.http_connector._build_pinned_opener",
                return_value=fake_opener,
            ),
        ):
            connector = HttpConnector(clock=CLOCK)
            desc = _make_connector_descriptor()
            result = connector.invoke(desc, {"url": "https://legit.example.com/page"})
        assert result.status is ConnectorStatus.FAILED
        assert "redirect_blocked" in result.error_code


# ---------------------------------------------------------------------------
# Issue D-2: HttpProviderPolicy enforcement
# ---------------------------------------------------------------------------

class TestHttpProviderPolicyEnforcement:
    """Verify that HttpProviderPolicy is enforced when provided."""

    def test_policy_blocks_non_https(self):
        """require_https=True should block HTTP URLs."""
        policy = HttpProviderPolicy(policy_id="pol-1", require_https=True)
        connector = HttpConnector(clock=CLOCK, policy=policy)
        desc = _make_connector_descriptor()
        result = connector.invoke(desc, {"url": "http://example.com/data"})
        assert result.status is ConnectorStatus.FAILED
        assert result.error_code == "policy_requires_https"

    def test_policy_blocks_disallowed_method(self):
        """Policy allowed_methods should override config allowed_methods."""
        policy = HttpProviderPolicy(
            policy_id="pol-2",
            allowed_methods=("GET",),
            require_https=False,
        )
        config = HttpConnectorConfig(allowed_methods=("GET", "POST"))
        connector = HttpConnector(clock=CLOCK, config=config, policy=policy)
        desc = _make_connector_descriptor()
        result = connector.invoke(desc, {"url": "https://example.com/api", "method": "POST"})
        assert result.status is ConnectorStatus.FAILED
        assert "method_not_allowed:POST" in result.error_code

    @patch("mcoi_runtime.adapters.http_connector._is_private_host", return_value=False)
    @patch("mcoi_runtime.adapters.http_connector.urllib.request.OpenerDirector.open")
    def test_policy_enforces_max_response_bytes(self, mock_open, _mock_priv):
        """Policy max_response_bytes should limit response size."""
        # Create a mock response that returns a body larger than policy limit
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.status = 200
        # Policy allows 100 bytes; return 200 bytes
        mock_response.read.return_value = b"x" * 200
        mock_open.return_value = mock_response

        policy = HttpProviderPolicy(
            policy_id="pol-3",
            max_response_bytes=100,
            require_https=False,
        )
        config = HttpConnectorConfig(max_response_bytes=10_000_000)
        connector = HttpConnector(clock=CLOCK, config=config, policy=policy)
        desc = _make_connector_descriptor()
        result = connector.invoke(desc, {"url": "https://example.com/big"})
        assert result.status is ConnectorStatus.FAILED
        assert "response_too_large" in result.error_code

    def test_no_policy_uses_config_behavior(self):
        """Without a policy, config behavior is preserved (backward compatible)."""
        config = HttpConnectorConfig(allowed_methods=("GET", "POST"))
        connector = HttpConnector(clock=CLOCK, config=config)
        desc = _make_connector_descriptor()
        # POST is allowed by config when no policy
        # (will fail at URL normalization or SSRF, but not at method check)
        result = connector.invoke(desc, {"url": "", "method": "POST"})
        # Should fail for missing_url, NOT method_not_allowed
        assert result.error_code == "missing_url"
