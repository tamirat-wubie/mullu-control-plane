"""Purpose: governed HTTP connector — read-only, allowlisted, bounded, hardened.
Governance scope: external integration adapter only.
Dependencies: provider registry, integration contracts.
Invariants:
  - Method allowlist (GET only by default).
  - URL normalization before scope check.
  - DNS resolution checked against private IP ranges (anti-rebinding).
  - Redirect following disabled (anti-SSRF via redirect).
  - Response size limits.
  - Content-type checks.
  - Status-code mapping into typed results.
  - Response is digested, not stored raw.
  - Optional HttpProviderPolicy enforcement.
"""

from __future__ import annotations

from typing import Callable

import hashlib
import ipaddress
import socket
import urllib.request
import urllib.error
from dataclasses import dataclass
from urllib.parse import urlparse

from mcoi_runtime.contracts.integration import ConnectorDescriptor, ConnectorResult, ConnectorStatus
from mcoi_runtime.contracts.provider_policy import HttpProviderPolicy
from mcoi_runtime.core.invariants import stable_identifier


@dataclass(frozen=True, slots=True)
class HttpConnectorConfig:
    """Configuration for the governed HTTP connector."""

    timeout_seconds: float = 30.0
    max_response_bytes: int = 10 * 1024 * 1024  # 10MB
    allowed_methods: tuple[str, ...] = ("GET",)
    allowed_content_types: tuple[str, ...] = ()  # empty = no restriction
    allowed_headers: tuple[str, ...] = ()  # headers to forward from request

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")


_BLOCKED_HOSTS = frozenset({
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "[::1]", "169.254.169.254",  # AWS metadata
})

_BLOCKED_PREFIXES = (
    "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
    "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
    "172.30.", "172.31.", "192.168.",
)


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address string is private, loopback, link-local, or reserved."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # Fail closed on unparseable addresses
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def _is_private_host(host: str) -> bool:
    """Check if a host resolves to a private/loopback/metadata address.

    Performs DNS resolution to defend against DNS rebinding attacks.
    """
    if not host:
        return True
    lower = host.lower().strip("[]")
    if lower in _BLOCKED_HOSTS:
        return True
    if any(lower.startswith(p) for p in _BLOCKED_PREFIXES):
        return True

    # DNS resolution check: resolve hostname and verify all IPs are public
    try:
        addr_infos = socket.getaddrinfo(lower, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, OSError):
        return True  # Fail closed: unresolvable hosts are blocked
    if not addr_infos:
        return True
    for family, _type, _proto, _canonname, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        if _is_private_ip(ip_str):
            return True
    return False


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """HTTP handler that blocks all redirects to prevent SSRF via redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            newurl, code, f"redirect_blocked:{code}:{newurl}", headers, fp
        )


def _normalize_url(url: str) -> str:
    """Normalize URL for consistent scope checking."""
    parsed = urlparse(url)
    # Reconstruct with lowercase scheme and host
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower() if parsed.hostname else ""
    port = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{scheme}://{host}{port}{path}{query}"


def _map_status_code(code: int) -> ConnectorStatus:
    """Map HTTP status code to connector status."""
    if 200 <= code < 300:
        return ConnectorStatus.SUCCEEDED
    return ConnectorStatus.FAILED


class HttpConnector:
    """Governed HTTP connector with response size limits, content-type checks, and status mapping.

    Optionally accepts an HttpProviderPolicy for stricter enforcement of
    allowed_methods, max_response_bytes, and require_https.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        config: HttpConnectorConfig | None = None,
        policy: HttpProviderPolicy | None = None,
    ) -> None:
        self._clock = clock
        self._config = config or HttpConnectorConfig()
        self._policy = policy
        # Build an opener that blocks redirects
        self._opener = urllib.request.build_opener(_NoRedirectHandler)

    def invoke(self, connector: ConnectorDescriptor, request: dict) -> ConnectorResult:
        """Execute a governed HTTP request.

        request keys:
          - url: str (required)
          - method: str (optional, default GET, must be in allowed_methods)
          - headers: dict[str, str] (optional, filtered by allowed_headers)
        """
        started_at = self._clock()
        url = request.get("url", "")
        method = request.get("method", "GET").upper()
        request_headers = request.get("headers", {})

        result_id = stable_identifier("http-result", {
            "connector_id": connector.connector_id,
            "url": url,
            "started_at": started_at,
        })

        if not url:
            return self._failure(result_id, connector.connector_id, started_at, "missing_url")

        # Policy: require_https check
        if self._policy and self._policy.require_https:
            if not url.lower().startswith("https://"):
                return self._failure(result_id, connector.connector_id, started_at,
                                     "policy_requires_https")

        # Policy: method allowlist (policy takes precedence over config)
        effective_methods = (
            self._policy.allowed_methods if self._policy else self._config.allowed_methods
        )
        if method not in effective_methods:
            return self._failure(result_id, connector.connector_id, started_at,
                                 f"method_not_allowed:{method}")

        # URL normalization
        try:
            normalized_url = _normalize_url(url)
        except (ValueError, TypeError):
            return self._failure(result_id, connector.connector_id, started_at, "malformed_url")

        # SSRF protection: block private/loopback/metadata addresses (includes DNS resolution)
        parsed = urlparse(normalized_url)
        if _is_private_host(parsed.hostname or ""):
            return self._failure(result_id, connector.connector_id, started_at,
                                 "blocked_private_address")

        # Effective max response bytes (policy overrides config if stricter)
        max_bytes = self._config.max_response_bytes
        if self._policy:
            max_bytes = min(max_bytes, self._policy.max_response_bytes)

        # Build request with filtered headers
        try:
            req = urllib.request.Request(normalized_url, method=method)
            if self._config.allowed_headers and isinstance(request_headers, dict):
                for key, value in request_headers.items():
                    if key.lower() in (h.lower() for h in self._config.allowed_headers):
                        req.add_header(key, value)

            with self._opener.open(req, timeout=self._config.timeout_seconds) as response:
                # Content-type check
                content_type = response.headers.get("Content-Type", "")
                if self._config.allowed_content_types:
                    ct_base = content_type.split(";")[0].strip().lower()
                    if ct_base not in (t.lower() for t in self._config.allowed_content_types):
                        return self._failure(result_id, connector.connector_id, started_at,
                                             f"content_type_not_allowed:{ct_base}")

                # Size-bounded read
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    return self._failure(result_id, connector.connector_id, started_at,
                                         f"response_too_large:{len(body)}")

                digest = hashlib.sha256(body).hexdigest()
                status = _map_status_code(response.status)
                finished_at = self._clock()

                return ConnectorResult(
                    result_id=result_id,
                    connector_id=connector.connector_id,
                    status=status,
                    response_digest=digest,
                    started_at=started_at,
                    finished_at=finished_at,
                    error_code=None if status is ConnectorStatus.SUCCEEDED else f"http_{response.status}",
                    metadata={
                        "url": normalized_url,
                        "method": method,
                        "status_code": response.status,
                        "content_type": content_type,
                        "content_length": len(body),
                    },
                )
        except urllib.error.HTTPError as exc:
            error_msg = f"http_{exc.code}"
            # Surface redirect-blocked errors distinctly
            if exc.msg and exc.msg.startswith("redirect_blocked:"):
                error_msg = exc.msg
            return self._failure(result_id, connector.connector_id, started_at, error_msg)
        except urllib.error.URLError as exc:
            return self._failure(result_id, connector.connector_id, started_at,
                                 f"url_error:{exc.reason}")
        except TimeoutError:
            return ConnectorResult(
                result_id=result_id,
                connector_id=connector.connector_id,
                status=ConnectorStatus.TIMEOUT,
                response_digest="none",
                started_at=started_at,
                finished_at=self._clock(),
                error_code="timeout",
            )
        except Exception as exc:
            return self._failure(result_id, connector.connector_id, started_at,
                                 f"unexpected:{type(exc).__name__}")

    def _failure(self, result_id: str, connector_id: str, started_at: str, error_code: str) -> ConnectorResult:
        return ConnectorResult(
            result_id=result_id,
            connector_id=connector_id,
            status=ConnectorStatus.FAILED,
            response_digest="none",
            started_at=started_at,
            finished_at=self._clock(),
            error_code=error_code,
        )
