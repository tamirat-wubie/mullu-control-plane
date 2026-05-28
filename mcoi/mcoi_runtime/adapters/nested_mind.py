"""Read-only nested-mind service connector.

Purpose: expose the external nested-mind Γ boundary as a governed read-only
connector.
Governance scope: nested-mind projection/history reads only; no proposal,
child-mind creation, or mutation route is reachable from this adapter.
Dependencies: governed HTTP connector and canonical integration contracts.
Invariants:
  - Every nested-mind operation is classified as EXTERNAL_READ.
  - The connector delegates transport to HttpConnector so SSRF, redirect,
    response-size, content-type, and receipt controls remain centralized.
  - Mind identifiers are path-segment safe and cannot alter route shape.
  - Bearer credentials are optional and are never embedded in descriptor
    metadata.
"""

from __future__ import annotations

import re
from typing import Callable, Mapping

from mcoi_runtime.adapters.http_connector import HttpConnector, HttpConnectorConfig
from mcoi_runtime.contracts._shared_enums import EffectClass, TrustClass
from mcoi_runtime.contracts.integration import ConnectorDescriptor, ConnectorResult
from mcoi_runtime.contracts.provider_policy import HttpProviderPolicy

__all__ = (
    "NESTED_MIND_CONNECTOR_ID",
    "NESTED_MIND_CREDENTIAL_SCOPE_ID",
    "NestedMindConnector",
    "validate_mind_id",
)

NESTED_MIND_CONNECTOR_ID = "nested-mind-readonly"
NESTED_MIND_CREDENTIAL_SCOPE_ID = "nested-mind:read:projection-history"
_NESTED_MIND_PROVIDER = "nested-mind"
_MIND_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ALLOWED_CONTENT_TYPES = ("application/json", "text/plain")
_AUTHORIZATION_HEADER = "Authorization"


def validate_mind_id(mind_id: str) -> str:
    """Return a path-segment-safe nested-mind identifier."""

    value = str(mind_id or "").strip()
    if not _MIND_ID_RE.fullmatch(value):
        raise ValueError("mind_id must be a path-segment-safe identifier")
    return value


class NestedMindConnector:
    """Governed read-only client for nested-mind projection/history routes."""

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        base_url: str,
        bearer_token: str | None = None,
        http_connector: HttpConnector | None = None,
    ) -> None:
        normalized_base_url = str(base_url or "").strip().rstrip("/")
        if not normalized_base_url:
            raise ValueError("base_url must be a non-empty string")
        token = str(bearer_token or "").strip()

        self._base_url = normalized_base_url
        self._bearer_token = token or None
        self._descriptor = ConnectorDescriptor(
            connector_id=NESTED_MIND_CONNECTOR_ID,
            name="Nested Mind read-only Γ bridge",
            provider=_NESTED_MIND_PROVIDER,
            effect_class=EffectClass.EXTERNAL_READ,
            trust_class=TrustClass.BOUNDED_EXTERNAL,
            credential_scope_id=NESTED_MIND_CREDENTIAL_SCOPE_ID,
            enabled=True,
            metadata={
                "route_surface": ("projection", "audit", "replay"),
                "mutation_routes_enabled": False,
            },
        )
        self._http_connector = http_connector or HttpConnector(
            clock=clock,
            config=HttpConnectorConfig(
                allowed_methods=("GET",),
                allowed_content_types=_ALLOWED_CONTENT_TYPES,
                allowed_headers=(_AUTHORIZATION_HEADER,),
            ),
            policy=HttpProviderPolicy(
                policy_id="nested-mind-readonly-http-policy",
                allowed_methods=("GET",),
                allowed_content_types=_ALLOWED_CONTENT_TYPES,
                max_response_bytes=1_048_576,
                header_allowlist=(_AUTHORIZATION_HEADER,),
                require_https=True,
            ),
        )

    @property
    def descriptor(self) -> ConnectorDescriptor:
        """Connector descriptor advertised to the integration plane."""

        return self._descriptor

    @property
    def base_url(self) -> str:
        """Normalized nested-mind service base URL."""

        return self._base_url

    def read_projection(self, mind_id: str = "root") -> ConnectorResult:
        """Read the Γ projection for a mind without mutation authority."""

        return self._get(self._mind_route(mind_id))

    def verify_history(self, mind_id: str = "root") -> ConnectorResult:
        """Read audit verification status for a mind's signed history."""

        return self._get(self._mind_route(mind_id, "audit"))

    def replay_history(self, mind_id: str = "root") -> ConnectorResult:
        """Read replay verification for a mind's causal history."""

        return self._get(self._mind_route(mind_id, "replay"))

    def _mind_route(self, mind_id: str, suffix: str = "") -> str:
        safe_mind_id = validate_mind_id(mind_id)
        path = f"/minds/{safe_mind_id}"
        if suffix:
            path = f"{path}/{suffix}"
        return path

    def _get(self, path: str) -> ConnectorResult:
        return self._http_connector.invoke(
            self._descriptor,
            {
                "url": self._url(path),
                "method": "GET",
                "headers": self._headers(),
            },
        )

    def _url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    def _headers(self) -> Mapping[str, str]:
        if self._bearer_token is None:
            return {}
        return {_AUTHORIZATION_HEADER: f"Bearer {self._bearer_token}"}
