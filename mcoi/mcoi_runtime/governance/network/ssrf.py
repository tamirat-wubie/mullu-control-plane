"""Shared SSRF policy for outbound HTTP / webhook destinations.

v4.29.0+ (audit F9, F10). Pre-v4.29 the platform had two SSRF
implementations:

- ``adapters/http_connector.py`` had a strong policy: hostname blocklist
  + RFC 1918 prefixes + DNS resolution + IPv6 multi-form check + redirect
  block.
- ``core/webhook_system.py`` had a weak policy: hostname blocklist of
  ``{"localhost", "metadata.google.internal"}`` plus prefix check. NO DNS
  resolution. NO IPv6 link-local. NO Azure / Alibaba / DO metadata.

The audit (Part 2 F9) flagged this as "two SSRF policies, one repo." This
module is the unified policy. Both http_connector and webhook_system
import from here.

For the DNS-rebinding window (audit F10), ``resolve_and_check`` returns
the resolved IP alongside the verdict. Callers that can use it (the
``ConnectionManager``-style HTTPS pinning) connect to the pinned IP
directly and pass the original hostname for TLS SNI / Host header,
closing the gap between the SSRF check and the actual TCP connect.

Security posture:
- Fail closed on resolve failure (unresolvable hosts blocked)
- Fail closed on parse failure (bogus URLs blocked)
- Block all categories of non-public IPs: private, loopback, link-local,
  reserved, multicast, unspecified
- Block known cloud metadata hostnames AND IPs (AWS/Azure/GCP/Alibaba/DO
  all converge on 169.254.169.254 except GCP which uses
  metadata.google.internal)
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


# Cloud metadata hostnames. Most providers use 169.254.169.254 (also blocked
# below), but a few have additional DNS aliases worth blocking explicitly.
_CLOUD_METADATA_HOSTS = frozenset({
    "metadata.google.internal",     # GCP IMDS
    "metadata.azure.com",           # Azure IMDS DNS alias
    "metadata.aliyun.com",          # Alibaba ECS
    "metadata",                     # Alibaba shorthand alias
    # AWS, DigitalOcean, Oracle Cloud, Linode all use 169.254.169.254
    # directly with no DNS hostname — the IP block below catches them
    # regardless of DNS.
})

# Always-blocked hostnames (loopback aliases + metadata IP literal).
_BLOCKED_LITERAL_HOSTS = frozenset({
    "localhost",
    "ip6-localhost", "ip6-loopback",
    "127.0.0.1", "0.0.0.0",
    "::1", "[::1]",
    "169.254.169.254",   # AWS / DigitalOcean / Azure / Linode / Oracle IMDS
}) | _CLOUD_METADATA_HOSTS

# Hostname-prefix block-list for raw IPv4 literals. RFC 1918 + link-local
# + loopback. Catches the cases where the URL's hostname IS the IP
# (no DNS lookup needed).
_BLOCKED_PREFIXES: tuple[str, ...] = (
    "10.",
    "127.",
    "169.254.",        # link-local (incl. AWS/Azure/DO metadata)
    "192.168.",
    "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.",
    "172.24.", "172.25.", "172.26.", "172.27.",
    "172.28.", "172.29.", "172.30.", "172.31.",
)

# IPv6 prefixes. ``ipaddress.is_private`` covers fc00::/7 (ULA) and
# ``is_link_local`` covers fe80::/10, but a literal-prefix check is a
# fast path for hostname-supplied IPv6 IPs.
_BLOCKED_IPV6_PREFIXES: tuple[str, ...] = (
    "fe80",            # link-local (incl. some metadata routers)
    "fc",              # unique-local (fc00::/7)
    "fd",              # unique-local (fc00::/7)
    "::ffff:",         # IPv4-mapped IPv6 — defer to ipaddress
)


def is_private_ip(ip_str: str) -> bool:
    """Return True if the given IP string is non-public.

    Covers: private (RFC 1918, RFC 4193), loopback, link-local, reserved,
    multicast, unspecified. Treats unparseable strings as private
    (fail-closed).
    """
    try:
        addr = ipaddress.ip_address(ip_str.strip("[]"))
    except ValueError:
        return True  # fail-closed
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def _matches_blocked_prefix(host_lower: str) -> bool:
    """True if the hostname (already lowercased + stripped) matches a
    blocked literal-IP prefix. IPv4 + IPv6 prefixes both checked."""
    return (
        any(host_lower.startswith(p) for p in _BLOCKED_PREFIXES)
        or any(host_lower.startswith(p) for p in _BLOCKED_IPV6_PREFIXES)
    )


def _normalize_host(host: str) -> str:
    """Lowercase + strip IPv6 brackets."""
    return host.lower().strip("[]")


def is_private_host(host: str) -> bool:
    """Return True if the host points to a non-public address.

    Steps:
    1. Empty hostname → blocked (fail-closed)
    2. Hostname literal in the static blocklist (loopback, IMDS, cloud
       metadata DNS) → blocked
    3. Hostname matches a blocked literal-IP prefix → blocked
    4. DNS-resolve the hostname; if any resolved IP is non-public →
       blocked. If resolve fails → blocked (fail-closed).

    Defends against:
    - Direct private-IP URLs
    - Cloud metadata hostnames
    - Hostnames that happen to resolve to private space (DNS-rebinding
      first leg; the second leg is closed by ``resolve_and_check``)
    """
    if not host:
        return True
    lower = _normalize_host(host)
    if lower in _BLOCKED_LITERAL_HOSTS:
        return True
    if _matches_blocked_prefix(lower):
        return True
    try:
        addr_infos = socket.getaddrinfo(lower, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, OSError):
        return True
    if not addr_infos:
        return True
    for _family, _type, _proto, _canonname, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        if is_private_ip(ip_str):
            return True
    return False


def resolve_and_check(url: str) -> tuple[bool, str | None]:
    """Resolve a URL's hostname and return ``(is_private, first_public_ip)``.

    For DNS-rebinding defense: callers that can pin the IP for the
    actual TCP connect (e.g., a custom ``HTTPSConnection``) use the
    returned IP directly, eliminating the gap between the SSRF check
    and the connection's own DNS lookup.

    On any check failure (parse, resolve, private), returns
    ``(True, None)``. Caller treats ``True`` as "block."

    On success, returns ``(False, ip_str)`` where ``ip_str`` is the
    first IP from ``getaddrinfo``. The caller may use this IP to
    connect directly with the original hostname preserved for TLS SNI
    and HTTP Host header.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return True, None
    host = parsed.hostname or ""
    if not host:
        return True, None
    lower = _normalize_host(host)
    if lower in _BLOCKED_LITERAL_HOSTS:
        return True, None
    if _matches_blocked_prefix(lower):
        return True, None
    try:
        addr_infos = socket.getaddrinfo(lower, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, OSError):
        return True, None
    if not addr_infos:
        return True, None
    first_public_ip: str | None = None
    for _family, _type, _proto, _canonname, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        if is_private_ip(ip_str):
            return True, None
        if first_public_ip is None:
            first_public_ip = ip_str
    return False, first_public_ip


def is_private_url(url: str) -> bool:
    """Convenience wrapper: parse a URL and apply ``is_private_host``.

    Use this from webhook subscribe + delivery paths where the IP-pin
    isn't needed (the http library handles its own resolution and the
    second-DNS-lookup window is acceptable for outbound webhooks).
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return True
    return is_private_host(parsed.hostname or "")
