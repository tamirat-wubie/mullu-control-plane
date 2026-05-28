"""Tests for nested-mind control-plane integration helper.

Purpose: verify default-off and fail-closed environment selection for the
optional nested-mind connector.
Governance scope: startup boundary validation and explicit bootstrap posture.
Dependencies: nested_mind_integration helper only; server.py is not imported.
Invariants: unset/false env never constructs a connector; enabled env requires
a normalized HTTPS base URL.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcoi_runtime.app.nested_mind_integration import (
    NESTED_MIND_BASE_URL_ENV,
    NESTED_MIND_BEARER_TOKEN_ENV,
    NESTED_MIND_ENABLED_ENV,
    mount_nested_mind_connector_from_env,
    validate_nested_mind_base_url,
)


def _clock() -> str:
    return "2026-05-28T00:00:00+00:00"


@dataclass(frozen=True)
class FakeConnector:
    clock: object
    base_url: str
    bearer_token: str | None = None


def test_mount_returns_disabled_posture_when_flag_unset() -> None:
    bootstrap = mount_nested_mind_connector_from_env(
        runtime_env={},
        clock=_clock,
        connector_cls=FakeConnector,
    )

    assert bootstrap.connector is None
    assert bootstrap.enabled is False
    assert bootstrap.base_url == ""
    assert bootstrap.credential_configured is False


def test_mount_returns_disabled_posture_when_flag_false() -> None:
    bootstrap = mount_nested_mind_connector_from_env(
        runtime_env={NESTED_MIND_ENABLED_ENV: "false"},
        clock=_clock,
        connector_cls=FakeConnector,
    )

    assert bootstrap.connector is None
    assert bootstrap.enabled is False


def test_mount_fails_closed_when_enabled_without_base_url() -> None:
    with pytest.raises(RuntimeError, match=NESTED_MIND_BASE_URL_ENV):
        mount_nested_mind_connector_from_env(
            runtime_env={NESTED_MIND_ENABLED_ENV: "true"},
            clock=_clock,
            connector_cls=FakeConnector,
        )


def test_mount_constructs_connector_with_normalized_base_url_and_token() -> None:
    bootstrap = mount_nested_mind_connector_from_env(
        runtime_env={
            NESTED_MIND_ENABLED_ENV: "enabled",
            NESTED_MIND_BASE_URL_ENV: "https://Nested.Example/api/",
            NESTED_MIND_BEARER_TOKEN_ENV: " nested-token ",
        },
        clock=_clock,
        connector_cls=FakeConnector,
    )

    assert isinstance(bootstrap.connector, FakeConnector)
    assert bootstrap.enabled is True
    assert bootstrap.base_url == "https://nested.example/api"
    assert bootstrap.credential_configured is True
    assert bootstrap.connector.base_url == "https://nested.example/api"
    assert bootstrap.connector.bearer_token == "nested-token"


def test_validate_rejects_non_https_base_url() -> None:
    with pytest.raises(RuntimeError, match="must use https"):
        validate_nested_mind_base_url("http://nested.example")


def test_validate_rejects_missing_host() -> None:
    with pytest.raises(RuntimeError, match="must include a host"):
        validate_nested_mind_base_url("https://")


def test_validate_rejects_credentials() -> None:
    with pytest.raises(RuntimeError, match="must not include credentials"):
        validate_nested_mind_base_url("https://user:pass@nested.example")


@pytest.mark.parametrize(
    "url",
    [
        "https://nested.example?x=1",
        "https://nested.example#fragment",
        "https://nested.example/path;param",
    ],
)
def test_validate_rejects_query_fragment_or_params(url: str) -> None:
    with pytest.raises(RuntimeError, match="must not include params"):
        validate_nested_mind_base_url(url)
