"""Purpose: verify server policy helper contracts for the governed server.
Governance scope: policy helper validation tests only.
Dependencies: server policy helpers, server import boundary, and pytest monkeypatch support.
Invariants: environment, backend, and CORS policy behavior stays bounded, deterministic, and auditable.
"""

from __future__ import annotations

import importlib

import pytest

from mcoi_runtime.app import server_policy


def test_env_flag_bounds_invalid_boolean_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCOI_TEST_FLAG", "sometimes")

    with pytest.raises(ValueError, match="^value must be a boolean flag$") as exc_info:
        server_policy._env_flag("MCOI_TEST_FLAG", {"MCOI_TEST_FLAG": "sometimes"})

    message = str(exc_info.value)
    assert message == "value must be a boolean flag"
    assert "MCOI_TEST_FLAG" not in message
    assert "boolean flag" in message


def test_db_backend_rejects_memory_in_production() -> None:
    with pytest.raises(
        RuntimeError,
        match="^MULLU_DB_BACKEND=memory is not allowed in production environment\\.",
    ) as exc_info:
        server_policy._validate_db_backend_for_env("memory", "production")

    message = str(exc_info.value)
    assert "postgresql" in message
    assert "production" in message


def test_db_backend_warns_for_unknown_non_dev_env() -> None:
    warning = server_policy._validate_db_backend_for_env("memory", "staging")
    assert warning is not None
    assert warning.startswith("MULLU_DB_BACKEND=memory in non-dev environment.")
    assert "postgresql" in warning


def test_resolve_cors_origins_uses_dev_defaults() -> None:
    origins = server_policy._resolve_cors_origins(None, "local_dev")
    assert origins == ["http://localhost:3000", "http://localhost:8080"]


def test_validate_cors_origins_rejects_empty_in_production() -> None:
    with pytest.raises(
        RuntimeError,
        match="^MULLU_CORS_ORIGINS must be set in pilot or production environment\\.",
    ) as exc_info:
        server_policy._validate_cors_origins_for_env([], "production")

    message = str(exc_info.value)
    assert "https://app.mullu.io" in message
    assert "*" not in message


def test_validate_cors_origins_warns_for_unknown_non_dev_env() -> None:
    warning = server_policy._validate_cors_origins_for_env([], "staging")
    assert warning is not None
    assert warning.startswith("MULLU_CORS_ORIGINS is empty in non-dev environment.")
    assert "https://app.mullu.io" in warning


def test_server_rejects_empty_cors_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MULLU_ENV", "production")
    monkeypatch.setenv("MULLU_DB_BACKEND", "postgresql")
    monkeypatch.delenv("MULLU_CORS_ORIGINS", raising=False)

    with pytest.raises(
        RuntimeError,
        match="^MULLU_CORS_ORIGINS must be set in pilot or production environment\\.",
    ):
        from mcoi_runtime.app import server as server_module

        importlib.reload(server_module)

    monkeypatch.setenv("MULLU_ENV", "local_dev")
    monkeypatch.setenv("MULLU_DB_BACKEND", "memory")
    monkeypatch.setenv(
        "MULLU_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:8080",
    )
    from mcoi_runtime.app import server as server_module

    importlib.reload(server_module)
