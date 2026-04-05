"""Tests for Phase 228A — Secret Rotation Engine."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.secret_rotation import (
    SecretRotationEngine, RotationPolicy, SecretStatus,
)


class TestSecretRotationEngine:
    def test_create_secret(self):
        engine = SecretRotationEngine()
        raw, managed = engine.create_secret("api-key")
        assert raw  # non-empty
        assert managed.secret_id.startswith("sec_")
        assert managed.status == SecretStatus.ACTIVE
        assert managed.is_valid
        assert engine.secret_count == 1

    def test_validate_secret(self):
        engine = SecretRotationEngine()
        raw, managed = engine.create_secret("token")
        assert engine.validate(managed.secret_id, raw)
        assert not engine.validate(managed.secret_id, "wrong-secret")

    def test_validate_nonexistent(self):
        engine = SecretRotationEngine()
        assert not engine.validate("nonexistent", "anything")

    def test_rotate_secret(self):
        engine = SecretRotationEngine()
        raw1, managed1 = engine.create_secret("key", RotationPolicy(grace_period_seconds=3600))
        new_raw, new_managed = engine.rotate(managed1.secret_id)
        assert new_raw != raw1
        assert new_managed.rotation_count == 1
        assert engine.validate(managed1.secret_id, new_raw)
        # Old raw should no longer validate (new hash replaced)
        assert not engine.validate(managed1.secret_id, raw1)

    def test_rotate_nonexistent(self):
        engine = SecretRotationEngine()
        with pytest.raises(ValueError, match="^secret not found$") as exc_info:
            engine.rotate("nonexistent")
        assert "nonexistent" not in str(exc_info.value)

    def test_revoke_secret(self):
        engine = SecretRotationEngine()
        raw, managed = engine.create_secret("key")
        assert engine.revoke(managed.secret_id)
        assert not engine.validate(managed.secret_id, raw)

    def test_revoke_nonexistent(self):
        engine = SecretRotationEngine()
        assert not engine.revoke("nonexistent")

    def test_needs_rotation(self):
        engine = SecretRotationEngine()
        _, managed = engine.create_secret("key", RotationPolicy(
            rotation_interval_seconds=0.01, auto_rotate=True,
        ))
        import time
        time.sleep(0.02)
        assert engine.needs_rotation(managed.secret_id)

    def test_no_auto_rotate(self):
        engine = SecretRotationEngine()
        _, managed = engine.create_secret("key", RotationPolicy(auto_rotate=False))
        assert not engine.needs_rotation(managed.secret_id)

    def test_to_dict(self):
        engine = SecretRotationEngine()
        _, managed = engine.create_secret("key")
        d = managed.to_dict()
        assert d["name"] == "key"
        assert d["status"] == "active"
        assert d["is_valid"] is True

    def test_summary(self):
        engine = SecretRotationEngine()
        engine.create_secret("k1")
        engine.create_secret("k2")
        s = engine.summary()
        assert s["total_secrets"] == 2
        assert s["active"] == 2
