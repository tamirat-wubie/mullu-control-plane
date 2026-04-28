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

from mcoi_runtime.contracts.connector_effects import ConnectorInvocationReceipt
from mcoi_runtime.contracts._shared_enums import EffectClass, TrustClass
from mcoi_runtime.contracts.integration import ConnectorDescriptor, ConnectorResult, ConnectorStatus
from mcoi_runtime.contracts.provider_policy import HttpProviderPolicy
from mcoi_runtime.core.invariants import stable_identifier


@dataclass(frozen=True, slots=True)
class HttpConnectorConfig:
    """Configuration for the governed HTTP connector."""

    timeout_seconds: float = 30.0
    read_timeout_seconds: float = 60.0  # Max time for response body read
    max_response_bytes: int = 10 * 1024 * 1024  # 10MB
    allowed_methods: tuple[str, ...] = ("GET",)
    allowed_content_types: tuple[str, ...] = ()  # empty = no restriction
    allowed_headers: tuple[str, ...] = ()  # headers to forward from request

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.read_timeout_seconds <= 0:
            raise ValueError("read_timeout_seconds must be positive")
        if self.max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")


# v4.29.0 (audit F9): SSRF policy unified into core/ssrf_policy. The
# shared module adds Azure / Alibaba / DigitalOcean metadata hostnames,
# IPv6 link-local + ULA prefixes, and the same DNS-resolution
# fail-closed posture this module already had.
from mcoi_runtime.governance.network.ssrf import (
    is_private_host as _is_private_host,
    is_private_ip as _is_private_ip,
    resolve_and_check as _resolve_and_check,
)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """HTTP handler that blocks all redirects to prevent SSRF via redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            newurl, code, f"redirect_blocked:{code}:{newurl}", headers, fp
        )


# v4.29.0 (audit F10): DNS-rebinding defense. Pre-v4.29 the SSRF check
# resolved the hostname once; urllib then resolved it AGAIN on the actual
# connect — two independent lookups separated by Python work. An attacker-
# controlled DNS server could return a public IP for the first lookup and
# a private IP (or 169.254.169.254) for the second. We close the gap with
# a custom HTTPSConnection that connects to a pre-resolved IP, preserves
# the original hostname for TLS SNI / Host header, and re-validates the
# IP at the socket level as defense-in-depth.


class _PinnedHTTPSConnection:
    """Factory for HTTPSConnection-shaped objects that connect to a
    specific pre-resolved IP rather than re-resolving the hostname.

    Returns a one-shot subclass via ``make(host, **kwargs)``. Used by
    ``_PinnedHTTPSHandler`` to wire a per-request connection.

    The TLS handshake uses ``server_hostname=host`` so SNI matches the
    original hostname (cert validation works), but the underlying TCP
    connect goes to the pinned IP — closing the rebinding window.
    """

    @staticmethod
    def make(pinned_ip: str):
        import http.client

        class _Connection(http.client.HTTPSConnection):
            def connect(self) -> None:  # type: ignore[override]
                sock = socket.create_connection(
                    (pinned_ip, self.port),
                    self.timeout,
                    self.source_address,
                )
                # Defense-in-depth: even though we resolved this IP
                # ourselves, re-validate. Cheap, immune to caller bugs.
                peer_ip = sock.getpeername()[0]
                if _is_private_ip(peer_ip):
                    sock.close()
                    raise OSError(
                        f"blocked_private_address_at_connect:{peer_ip}"
                    )
                if self._tunnel_host:
                    self.sock = sock
                    self._tunnel()
                else:
                    self.sock = self._context.wrap_socket(
                        sock, server_hostname=self.host
                    )

        return _Connection


class _PinnedHTTPConnection:
    """HTTP (non-TLS) variant. Connects to a pre-resolved IP, sets the
    Host header from the original hostname so vhost routing works."""

    @staticmethod
    def make(pinned_ip: str):
        import http.client

        class _Connection(http.client.HTTPConnection):
            def connect(self) -> None:  # type: ignore[override]
                sock = socket.create_connection(
                    (pinned_ip, self.port),
                    self.timeout,
                    self.source_address,
                )
                peer_ip = sock.getpeername()[0]
                if _is_private_ip(peer_ip):
                    sock.close()
                    raise OSError(
                        f"blocked_private_address_at_connect:{peer_ip}"
                    )
                self.sock = sock

        return _Connection


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    """urllib HTTPSHandler that uses a pre-resolved IP for connect."""

    def __init__(self, pinned_ip: str) -> None:
        super().__init__()
        self._connection_cls = _PinnedHTTPSConnection.make(pinned_ip)

    def https_open(self, req):  # type: ignore[override]
        return self.do_open(self._connection_cls, req)


class _PinnedHTTPHandler(urllib.request.HTTPHandler):
    """urllib HTTPHandler that uses a pre-resolved IP for connect."""

    def __init__(self, pinned_ip: str) -> None:
        super().__init__()
        self._connection_cls = _PinnedHTTPConnection.make(pinned_ip)

    def http_open(self, req):  # type: ignore[override]
        return self.do_open(self._connection_cls, req)


def _build_pinned_opener(pinned_ip: str) -> urllib.request.OpenerDirector:
    """Build a one-shot opener that uses the pinned IP for both
    HTTP and HTTPS, with redirects blocked."""
    return urllib.request.build_opener(
        _PinnedHTTPHandler(pinned_ip),
        _PinnedHTTPSHandler(pinned_ip),
        _NoRedirectHandler,
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


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _build_connector_receipt(
    *,
    result_id: str,
    connector: ConnectorDescriptor,
    method: str,
    url: str,
    request: dict,
    response_digest: str,
    status: ConnectorStatus,
    started_at: str,
    finished_at: str,
    status_code: int | None = None,
    error_code: str | None = None,
) -> ConnectorInvocationReceipt:
    request_hash = _sha256_text(str({
        "url": url,
        "method": method,
        "headers": sorted((request.get("headers") or {}).keys()) if isinstance(request.get("headers"), dict) else (),
    }))
    receipt_id = stable_identifier(
        "connector-invocation-receipt",
        {
            "result_id": result_id,
            "connector_id": connector.connector_id,
            "method": method,
            "url_hash": _sha256_text(url),
            "request_hash": request_hash,
            "response_digest": response_digest,
            "status": status.value,
            "status_code": status_code,
            "error_code": error_code,
        },
    )
    return ConnectorInvocationReceipt(
        receipt_id=receipt_id,
        result_id=result_id,
        connector_id=connector.connector_id,
        provider=connector.provider,
        method=method,
        url_hash=_sha256_text(url),
        request_hash=request_hash,
        response_digest=response_digest,
        status=status,
        evidence_ref=f"connector-invocation:{connector.connector_id}:{receipt_id}",
        started_at=started_at,
        finished_at=finished_at,
        status_code=status_code,
        error_code=error_code,
        metadata={"effect_class": connector.effect_class.value, "trust_class": connector.trust_class.value},
    )


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
            return self._failure(result_id, connector, method, url, request, started_at, "missing_url")

        # Policy: require_https check
        if self._policy and self._policy.require_https:
            if not url.lower().startswith("https://"):
                return self._failure(result_id, connector, method, url, request, started_at,
                                     "policy_requires_https")

        # Policy: method allowlist (policy takes precedence over config)
        effective_methods = (
            self._policy.allowed_methods if self._policy else self._config.allowed_methods
        )
        if method not in effective_methods:
            return self._failure(result_id, connector, method, url, request, started_at,
                                 f"method_not_allowed:{method}")

        # URL normalization
        try:
            normalized_url = _normalize_url(url)
        except (ValueError, TypeError):
            return self._failure(result_id, connector, method, url, request, started_at, "malformed_url")

        # SSRF protection: block private/loopback/metadata addresses
        # (includes DNS resolution + cloud metadata blocklist).
        # v4.29.0 (audit F10): use ``resolve_and_check`` so we pin the
        # resolved IP for the upcoming connect — closes the DNS-rebinding
        # window between the SSRF check and urllib's own DNS lookup.
        is_private, pinned_ip = _resolve_and_check(normalized_url)
        if is_private or pinned_ip is None:
            return self._failure(result_id, connector, method, normalized_url, request, started_at,
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

            # v4.29.0 (audit F10): per-request opener pinned to the
            # resolved IP. Connects to ``pinned_ip`` directly while
            # preserving the original hostname for TLS SNI / Host header.
            # The default ``self._opener`` (built once at __init__) is
            # kept around for tests / explicit non-pinned use only.
            opener = _build_pinned_opener(pinned_ip)
            with opener.open(req, timeout=self._config.timeout_seconds) as response:
                # Content-type check
                content_type = response.headers.get("Content-Type", "")
                if self._config.allowed_content_types:
                    ct_base = content_type.split(";")[0].strip().lower()
                    if ct_base not in (t.lower() for t in self._config.allowed_content_types):
                        return self._failure(result_id, connector, method, normalized_url, request, started_at,
                                             f"content_type_not_allowed:{ct_base}")

                # Time-bounded and size-bounded read (defends against slow trickle)
                import time as _time
                read_deadline = _time.monotonic() + self._config.read_timeout_seconds
                chunks: list[bytes] = []
                total_read = 0
                chunk_size = 65536
                while True:
                    if _time.monotonic() > read_deadline:
                        finished_at = self._clock()
                        receipt = _build_connector_receipt(
                            result_id=result_id,
                            connector=connector,
                            method=method,
                            url=normalized_url,
                            request=request,
                            response_digest="none",
                            status=ConnectorStatus.TIMEOUT,
                            started_at=started_at,
                            finished_at=finished_at,
                            error_code="read_timeout",
                        )
                        return ConnectorResult(
                            result_id=result_id,
                            connector_id=connector.connector_id,
                            status=ConnectorStatus.TIMEOUT,
                            response_digest="none",
                            started_at=started_at,
                            finished_at=finished_at,
                            error_code="read_timeout",
                            metadata={"connector_receipt": receipt.to_json_dict()},
                        )
                    chunk = response.read(min(chunk_size, max_bytes + 1 - total_read))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total_read += len(chunk)
                    if total_read > max_bytes:
                        return self._failure(result_id, connector, method, normalized_url, request, started_at,
                                             f"response_too_large:{total_read}")
                body = b"".join(chunks)

                digest = hashlib.sha256(body).hexdigest()
                status = _map_status_code(response.status)
                finished_at = self._clock()

                receipt = _build_connector_receipt(
                    result_id=result_id,
                    connector=connector,
                    method=method,
                    url=normalized_url,
                    request=request,
                    response_digest=digest,
                    status=status,
                    started_at=started_at,
                    finished_at=finished_at,
                    status_code=response.status,
                    error_code=None if status is ConnectorStatus.SUCCEEDED else f"http_{response.status}",
                )
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
                        "connector_receipt": receipt.to_json_dict(),
                    },
                )
        except urllib.error.HTTPError as exc:
            error_msg = f"http_{exc.code}"
            # Surface redirect-blocked errors distinctly
            if exc.msg and exc.msg.startswith("redirect_blocked:"):
                error_msg = exc.msg
            return self._failure(result_id, connector, method, url, request, started_at, error_msg)
        except urllib.error.URLError as exc:
            return self._failure(result_id, connector, method, url, request, started_at,
                                 f"url_error:{exc.reason}")
        except TimeoutError:
            finished_at = self._clock()
            receipt = _build_connector_receipt(
                result_id=result_id,
                connector=connector,
                method=method,
                url=url,
                request=request,
                response_digest="none",
                status=ConnectorStatus.TIMEOUT,
                started_at=started_at,
                finished_at=finished_at,
                error_code="timeout",
            )
            return ConnectorResult(
                result_id=result_id,
                connector_id=connector.connector_id,
                status=ConnectorStatus.TIMEOUT,
                response_digest="none",
                started_at=started_at,
                finished_at=finished_at,
                error_code="timeout",
                metadata={"connector_receipt": receipt.to_json_dict()},
            )
        except Exception as exc:
            return self._failure(result_id, connector, method, url, request, started_at,
                                 f"unexpected:{type(exc).__name__}")

    def _failure(
        self,
        result_id: str,
        connector: ConnectorDescriptor | str,
        method: str | None = None,
        url: str = "",
        request: dict | None = None,
        started_at: str = "",
        error_code: str = "",
    ) -> ConnectorResult:
        if isinstance(connector, str) and started_at == "" and error_code == "" and method and url:
            started_at = method
            error_code = url
            method = "GET"
            url = ""
        if isinstance(connector, str):
            connector = ConnectorDescriptor(
                connector_id=connector,
                name=connector,
                provider="unknown",
                effect_class=EffectClass.EXTERNAL_READ,
                trust_class=TrustClass.BOUNDED_EXTERNAL,
                credential_scope_id="unknown",
                enabled=True,
            )
        finished_at = self._clock()
        receipt = _build_connector_receipt(
            result_id=result_id,
            connector=connector,
            method=method or "GET",
            url=url,
            request=request or {},
            response_digest="none",
            status=ConnectorStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            error_code=error_code,
        )
        return ConnectorResult(
            result_id=result_id,
            connector_id=connector.connector_id,
            status=ConnectorStatus.FAILED,
            response_digest="none",
            started_at=started_at,
            finished_at=finished_at,
            error_code=error_code,
            metadata={"connector_receipt": receipt.to_json_dict()},
        )
