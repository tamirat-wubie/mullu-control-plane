"""Purpose: verify bootstrap and context helper contracts for the governed server.
Governance scope: bootstrap helper validation tests only.
Dependencies: server bootstrap helpers with pytest support.
Invariants: bootstrap wiring remains deterministic, bounded, and auditable.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from mcoi_runtime.app import server_bootstrap


def test_utc_clock_returns_parseable_utc_timestamp() -> None:
    value = server_bootstrap.utc_clock()
    parsed = datetime.fromisoformat(value)

    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_init_field_encryption_from_env_without_key_is_disabled() -> None:
    encryptor, state = server_bootstrap.init_field_encryption_from_env(
        env={},
        bounded_bootstrap_warning=lambda context, exc: f"{context} failed ({type(exc).__name__})",
    )

    assert encryptor is None
    assert state == {
        "configured": False,
        "enabled": False,
        "aes_available": False,
        "warning": "",
    }


def test_init_field_encryption_from_env_bounds_invalid_key() -> None:
    def raise_invalid_key():
        raise ValueError("secret bootstrap detail")

    encryptor, state = server_bootstrap.init_field_encryption_from_env(
        env={"MULLU_ENCRYPTION_KEY": "c2hvcnQ="},
        bounded_bootstrap_warning=lambda context, exc: f"{context} failed ({type(exc).__name__})",
        key_provider_factory=raise_invalid_key,
    )

    assert encryptor is None
    assert state["configured"] is True
    assert state["enabled"] is False
    assert state["aes_available"] is False
    assert state["warning"] == "field encryption failed (ValueError)"


def test_validate_field_encryption_posture_rejects_production_postgres_without_encryption() -> None:
    with pytest.raises(
        RuntimeError,
        match="^Production PostgreSQL deployments require field encryption to be enabled\\.$",
    ):
        server_bootstrap.validate_field_encryption_posture(
            env="production",
            db_backend="postgresql",
            field_encryption_bootstrap={"enabled": False},
        )


def test_validate_field_encryption_posture_allows_production_postgres_with_encryption() -> None:
    server_bootstrap.validate_field_encryption_posture(
        env="production",
        db_backend="postgresql",
        field_encryption_bootstrap={"enabled": True},
    )
