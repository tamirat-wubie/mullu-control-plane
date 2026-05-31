"""Tests for nested-mind observation submitter environment mounting.

Purpose: verify default-off and fail-closed bootstrap for live record_observation
submission.
Governance scope: operator flag gating, base URL validation, and credential
posture only.
Dependencies: nested_mind_integration helper.
Invariants: submitter construction requires all gates and never exposes token
values in the bootstrap record.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcoi_runtime.app.nested_mind_integration import (
    NESTED_MIND_BASE_URL_ENV,
    NESTED_MIND_BEARER_TOKEN_ENV,
    NESTED_MIND_ENABLED_ENV,
    NESTED_MIND_OBSERVATION_BRIDGE_ENABLED_ENV,
    NESTED_MIND_OBSERVATION_SUBMIT_ENABLED_ENV,
    mount_nested_mind_observation_submitter_from_env,
)


def _clock() -> str:
    return "2026-05-31T00:00:00+00:00"


@dataclass(frozen=True)
class FakeSubmitter:
    clock: object
    base_url: str
    bearer_token: str | None = None


def test_submitter_default_off() -> None:
    bootstrap = mount_nested_mind_observation_submitter_from_env(
        runtime_env={},
        clock=_clock,
        submitter_cls=FakeSubmitter,
    )

    assert bootstrap.submitter is None
    assert bootstrap.enabled is False
    assert bootstrap.base_url == ""
    assert bootstrap.credential_configured is False


def test_submit_flag_true_requires_nested_mind_enabled() -> None:
    with pytest.raises(RuntimeError, match=NESTED_MIND_ENABLED_ENV):
        mount_nested_mind_observation_submitter_from_env(
            runtime_env={NESTED_MIND_OBSERVATION_SUBMIT_ENABLED_ENV: "true"},
            clock=_clock,
            submitter_cls=FakeSubmitter,
        )


def test_submit_flag_true_requires_observation_bridge_enabled() -> None:
    with pytest.raises(RuntimeError, match=NESTED_MIND_OBSERVATION_BRIDGE_ENABLED_ENV):
        mount_nested_mind_observation_submitter_from_env(
            runtime_env={
                NESTED_MIND_ENABLED_ENV: "true",
                NESTED_MIND_OBSERVATION_SUBMIT_ENABLED_ENV: "true",
            },
            clock=_clock,
            submitter_cls=FakeSubmitter,
        )


def test_submit_flag_true_requires_https_base_url() -> None:
    with pytest.raises(RuntimeError, match="must use https"):
        mount_nested_mind_observation_submitter_from_env(
            runtime_env={
                NESTED_MIND_ENABLED_ENV: "true",
                NESTED_MIND_OBSERVATION_BRIDGE_ENABLED_ENV: "true",
                NESTED_MIND_OBSERVATION_SUBMIT_ENABLED_ENV: "true",
                NESTED_MIND_BASE_URL_ENV: "http://nested.example",
            },
            clock=_clock,
            submitter_cls=FakeSubmitter,
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "https://nested.example?x=1",
        "https://nested.example#frag",
        "https://operator:secret@nested.example",
    ],
)
def test_submit_flag_true_rejects_query_fragment_or_credentials(base_url: str) -> None:
    with pytest.raises(RuntimeError):
        mount_nested_mind_observation_submitter_from_env(
            runtime_env={
                NESTED_MIND_ENABLED_ENV: "true",
                NESTED_MIND_OBSERVATION_BRIDGE_ENABLED_ENV: "true",
                NESTED_MIND_OBSERVATION_SUBMIT_ENABLED_ENV: "true",
                NESTED_MIND_BASE_URL_ENV: base_url,
            },
            clock=_clock,
            submitter_cls=FakeSubmitter,
        )


def test_token_configured_only_reports_credential_configured_true() -> None:
    bootstrap = mount_nested_mind_observation_submitter_from_env(
        runtime_env={
            NESTED_MIND_ENABLED_ENV: "true",
            NESTED_MIND_OBSERVATION_BRIDGE_ENABLED_ENV: "true",
            NESTED_MIND_OBSERVATION_SUBMIT_ENABLED_ENV: "true",
            NESTED_MIND_BASE_URL_ENV: "https://Nested.Example/api/",
            NESTED_MIND_BEARER_TOKEN_ENV: " token-value ",
        },
        clock=_clock,
        submitter_cls=FakeSubmitter,
    )

    assert isinstance(bootstrap.submitter, FakeSubmitter)
    assert bootstrap.enabled is True
    assert bootstrap.base_url == "https://nested.example/api"
    assert bootstrap.credential_configured is True
    assert bootstrap.submitter.bearer_token == "token-value"
