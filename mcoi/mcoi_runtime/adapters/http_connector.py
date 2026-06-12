"""Purpose: governed HTTP connector — read-only, allowlisted, bounded, hardened.
Governance scope: external integration adapter only.
Dependencies: provider registry, integration contracts.
Invariants:
  - Method allowlist (GET only by default).
  - URL normalization before scope check.
  - DNS resolution checked against private IP ranges (anti-rebinding).
  - Redirect following disabled (anti-SSRF via redirect).
  - Request JSON bodies are deterministic, bounded, and digest-only in receipts.
  - Response size limits.
  - Content-type checks.
  - Status-code mapping into typed results.
  - Response is digested, not stored raw.
  - Optional HttpProviderPolicy enforcement.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import hashlib
import json
import socket
import urllib.request
import urllib.error
from dataclasses import dataclass
from urllib.parse import urlparse

from mcoi_runtime.governance.network.ssrf import (
    is_private_host as _is_private_host,
    is_private_ip as _is_private_ip,
    resolve_and_check as _resolve_and_check,
)
from mcoi_runtime.contracts.connector_effects import ConnectorInvocationReceipt
from mcoi_runtime.contracts._shared_enums import EffectClass, TrustClass
from mcoi_runtime.contracts.integration import ConnectorDescriptor, ConnectorResult, ConnectorStatus
from mcoi_runtime.contracts.provider_policy import HttpProviderPolicy
from mcoi_runtime.adapters.proxy_policy import assert_proxy_environment_allowed
from mcoi_runtime.core.invariants import stable_identifier


__all__ = (
    "HttpConnector",
    "HttpConnectorConfig",
    "JsonConnectorOutcome",
    "_NoRedirectHandler",
    "_is_private_host",
    "_is_private_ip",
    "_map_status_code",
    "_normalize_url",
)


@dataclass(frozen=True, slots=True)
class HttpConnectorConfig:
    """Configuration for the governed HTTP connector."""

    timeout_seconds: float = 30.0
    read_timeout_seconds: float = 60.0  # Max time for response body read
    max_response_bytes: int = 10 * 1024 * 1024  # 10MB
    max_request_body_bytes: int = 1 * 1024 * 1024  # 1MB
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
        if self.max_request_body_bytes <= 0:
            raise ValueError("max_request_body_bytes must be positive")


@dataclass(frozen=True, slots=True)
class JsonConnectorOutcome:
    """Runtime-only connector outcome carrying transient parsed JSON.

    The parsed payload is returned only to the immediate caller. It is not
    stored in ConnectorResult metadata or connector receipts.
    """

    connector_result: ConnectorResult
    json_payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _HttpConnectorRawOutcome:
    connector_result: ConnectorResult
    response_body: bytes | None
    content_type: str


# v4.29.0 (audit F9): SSRF policy unified into core/ssrf_policy. The
# shared module adds Azure / Alibaba / DigitalOcean metadata hostnames,
# IPv6 link-local + ULA prefixes, and the same DNS-resolution
# fail-closed posture this module already had.
class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """HTTP handler that blocks all redirects to prevent SSRF via redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            newurl, code, f"redirect_blocked:{code}", headers, fp
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


def _bounded_url_error_code(exc: urllib.error.URLError) -> str:
    """Classify URL failures without leaking raw transport details."""
    reason = getattr(exc, "reason", None)
    reason_type = type(reason).__name__ if reason is not None else type(exc).__name__
    return f"url_error:{reason_type}"


def _encode_json_body(value: Any, *, max_bytes: int) -> tuple[bytes, str]:
    """Encode a deterministic JSON request body and return bytes + digest."""

    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("json_body must be deterministic JSON") from exc
    if len(encoded) > max_bytes:
        raise ValueError(f"json_body_too_large:{len(encoded)}")
    return encoded, hashlib.sha256(encoded).hexdigest()


def _request_hash_payload(*, url: str, method: str, request: dict) -> dict[str, Any]:
    headers = sorted((request.get("headers") or {}).keys()) if isinstance(request.get("headers"), dict) else ()
    payload: dict[str, Any] = {
        "url": url,
        "method": method,
        "headers": headers,
    }
    body_digest = request.get("body_digest")
    if body_digest:
        payload["body_digest"] = str(body_digest)
    return payload


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
    request_hash = _sha256_text(str(_request_hash_payload(url=url, method=method, request=request)))
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
          - json_body: JSON-compatible value (optional, not allowed for GET/HEAD)
        """
        return self._invoke(connector, request, capture_body=False).connector_result

    def invoke_json(
        self,
        connector: ConnectorDescriptor,
        request: dict,
        *,
        require_json_response: bool = True,
    ) -> JsonConnectorOutcome:
        """Execute a governed HTTP request and parse a transient JSON object.

        The raw response body is size-bounded by the same HTTP path used by
        invoke(), parsed in-process, and then discarded. Only the typed parsed
        object is returned to the immediate caller.
        """
        outcome = self._invoke(connector, request, capture_body=True)
        connector_result = outcome.connector_result
        if connector_result.status is not ConnectorStatus.SUCCEEDED:
            return JsonConnectorOutcome(connector_result=connector_result, json_payload={})

        content_type_base = outcome.content_type.split(";")[0].strip().lower()
        if require_json_response and content_type_base != "application/json":
            return JsonConnectorOutcome(
                connector_result=self._failure(
                    stable_identifier(
                        "http-json-result",
                        {
                            "result_id": connector_result.result_id,
                            "error_code": "json_content_type_required",
                        },
                    ),
                    connector,
                    str(request.get("method", "GET")).upper(),
                    str(request.get("url", "")),
                    self._sanitized_receipt_request(request, None),
                    connector_result.started_at,
                    f"json_content_type_required:{content_type_base or 'missing'}",
                ),
                json_payload={},
            )

        try:
            parsed_payload = json.loads((outcome.response_body or b"").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return JsonConnectorOutcome(
                connector_result=self._failure(
                    stable_identifier(
                        "http-json-result",
                        {
                            "result_id": connector_result.result_id,
                            "error_code": "invalid_json_response",
                        },
                    ),
                    connector,
                    str(request.get("method", "GET")).upper(),
                    str(request.get("url", "")),
                    self._sanitized_receipt_request(request, None),
                    connector_result.started_at,
                    f"invalid_json_response:{type(exc).__name__}",
                ),
                json_payload={},
            )
        if not isinstance(parsed_payload, Mapping):
            return JsonConnectorOutcome(
                connector_result=self._failure(
                    stable_identifier(
                        "http-json-result",
                        {
                            "result_id": connector_result.result_id,
                            "error_code": "json_response_not_object",
                        },
                    ),
                    connector,
                    str(request.get("method", "GET")).upper(),
                    str(request.get("url", "")),
                    self._sanitized_receipt_request(request, None),
                    connector_result.started_at,
                    "json_response_not_object",
                ),
                json_payload={},
            )
        return JsonConnectorOutcome(
            connector_result=connector_result,
            json_payload=parsed_payload,
        )

    def _invoke(
        self,
        connector: ConnectorDescriptor,
        request: dict,
        *,
        capture_body: bool,
    ) -> _HttpConnectorRawOutcome:
        started_at = self._clock()
        url = request.get("url", "")
        method = request.get("method", "GET").upper()
        request_headers = request.get("headers", {})
        request_body: bytes | None = None
        body_digest: str | None = None
        receipt_request = request

        result_id = stable_identifier("http-result", {
            "connector_id": connector.connector_id,
            "url": url,
            "started_at": started_at,
        })

        if not url:
            return self._raw_result(
                self._failure(result_id, connector, method, url, request, started_at, "missing_url")
            )

        # Policy: require_https check
        if self._policy and self._policy.require_https:
            if not url.lower().startswith("https://"):
                return self._raw_result(
                    self._failure(result_id, connector, method, url, request, started_at,
                                  "policy_requires_https")
                )

        # Policy: method allowlist (policy takes precedence over config)
        effective_methods = (
            self._policy.allowed_methods if self._policy else self._config.allowed_methods
        )
        if method not in effective_methods:
            return self._raw_result(self._failure(result_id, connector, method, url, request, started_at,
                                                  f"method_not_allowed:{method}"))

        effective_content_types = (
            self._policy.allowed_content_types if self._policy else self._config.allowed_content_types
        )
        if "json_body" in request:
            if method in {"GET", "HEAD"}:
                return self._raw_result(
                    self._failure(
                        result_id,
                        connector,
                        method,
                        url,
                        request,
                        started_at,
                        f"json_body_not_allowed_for_method:{method}",
                    )
                )
            try:
                request_body, body_digest = _encode_json_body(
                    request["json_body"],
                    max_bytes=self._config.max_request_body_bytes,
                )
            except ValueError as exc:
                return self._raw_result(
                    self._failure(result_id, connector, method, url, request, started_at, str(exc))
                )
            receipt_request = {**request, "body_digest": body_digest}

        # URL normalization
        try:
            normalized_url = _normalize_url(url)
        except (ValueError, TypeError):
            return self._raw_result(
                self._failure(result_id, connector, method, url, receipt_request, started_at, "malformed_url")
            )

        # SSRF protection: block private/loopback/metadata addresses
        # (includes DNS resolution + cloud metadata blocklist).
        # v4.29.0 (audit F10): use ``resolve_and_check`` so we pin the
        # resolved IP for the upcoming connect — closes the DNS-rebinding
        # window between the SSRF check and urllib's own DNS lookup.
        is_private, pinned_ip = _resolve_and_check(normalized_url)
        if is_private or pinned_ip is None:
            return self._raw_result(
                self._failure(result_id, connector, method, normalized_url, receipt_request, started_at,
                              "blocked_private_address")
            )

        # Effective max response bytes (policy overrides config if stricter)
        max_bytes = self._config.max_response_bytes
        if self._policy:
            max_bytes = min(max_bytes, self._policy.max_response_bytes)

        # Build request with filtered headers
        try:
            req = urllib.request.Request(normalized_url, method=method)
            effective_allowed_headers = (
                self._policy.header_allowlist if self._policy else self._config.allowed_headers
            )
            if effective_allowed_headers and isinstance(request_headers, dict):
                allowed_header_names = tuple(h.lower() for h in effective_allowed_headers)
                for key, value in request_headers.items():
                    if key.lower() in allowed_header_names:
                        req.add_header(key, value)
            if request_body is not None:
                req.data = request_body
                req.add_header("Content-Type", "application/json")
                req.add_header("Content-Length", str(len(request_body)))

            # v4.29.0 (audit F10): per-request opener pinned to the
            # resolved IP. Connects to ``pinned_ip`` directly while
            # preserving the original hostname for TLS SNI / Host header.
            # The default ``self._opener`` (built once at __init__) is
            # kept around for tests / explicit non-pinned use only.
            assert_proxy_environment_allowed()
            opener = _build_pinned_opener(pinned_ip)
            with opener.open(req, timeout=self._config.timeout_seconds) as response:
                # Content-type check
                content_type = response.headers.get("Content-Type", "")
                if effective_content_types:
                    ct_base = content_type.split(";")[0].strip().lower()
                    if ct_base not in (t.lower() for t in effective_content_types):
                        return self._raw_result(
                            self._failure(
                                result_id,
                                connector,
                                method,
                                normalized_url,
                                self._sanitized_receipt_request(request, body_digest),
                                started_at,
                                f"content_type_not_allowed:{ct_base}",
                            )
                        )

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
                            request=self._sanitized_receipt_request(request, body_digest),
                            response_digest="none",
                            status=ConnectorStatus.TIMEOUT,
                            started_at=started_at,
                            finished_at=finished_at,
                            error_code="read_timeout",
                        )
                        return self._raw_result(
                            ConnectorResult(
                                result_id=result_id,
                                connector_id=connector.connector_id,
                                status=ConnectorStatus.TIMEOUT,
                                response_digest="none",
                                started_at=started_at,
                                finished_at=finished_at,
                                error_code="read_timeout",
                                metadata={"connector_receipt": receipt.to_json_dict()},
                            )
                        )
                    chunk = response.read(min(chunk_size, max_bytes + 1 - total_read))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total_read += len(chunk)
                    if total_read > max_bytes:
                        return self._raw_result(
                            self._failure(
                                result_id,
                                connector,
                                method,
                                normalized_url,
                                self._sanitized_receipt_request(request, body_digest),
                                started_at,
                                f"response_too_large:{total_read}",
                            )
                        )
                body = b"".join(chunks)

                digest = hashlib.sha256(body).hexdigest()
                status = _map_status_code(response.status)
                finished_at = self._clock()

                receipt = _build_connector_receipt(
                    result_id=result_id,
                    connector=connector,
                    method=method,
                    url=normalized_url,
                    request=self._sanitized_receipt_request(request, body_digest),
                    response_digest=digest,
                    status=status,
                    started_at=started_at,
                    finished_at=finished_at,
                    status_code=response.status,
                    error_code=None if status is ConnectorStatus.SUCCEEDED else f"http_{response.status}",
                )
                return _HttpConnectorRawOutcome(
                    connector_result=ConnectorResult(
                        result_id=result_id,
                        connector_id=connector.connector_id,
                        status=status,
                        response_digest=digest,
                        started_at=started_at,
                        finished_at=finished_at,
                        error_code=None if status is ConnectorStatus.SUCCEEDED else f"http_{response.status}",
                        metadata={
                            "url_hash": _sha256_text(normalized_url),
                            "method": method,
                            "status_code": response.status,
                            "content_type": content_type,
                            "content_length": len(body),
                            "request_body_digest": body_digest,
                            "connector_receipt": receipt.to_json_dict(),
                        },
                    ),
                    response_body=body if capture_body else None,
                    content_type=content_type,
                )
        except urllib.error.HTTPError as exc:
            error_msg = f"http_{exc.code}"
            # Surface redirect-blocked errors distinctly
            if exc.msg and exc.msg.startswith("redirect_blocked:"):
                error_msg = exc.msg
            return self._raw_result(
                self._failure(
                    result_id,
                    connector,
                    method,
                    url,
                    self._sanitized_receipt_request(request, body_digest),
                    started_at,
                    error_msg,
                )
            )
        except urllib.error.URLError as exc:
            return self._raw_result(
                self._failure(
                    result_id,
                    connector,
                    method,
                    url,
                    self._sanitized_receipt_request(request, body_digest),
                    started_at,
                    _bounded_url_error_code(exc),
                )
            )
        except TimeoutError:
            finished_at = self._clock()
            receipt = _build_connector_receipt(
                result_id=result_id,
                connector=connector,
                method=method,
                url=url,
                request=self._sanitized_receipt_request(request, body_digest),
                response_digest="none",
                status=ConnectorStatus.TIMEOUT,
                started_at=started_at,
                finished_at=finished_at,
                error_code="timeout",
            )
            return self._raw_result(
                ConnectorResult(
                    result_id=result_id,
                    connector_id=connector.connector_id,
                    status=ConnectorStatus.TIMEOUT,
                    response_digest="none",
                    started_at=started_at,
                    finished_at=finished_at,
                    error_code="timeout",
                    metadata={"connector_receipt": receipt.to_json_dict()},
                )
            )
        except Exception as exc:
            return self._raw_result(
                self._failure(
                    result_id,
                    connector,
                    method,
                    url,
                    self._sanitized_receipt_request(request, body_digest),
                    started_at,
                    f"unexpected:{type(exc).__name__}",
                )
            )

    def _raw_result(
        self,
        connector_result: ConnectorResult,
        response_body: bytes | None = None,
        content_type: str = "",
    ) -> _HttpConnectorRawOutcome:
        return _HttpConnectorRawOutcome(
            connector_result=connector_result,
            response_body=response_body,
            content_type=content_type,
        )

    def _sanitized_receipt_request(
        self,
        request: dict,
        body_digest: str | None,
    ) -> dict:
        sanitized = {
            "headers": request.get("headers") if isinstance(request.get("headers"), dict) else {},
        }
        if body_digest is not None:
            sanitized["body_digest"] = body_digest
        return sanitized

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
