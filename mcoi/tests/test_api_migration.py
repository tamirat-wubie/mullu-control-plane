"""Tests for Phase 230B — API Migration Versioning Engine."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.api_migration import (
    ApiMigrationEngine, VersionStatus,
)


class TestApiMigrationEngine:
    def test_register_version(self):
        engine = ApiMigrationEngine()
        v = engine.register_version("v1", endpoints=["/api/v1/users"])
        assert v.version == "v1"
        assert v.status == VersionStatus.ACTIVE
        assert v.is_routable

    def test_deprecate(self):
        engine = ApiMigrationEngine()
        engine.register_version("v1")
        v = engine.deprecate("v1", sunset_at=9999999999.0)
        assert v is not None
        assert v.status == VersionStatus.DEPRECATED
        assert v.is_routable  # still routable

    def test_retire(self):
        engine = ApiMigrationEngine()
        engine.register_version("v1")
        v = engine.retire("v1")
        assert v is not None
        assert v.status == VersionStatus.RETIRED
        assert not v.is_routable

    def test_route_active(self):
        engine = ApiMigrationEngine()
        engine.register_version("v1")
        result = engine.route("v1")
        assert result["code"] == 200

    def test_route_deprecated(self):
        engine = ApiMigrationEngine()
        engine.register_version("v1")
        engine.deprecate("v1")
        result = engine.route("v1")
        assert result["code"] == 200
        assert "Deprecation" in result["headers"]

    def test_route_retired(self):
        engine = ApiMigrationEngine()
        engine.register_version("v1")
        engine.retire("v1")
        result = engine.route("v1")
        assert result["code"] == 410

    def test_route_not_found(self):
        engine = ApiMigrationEngine()
        result = engine.route("v99")
        assert result["code"] == 404

    def test_add_migration(self):
        engine = ApiMigrationEngine()
        engine.register_version("v1")
        engine.register_version("v2")
        path = engine.add_migration("v1", "v2", ["removed /legacy endpoint"])
        assert path.from_version == "v1"
        assert len(path.breaking_changes) == 1

    def test_list_versions(self):
        engine = ApiMigrationEngine()
        engine.register_version("v1")
        engine.register_version("v2")
        assert len(engine.list_versions()) == 2

    def test_summary(self):
        engine = ApiMigrationEngine()
        engine.register_version("v1")
        engine.register_version("v2")
        engine.deprecate("v1")
        s = engine.summary()
        assert s["active"] == 1
        assert s["deprecated"] == 1
