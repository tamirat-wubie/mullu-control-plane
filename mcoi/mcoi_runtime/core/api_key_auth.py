"""Phase 224B — API Key Authentication Middleware.

Purpose: Manage API keys for programmatic access with scopes, expiry,
    and rate-limit association.
Dependencies: None (stdlib only).
Invariants:
  - API keys are hashed before storage (never stored in plaintext).
  - Keys have scopes and optional expiry.
  - Revoked keys are rejected immediately.
  - Authentication results are auditable.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class APIKey:
    """Represents an API key with metadata."""
    key_id: str
    key_hash: str  # SHA-256 of raw key
    tenant_id: str
    scopes: frozenset[str]
    created_at: float
    expires_at: float | None = None
    revoked: bool = False
    description: str = ""
    last_used_at: float | None = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.revoked and not self.is_expired

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes or "*" in self.scopes

    def to_dict(self) -> dict[str, Any]:
        return {
            "key_id": self.key_id,
            "tenant_id": self.tenant_id,
            "scopes": sorted(self.scopes),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "revoked": self.revoked,
            "is_valid": self.is_valid,
            "description": self.description,
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
        self._total_auth_success = 0
        self._total_auth_failure = 0

    def create_key(self, tenant_id: str, scopes: frozenset[str],
                   description: str = "", ttl_seconds: float | None = None) -> tuple[str, APIKey]:
        """Create a new API key. Returns (raw_key, APIKey)."""
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
        api_key = self._keys.get(key_hash)

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

    @property
    def key_count(self) -> int:
        return len(self._keys_by_id)

    def summary(self) -> dict[str, Any]:
        return {
            "total_keys": self.key_count,
            "total_created": self._total_created,
            "total_revoked": self._total_revoked,
            "auth_success": self._total_auth_success,
            "auth_failure": self._total_auth_failure,
        }
