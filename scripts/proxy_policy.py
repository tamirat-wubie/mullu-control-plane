"""Standalone script proxy usage policy.

Purpose: bound process-level HTTP proxy environment variables before
    repository scripts perform outbound probes.
Governance scope: operator evidence scripts, proxy credential redaction, and
    production fail-closed behavior.
Dependencies: stdlib os and urllib parsing only.
Invariants:
  - Proxy URLs are never returned in raw form.
  - Pilot and production block active proxy environment variables by default.
  - Local/test may keep developer proxy variables, but callers must still log
    only variable names and redacted values.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

PROXY_ENVIRONMENT_VARIABLES = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)

_FAIL_CLOSED_ENVIRONMENTS = frozenset({"pilot", "prod", "production"})


class ProxyEnvironmentBlocked(RuntimeError):
    """Raised when a production-like script run has unapproved proxy env vars."""


@dataclass(frozen=True, slots=True)
class ProxyUsagePolicy:
    """Policy for implicit process proxy variables."""

    environment: str = "local_dev"
    allowed_environment_variables: tuple[str, ...] = ()

    @property
    def fail_closed(self) -> bool:
        """Return whether active proxy variables block outbound transport."""
        return self.environment.strip().lower() in _FAIL_CLOSED_ENVIRONMENTS


def proxy_usage_policy_from_env(environ: Mapping[str, str] | None = None) -> ProxyUsagePolicy:
    """Build proxy policy from process environment without reading proxy values."""
    source = environ if environ is not None else os.environ
    environment = source.get("MULLU_ENV", "local_dev").strip().lower() or "local_dev"
    allowlist = tuple(
        value.strip()
        for value in source.get("MULLU_PROXY_ENV_ALLOWLIST", "").split(",")
        if value.strip()
    )
    return ProxyUsagePolicy(
        environment=environment,
        allowed_environment_variables=allowlist,
    )


def active_proxy_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return active proxy variables with values redacted."""
    source = environ if environ is not None else os.environ
    return {
        key: redact_proxy_url(value)
        for key in PROXY_ENVIRONMENT_VARIABLES
        if (value := source.get(key, "")).strip()
    }


def assert_proxy_environment_allowed(
    *,
    policy: ProxyUsagePolicy | None = None,
    environ: Mapping[str, str] | None = None,
) -> None:
    """Fail closed when production-like script probes would inherit proxies."""
    effective_policy = policy or proxy_usage_policy_from_env(environ)
    active = active_proxy_environment(environ)
    if not active:
        return
    unapproved = tuple(
        name
        for name in sorted(active)
        if name not in effective_policy.allowed_environment_variables
    )
    if effective_policy.fail_closed and unapproved:
        joined_names = ",".join(unapproved)
        raise ProxyEnvironmentBlocked(f"proxy environment blocked:{joined_names}")


def redact_proxy_url(value: str) -> str:
    """Redact proxy URL credentials and host details for receipts/errors."""
    if not value.strip():
        return ""
    if "," in value and "://" not in value:
        return "<redacted-no-proxy-list>"
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return "<redacted-proxy>"
    host = parsed.hostname or ""
    try:
        parsed_port = parsed.port
    except ValueError:
        parsed_port = None
    port = f":{parsed_port}" if parsed_port else ""
    redacted_netloc = f"<redacted-host>{port}" if host else "<redacted-host>"
    return urlunsplit((parsed.scheme.lower(), redacted_netloc, "", "", ""))
