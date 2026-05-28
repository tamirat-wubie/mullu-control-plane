"""Nested-mind service integration for the control-plane app.

Purpose: select and mount the optional nested-mind read-only connector from
runtime environment.
Governance scope: default-off external read boundary, HTTPS-only base URL
validation, optional credential binding, and fail-closed misconfiguration.
Dependencies: shared env flag helper and nested_mind adapter.
Invariants:
  - unset/false flag means no connector and no runtime behavior change.
  - enabled flag requires an HTTPS base URL with no credentials/query/fragment.
  - bearer token presence is reported as posture only; the token value is not
    stored in the bootstrap record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping
from urllib.parse import urlparse

from mcoi_runtime.adapters.nested_mind import NestedMindConnector
from mcoi_runtime.app._integration_paths import env_flag

NESTED_MIND_ENABLED_ENV = "MULLU_NESTED_MIND_ENABLED"
NESTED_MIND_BASE_URL_ENV = "MULLU_NESTED_MIND_BASE_URL"
NESTED_MIND_BEARER_TOKEN_ENV = "MULLU_NESTED_MIND_BEARER_TOKEN"


@dataclass(frozen=True)
class NestedMindConnectorBootstrap:
    """Startup posture for the optional nested-mind read-only connector."""

    connector: object | None
    enabled: bool
    base_url: str
    credential_configured: bool


def mount_nested_mind_connector_from_env(
    *,
    runtime_env: Mapping[str, str],
    clock: Callable[[], str],
    connector_cls: type[NestedMindConnector] = NestedMindConnector,
) -> NestedMindConnectorBootstrap:
    """Build the nested-mind connector when the feature flag is enabled."""

    if not env_flag(runtime_env.get(NESTED_MIND_ENABLED_ENV)):
        return NestedMindConnectorBootstrap(
            connector=None,
            enabled=False,
            base_url="",
            credential_configured=False,
        )

    raw_base_url = str(runtime_env.get(NESTED_MIND_BASE_URL_ENV, "")).strip()
    if not raw_base_url:
        raise RuntimeError(
            f"{NESTED_MIND_BASE_URL_ENV} is required when "
            f"{NESTED_MIND_ENABLED_ENV} is enabled"
        )
    base_url = validate_nested_mind_base_url(raw_base_url)

    raw_token = str(runtime_env.get(NESTED_MIND_BEARER_TOKEN_ENV, "")).strip()
    token = raw_token or None
    connector = connector_cls(
        clock=clock,
        base_url=base_url,
        bearer_token=token,
    )
    return NestedMindConnectorBootstrap(
        connector=connector,
        enabled=True,
        base_url=base_url,
        credential_configured=token is not None,
    )


def validate_nested_mind_base_url(base_url: str) -> str:
    """Validate and normalize the nested-mind HTTPS service boundary."""

    parsed = urlparse(str(base_url or "").strip())
    if parsed.scheme.lower() != "https":
        raise RuntimeError(f"{NESTED_MIND_BASE_URL_ENV} must use https")
    if not parsed.netloc or not parsed.hostname:
        raise RuntimeError(f"{NESTED_MIND_BASE_URL_ENV} must include a host")
    if parsed.username or parsed.password:
        raise RuntimeError(f"{NESTED_MIND_BASE_URL_ENV} must not include credentials")
    if parsed.params or parsed.query or parsed.fragment:
        raise RuntimeError(
            f"{NESTED_MIND_BASE_URL_ENV} must not include params, query, or fragment"
        )

    path = parsed.path.rstrip("/")
    netloc = parsed.netloc.lower()
    normalized = f"https://{netloc}{path}" if path else f"https://{netloc}"
    return normalized
