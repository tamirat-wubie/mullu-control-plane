"""Phase 2B — Field-Level Encryption at Rest.

Purpose: AES-256-GCM encryption for sensitive data fields stored in PostgreSQL.
    Provides a KeyProvider abstraction for key management and rotation.
Governance scope: data confidentiality only.
Dependencies: stdlib (os, base64, hashlib, hmac). Optional: cryptography (for AES-GCM).
Invariants:
  - Encryption keys are never stored in the database.
  - Each encrypted value includes key_id for rotation support.
  - Nonces are unique per encryption (random 12 bytes).
  - Decryption verifies authenticity (GCM tag or HMAC).
  - Fallback to HMAC-SHA256 integrity mode if cryptography is unavailable.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from typing import Any, Protocol, runtime_checkable

_log = logging.getLogger(__name__)


@runtime_checkable
class KeyProvider(Protocol):
    """Protocol for encryption key management.

    Implementations provide keys by ID and indicate which key is current.
    Supports key rotation: encrypt with current key, decrypt with any known key.
    """

    def get_key(self, key_id: str) -> bytes | None:
        """Get encryption key by ID. Returns None if key not found."""
        ...

    def current_key_id(self) -> str:
        """ID of the current encryption key (used for new encryptions)."""
        ...


class EnvKeyProvider:
    """Key provider that reads a single key from an environment variable.

    Key format: base64-encoded 32-byte key in MULLU_ENCRYPTION_KEY env var.
    Key ID is derived from the key hash (first 8 hex chars of SHA-256).

    WARNING: Environment variables are visible in process listings and container
    logs. For production, use a dedicated key management service (AWS KMS,
    HashiCorp Vault, GCP KMS) instead of environment variables.
    """

    def __init__(self, env_var: str = "MULLU_ENCRYPTION_KEY") -> None:
        raw = os.environ.get(env_var, "")
        if raw:
            self._key = base64.b64decode(raw)
            if len(self._key) != 32:
                raise ValueError("encryption key must decode to exactly 32 bytes")
            self._key_id = hashlib.sha256(self._key).hexdigest()[:8]
            _log.warning(
                "EnvKeyProvider loaded encryption key from environment variable %s. "
                "For production, use a dedicated KMS (AWS KMS, HashiCorp Vault).",
                env_var,
            )
        else:
            self._key = b""
            self._key_id = ""

    def get_key(self, key_id: str) -> bytes | None:
        if key_id == self._key_id and self._key:
            return self._key
        return None

    def current_key_id(self) -> str:
        return self._key_id

    @property
    def available(self) -> bool:
        return bool(self._key)


class StaticKeyProvider:
    """Key provider with statically configured keys. Useful for testing."""

    def __init__(self, keys: dict[str, bytes], current: str) -> None:
        if current not in keys:
            raise ValueError("current encryption key must exist in keys")
        self._keys = keys
        self._current = current

    def get_key(self, key_id: str) -> bytes | None:
        return self._keys.get(key_id)

    def current_key_id(self) -> str:
        return self._current


class FieldEncryptor:
    """Field-level encryptor using AES-256-GCM.

    Encrypts string values into tokens: "key_id:nonce_b64:ciphertext_b64"
    Decrypts tokens back to plaintext strings.

    If the `cryptography` library is unavailable:
      - By default, encrypt/decrypt raise RuntimeError (fail-closed).
      - Pass allow_hmac_fallback=True for HMAC-SHA256 integrity-only mode
        (test/dev only — data is NOT encrypted, only tamper-evident).
    """

    def __init__(self, key_provider: KeyProvider, *,
                 allow_hmac_fallback: bool = False) -> None:
        self._provider = key_provider
        self._allow_hmac_fallback = allow_hmac_fallback
        self._aes_available = False
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
            self._aes_available = True
        except ImportError:
            if not allow_hmac_fallback:
                _log.warning(
                    "cryptography library not installed. FieldEncryptor will "
                    "raise RuntimeError on encrypt/decrypt. Install it for "
                    "production: pip install cryptography"
                )

    @property
    def aes_available(self) -> bool:
        return self._aes_available

    @property
    def provider(self) -> KeyProvider:
        return self._provider

    def encrypt(self, plaintext: str, *, aad: str = "") -> str:
        """Encrypt a string field value.

        Returns a token string: "key_id:nonce_b64:ciphertext_b64"
        The token is safe to store in a TEXT database column.

        Args:
            plaintext: The string to encrypt.
            aad: Additional Authenticated Data (e.g., "field_name:record_id").
                 Binds the ciphertext to its context — prevents moving encrypted
                 values between fields/records. Must be supplied at decrypt time.
        """
        key_id = self._provider.current_key_id()
        if not key_id:
            raise ValueError("no encryption key available")
        key = self._provider.get_key(key_id)
        if key is None:
            raise ValueError("encryption key not found")

        plaintext_bytes = plaintext.encode("utf-8")
        nonce = os.urandom(12)
        aad_bytes = aad.encode("utf-8") if aad else None

        if self._aes_available:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, aad_bytes)
        elif self._allow_hmac_fallback:
            # HMAC integrity-only mode (NOT encryption — test/dev only)
            tag = hmac.new(key, nonce + plaintext_bytes, hashlib.sha256).digest()
            ciphertext = plaintext_bytes + tag
        else:
            raise RuntimeError(
                "field encryption requires the 'cryptography' library. "
                "Install it: pip install cryptography"
            )

        nonce_b64 = base64.b64encode(nonce).decode("ascii")
        ct_b64 = base64.b64encode(ciphertext).decode("ascii")
        return f"{key_id}:{nonce_b64}:{ct_b64}"

    def decrypt(self, token: str, *, aad: str = "") -> str:
        """Decrypt a token string back to plaintext.

        Raises ValueError if the token is malformed, the key is missing,
        or authentication/integrity check fails.

        Args:
            token: The encrypted token string.
            aad: Additional Authenticated Data — must match the value used
                 during encryption. Pass empty string if none was used.
        """
        parts = token.split(":")
        if len(parts) != 3:
            raise ValueError("invalid encryption token format")

        key_id, nonce_b64, ct_b64 = parts
        key = self._provider.get_key(key_id)
        if key is None:
            raise ValueError("decryption key not found")

        nonce = base64.b64decode(nonce_b64)
        ciphertext = base64.b64decode(ct_b64)
        aad_bytes = aad.encode("utf-8") if aad else None

        if self._aes_available:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(key)
            try:
                plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, aad_bytes)
            except Exception as exc:
                raise ValueError("decryption failed") from exc
        elif self._allow_hmac_fallback:
            # HMAC integrity-only mode (NOT encryption — test/dev only)
            if len(ciphertext) < 32:
                raise ValueError("ciphertext too short for HMAC tag")
            plaintext_bytes = ciphertext[:-32]
            stored_tag = ciphertext[-32:]
            expected_tag = hmac.new(key, nonce + plaintext_bytes, hashlib.sha256).digest()
            if not hmac.compare_digest(stored_tag, expected_tag):
                raise ValueError("integrity check failed: data may have been tampered with")
        else:
            raise RuntimeError(
                "field decryption requires the 'cryptography' library. "
                "Install it: pip install cryptography"
            )

        return plaintext_bytes.decode("utf-8")

    def is_encrypted(self, value: str) -> bool:
        """Check if a string value looks like an encrypted token."""
        parts = value.split(":")
        if len(parts) != 3:
            return False
        key_id, nonce_b64, ct_b64 = parts
        try:
            base64.b64decode(nonce_b64)
            base64.b64decode(ct_b64)
            return True
        except Exception:
            return False
