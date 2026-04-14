"""Phase 2B — Field-Level Encryption tests.

Tests: FieldEncryptor encrypt/decrypt, key providers, token format,
    integrity verification, key rotation support.
"""

import base64
import os

import pytest
from mcoi_runtime.core.field_encryption import (
    EnvKeyProvider,
    FieldEncryptor,
    StaticKeyProvider,
)


# ═══ Test Fixtures ═══


def _test_key(seed: int = 1) -> bytes:
    """Generate a deterministic 32-byte test key."""
    return bytes([seed] * 32)


def _provider(keys: dict[str, bytes] | None = None, current: str = "k1") -> StaticKeyProvider:
    if keys is None:
        keys = {"k1": _test_key(1), "k2": _test_key(2)}
    return StaticKeyProvider(keys, current)


def _encryptor(provider: StaticKeyProvider | None = None) -> FieldEncryptor:
    return FieldEncryptor(provider or _provider(), allow_hmac_fallback=True)


# ═══ StaticKeyProvider ═══


class TestStaticKeyProvider:
    def test_get_current_key(self):
        p = _provider()
        assert p.get_key("k1") is not None
        assert len(p.get_key("k1")) == 32

    def test_get_missing_key(self):
        p = _provider()
        assert p.get_key("nonexistent") is None

    def test_current_key_id(self):
        p = _provider(current="k2")
        assert p.current_key_id() == "k2"

    def test_invalid_current_raises(self):
        with pytest.raises(ValueError, match="^current encryption key must exist in keys$") as exc_info:
            StaticKeyProvider({"k1": _test_key()}, "missing")
        assert "missing" not in str(exc_info.value)

    def test_multiple_keys(self):
        p = _provider()
        assert p.get_key("k1") is not None
        assert p.get_key("k2") is not None


# ═══ EnvKeyProvider ═══


class TestEnvKeyProvider:
    def test_available_when_key_set(self, monkeypatch):
        key = _test_key()
        monkeypatch.setenv("MULLU_ENCRYPTION_KEY", base64.b64encode(key).decode())
        p = EnvKeyProvider()
        assert p.available
        assert p.current_key_id() != ""
        assert p.get_key(p.current_key_id()) == key

    def test_unavailable_when_not_set(self, monkeypatch):
        monkeypatch.delenv("MULLU_ENCRYPTION_KEY", raising=False)
        p = EnvKeyProvider()
        assert not p.available
        assert p.current_key_id() == ""

    def test_wrong_key_length_raises(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENCRYPTION_KEY", base64.b64encode(b"short").decode())
        with pytest.raises(ValueError, match="^encryption key must decode to exactly 32 bytes$") as exc_info:
            EnvKeyProvider()
        assert "MULLU_ENCRYPTION_KEY" not in str(exc_info.value)
        assert "5" not in str(exc_info.value)

    def test_custom_env_var(self, monkeypatch):
        key = _test_key()
        monkeypatch.setenv("MY_KEY", base64.b64encode(key).decode())
        p = EnvKeyProvider("MY_KEY")
        assert p.available


# ═══ FieldEncryptor — Encrypt/Decrypt ═══


class TestFieldEncryptorRoundtrip:
    def test_encrypt_decrypt_roundtrip(self):
        enc = _encryptor()
        plaintext = "sensitive tenant data"
        token = enc.encrypt(plaintext)
        result = enc.decrypt(token)
        assert result == plaintext

    def test_empty_string(self):
        enc = _encryptor()
        token = enc.encrypt("")
        assert enc.decrypt(token) == ""

    def test_unicode_content(self):
        enc = _encryptor()
        plaintext = "Hello, World! \u2603 \u00e9\u00e8\u00ea"
        token = enc.encrypt(plaintext)
        assert enc.decrypt(token) == plaintext

    def test_large_content(self):
        enc = _encryptor()
        plaintext = "A" * 10000
        token = enc.encrypt(plaintext)
        assert enc.decrypt(token) == plaintext

    def test_json_content(self):
        enc = _encryptor()
        import json
        data = json.dumps({"key": "value", "nested": {"a": 1}})
        token = enc.encrypt(data)
        assert enc.decrypt(token) == data


# ═══ Token Format ═══


class TestTokenFormat:
    def test_token_has_three_parts(self):
        enc = _encryptor()
        token = enc.encrypt("test")
        parts = token.split(":")
        assert len(parts) == 3

    def test_token_starts_with_key_id(self):
        enc = _encryptor()
        token = enc.encrypt("test")
        key_id = token.split(":")[0]
        assert key_id == "k1"

    def test_nonce_is_base64(self):
        enc = _encryptor()
        token = enc.encrypt("test")
        nonce_b64 = token.split(":")[1]
        nonce = base64.b64decode(nonce_b64)
        assert len(nonce) == 12  # 96-bit nonce

    def test_unique_nonces(self):
        enc = _encryptor()
        tokens = [enc.encrypt("same") for _ in range(10)]
        nonces = [t.split(":")[1] for t in tokens]
        assert len(set(nonces)) == 10  # All unique

    def test_is_encrypted_detection(self):
        enc = _encryptor()
        token = enc.encrypt("test")
        assert enc.is_encrypted(token)
        assert not enc.is_encrypted("plain text")
        assert not enc.is_encrypted("only:two")
        assert not enc.is_encrypted("not:valid:base64!!!")


# ═══ Error Cases ═══


class TestEncryptionErrors:
    def test_no_key_available(self):
        p = StaticKeyProvider({"k1": _test_key()}, "k1")
        enc = FieldEncryptor(p, allow_hmac_fallback=True)
        # Override to simulate no current key
        p._current = ""
        with pytest.raises(ValueError, match="no encryption key"):
            enc.encrypt("test")

    def test_decrypt_invalid_format(self):
        enc = _encryptor()
        with pytest.raises(ValueError, match="invalid"):
            enc.decrypt("not-a-token")

    def test_decrypt_unknown_key(self):
        enc = _encryptor()
        token = enc.encrypt("test")
        # Replace key_id with unknown
        parts = token.split(":")
        tampered = f"unknown:{parts[1]}:{parts[2]}"
        with pytest.raises(ValueError, match="^decryption key not found$") as exc_info:
            enc.decrypt(tampered)
        assert "unknown" not in str(exc_info.value)

    def test_decrypt_tampered_ciphertext(self):
        enc = _encryptor()
        token = enc.encrypt("test")
        parts = token.split(":")
        # Tamper with ciphertext
        ct = base64.b64decode(parts[2])
        tampered_ct = bytes([b ^ 0xFF for b in ct])
        tampered = f"{parts[0]}:{parts[1]}:{base64.b64encode(tampered_ct).decode()}"
        with pytest.raises(ValueError) as exc_info:
            enc.decrypt(tampered)
        assert "decryption failed:" not in str(exc_info.value)

    def test_encrypt_missing_current_key_is_bounded(self):
        p = StaticKeyProvider({"k1": _test_key()}, "k1")
        enc = FieldEncryptor(p, allow_hmac_fallback=True)
        p._keys.pop("k1")
        with pytest.raises(ValueError, match="^encryption key not found$") as exc_info:
            enc.encrypt("test")
        assert "k1" not in str(exc_info.value)


# ═══ Key Rotation ═══


class TestKeyRotation:
    def test_decrypt_with_old_key(self):
        p = _provider(current="k1")
        enc = FieldEncryptor(p, allow_hmac_fallback=True)
        token = enc.encrypt("secret")
        # Switch to k2 for new encryptions
        p._current = "k2"
        # Should still decrypt with k1
        assert enc.decrypt(token) == "secret"

    def test_new_encryptions_use_current_key(self):
        p = _provider(current="k1")
        enc = FieldEncryptor(p, allow_hmac_fallback=True)
        token1 = enc.encrypt("test")
        assert token1.startswith("k1:")
        p._current = "k2"
        token2 = enc.encrypt("test")
        assert token2.startswith("k2:")

    def test_cross_key_roundtrip(self):
        p = _provider(current="k1")
        enc = FieldEncryptor(p, allow_hmac_fallback=True)
        token_k1 = enc.encrypt("data-k1")
        p._current = "k2"
        token_k2 = enc.encrypt("data-k2")
        # Both should decrypt successfully
        assert enc.decrypt(token_k1) == "data-k1"
        assert enc.decrypt(token_k2) == "data-k2"
