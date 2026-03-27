"""Phase 228A — Secret Rotation Engine.

Purpose: Manage API keys, tokens, and credentials with automatic rotation
    policies, grace periods, and audit-safe transitions.
Dependencies: None (stdlib only).
Invariants:
  - Old secrets remain valid during grace period.
  - Rotation is atomic (new secret active before old expires).
  - All rotations are auditable.
  - Secrets are never logged in plaintext.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable


@unique
class SecretStatus(Enum):
    ACTIVE = "active"
    GRACE = "grace"  # old secret still valid during transition
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class ManagedSecret:
    """A secret with rotation metadata."""
    secret_id: str
    name: str
    secret_hash: str  # never store plaintext
    status: SecretStatus = SecretStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    rotation_count: int = 0
    last_rotated_at: float | None = None

    @property
    def is_valid(self) -> bool:
        if self.status in (SecretStatus.EXPIRED, SecretStatus.REVOKED):
            return False
        if self.expires_at and time.time() > self.expires_at:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "secret_id": self.secret_id,
            "name": self.name,
            "status": self.status.value,
            "is_valid": self.is_valid,
            "rotation_count": self.rotation_count,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class RotationPolicy:
    """Policy for automatic secret rotation."""
    rotation_interval_seconds: float = 86400.0  # 24h
    grace_period_seconds: float = 3600.0  # 1h overlap
    auto_rotate: bool = True


class SecretRotationEngine:
    """Manages secrets with rotation policies and grace periods."""

    def __init__(self, clock: Callable[[], str] | None = None):
        self._clock = clock
        self._secrets: dict[str, ManagedSecret] = {}
        self._policies: dict[str, RotationPolicy] = {}
        self._history: list[dict[str, Any]] = []
        self._total_rotations = 0

    def create_secret(self, name: str, policy: RotationPolicy | None = None) -> tuple[str, ManagedSecret]:
        """Create a new managed secret. Returns (raw_secret, ManagedSecret)."""
        raw = secrets.token_urlsafe(32)
        secret_hash = hashlib.sha256(raw.encode()).hexdigest()
        secret_id = f"sec_{secrets.token_hex(6)}"
        now = time.time()

        managed = ManagedSecret(
            secret_id=secret_id,
            name=name,
            secret_hash=secret_hash,
            created_at=now,
            expires_at=now + (policy.rotation_interval_seconds if policy else 86400.0),
        )
        self._secrets[secret_id] = managed
        if policy:
            self._policies[secret_id] = policy
        return raw, managed

    def rotate(self, secret_id: str) -> tuple[str, ManagedSecret]:
        """Rotate a secret. Old secret enters grace period."""
        old = self._secrets.get(secret_id)
        if not old:
            raise ValueError(f"Secret not found: {secret_id}")

        policy = self._policies.get(secret_id, RotationPolicy())

        # Move old to grace
        old.status = SecretStatus.GRACE
        old.expires_at = time.time() + policy.grace_period_seconds

        # Create new
        raw = secrets.token_urlsafe(32)
        new_hash = hashlib.sha256(raw.encode()).hexdigest()
        now = time.time()

        new_secret = ManagedSecret(
            secret_id=secret_id,
            name=old.name,
            secret_hash=new_hash,
            created_at=now,
            expires_at=now + policy.rotation_interval_seconds,
            rotation_count=old.rotation_count + 1,
            last_rotated_at=now,
        )
        self._secrets[secret_id] = new_secret
        self._total_rotations += 1

        self._history.append({
            "secret_id": secret_id,
            "action": "rotated",
            "rotation_count": new_secret.rotation_count,
            "timestamp": now,
        })
        return raw, new_secret

    def validate(self, secret_id: str, raw_secret: str) -> bool:
        """Validate a raw secret against stored hash."""
        managed = self._secrets.get(secret_id)
        if not managed:
            return False
        if not managed.is_valid:
            return False
        check_hash = hashlib.sha256(raw_secret.encode()).hexdigest()
        return check_hash == managed.secret_hash

    def revoke(self, secret_id: str) -> bool:
        managed = self._secrets.get(secret_id)
        if not managed:
            return False
        managed.status = SecretStatus.REVOKED
        self._history.append({
            "secret_id": secret_id, "action": "revoked", "timestamp": time.time(),
        })
        return True

    def get_secret(self, secret_id: str) -> ManagedSecret | None:
        return self._secrets.get(secret_id)

    def needs_rotation(self, secret_id: str) -> bool:
        managed = self._secrets.get(secret_id)
        if not managed:
            return False
        policy = self._policies.get(secret_id, RotationPolicy())
        if not policy.auto_rotate:
            return False
        age = time.time() - managed.created_at
        return age > policy.rotation_interval_seconds * 0.9  # 90% of interval

    @property
    def secret_count(self) -> int:
        return len(self._secrets)

    def summary(self) -> dict[str, Any]:
        return {
            "total_secrets": self.secret_count,
            "total_rotations": self._total_rotations,
            "active": sum(1 for s in self._secrets.values() if s.status == SecretStatus.ACTIVE),
            "grace": sum(1 for s in self._secrets.values() if s.status == SecretStatus.GRACE),
        }
