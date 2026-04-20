"""Tests for Phase 224B — API Key Authentication."""
from __future__ import annotations

import pytest

from mcoi_runtime.core.api_key_auth import APIKeyManager, APIKey, AuthResult


class TestAPIKeyManager:
    @pytest.fixture
    def mgr(self):
        return APIKeyManager()

    def test_create_key(self, mgr):
        raw_key, api_key = mgr.create_key("tenant-1", frozenset({"read", "write"}))
        assert raw_key  # non-empty
        assert api_key.key_id.startswith("mk_")
        assert api_key.tenant_id == "tenant-1"
        assert api_key.is_valid
        assert mgr.key_count == 1

    def test_authenticate_valid_key(self, mgr):
        raw_key, _ = mgr.create_key("t1", frozenset({"read"}))
        result = mgr.authenticate(raw_key)
        assert result.authenticated
        assert result.tenant_id == "t1"

    def test_authenticate_invalid_key(self, mgr):
        result = mgr.authenticate("bad-key")
        assert not result.authenticated
        assert "Invalid" in result.error

    def test_authenticate_with_scope(self, mgr):
        raw_key, _ = mgr.create_key("t1", frozenset({"read"}))
        result = mgr.authenticate(raw_key, required_scope="read")
        assert result.authenticated

    def test_authenticate_missing_scope(self, mgr):
        raw_key, _ = mgr.create_key("t1", frozenset({"read"}))
        result = mgr.authenticate(raw_key, required_scope="admin")
        assert not result.authenticated
        assert result.error == "missing required scope"
        assert "admin" not in result.error

    def test_wildcard_scope(self, mgr):
        raw_key, _ = mgr.create_key("t1", frozenset({"*"}))
        result = mgr.authenticate(raw_key, required_scope="anything")
        assert result.authenticated

    def test_revoke_key(self, mgr):
        raw_key, api_key = mgr.create_key("t1", frozenset({"read"}))
        assert mgr.revoke(api_key.key_id)
        result = mgr.authenticate(raw_key)
        assert not result.authenticated
        assert result.error == "inactive API key"
        assert "revoked" not in result.error

    def test_revoke_nonexistent(self, mgr):
        assert not mgr.revoke("nonexistent")

    def test_expired_key(self, mgr):
        raw_key, api_key = mgr.create_key("t1", frozenset({"read"}), ttl_seconds=-1)
        result = mgr.authenticate(raw_key)
        assert not result.authenticated
        assert result.error == "inactive API key"
        assert "expired" not in result.error

    def test_get_key(self, mgr):
        _, api_key = mgr.create_key("t1", frozenset({"read"}), description="Test key")
        found = mgr.get_key(api_key.key_id)
        assert found is api_key
        assert found.description == "Test key"

    def test_get_nonexistent(self, mgr):
        assert mgr.get_key("nonexistent") is None

    def test_list_keys(self, mgr):
        mgr.create_key("t1", frozenset({"read"}))
        mgr.create_key("t2", frozenset({"write"}))
        mgr.create_key("t1", frozenset({"admin"}))
        assert len(mgr.list_keys()) == 3
        assert len(mgr.list_keys(tenant_id="t1")) == 2

    def test_to_dict(self, mgr):
        _, api_key = mgr.create_key("t1", frozenset({"read", "write"}))
        d = api_key.to_dict()
        assert d["tenant_id"] == "t1"
        assert d["is_valid"] is True
        assert "read" in d["scopes"]

    def test_summary(self, mgr):
        mgr.create_key("t1", frozenset({"read"}))
        raw_key, _ = mgr.create_key("t2", frozenset({"write"}))
        mgr.authenticate(raw_key)
        mgr.authenticate("bad")
        s = mgr.summary()
        assert s["total_keys"] == 2
        assert s["auth_success"] == 1
        assert s["auth_failure"] == 1
        assert s["allow_wildcard_keys"] is True

    def test_manager_can_disable_wildcard_key_posture(self):
        mgr = APIKeyManager(allow_wildcard_keys=False)
        assert mgr.allow_wildcard_keys is False
        assert mgr.summary()["allow_wildcard_keys"] is False
