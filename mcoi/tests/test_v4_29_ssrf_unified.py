"""v4.29.0 — unified SSRF policy + DNS-rebinding defense (audit F9, F10).

Pre-v4.29 ``adapters/http_connector`` had a strong policy (DNS resolution,
cloud metadata IPs, RFC 1918) while ``core/webhook_system`` had a weak
hostname-prefix-only policy (no DNS, no IPv6 link-local, missing Azure /
Alibaba / DigitalOcean metadata). Two SSRF policies, one repo.

v4.29 unifies them via ``core/ssrf_policy``:
- Cloud metadata: GCP, Azure, Alibaba, AWS/DO/Linode/Oracle (the last
  four converge on 169.254.169.254)
- IPv6 link-local + ULA prefixes
- DNS resolution check at registration AND delivery
- ``resolve_and_check`` returns the resolved IP for DNS pinning

For F10 (DNS-rebinding window), ``http_connector`` now uses a custom
``HTTPSConnection`` that connects directly to the pinned IP while
preserving the original hostname for TLS SNI / HTTP Host header.
The defense-in-depth ``_is_private_ip`` re-check at socket level
catches any case where the OS resolver returns a private address
despite ``getaddrinfo`` reporting public.
"""
from __future__ import annotations

from unittest import mock

import pytest

from mcoi_runtime.governance.network.ssrf import (
    is_private_host,
    is_private_ip,
    is_private_url,
    resolve_and_check,
)


# ============================================================
# is_private_ip
# ============================================================


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "127.42.0.1",        # loopback
    "10.0.0.1", "10.255.255.255",     # RFC 1918 /8
    "172.16.0.1", "172.31.255.254",   # RFC 1918 /12
    "192.168.1.1",                    # RFC 1918 /16
    "169.254.169.254",                # AWS / Azure / DO IMDS
    "169.254.1.1",                    # link-local /16
    "0.0.0.0",                        # unspecified
    "224.0.0.1",                      # multicast
    "::1",                            # IPv6 loopback
    "fe80::1",                        # IPv6 link-local
    "fc00::1", "fd00::1",             # IPv6 ULA
    "ff00::1",                        # IPv6 multicast
    "::",                             # IPv6 unspecified
])
def test_is_private_ip_blocks_non_public_addresses(ip):
    assert is_private_ip(ip) is True


@pytest.mark.parametrize("ip", [
    "8.8.8.8",                        # Google DNS
    "1.1.1.1",                        # Cloudflare DNS
    "93.184.216.34",                  # example.com
    "2001:4860:4860::8888",           # Google DNS v6
])
def test_is_private_ip_allows_public_addresses(ip):
    assert is_private_ip(ip) is False


def test_is_private_ip_fail_closed_on_unparseable():
    assert is_private_ip("not-an-ip") is True
    assert is_private_ip("") is True
    assert is_private_ip("999.999.999.999") is True


# ============================================================
# is_private_host — hostname blocklists
# ============================================================


@pytest.mark.parametrize("host", [
    "localhost",
    "127.0.0.1",
    "169.254.169.254",
    "metadata.google.internal",        # GCP IMDS
    "metadata.azure.com",              # Azure IMDS DNS alias
    "metadata.aliyun.com",             # Alibaba ECS
    "metadata",                        # Alibaba shorthand
    "::1",
    "[::1]",
])
def test_is_private_host_blocks_static_hosts(host):
    assert is_private_host(host) is True


@pytest.mark.parametrize("host", [
    "10.1.2.3",
    "172.16.0.1",
    "192.168.0.1",
    "169.254.169.255",
    "fe80::1",
    "fc00::1",
])
def test_is_private_host_blocks_literal_ip_prefixes(host):
    assert is_private_host(host) is True


def test_is_private_host_empty_blocks():
    assert is_private_host("") is True


def test_is_private_host_fail_closed_on_resolve_failure():
    """Unresolvable hostnames are blocked."""
    with mock.patch(
        "mcoi_runtime.governance.network.ssrf.socket.getaddrinfo",
        side_effect=__import__("socket").gaierror("not found"),
    ):
        assert is_private_host("nonexistent-domain-x9z2.invalid") is True


def test_is_private_host_blocks_when_dns_resolves_to_private():
    """DNS-rebinding first-leg defense: even if hostname looks public,
    DNS that resolves to a private IP is blocked."""
    with mock.patch(
        "mcoi_runtime.governance.network.ssrf.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("10.0.0.5", 0))],
    ):
        assert is_private_host("attacker-controlled.example") is True


def test_is_private_host_allows_public_dns():
    """Hostname that resolves to a public IP is allowed."""
    with mock.patch(
        "mcoi_runtime.governance.network.ssrf.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("8.8.8.8", 0))],
    ):
        assert is_private_host("real-public-host.example") is False


def test_is_private_host_blocks_when_any_resolved_ip_is_private():
    """Multi-A hostname: if ANY resolved IP is private, block.
    Defense against split-horizon DNS that returns mixed."""
    with mock.patch(
        "mcoi_runtime.governance.network.ssrf.socket.getaddrinfo",
        return_value=[
            (2, 1, 6, "", ("8.8.8.8", 0)),       # public
            (2, 1, 6, "", ("10.0.0.5", 0)),      # PRIVATE
        ],
    ):
        assert is_private_host("mixed-resolver.example") is True


# ============================================================
# resolve_and_check — DNS pinning support
# ============================================================


def test_resolve_and_check_returns_public_ip_for_safe_url():
    with mock.patch(
        "mcoi_runtime.governance.network.ssrf.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        is_priv, ip = resolve_and_check("https://example.com/path")
    assert is_priv is False
    assert ip == "93.184.216.34"


def test_resolve_and_check_blocks_metadata_url():
    is_priv, ip = resolve_and_check("http://169.254.169.254/latest/meta-data/")
    assert is_priv is True
    assert ip is None


def test_resolve_and_check_blocks_metadata_hostname():
    is_priv, ip = resolve_and_check("http://metadata.google.internal/computeMetadata/v1/")
    assert is_priv is True
    assert ip is None


def test_resolve_and_check_blocks_azure_metadata():
    is_priv, ip = resolve_and_check("http://metadata.azure.com/instance")
    assert is_priv is True
    assert ip is None


def test_resolve_and_check_blocks_alibaba_metadata():
    is_priv, ip = resolve_and_check("http://metadata.aliyun.com/latest/")
    assert is_priv is True
    assert ip is None


def test_resolve_and_check_blocks_unparseable():
    is_priv, ip = resolve_and_check("not-a-url")
    assert is_priv is True
    assert ip is None


def test_resolve_and_check_blocks_when_dns_resolves_private():
    """DNS-rebinding first leg: caller's resolved IP is private. Block."""
    with mock.patch(
        "mcoi_runtime.governance.network.ssrf.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("10.0.0.5", 0))],
    ):
        is_priv, ip = resolve_and_check("https://attacker.example/api")
    assert is_priv is True
    assert ip is None


# ============================================================
# is_private_url — webhook-side wrapper
# ============================================================


def test_is_private_url_blocks_metadata_endpoints():
    """The exact gap that pre-v4.29 webhook_system had: cloud metadata
    URLs registered via subscribe() were silently accepted.
    Post-v4.29, all known IMDS endpoints are blocked."""
    blocked_urls = [
        "http://169.254.169.254/latest/meta-data/",        # AWS / DO / Linode
        "http://metadata.google.internal/v1/instance",      # GCP
        "http://metadata.azure.com/instance",               # Azure DNS alias
        "http://metadata.aliyun.com/latest/",               # Alibaba
        "http://metadata/latest/",                          # Alibaba shorthand
    ]
    for url in blocked_urls:
        assert is_private_url(url) is True, f"failed to block {url}"


def test_is_private_url_blocks_ipv6_link_local():
    """Pre-v4.29 webhook_system didn't check IPv6 link-local. Verify
    the unified policy now does."""
    blocked = [
        "http://[fe80::1]/",
        "http://[fe80::abcd]/",
        "http://[::1]/",
    ]
    for url in blocked:
        assert is_private_url(url) is True, f"failed to block {url}"


def test_is_private_url_blocks_ipv6_unique_local():
    """fc00::/7 is RFC 4193 ULA. Mostly used for internal-only
    networking. Block."""
    blocked = [
        "http://[fc00::1]/",
        "http://[fd00::abcd]/",
    ]
    for url in blocked:
        assert is_private_url(url) is True


# ============================================================
# Webhook integration: registration + delivery checks
# ============================================================


class TestWebhookSSRFAtRegistration:
    """v4.29 strengthens the SSRF check at subscribe() time."""

    def test_metadata_url_rejected_at_subscribe(self):
        from mcoi_runtime.governance.network.webhook import (
            WebhookManager,
            WebhookSubscription,
        )
        mgr = WebhookManager(clock=lambda: "2026-01-01T00:00:00Z")
        with pytest.raises(ValueError, match="private/internal"):
            mgr.subscribe(WebhookSubscription(
                subscription_id="evil",
                tenant_id="t1",
                url="http://169.254.169.254/latest/meta-data/iam/",
                events=("event.x",),
            ))

    def test_ipv6_link_local_rejected_at_subscribe(self):
        from mcoi_runtime.governance.network.webhook import (
            WebhookManager,
            WebhookSubscription,
        )
        mgr = WebhookManager(clock=lambda: "2026-01-01T00:00:00Z")
        with pytest.raises(ValueError, match="private/internal"):
            mgr.subscribe(WebhookSubscription(
                subscription_id="evil",
                tenant_id="t1",
                url="http://[fe80::1]/",
                events=("event.x",),
            ))


class TestWebhookSSRFAtDelivery:
    """v4.29 ALSO re-checks at delivery time (defense against
    DNS-rebinding by an attacker who controls the subscribed domain)."""

    def test_dns_rebinding_blocked_at_delivery(self):
        """A subscription registered with a hostname that DNS-resolves
        to public at registration time, then flips to private at delivery
        time, is silently skipped on emit. The subscription remains
        registered (no delete-on-block) so operators can investigate."""
        from mcoi_runtime.governance.network.webhook import (
            WebhookManager,
            WebhookSubscription,
        )
        mgr = WebhookManager(clock=lambda: "2026-01-01T00:00:00Z")

        # Registration: DNS returns public
        with mock.patch(
            "mcoi_runtime.governance.network.ssrf.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            mgr.subscribe(WebhookSubscription(
                subscription_id="rebinding-target",
                tenant_id="t1",
                url="https://attacker.example/webhook",
                events=("evt",),
            ))

        # Delivery: same hostname, DNS now returns private (rebinding)
        with mock.patch(
            "mcoi_runtime.governance.network.ssrf.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("10.0.0.5", 0))],
        ):
            deliveries = mgr.emit("evt", {"data": "x"}, tenant_id="t1")

        # No delivery queued — caught at delivery time
        assert deliveries == []
        # Subscription still registered (operator-visible audit signal)
        assert mgr.subscription_count == 1


# ============================================================
# http_connector DNS-pinning integration
# ============================================================


class TestHttpConnectorDNSPin:
    """v4.29 (audit F10): http_connector connects to the resolved IP
    rather than letting urllib resolve again. This closes the
    rebinding window between SSRF check and TCP connect."""

    def test_resolve_and_check_called_during_invoke(self):
        """Verify the connector goes through the new pinning path,
        not the legacy single-DNS-lookup ``_is_private_host`` path."""
        from mcoi_runtime.adapters.http_connector import HttpConnector
        from mcoi_runtime.contracts.integration import ConnectorDescriptor
        from mcoi_runtime.contracts._shared_enums import (
            EffectClass, TrustClass,
        )

        connector = HttpConnector(clock=lambda: "2026-01-01T00:00:00Z")
        descriptor = ConnectorDescriptor(
            connector_id="conn-test", name="test", provider="test-prov",
            effect_class=EffectClass.EXTERNAL_READ,
            trust_class=TrustClass.BOUNDED_EXTERNAL,
            credential_scope_id="scope-x", enabled=True,
        )

        with mock.patch(
            "mcoi_runtime.adapters.http_connector._resolve_and_check",
            return_value=(True, None),  # blocked
        ) as mock_check:
            result = connector.invoke(
                descriptor, {"url": "http://attacker.example/"}
            )
        # _resolve_and_check was called (the pinning path is exercised)
        assert mock_check.called
        # Result is failure with the expected error code
        assert result.error_code == "blocked_private_address"


def test_pinned_handlers_install_correctly():
    """The pinned-opener factory builds an opener with the redirect
    blocker AND the pinned handlers. Smoke test the construction
    without actually opening a connection."""
    from mcoi_runtime.adapters.http_connector import _build_pinned_opener
    opener = _build_pinned_opener("93.184.216.34")
    # Opener has handlers registered (smoke check; we don't open a
    # real connection because that would require a real network)
    assert opener is not None
    handler_classes = {type(h).__name__ for h in opener.handlers}
    # Both http and https pinned handlers present
    assert "_PinnedHTTPHandler" in handler_classes
    assert "_PinnedHTTPSHandler" in handler_classes
