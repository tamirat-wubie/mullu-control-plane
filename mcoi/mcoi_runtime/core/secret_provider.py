"""Secret Provider — Pluggable secret backend abstraction.

Purpose: Abstract secret retrieval so the platform can use env vars in
    development and vault backends (HashiCorp Vault, AWS Secrets Manager)
    in production without code changes.
Governance scope: secret access only — no secret rotation logic here.
Dependencies: none (pure abstraction + env vars).
Invariants:
  - Secrets are never logged (even on error).
  - Secret access is auditable (who accessed what, when).
  - Backends are pluggable (env, file, vault via protocol).
  - Missing secrets fail explicitly (never return empty string silently).
  - Thread-safe — concurrent secret access is safe.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class SecretValue:
    """A retrieved secret with metadata."""

    key: str
    value: str
    source: str  # "env", "file", "vault", etc.
    version: str = ""
    expires_at: str = ""

    def __repr__(self) -> str:
        """Never expose secret value in repr."""
        return f"SecretValue(key={self.key!r}, source={self.source!r})"

    def __str__(self) -> str:
        return f"SecretValue({self.key})"


@dataclass(frozen=True, slots=True)
class SecretAccessRecord:
    """Audit record of a secret access."""

    key: str
    source: str
    accessor: str
    accessed_at: str
    found: bool


class SecretProvider:
    """Protocol for secret backends."""

    def get(self, key: str, *, accessor: str = "") -> SecretValue | None:
        """Retrieve a secret by key. Returns None if not found."""
        return None

    def exists(self, key: str) -> bool:
        """Check if a secret exists without retrieving it."""
        return False

    def list_keys(self) -> list[str]:
        """List available secret keys (not values)."""
        return []


class EnvSecretProvider(SecretProvider):
    """Retrieves secrets from environment variables.

    Optionally applies a prefix (e.g., MULLU_SECRET_) to key lookups.
    """

    def __init__(self, *, prefix: str = "", clock: Callable[[], str] | None = None) -> None:
        self._prefix = prefix
        self._clock = clock or (lambda: "")
        self._access_log: list[SecretAccessRecord] = []
        self._lock = threading.Lock()

    def _env_key(self, key: str) -> str:
        return f"{self._prefix}{key}".upper()

    def get(self, key: str, *, accessor: str = "") -> SecretValue | None:
        env_key = self._env_key(key)
        value = os.environ.get(env_key)
        with self._lock:
            self._access_log.append(SecretAccessRecord(
                key=key, source="env", accessor=accessor,
                accessed_at=self._clock(), found=value is not None,
            ))
        if value is None:
            return None
        return SecretValue(key=key, value=value, source="env")

    def exists(self, key: str) -> bool:
        return self._env_key(key) in os.environ

    def list_keys(self) -> list[str]:
        if not self._prefix:
            return []  # Don't enumerate all env vars without prefix
        return [
            k[len(self._prefix):].lower()
            for k in os.environ
            if k.startswith(self._prefix.upper())
        ]

    @property
    def access_log(self) -> list[SecretAccessRecord]:
        with self._lock:
            return list(self._access_log)


class FileSecretProvider(SecretProvider):
    """Retrieves secrets from a JSON file.

    File format: {"key_name": "secret_value", ...}
    Suitable for development/testing. NOT for production.
    """

    def __init__(self, *, path: str, clock: Callable[[], str] | None = None) -> None:
        self._path = Path(path).resolve()
        self._clock = clock or (lambda: "")
        self._cache: dict[str, str] | None = None
        self._lock = threading.Lock()
        self._access_log: list[SecretAccessRecord] = []

    def _load(self) -> dict[str, str]:
        if self._cache is not None:
            return self._cache
        try:
            with self._path.open("r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._cache = {str(k): str(v) for k, v in data.items()}
            else:
                self._cache = {}
        except (json.JSONDecodeError, OSError):
            self._cache = {}
        return self._cache

    def get(self, key: str, *, accessor: str = "") -> SecretValue | None:
        with self._lock:
            secrets = self._load()
            value = secrets.get(key)
            self._access_log.append(SecretAccessRecord(
                key=key, source="file", accessor=accessor,
                accessed_at=self._clock(), found=value is not None,
            ))
        if value is None:
            return None
        return SecretValue(key=key, value=value, source="file")

    def exists(self, key: str) -> bool:
        with self._lock:
            return key in self._load()

    def list_keys(self) -> list[str]:
        with self._lock:
            return sorted(self._load().keys())

    def reload(self) -> None:
        """Force reload from disk."""
        with self._lock:
            self._cache = None

    @property
    def access_log(self) -> list[SecretAccessRecord]:
        with self._lock:
            return list(self._access_log)


class ChainedSecretProvider(SecretProvider):
    """Tries multiple providers in order (first match wins).

    Usage:
        provider = ChainedSecretProvider([
            EnvSecretProvider(prefix="MULLU_"),  # Check env first
            FileSecretProvider(path="secrets.json"),  # Fallback to file
        ])
    """

    def __init__(self, providers: list[SecretProvider]) -> None:
        self._providers = list(providers)

    def get(self, key: str, *, accessor: str = "") -> SecretValue | None:
        for provider in self._providers:
            result = provider.get(key, accessor=accessor)
            if result is not None:
                return result
        return None

    def exists(self, key: str) -> bool:
        return any(p.exists(key) for p in self._providers)

    def list_keys(self) -> list[str]:
        keys: set[str] = set()
        for p in self._providers:
            keys.update(p.list_keys())
        return sorted(keys)

    @property
    def provider_count(self) -> int:
        return len(self._providers)
