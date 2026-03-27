"""Phase 230B — API Migration Versioning Engine.

Purpose: Track API version migrations, deprecation schedules, and
    backward-compatible endpoint routing with sunset headers.
Dependencies: None (stdlib only).
Invariants:
  - Active versions are always routable.
  - Deprecated versions emit sunset headers.
  - Retired versions return 410 Gone.
  - Migration paths are auditable.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any


@unique
class VersionStatus(Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


@dataclass
class ApiVersion:
    """An API version with lifecycle metadata."""
    version: str
    status: VersionStatus = VersionStatus.ACTIVE
    introduced_at: float = field(default_factory=time.time)
    deprecated_at: float | None = None
    sunset_at: float | None = None
    endpoints: list[str] = field(default_factory=list)

    @property
    def is_routable(self) -> bool:
        return self.status != VersionStatus.RETIRED

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "status": self.status.value,
            "is_routable": self.is_routable,
            "endpoint_count": len(self.endpoints),
            "sunset_at": self.sunset_at,
        }


@dataclass(frozen=True)
class MigrationPath:
    """A migration path from one version to another."""
    from_version: str
    to_version: str
    breaking_changes: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class ApiMigrationEngine:
    """Manages API version lifecycle and migration paths."""

    def __init__(self):
        self._versions: dict[str, ApiVersion] = {}
        self._migrations: list[MigrationPath] = []
        self._route_count = 0

    def register_version(self, version: str, endpoints: list[str] | None = None) -> ApiVersion:
        api_ver = ApiVersion(version=version, endpoints=endpoints or [])
        self._versions[version] = api_ver
        return api_ver

    def deprecate(self, version: str, sunset_at: float | None = None) -> ApiVersion | None:
        v = self._versions.get(version)
        if not v:
            return None
        v.status = VersionStatus.DEPRECATED
        v.deprecated_at = time.time()
        v.sunset_at = sunset_at
        return v

    def retire(self, version: str) -> ApiVersion | None:
        v = self._versions.get(version)
        if not v:
            return None
        v.status = VersionStatus.RETIRED
        return v

    def add_migration(self, from_version: str, to_version: str,
                      breaking_changes: list[str] | None = None) -> MigrationPath:
        path = MigrationPath(
            from_version=from_version,
            to_version=to_version,
            breaking_changes=breaking_changes or [],
        )
        self._migrations.append(path)
        return path

    def route(self, version: str) -> dict[str, Any]:
        """Route a request to the appropriate version."""
        self._route_count += 1
        v = self._versions.get(version)
        if not v:
            return {"status": "not_found", "code": 404}
        if v.status == VersionStatus.RETIRED:
            return {"status": "gone", "code": 410, "message": f"API {version} retired"}
        headers: dict[str, str] = {}
        if v.status == VersionStatus.DEPRECATED:
            headers["Sunset"] = str(v.sunset_at) if v.sunset_at else "TBD"
            headers["Deprecation"] = "true"
        return {
            "status": "ok",
            "code": 200,
            "version": version,
            "headers": headers,
        }

    def get_version(self, version: str) -> ApiVersion | None:
        return self._versions.get(version)

    def list_versions(self) -> list[ApiVersion]:
        return list(self._versions.values())

    def summary(self) -> dict[str, Any]:
        return {
            "total_versions": len(self._versions),
            "active": sum(1 for v in self._versions.values() if v.status == VersionStatus.ACTIVE),
            "deprecated": sum(1 for v in self._versions.values() if v.status == VersionStatus.DEPRECATED),
            "retired": sum(1 for v in self._versions.values() if v.status == VersionStatus.RETIRED),
            "migrations": len(self._migrations),
            "total_routes": self._route_count,
        }
