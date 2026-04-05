"""Purpose: verify SecretStore and SecretSerializer runtime behaviour.
Governance scope: secrets core engine tests only.
Dependencies: secrets contracts + core modules.
Invariants:
  - Register/resolve round-trip works with MaskedValue.
  - Expired and revoked secrets are detected correctly.
  - Clock injection produces deterministic results.
  - scan_for_secrets finds embedded values in nested dicts.
  - mask_secrets replaces secret values with masked placeholder.
  - Secret values never appear in repr of any contract.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from mcoi_runtime.contracts.secrets import (
    MaskedValue,
    SecretDescriptor,
    SecretReference,
    SecretSource,
    SecretStatus,
)
from mcoi_runtime.core.secrets import SecretSerializer, SecretStore


_FIXED_NOW = datetime(2026, 3, 19, 0, 0, 0, tzinfo=timezone.utc)
_FIXED_NOW_ISO = "2026-03-19T00:00:00+00:00"


def _make_clock(dt: datetime = _FIXED_NOW):
    return lambda: dt


def _make_descriptor(
    secret_id: str = "sec-1",
    scope_id: str = "scope-gh",
    provider_id: str | None = None,
    expires_at: str | None = None,
    status: SecretStatus = SecretStatus.ACTIVE,
) -> SecretDescriptor:
    return SecretDescriptor(
        secret_id=secret_id,
        source=SecretSource.ENVIRONMENT,
        scope_id=scope_id,
        created_at=_FIXED_NOW_ISO,
        status=status,
        provider_id=provider_id,
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# SecretStore
# ---------------------------------------------------------------------------

class TestSecretStoreRegisterResolve:

    def test_round_trip(self) -> None:
        store = SecretStore(clock=_make_clock())
        desc = _make_descriptor()
        ref = store.register_secret(desc, "ghp_token_abc123")
        assert isinstance(ref, SecretReference)
        assert ref.secret_id == "sec-1"
        assert ref.scope_id == "scope-gh"

        resolved = store.resolve(ref)
        assert isinstance(resolved, MaskedValue)
        assert resolved.reveal() == "ghp_token_abc123"

    def test_repr_never_leaks_value(self) -> None:
        store = SecretStore(clock=_make_clock())
        ref = store.register_secret(_make_descriptor(), "ghp_token_abc123")
        resolved = store.resolve(ref)
        assert "ghp_token_abc123" not in repr(resolved)
        assert "ghp_token_abc123" not in str(resolved)

    def test_duplicate_registration_rejected(self) -> None:
        store = SecretStore(clock=_make_clock())
        store.register_secret(_make_descriptor(), "val")
        with pytest.raises(ValueError, match="^secret already registered$") as exc_info:
            store.register_secret(_make_descriptor(), "val2")
        assert "sec-1" not in str(exc_info.value)

    def test_resolve_unknown_raises(self) -> None:
        store = SecretStore(clock=_make_clock())
        ref = SecretReference(secret_id="nope", scope_id="scope-gh")
        with pytest.raises(ValueError, match="^secret reference unavailable$") as exc_info:
            store.resolve(ref)
        assert "nope" not in str(exc_info.value)

    def test_scope_mismatch_raises(self) -> None:
        store = SecretStore(clock=_make_clock())
        store.register_secret(_make_descriptor(), "val")
        bad_ref = SecretReference(secret_id="sec-1", scope_id="wrong-scope")
        with pytest.raises(ValueError, match="scope_id mismatch"):
            store.resolve(bad_ref)


class TestSecretStoreExpiry:

    def test_not_expired_when_no_expiry(self) -> None:
        store = SecretStore(clock=_make_clock())
        ref = store.register_secret(_make_descriptor(), "val")
        assert store.is_expired(ref) is False

    def test_not_expired_before_deadline(self) -> None:
        store = SecretStore(clock=_make_clock())
        desc = _make_descriptor(expires_at="2026-04-19T00:00:00+00:00")
        ref = store.register_secret(desc, "val")
        assert store.is_expired(ref) is False

    def test_expired_after_deadline(self) -> None:
        future = _FIXED_NOW + timedelta(days=60)
        store = SecretStore(clock=_make_clock(future))
        desc = _make_descriptor(expires_at="2026-04-19T00:00:00+00:00")
        ref = store.register_secret(desc, "val")
        assert store.is_expired(ref) is True

    def test_expired_status_is_always_expired(self) -> None:
        store = SecretStore(clock=_make_clock())
        desc = _make_descriptor(status=SecretStatus.EXPIRED)
        ref = store.register_secret(desc, "val")
        assert store.is_expired(ref) is True

    def test_explicit_now_overrides_clock(self) -> None:
        store = SecretStore(clock=_make_clock())
        desc = _make_descriptor(expires_at="2026-04-01T00:00:00+00:00")
        ref = store.register_secret(desc, "val")
        future = datetime(2026, 5, 1, tzinfo=timezone.utc)
        assert store.is_expired(ref, now=future) is True


class TestSecretStoreRevocation:

    def test_revoke_marks_status(self) -> None:
        store = SecretStore(clock=_make_clock())
        store.register_secret(_make_descriptor(), "val")
        updated = store.revoke("sec-1")
        assert updated.status is SecretStatus.REVOKED

    def test_resolve_revoked_raises(self) -> None:
        store = SecretStore(clock=_make_clock())
        ref = store.register_secret(_make_descriptor(), "val")
        store.revoke("sec-1")
        with pytest.raises(ValueError, match="^secret unavailable$") as exc_info:
            store.resolve(ref)
        assert "sec-1" not in str(exc_info.value)

    def test_revoke_unknown_raises(self) -> None:
        store = SecretStore(clock=_make_clock())
        with pytest.raises(ValueError, match="^secret reference unavailable$") as exc_info:
            store.revoke("nope")
        assert "nope" not in str(exc_info.value)

    def test_missing_value_raises_bounded_error(self) -> None:
        store = SecretStore(clock=_make_clock())
        ref = store.register_secret(_make_descriptor(), "val")
        store._values.pop("sec-1")
        with pytest.raises(ValueError, match="^secret unavailable$") as exc_info:
            store.resolve(ref)
        assert "sec-1" not in str(exc_info.value)


class TestSecretStoreListExpiring:

    def test_lists_expiring_within_window(self) -> None:
        store = SecretStore(clock=_make_clock())
        # Expires in 10 days — within 30-day window
        desc_soon = _make_descriptor(
            secret_id="sec-soon",
            expires_at="2026-03-29T00:00:00+00:00",
        )
        # Expires in 60 days — outside 30-day window
        desc_far = _make_descriptor(
            secret_id="sec-far",
            expires_at="2026-05-18T00:00:00+00:00",
        )
        # No expiry
        desc_none = _make_descriptor(secret_id="sec-none")

        store.register_secret(desc_soon, "a")
        store.register_secret(desc_far, "b")
        store.register_secret(desc_none, "c")

        expiring = store.list_expiring(within_days=30)
        ids = [d.secret_id for d in expiring]
        assert "sec-soon" in ids
        assert "sec-far" not in ids
        assert "sec-none" not in ids

    def test_excludes_non_active(self) -> None:
        store = SecretStore(clock=_make_clock())
        desc = _make_descriptor(
            secret_id="sec-revoked",
            expires_at="2026-03-29T00:00:00+00:00",
            status=SecretStatus.REVOKED,
        )
        store.register_secret(desc, "x")
        assert store.list_expiring(within_days=30) == []


class TestSecretStoreClockDeterminism:

    def test_clock_injection(self) -> None:
        t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2026, 6, 1, tzinfo=timezone.utc)

        store1 = SecretStore(clock=_make_clock(t1))
        store2 = SecretStore(clock=_make_clock(t2))

        desc = _make_descriptor(expires_at="2026-03-01T00:00:00+00:00")
        ref1 = store1.register_secret(desc, "v")
        # Same descriptor re-created for store2
        desc2 = _make_descriptor(expires_at="2026-03-01T00:00:00+00:00")
        ref2 = store2.register_secret(desc2, "v")

        assert store1.is_expired(ref1) is False  # Jan 1 < Mar 1
        assert store2.is_expired(ref2) is True   # Jun 1 >= Mar 1


# ---------------------------------------------------------------------------
# SecretSerializer
# ---------------------------------------------------------------------------

class TestSecretSerializerScan:

    def test_finds_flat_secret(self) -> None:
        data = {"api_key": "tok_abc", "name": "safe"}
        paths = SecretSerializer.scan_for_secrets(data, {"tok_abc"})
        assert paths == ["api_key"]

    def test_finds_nested_secret(self) -> None:
        data = {"outer": {"inner": {"key": "tok_abc"}}}
        paths = SecretSerializer.scan_for_secrets(data, {"tok_abc"})
        assert paths == ["outer.inner.key"]

    def test_finds_secret_in_list(self) -> None:
        data = {"tokens": ["safe", "tok_abc", "also_safe"]}
        paths = SecretSerializer.scan_for_secrets(data, {"tok_abc"})
        assert paths == ["tokens[1]"]

    def test_multiple_occurrences(self) -> None:
        data = {"a": "tok_abc", "b": {"c": "tok_abc"}}
        paths = SecretSerializer.scan_for_secrets(data, {"tok_abc"})
        assert "a" in paths
        assert "b.c" in paths

    def test_empty_secrets_set(self) -> None:
        data = {"key": "value"}
        assert SecretSerializer.scan_for_secrets(data, set()) == []

    def test_no_match(self) -> None:
        data = {"key": "value"}
        assert SecretSerializer.scan_for_secrets(data, {"other"}) == []


class TestSecretSerializerMask:

    def test_masks_flat_secret(self) -> None:
        data = {"api_key": "tok_abc", "name": "safe"}
        masked = SecretSerializer.mask_secrets(data, {"tok_abc"})
        assert masked["api_key"] == "***MASKED***"
        assert masked["name"] == "safe"
        # Original unchanged
        assert data["api_key"] == "tok_abc"

    def test_masks_nested_secret(self) -> None:
        data = {"outer": {"inner": "tok_abc"}}
        masked = SecretSerializer.mask_secrets(data, {"tok_abc"})
        assert masked["outer"]["inner"] == "***MASKED***"

    def test_masks_secret_in_list(self) -> None:
        data = {"tokens": ["safe", "tok_abc"]}
        masked = SecretSerializer.mask_secrets(data, {"tok_abc"})
        assert masked["tokens"][0] == "safe"
        assert masked["tokens"][1] == "***MASKED***"

    def test_empty_secrets_returns_deep_copy(self) -> None:
        data = {"key": "value"}
        masked = SecretSerializer.mask_secrets(data, set())
        assert masked == data
        assert masked is not data


class TestSecretValueNeverInRepr:

    def test_descriptor_repr_no_secret(self) -> None:
        """SecretDescriptor never carries a value, so repr is safe by design."""
        desc = _make_descriptor()
        assert "ghp_token" not in repr(desc)

    def test_reference_repr_no_secret(self) -> None:
        ref = SecretReference(secret_id="sec-1", scope_id="scope-gh")
        assert "ghp_token" not in repr(ref)
        assert "secret" not in ref.to_json().lower() or "secret_id" in ref.to_json()

    def test_masked_value_repr(self) -> None:
        mv = MaskedValue("ghp_token_abc123")
        assert "ghp_token_abc123" not in repr(mv)
        assert "ghp_token_abc123" not in str(mv)
        assert "ghp_token_abc123" not in f"logged: {mv}"
