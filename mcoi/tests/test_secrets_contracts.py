"""Purpose: verify secret lifecycle contracts enforce invariants.
Governance scope: secrets contract tests only.
Dependencies: secrets contracts module.
Invariants:
  - SecretDescriptor validates required fields.
  - SecretReference never carries an actual secret value.
  - MaskedValue hides the real value in repr/str; reveal() exposes it.
  - SecretPolicy defaults enforce strictest posture.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.secrets import (
    MaskedValue,
    SecretDescriptor,
    SecretPolicy,
    SecretReference,
    SecretSource,
    SecretStatus,
)


_NOW = "2026-03-19T00:00:00+00:00"


# ---------------------------------------------------------------------------
# SecretDescriptor
# ---------------------------------------------------------------------------

class TestSecretDescriptor:

    def test_construction_minimal(self) -> None:
        desc = SecretDescriptor(
            secret_id="sec-1",
            source=SecretSource.ENVIRONMENT,
            scope_id="scope-gh",
            created_at=_NOW,
        )
        assert desc.secret_id == "sec-1"
        assert desc.source is SecretSource.ENVIRONMENT
        assert desc.scope_id == "scope-gh"
        assert desc.status is SecretStatus.ACTIVE
        assert desc.provider_id is None
        assert desc.expires_at is None

    def test_construction_full(self) -> None:
        desc = SecretDescriptor(
            secret_id="sec-2",
            source=SecretSource.VAULT,
            scope_id="scope-aws",
            created_at=_NOW,
            status=SecretStatus.ROTATION_PENDING,
            provider_id="provider-aws",
            expires_at="2026-04-19T00:00:00+00:00",
        )
        assert desc.provider_id == "provider-aws"
        assert desc.expires_at == "2026-04-19T00:00:00+00:00"
        assert desc.status is SecretStatus.ROTATION_PENDING

    def test_rejects_empty_secret_id(self) -> None:
        with pytest.raises(ValueError, match="secret_id"):
            SecretDescriptor(
                secret_id="",
                source=SecretSource.FILE,
                scope_id="scope-x",
                created_at=_NOW,
            )

    def test_rejects_empty_scope_id(self) -> None:
        with pytest.raises(ValueError, match="scope_id"):
            SecretDescriptor(
                secret_id="sec-1",
                source=SecretSource.FILE,
                scope_id="  ",
                created_at=_NOW,
            )

    def test_rejects_invalid_source(self) -> None:
        with pytest.raises(ValueError, match="source"):
            SecretDescriptor(
                secret_id="sec-1",
                source="not_a_source",  # type: ignore[arg-type]
                scope_id="scope-x",
                created_at=_NOW,
            )

    def test_frozen(self) -> None:
        desc = SecretDescriptor(
            secret_id="sec-1",
            source=SecretSource.ENVIRONMENT,
            scope_id="scope-x",
            created_at=_NOW,
        )
        with pytest.raises(AttributeError):
            desc.secret_id = "changed"  # type: ignore[misc]

    def test_to_dict_round_trip(self) -> None:
        desc = SecretDescriptor(
            secret_id="sec-1",
            source=SecretSource.OPERATOR_INPUT,
            scope_id="scope-x",
            created_at=_NOW,
        )
        d = desc.to_dict()
        assert d["secret_id"] == "sec-1"
        assert d["source"] == "operator_input"


# ---------------------------------------------------------------------------
# SecretReference
# ---------------------------------------------------------------------------

class TestSecretReference:

    def test_construction(self) -> None:
        ref = SecretReference(secret_id="sec-1", scope_id="scope-x")
        assert ref.secret_id == "sec-1"
        assert ref.scope_id == "scope-x"

    def test_has_no_value_field(self) -> None:
        ref = SecretReference(secret_id="sec-1", scope_id="scope-x")
        assert not hasattr(ref, "value")
        assert not hasattr(ref, "_value")
        assert not hasattr(ref, "secret_value")
        d = ref.to_dict()
        assert "value" not in d

    def test_rejects_empty_ids(self) -> None:
        with pytest.raises(ValueError, match="secret_id"):
            SecretReference(secret_id="", scope_id="scope-x")
        with pytest.raises(ValueError, match="scope_id"):
            SecretReference(secret_id="sec-1", scope_id="")

    def test_frozen(self) -> None:
        ref = SecretReference(secret_id="sec-1", scope_id="scope-x")
        with pytest.raises(AttributeError):
            ref.secret_id = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MaskedValue
# ---------------------------------------------------------------------------

class TestMaskedValue:

    def test_repr_is_masked(self) -> None:
        mv = MaskedValue("super-secret-token")
        assert repr(mv) == "***MASKED***"

    def test_str_is_masked(self) -> None:
        mv = MaskedValue("super-secret-token")
        assert str(mv) == "***MASKED***"

    def test_format_is_masked(self) -> None:
        mv = MaskedValue("super-secret-token")
        assert f"{mv}" == "***MASKED***"
        assert format(mv, "") == "***MASKED***"

    def test_reveal_returns_actual(self) -> None:
        mv = MaskedValue("super-secret-token")
        assert mv.reveal() == "super-secret-token"

    def test_immutable(self) -> None:
        mv = MaskedValue("x")
        with pytest.raises(AttributeError, match="immutable"):
            mv.value = "y"  # type: ignore[attr-defined]
        with pytest.raises(AttributeError, match="immutable"):
            del mv._MaskedValue__value  # type: ignore[attr-defined]

    def test_equality(self) -> None:
        a = MaskedValue("tok")
        b = MaskedValue("tok")
        c = MaskedValue("other")
        assert a == b
        assert a != c

    def test_hashable(self) -> None:
        a = MaskedValue("tok")
        b = MaskedValue("tok")
        assert hash(a) == hash(b)
        assert len({a, b}) == 1

    def test_rejects_non_string(self) -> None:
        with pytest.raises(TypeError, match="str"):
            MaskedValue(12345)  # type: ignore[arg-type]

    def test_secret_not_in_fstring(self) -> None:
        mv = MaskedValue("do-not-leak")
        msg = f"The credential is {mv}"
        assert "do-not-leak" not in msg
        assert "***MASKED***" in msg


# ---------------------------------------------------------------------------
# SecretPolicy
# ---------------------------------------------------------------------------

class TestSecretPolicy:

    def test_defaults(self) -> None:
        policy = SecretPolicy(policy_id="pol-1")
        assert policy.never_persist is True
        assert policy.never_log is True
        assert policy.mask_in_errors is True
        assert policy.rotation_warning_days == 30

    def test_custom_values(self) -> None:
        policy = SecretPolicy(
            policy_id="pol-2",
            never_persist=False,
            never_log=False,
            mask_in_errors=False,
            rotation_warning_days=7,
        )
        assert policy.never_persist is False
        assert policy.rotation_warning_days == 7

    def test_rejects_empty_policy_id(self) -> None:
        with pytest.raises(ValueError, match="policy_id"):
            SecretPolicy(policy_id="")

    def test_rejects_negative_rotation_days(self) -> None:
        with pytest.raises(ValueError, match="rotation_warning_days"):
            SecretPolicy(policy_id="pol-1", rotation_warning_days=-1)

    def test_frozen(self) -> None:
        policy = SecretPolicy(policy_id="pol-1")
        with pytest.raises(AttributeError):
            policy.never_persist = False  # type: ignore[misc]
