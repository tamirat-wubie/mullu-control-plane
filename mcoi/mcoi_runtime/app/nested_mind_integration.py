"""Nested-mind service integration for the control-plane app.

Purpose: select and mount optional nested-mind integration helpers from runtime
environment.
Governance scope: default-off external read boundary, HTTPS-only base URL
validation, optional credential binding, default-off observation proposal
planning, and separately gated live observation submission.
Dependencies: shared env flag helper, nested_mind adapters, and nested-mind
contract helpers.
Invariants:
  - unset/false read flag means no connector and no runtime behavior change.
  - enabled read flag requires an HTTPS base URL with no credentials/query/fragment.
  - bearer token presence is reported as posture only; the token value is not
    stored in the bootstrap record.
  - observation bridge helper constructs plans only; it never executes connector
    calls or submits nested-mind proposals.
  - observation submitter mounts only when read, planning, and submit gates pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from mcoi_runtime.adapters.nested_mind import NestedMindConnector
from mcoi_runtime.adapters.nested_mind_observation_submitter import (
    NestedMindObservationSubmitter,
)
from mcoi_runtime.app._integration_paths import env_flag
from mcoi_runtime.contracts.nested_mind_observation_bridge import (
    NestedMindObservationProposalPlan,
    build_observation_proposal_plan,
    stable_json_hash,
)
from mcoi_runtime.contracts.nested_mind_receipts import NestedMindProposalEvidence
from mcoi_runtime.core.invariants import stable_identifier

NESTED_MIND_ENABLED_ENV = "MULLU_NESTED_MIND_ENABLED"
NESTED_MIND_OBSERVATION_BRIDGE_ENABLED_ENV = "MULLU_NESTED_MIND_OBSERVATION_BRIDGE_ENABLED"
NESTED_MIND_OBSERVATION_SUBMIT_ENABLED_ENV = "MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED"
NESTED_MIND_BASE_URL_ENV = "MULLU_NESTED_MIND_BASE_URL"
NESTED_MIND_BEARER_TOKEN_ENV = "MULLU_NESTED_MIND_BEARER_TOKEN"


@dataclass(frozen=True)
class NestedMindConnectorBootstrap:
    """Startup posture for the optional nested-mind read-only connector."""

    connector: object | None
    enabled: bool
    base_url: str
    credential_configured: bool


@dataclass(frozen=True)
class NestedMindObservationSubmitterBootstrap:
    """Startup posture for the optional nested-mind observation submitter."""

    submitter: object | None
    enabled: bool
    base_url: str
    credential_configured: bool


@dataclass(frozen=True)
class NestedMindObservationBridgeBootstrap:
    """Startup posture for the nested-mind observation proposal planner."""

    planner: object
    enabled: bool


class NestedMindObservationBridgePlanner:
    """Runtime helper that builds observation proposal plans without execution."""

    def __init__(self, *, enabled: bool, clock: Callable[[], str]) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")
        self._enabled = enabled
        self._clock = clock

    @property
    def enabled(self) -> bool:
        """Whether generated plans should be marked planned instead of disabled."""

        return self._enabled

    def plan_observation(
        self,
        evidence: NestedMindProposalEvidence,
        *,
        observation_id: str,
        observation: Mapping[str, Any],
        observed_at: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> NestedMindObservationProposalPlan:
        """Build a fixed-shape record_observation proposal plan."""

        if not isinstance(evidence, NestedMindProposalEvidence):
            raise ValueError("evidence must be NestedMindProposalEvidence")
        effective_observed_at = observed_at or self._clock()
        created_at = self._clock()
        plan_id = stable_identifier(
            "nested-mind-observation-plan",
            {
                "evidence_id": evidence.evidence_id,
                "mind_id": evidence.mind_id,
                "observation_id": observation_id,
                "observation_hash": stable_json_hash(dict(observation)),
                "observed_at": effective_observed_at,
                "bridge_enabled": self._enabled,
            },
        )
        return build_observation_proposal_plan(
            evidence,
            plan_id=plan_id,
            observation_id=observation_id,
            observation=observation,
            observed_at=effective_observed_at,
            created_at=created_at,
            bridge_enabled=self._enabled,
            metadata=metadata or {},
        )


def mount_nested_mind_connector_from_env(
    *,
    runtime_env: Mapping[str, str],
    clock: Callable[[], str],
    connector_cls: type[NestedMindConnector] = NestedMindConnector,
) -> NestedMindConnectorBootstrap:
    """Build the nested-mind connector when the feature flag is enabled."""

    if not env_flag(runtime_env.get(NESTED_MIND_ENABLED_ENV)):
        return NestedMindConnectorBootstrap(
            connector=None,
            enabled=False,
            base_url="",
            credential_configured=False,
        )

    raw_base_url = str(runtime_env.get(NESTED_MIND_BASE_URL_ENV, "")).strip()
    if not raw_base_url:
        raise RuntimeError(
            f"{NESTED_MIND_BASE_URL_ENV} is required when "
            f"{NESTED_MIND_ENABLED_ENV} is enabled"
        )
    base_url = validate_nested_mind_base_url(raw_base_url)

    raw_token = str(runtime_env.get(NESTED_MIND_BEARER_TOKEN_ENV, "")).strip()
    token = raw_token or None
    connector = connector_cls(
        clock=clock,
        base_url=base_url,
        bearer_token=token,
    )
    return NestedMindConnectorBootstrap(
        connector=connector,
        enabled=True,
        base_url=base_url,
        credential_configured=token is not None,
    )


def mount_nested_mind_observation_bridge_from_env(
    *,
    runtime_env: Mapping[str, str],
    clock: Callable[[], str],
    planner_cls: type[NestedMindObservationBridgePlanner] = NestedMindObservationBridgePlanner,
) -> NestedMindObservationBridgeBootstrap:
    """Build the default-off observation proposal planner from env posture."""

    enabled = env_flag(runtime_env.get(NESTED_MIND_OBSERVATION_BRIDGE_ENABLED_ENV))
    return NestedMindObservationBridgeBootstrap(
        planner=planner_cls(enabled=enabled, clock=clock),
        enabled=enabled,
    )


def mount_nested_mind_observation_submitter_from_env(
    *,
    runtime_env: Mapping[str, str],
    clock: Callable[[], str],
    submitter_cls: type[NestedMindObservationSubmitter] = NestedMindObservationSubmitter,
) -> NestedMindObservationSubmitterBootstrap:
    """Build the observation submitter only when all mutation gates are enabled."""

    if not env_flag(runtime_env.get(NESTED_MIND_OBSERVATION_SUBMIT_ENABLED_ENV)):
        return NestedMindObservationSubmitterBootstrap(
            submitter=None,
            enabled=False,
            base_url="",
            credential_configured=False,
        )
    if not env_flag(runtime_env.get(NESTED_MIND_ENABLED_ENV)):
        raise RuntimeError(
            f"{NESTED_MIND_ENABLED_ENV} must be enabled when "
            f"{NESTED_MIND_OBSERVATION_SUBMIT_ENABLED_ENV} is enabled"
        )
    if not env_flag(runtime_env.get(NESTED_MIND_OBSERVATION_BRIDGE_ENABLED_ENV)):
        raise RuntimeError(
            f"{NESTED_MIND_OBSERVATION_BRIDGE_ENABLED_ENV} must be enabled when "
            f"{NESTED_MIND_OBSERVATION_SUBMIT_ENABLED_ENV} is enabled"
        )

    raw_base_url = str(runtime_env.get(NESTED_MIND_BASE_URL_ENV, "")).strip()
    if not raw_base_url:
        raise RuntimeError(
            f"{NESTED_MIND_BASE_URL_ENV} is required when "
            f"{NESTED_MIND_OBSERVATION_SUBMIT_ENABLED_ENV} is enabled"
        )
    base_url = validate_nested_mind_base_url(raw_base_url)
    raw_token = str(runtime_env.get(NESTED_MIND_BEARER_TOKEN_ENV, "")).strip()
    token = raw_token or None
    submitter = submitter_cls(
        clock=clock,
        base_url=base_url,
        bearer_token=token,
    )
    return NestedMindObservationSubmitterBootstrap(
        submitter=submitter,
        enabled=True,
        base_url=base_url,
        credential_configured=token is not None,
    )


def validate_nested_mind_base_url(base_url: str) -> str:
    """Validate and normalize the nested-mind HTTPS service boundary."""

    parsed = urlparse(str(base_url or "").strip())
    if parsed.scheme.lower() != "https":
        raise RuntimeError(f"{NESTED_MIND_BASE_URL_ENV} must use https")
    if not parsed.netloc or not parsed.hostname:
        raise RuntimeError(f"{NESTED_MIND_BASE_URL_ENV} must include a host")
    if parsed.username or parsed.password:
        raise RuntimeError(f"{NESTED_MIND_BASE_URL_ENV} must not include credentials")
    if parsed.params or parsed.query or parsed.fragment:
        raise RuntimeError(
            f"{NESTED_MIND_BASE_URL_ENV} must not include params, query, or fragment"
        )

    path = parsed.path.rstrip("/")
    netloc = parsed.netloc.lower()
    normalized = f"https://{netloc}{path}" if path else f"https://{netloc}"
    return normalized
