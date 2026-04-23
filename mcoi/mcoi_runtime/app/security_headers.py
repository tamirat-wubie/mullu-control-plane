"""Security Headers Middleware — OWASP-recommended response headers.

Purpose: Adds security headers to all HTTP responses to protect against
    clickjacking, MIME-sniffing, XSS, and other common web attacks.
    Configurable per-environment (dev vs production).
Governance scope: transport security only — no business logic.
Dependencies: Starlette/FastAPI middleware.
Invariants:
  - Headers are applied to ALL responses (including error responses).
  - Production mode enables strict headers (HSTS, strict CSP).
  - Development mode relaxes CSP for debugging tools.
  - Headers never leak internal state (no server version, no stack traces).
  - Thread-safe — stateless per-request.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_HEADER_NAME_CHARS = frozenset(
    "!#$%&'*+-.^_`|~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
)
_HEADER_CONTROL_CHARS = frozenset(("\r", "\n", "\0"))


def _reject_header_control_chars(field_name: str, value: str) -> None:
    if any(ch in value for ch in _HEADER_CONTROL_CHARS):
        raise ValueError(f"{field_name} must not contain control characters")


@dataclass(frozen=True)
class SecurityHeadersConfig:
    """Configuration for security headers.

    Production defaults follow OWASP recommendations.
    Set environment="development" to relax for local debugging.
    """

    environment: str = "production"

    # Content Security Policy
    csp: str = ""  # Empty = use default based on environment

    # HTTP Strict Transport Security (seconds)
    hsts_max_age: int = 31536000  # 1 year
    hsts_include_subdomains: bool = True
    hsts_preload: bool = False

    # Referrer Policy
    referrer_policy: str = "strict-origin-when-cross-origin"

    # Permissions Policy (formerly Feature-Policy)
    permissions_policy: str = "camera=(), microphone=(), geolocation=(), payment=()"

    # Additional custom headers
    custom_headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.environment, str):
            raise ValueError("environment must be text")
        environment = self.environment.strip().lower()
        if not environment:
            raise ValueError("environment must be non-empty")
        object.__setattr__(self, "environment", environment)

        if not isinstance(self.hsts_max_age, int) or self.hsts_max_age < 0:
            raise ValueError("hsts_max_age must be non-negative")

        for field_name in ("csp", "referrer_policy", "permissions_policy"):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise ValueError(f"{field_name} must be text")
            _reject_header_control_chars(field_name, value)
            normalized = value.strip()
            if field_name != "csp" and not normalized:
                raise ValueError(f"{field_name} must be non-empty")
            object.__setattr__(self, field_name, normalized)

        if not isinstance(self.custom_headers, Mapping):
            raise ValueError("custom_headers must be a mapping")
        custom_headers: dict[str, str] = {}
        for name, value in self.custom_headers.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("custom header names must be non-empty")
            _reject_header_control_chars("custom header names", name)
            normalized_name = name.strip()
            if any(ch not in _HEADER_NAME_CHARS for ch in normalized_name):
                raise ValueError("custom header names must be HTTP tokens")
            if not isinstance(value, str) or not value.strip():
                raise ValueError("custom header values must be non-empty")
            _reject_header_control_chars("custom header values", value)
            normalized_value = value.strip()
            custom_headers[normalized_name] = normalized_value
        object.__setattr__(self, "custom_headers", MappingProxyType(custom_headers))

    @property
    def is_production(self) -> bool:
        return self.environment not in ("development", "local_dev", "test")

    @property
    def effective_csp(self) -> str:
        if self.csp:
            return self.csp
        if self.is_production:
            return "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; media-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return "default-src 'self' 'unsafe-inline' 'unsafe-eval'; img-src * data:; connect-src *"

    @property
    def effective_hsts(self) -> str:
        parts = [f"max-age={self.hsts_max_age}"]
        if self.hsts_include_subdomains:
            parts.append("includeSubDomains")
        if self.hsts_preload:
            parts.append("preload")
        return "; ".join(parts)


# Default headers applied to every response
_STATIC_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",  # Disabled per OWASP (CSP is the modern replacement)
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
}


def build_security_headers(config: SecurityHeadersConfig | None = None) -> dict[str, str]:
    """Build the complete set of security headers from config.

    Returns a dict of header name → value. This can be used
    standalone (without middleware) for testing or manual injection.
    """
    cfg = config or SecurityHeadersConfig()
    headers = dict(_STATIC_HEADERS)

    headers["Content-Security-Policy"] = cfg.effective_csp
    headers["Referrer-Policy"] = cfg.referrer_policy
    headers["Permissions-Policy"] = cfg.permissions_policy

    if cfg.is_production:
        headers["Strict-Transport-Security"] = cfg.effective_hsts

    # Remove Server header to avoid version leakage
    headers["Server"] = "mullu"

    # Custom overrides
    headers.update(cfg.custom_headers)

    return headers


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware that adds security headers to all responses.

    Usage:
        from mcoi_runtime.app.security_headers import (
            SecurityHeadersMiddleware, SecurityHeadersConfig,
        )

        app.add_middleware(
            SecurityHeadersMiddleware,
            config=SecurityHeadersConfig(environment="production"),
        )
    """

    def __init__(
        self,
        app: Any,
        *,
        config: SecurityHeadersConfig | None = None,
    ) -> None:
        super().__init__(app)
        self._headers = build_security_headers(config)

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        for name, value in self._headers.items():
            response.headers[name] = value
        return response
