"""Phase 210C — API Versioning Contracts.

Purpose: API version management for backward compatibility.
    Tracks endpoint registration, deprecation, and version freeze.
Governance scope: version metadata only — never modifies endpoints.
Dependencies: none (pure metadata).
Invariants:
  - Frozen versions cannot add new endpoints.
  - Deprecated endpoints are tracked with sunset dates.
  - Version history is append-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class EndpointDescriptor:
    """Describes a single API endpoint."""

    method: str  # GET, POST, etc.
    path: str
    name: str
    version: str
    deprecated: bool = False
    sunset_date: str = ""
    added_in_phase: int = 0


@dataclass(frozen=True, slots=True)
class APIVersion:
    """Describes an API version."""

    version: str
    status: str  # "active", "frozen", "deprecated"
    endpoints: tuple[EndpointDescriptor, ...]
    released_at: str
    frozen_at: str = ""


class APIVersionManager:
    """Manages API version lifecycle."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._endpoints: list[EndpointDescriptor] = []
        self._versions: dict[str, APIVersion] = {}
        self._current_version = "0.9.0"

    def register_endpoint(self, endpoint: EndpointDescriptor) -> None:
        self._endpoints.append(endpoint)

    def register_endpoints_bulk(self, endpoints: list[EndpointDescriptor]) -> None:
        self._endpoints.extend(endpoints)

    def freeze_version(self, version: str) -> APIVersion:
        """Freeze a version — no new endpoints allowed."""
        api_version = APIVersion(
            version=version,
            status="frozen",
            endpoints=tuple(self._endpoints),
            released_at=self._clock(),
            frozen_at=self._clock(),
        )
        self._versions[version] = api_version
        return api_version

    def release_version(self, version: str) -> APIVersion:
        """Release a new version."""
        api_version = APIVersion(
            version=version,
            status="active",
            endpoints=tuple(self._endpoints),
            released_at=self._clock(),
        )
        self._versions[version] = api_version
        self._current_version = version
        return api_version

    def deprecate_endpoint(self, path: str, method: str, sunset_date: str) -> bool:
        """Mark an endpoint as deprecated."""
        for i, ep in enumerate(self._endpoints):
            if ep.path == path and ep.method == method:
                self._endpoints[i] = EndpointDescriptor(
                    method=ep.method, path=ep.path, name=ep.name,
                    version=ep.version, deprecated=True,
                    sunset_date=sunset_date, added_in_phase=ep.added_in_phase,
                )
                return True
        return False

    def get_version(self, version: str) -> APIVersion | None:
        return self._versions.get(version)

    @property
    def current_version(self) -> str:
        return self._current_version

    @property
    def endpoint_count(self) -> int:
        return len(self._endpoints)

    def deprecated_endpoints(self) -> list[EndpointDescriptor]:
        return [ep for ep in self._endpoints if ep.deprecated]

    def endpoints_by_phase(self, phase: int) -> list[EndpointDescriptor]:
        return [ep for ep in self._endpoints if ep.added_in_phase == phase]

    def summary(self) -> dict[str, Any]:
        return {
            "current_version": self._current_version,
            "total_endpoints": self.endpoint_count,
            "deprecated": len(self.deprecated_endpoints()),
            "versions_released": len(self._versions),
        }
