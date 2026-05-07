"""Purpose: in-memory secret store and pre-persistence secret scanner.
Governance scope: secret lifecycle engine (register, resolve, expire, revoke, scan).
Dependencies: secrets contracts module.
Invariants:
  - Actual secret values live only in memory; never persisted.
  - All time comparisons use an injected clock for determinism.
  - scan_for_secrets / mask_secrets operate on arbitrary nested dicts.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Callable

from mcoi_runtime.contracts.secrets import (
    MaskedValue,
    SecretDescriptor,
    SecretReference,
    SecretStatus,
    _MASKED_DISPLAY,
)


# ---------------------------------------------------------------------------
# SecretStore — in-memory vault
# ---------------------------------------------------------------------------

class SecretStore:
    """Register, resolve, and lifecycle-manage secrets without persistence.

    Parameters
    ----------
    clock : callable returning a ``datetime``
        Injected for deterministic testing.  Defaults to ``datetime.now(timezone.utc)``.
    """

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._descriptors: dict[str, SecretDescriptor] = {}
        self._values: dict[str, MaskedValue] = {}

    # -- mutators ----------------------------------------------------------

    def register_secret(self, descriptor: SecretDescriptor, value: str) -> SecretReference:
        """Store a secret and return a safe reference handle."""
        if not isinstance(descriptor, SecretDescriptor):
            raise TypeError("descriptor must be a SecretDescriptor")
        if not isinstance(value, str) or not value:
            raise ValueError("value must be a non-empty string")
        if descriptor.secret_id in self._descriptors:
            raise ValueError("secret already registered")

        self._descriptors[descriptor.secret_id] = descriptor
        self._values[descriptor.secret_id] = MaskedValue(value)
        return SecretReference(secret_id=descriptor.secret_id, scope_id=descriptor.scope_id)

    def revoke(self, secret_id: str) -> SecretDescriptor:
        """Mark a secret as revoked and remove its value from memory."""
        desc = self._get_descriptor(secret_id)
        revoked = SecretDescriptor(
            secret_id=desc.secret_id,
            source=desc.source,
            scope_id=desc.scope_id,
            created_at=desc.created_at,
            status=SecretStatus.REVOKED,
            provider_id=desc.provider_id,
            expires_at=desc.expires_at,
        )
        self._descriptors[secret_id] = revoked
        self._values.pop(secret_id, None)
        return revoked

    # -- queries -----------------------------------------------------------

    def resolve(self, reference: SecretReference) -> MaskedValue:
        """Return the MaskedValue for a reference, or raise."""
        if not isinstance(reference, SecretReference):
            raise TypeError("reference must be a SecretReference")
        desc = self._get_descriptor(reference.secret_id)
        if desc.scope_id != reference.scope_id:
            raise ValueError("scope_id mismatch")
        if desc.status is SecretStatus.REVOKED:
            raise ValueError("secret unavailable")
        if reference.secret_id not in self._values:
            raise ValueError("secret unavailable")
        return self._values[reference.secret_id]

    def is_expired(self, reference: SecretReference, now: datetime | None = None) -> bool:
        """Check whether a secret's expiry timestamp has passed."""
        desc = self._get_descriptor(reference.secret_id)
        if desc.status is SecretStatus.EXPIRED:
            return True
        if desc.expires_at is None:
            return False
        effective_now = now or self._clock()
        expires = datetime.fromisoformat(desc.expires_at.replace("Z", "+00:00"))
        return effective_now >= expires

    def list_expiring(self, within_days: int, now: datetime | None = None) -> list[SecretDescriptor]:
        """Return descriptors for secrets expiring within *within_days* of *now*."""
        effective_now = now or self._clock()
        results: list[SecretDescriptor] = []
        for desc in self._descriptors.values():
            if desc.status is not SecretStatus.ACTIVE:
                continue
            if desc.expires_at is None:
                continue
            expires = datetime.fromisoformat(desc.expires_at.replace("Z", "+00:00"))
            from datetime import timedelta
            if effective_now <= expires <= effective_now + timedelta(days=within_days):
                results.append(desc)
        return results

    # -- internal ----------------------------------------------------------

    def _get_descriptor(self, secret_id: str) -> SecretDescriptor:
        try:
            return self._descriptors[secret_id]
        except KeyError:
            raise ValueError("secret reference unavailable") from None


# ---------------------------------------------------------------------------
# SecretSerializer — pre-persistence scanning
# ---------------------------------------------------------------------------

class SecretSerializer:
    """Scan and mask secret values in arbitrary nested dicts.

    Intended to run before any persistence write to guarantee no secret
    material leaks into serialized artifacts.
    """

    @staticmethod
    def scan_for_secrets(data: dict[str, Any], secrets: set[str]) -> list[str]:
        """Return dotted field paths where any value in *secrets* appears.

        Recursively walks dicts and lists.
        """
        if not secrets:
            return []
        found: list[str] = []
        SecretSerializer._walk(data, secrets, "", found)
        return sorted(found)

    @staticmethod
    def mask_secrets(data: dict[str, Any], secrets: set[str]) -> dict[str, Any]:
        """Return a deep copy of *data* with every occurrence of a secret replaced."""
        if not secrets:
            return copy.deepcopy(data)
        return SecretSerializer._mask_node(data, secrets)  # type: ignore[return-value]

    # -- recursive helpers -------------------------------------------------

    @staticmethod
    def _walk(node: Any, secrets: set[str], prefix: str, found: list[str]) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                path = f"{prefix}.{key}" if prefix else key
                SecretSerializer._walk(value, secrets, path, found)
        elif isinstance(node, (list, tuple)):
            for idx, value in enumerate(node):
                path = f"{prefix}[{idx}]"
                SecretSerializer._walk(value, secrets, path, found)
        elif isinstance(node, str) and node in secrets:
            found.append(prefix)

    @staticmethod
    def _mask_node(node: Any, secrets: set[str]) -> Any:
        if isinstance(node, dict):
            return {k: SecretSerializer._mask_node(v, secrets) for k, v in node.items()}
        if isinstance(node, list):
            return [SecretSerializer._mask_node(v, secrets) for v in node]
        if isinstance(node, tuple):
            return tuple(SecretSerializer._mask_node(v, secrets) for v in node)
        if isinstance(node, str) and node in secrets:
            return _MASKED_DISPLAY
        return node
