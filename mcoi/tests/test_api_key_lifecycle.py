"""API Key Lifecycle Tests — Rotation, expiration, usage tracking."""

import time

import pytest
from mcoi_runtime.governance.auth.api_key import APIKey, APIKeyManager, AuthResult


# ── Key rotation ───────────────────────────────────────────────

class TestKeyRotation:
    def test_rotate_creates_new_key(self):
        mgr = APIKeyManager()
        raw_old, old_key = mgr.create_key("t1", frozenset({"read", "write"}))
        result = mgr.rotate_key(old_key.key_id, grace_period_seconds=60)
        assert result is not None
        raw_new, new_key = result
        assert new_key.key_id != old_key.key_id
        assert new_key.tenant_id == "t1"
        assert new_key.scopes == frozenset({"read", "write"})

    def test_rotate_links_old_to_new(self):
        mgr = APIKeyManager()
        _, old_key = mgr.create_key("t1", frozenset({"*"}))
        _, new_key = mgr.rotate_key(old_key.key_id)
        assert old_key.rotated_to == new_key.key_id
        assert new_key.rotated_from == old_key.key_id

    def test_rotate_sets_grace_period(self):
        mgr = APIKeyManager()
        _, old_key = mgr.create_key("t1", frozenset({"*"}))
        original_expiry = old_key.expires_at
        mgr.rotate_key(old_key.key_id, grace_period_seconds=3600)
        # Old key should now have an expiry
        assert old_key.expires_at is not None
        assert old_key.is_valid is True  # Still valid during grace period

    def test_old_key_still_works_during_grace(self):
        mgr = APIKeyManager()
        raw_old, old_key = mgr.create_key("t1", frozenset({"read"}))
        mgr.rotate_key(old_key.key_id, grace_period_seconds=3600)
        # Old key should still authenticate
        result = mgr.authenticate(raw_old)
        assert result.authenticated is True

    def test_new_key_works_immediately(self):
        mgr = APIKeyManager()
        _, old_key = mgr.create_key("t1", frozenset({"read"}))
        raw_new, _ = mgr.rotate_key(old_key.key_id)
        result = mgr.authenticate(raw_new)
        assert result.authenticated is True

    def test_rotate_nonexistent_returns_none(self):
        mgr = APIKeyManager()
        assert mgr.rotate_key("nonexistent") is None

    def test_rotate_revoked_returns_none(self):
        mgr = APIKeyManager()
        _, key = mgr.create_key("t1", frozenset({"*"}))
        mgr.revoke(key.key_id)
        assert mgr.rotate_key(key.key_id) is None

    def test_rotate_with_custom_ttl(self):
        mgr = APIKeyManager()
        _, old_key = mgr.create_key("t1", frozenset({"*"}))
        _, new_key = mgr.rotate_key(old_key.key_id, new_ttl_seconds=7200)
        assert new_key.expires_at is not None

    def test_rotate_counter(self):
        mgr = APIKeyManager()
        _, key = mgr.create_key("t1", frozenset({"*"}))
        mgr.rotate_key(key.key_id)
        assert mgr.summary()["total_rotated"] == 1

    def test_is_rotated_property(self):
        mgr = APIKeyManager()
        _, key = mgr.create_key("t1", frozenset({"*"}))
        assert key.is_rotated is False
        mgr.rotate_key(key.key_id)
        assert key.is_rotated is True


# ── Usage tracking ─────────────────────────────────────────────

class TestUsageTracking:
    def test_use_count_increments(self):
        mgr = APIKeyManager()
        raw, key = mgr.create_key("t1", frozenset({"*"}))
        assert key.use_count == 0
        mgr.authenticate(raw)
        assert key.use_count == 1
        mgr.authenticate(raw)
        assert key.use_count == 2

    def test_last_used_at_updated(self):
        mgr = APIKeyManager()
        raw, key = mgr.create_key("t1", frozenset({"*"}))
        assert key.last_used_at is None
        mgr.authenticate(raw)
        assert key.last_used_at is not None

    def test_failed_auth_does_not_increment(self):
        mgr = APIKeyManager()
        raw, key = mgr.create_key("t1", frozenset({"read"}))
        mgr.authenticate(raw, required_scope="admin")  # Scope mismatch
        assert key.use_count == 0  # Failed auth doesn't count


# ── Expiration ─────────────────────────────────────────────────

class TestExpiration:
    def test_expires_in_seconds(self):
        mgr = APIKeyManager()
        _, key = mgr.create_key("t1", frozenset({"*"}), ttl_seconds=3600)
        remaining = key.expires_in_seconds
        assert remaining is not None
        assert remaining > 3500  # Close to 3600

    def test_no_expiry_returns_none(self):
        mgr = APIKeyManager()
        _, key = mgr.create_key("t1", frozenset({"*"}))
        assert key.expires_in_seconds is None

    def test_prune_expired(self):
        mgr = APIKeyManager()
        _, k1 = mgr.create_key("t1", frozenset({"*"}), ttl_seconds=0.001)
        _, k2 = mgr.create_key("t1", frozenset({"*"}))  # No expiry
        time.sleep(0.01)  # Let k1 expire
        pruned = mgr.prune_expired()
        assert pruned == 1
        assert k1.revoked is True
        assert k2.revoked is False

    def test_expiring_soon(self):
        mgr = APIKeyManager()
        mgr.create_key("t1", frozenset({"*"}), ttl_seconds=100)  # Expires soon
        mgr.create_key("t1", frozenset({"*"}), ttl_seconds=200000)  # Not soon
        mgr.create_key("t1", frozenset({"*"}))  # Never expires
        expiring = mgr.expiring_soon(within_seconds=500)
        assert len(expiring) == 1


# ── Stale key detection ───────────────────────────────────────

class TestStaleKeys:
    def test_stale_keys_detected(self):
        mgr = APIKeyManager()
        # Create a key that appears old (created_at in past)
        raw, key = mgr.create_key("t1", frozenset({"*"}))
        key.created_at = time.time() - 100  # 100 seconds old
        stale = mgr.stale_keys(unused_for_seconds=50)
        assert len(stale) == 1

    def test_recently_used_not_stale(self):
        mgr = APIKeyManager()
        raw, key = mgr.create_key("t1", frozenset({"*"}))
        key.created_at = time.time() - 100
        mgr.authenticate(raw)  # Updates last_used_at
        stale = mgr.stale_keys(unused_for_seconds=50)
        assert len(stale) == 0

    def test_new_key_not_stale(self):
        mgr = APIKeyManager()
        mgr.create_key("t1", frozenset({"*"}))
        stale = mgr.stale_keys(unused_for_seconds=50)
        assert len(stale) == 0  # Too new


# ── Bulk operations ────────────────────────────────────────────

class TestBulkOperations:
    def test_revoke_all_for_tenant(self):
        mgr = APIKeyManager()
        mgr.create_key("t1", frozenset({"*"}))
        mgr.create_key("t1", frozenset({"*"}))
        mgr.create_key("t2", frozenset({"*"}))
        count = mgr.revoke_all_for_tenant("t1")
        assert count == 2
        assert mgr.active_key_count == 1  # Only t2 key remains active

    def test_revoke_all_for_nonexistent_tenant(self):
        mgr = APIKeyManager()
        mgr.create_key("t1", frozenset({"*"}))
        assert mgr.revoke_all_for_tenant("t99") == 0


# ── Summary ────────────────────────────────────────────────────

class TestSummary:
    def test_summary_includes_lifecycle_fields(self):
        mgr = APIKeyManager()
        raw, key = mgr.create_key("t1", frozenset({"*"}), ttl_seconds=0.001)
        mgr.authenticate(raw)
        time.sleep(0.01)
        mgr.prune_expired()
        summary = mgr.summary()
        assert summary["total_keys"] == 1
        assert summary["active_keys"] == 0
        assert summary["expired_keys"] == 1
        assert summary["total_created"] == 1
        assert summary["total_revoked"] == 1
        assert "total_rotated" in summary

    def test_active_key_count(self):
        mgr = APIKeyManager()
        mgr.create_key("t1", frozenset({"*"}))
        mgr.create_key("t1", frozenset({"*"}))
        _, k3 = mgr.create_key("t1", frozenset({"*"}))
        mgr.revoke(k3.key_id)
        assert mgr.active_key_count == 2


# ── to_dict includes new fields ────────────────────────────────

class TestToDict:
    def test_to_dict_has_lifecycle_fields(self):
        mgr = APIKeyManager()
        raw, key = mgr.create_key("t1", frozenset({"read"}))
        mgr.authenticate(raw)
        mgr.rotate_key(key.key_id)
        d = key.to_dict()
        assert "use_count" in d
        assert d["use_count"] == 1
        assert "last_used_at" in d
        assert "rotated_to" in d
        assert "is_rotated" in d
        assert d["is_rotated"] is True
