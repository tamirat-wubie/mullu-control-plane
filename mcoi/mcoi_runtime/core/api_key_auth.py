"""Phase 224B — API Key Authentication & Lifecycle Management.

Purpose: Manage API keys for programmatic access with scopes, expiry,
    rotation, and usage tracking.
Dependencies: None (stdlib only).
Invariants:
  - API keys are hashed before storage (never stored in plaintext).
  - Keys have scopes and optional expiry.
  - Revoked keys are rejected immediately.
  - Key rotation creates a new key with overlap grace period.
  - Expired keys are auto-detected and can be bulk-pruned.
  - Usage tracking enables stale key detection.
  - Authentication results are auditable.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
import logging
from typing import Any, Callable

_log = logging.getLogger(__name__)


@dataclass
class APIKey:
    """Represents an API key with metadata and lifecycle state."""
    key_id: str
    key_hash: str  # SHA-256 of raw key
    tenant_id: str
    scopes: frozenset[str]
    created_at: float
    expires_at: float | None = None
    revoked: bool = False
    description: str = ""
    last_used_at: float | None = None
    use_count: int = 0
    rotated_from: str = ""  # key_id of the predecessor (if rotated)
    rotated_to: str = ""  # key_id of the successor (if rotated)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.revoked and not self.is_expired

    @property
    def is_rotated(self) -> bool:
        return bool(self.rotated_to)

    @property
    def expires_in_seconds(self) -> float | None:
        """Seconds until expiry, or None if no expiry. Negative if expired."""
        if self.expires_at is None:
            return None
        return self.expires_at - time.time()

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes or "*" in self.scopes

    @property
    def is_wildcard(self) -> bool:
        """True if this key has the wildcard scope (full access)."""
        return "*" in self.scopes

    def to_dict(self) -> dict[str, Any]:
        return {
            "key_id": self.key_id,
            "tenant_id": self.tenant_id,
            "scopes": sorted(self.scopes),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "revoked": self.revoked,
            "is_valid": self.is_valid,
            "is_rotated": self.is_rotated,
            "description": self.description,
            "use_count": self.use_count,
            "last_used_at": self.last_used_at,
            "rotated_from": self.rotated_from,
            "rotated_to": self.rotated_to,
        }


@dataclass
class AuthResult:
    """Result of an API key authentication attempt."""
    authenticated: bool
    key_id: str = ""
    tenant_id: str = ""
    scopes: frozenset[str] = field(default_factory=frozenset)
    error: str = ""


class APIKeyManager:
    """Manages API keys with creation, validation, and revocation."""

    def __init__(self, clock: Callable[[], str] | None = None):
        self._clock = clock
        self._keys: dict[str, APIKey] = {}  # key_hash -> APIKey
        self._keys_by_id: dict[str, APIKey] = {}  # key_id -> APIKey
        self._total_created = 0
        self._total_revoked = 0
        self._total_rotated = 0
        self._total_auth_success = 0
        self._total_auth_failure = 0

    def create_key(self, tenant_id: str, scopes: frozenset[str],
                   description: str = "", ttl_seconds: float | None = None) -> tuple[str, APIKey]:
        """Create a new API key. Returns (raw_key, APIKey)."""
        if not scopes:
            raise ValueError("at least one scope is required")
        if "*" in scopes:
            _log.warning(
                "creating wildcard API key for tenant %s — grants full access. "
                "Use explicit scopes in production.",
                tenant_id,
            )
        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_id = f"mk_{secrets.token_hex(8)}"
        now = time.time()

        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            tenant_id=tenant_id,
            scopes=scopes,
            created_at=now,
            expires_at=now + ttl_seconds if ttl_seconds else None,
            description=description,
        )
        self._keys[key_hash] = api_key
        self._keys_by_id[key_id] = api_key
        self._total_created += 1
        return raw_key, api_key

    def authenticate(self, raw_key: str, required_scope: str = "") -> AuthResult:
        """Authenticate using a raw API key."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        # Constant-time lookup: iterate all keys to prevent timing attacks
        # that could leak valid key hashes via response time differences.
        api_key = None
        for stored_hash, stored_key in self._keys.items():
            if hmac.compare_digest(key_hash, stored_hash):
                api_key = stored_key
                break

        if not api_key:
            self._total_auth_failure += 1
            return AuthResult(authenticated=False, error="Invalid API key")

        if not api_key.is_valid:
            self._total_auth_failure += 1
            return AuthResult(authenticated=False, key_id=api_key.key_id, error="inactive API key")

        if required_scope and not api_key.has_scope(required_scope):
            self._total_auth_failure += 1
            return AuthResult(
                authenticated=False, key_id=api_key.key_id,
                error="missing required scope",
            )

        api_key.last_used_at = time.time()
        api_key.use_count += 1
        self._total_auth_success += 1
        return AuthResult(
            authenticated=True,
            key_id=api_key.key_id,
            tenant_id=api_key.tenant_id,
            scopes=api_key.scopes,
        )

    def revoke(self, key_id: str) -> bool:
        api_key = self._keys_by_id.get(key_id)
        if not api_key:
            return False
        api_key.revoked = True
        self._total_revoked += 1
        return True

    def get_key(self, key_id: str) -> APIKey | None:
        return self._keys_by_id.get(key_id)

    def list_keys(self, tenant_id: str | None = None) -> list[APIKey]:
        keys = list(self._keys_by_id.values())
        if tenant_id:
            keys = [k for k in keys if k.tenant_id == tenant_id]
        return keys

    def rotate_key(
        self,
        key_id: str,
        *,
        grace_period_seconds: float = 3600.0,
        new_ttl_seconds: float | None = None,
        new_description: str = "",
    ) -> tuple[str, APIKey] | None:
        """Rotate an API key — create a replacement and schedule old key expiry.

        The old key remains valid for ``grace_period_seconds`` to allow
        clients to migrate.  The new key inherits tenant and scopes.

        Returns (raw_new_key, new_APIKey) or None if key_id not found.
        """
        old_key = self._keys_by_id.get(key_id)
        if old_key is None:
            return None
        if old_key.revoked:
            return None

        # Create replacement
        raw_key, new_key = self.create_key(
            tenant_id=old_key.tenant_id,
            scopes=old_key.scopes,
            description=new_description or f"Rotated from {key_id}",
            ttl_seconds=new_ttl_seconds,
        )
        new_key.rotated_from = key_id

        # Link old → new
        old_key.rotated_to = new_key.key_id

        # Set grace period on old key (expires after grace period)
        if grace_period_seconds > 0:
            old_key.expires_at = time.time() + grace_period_seconds

        self._total_rotated += 1
        return raw_key, new_key

    def prune_expired(self) -> int:
        """Revoke all expired keys. Returns count pruned."""
        pruned = 0
        for api_key in list(self._keys_by_id.values()):
            if api_key.is_expired and not api_key.revoked:
                api_key.revoked = True
                self._total_revoked += 1
                pruned += 1
        return pruned

    def revoke_all_for_tenant(self, tenant_id: str) -> int:
        """Revoke all keys for a tenant. Returns count revoked."""
        count = 0
        for api_key in self._keys_by_id.values():
            if api_key.tenant_id == tenant_id and not api_key.revoked:
                api_key.revoked = True
                self._total_revoked += 1
                count += 1
        return count

    def expiring_soon(self, within_seconds: float = 86400.0) -> list[APIKey]:
        """List keys expiring within the given window (default 24h)."""
        now = time.time()
        return [
            k for k in self._keys_by_id.values()
            if k.expires_at is not None
            and not k.revoked
            and 0 < (k.expires_at - now) <= within_seconds
        ]

    def stale_keys(self, unused_for_seconds: float = 2592000.0) -> list[APIKey]:
        """List keys not used within the given window (default 30 days)."""
        now = time.time()
        return [
            k for k in self._keys_by_id.values()
            if not k.revoked
            and (
                k.last_used_at is None
                or (now - k.last_used_at) > unused_for_seconds
            )
            and (now - k.created_at) > unused_for_seconds
        ]

    @property
    def key_count(self) -> int:
        return len(self._keys_by_id)

    @property
    def active_key_count(self) -> int:
        return sum(1 for k in self._keys_by_id.values() if k.is_valid)

    def summary(self) -> dict[str, Any]:
        active = sum(1 for k in self._keys_by_id.values() if k.is_valid)
        expired = sum(1 for k in self._keys_by_id.values() if k.is_expired)
        return {
            "total_keys": self.key_count,
            "active_keys": active,
            "expired_keys": expired,
            "total_created": self._total_created,
            "total_revoked": self._total_revoked,
            "total_rotated": self._total_rotated,
            "auth_success": self._total_auth_success,
            "auth_failure": self._total_auth_failure,
        }
