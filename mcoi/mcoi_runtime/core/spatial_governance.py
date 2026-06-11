"""Mullusi universal spatial-causal governance read model.

Purpose: map gateway entities, regions, boundaries, paths, metrics, blockers,
and judgments into a bounded operator-visible spatial map.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library dataclasses and enum support.
Invariants:
  - Every path crossing is witnessed.
  - Missing boundaries are reported as explicit blockers.
  - The model returns no secrets or runtime credential values.
  - Reachability is never claimed when evidence is required.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class BoundaryRule(StrEnum):
    """Boundary crossing rule."""

    ALLOW = "allow"
    BLOCK = "block"
    REQUIRES_EVIDENCE = "requires_evidence"


class SpatialStatus(StrEnum):
    """Spatial path judgment status."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SpatialEntity:
    """Entity located in a governed control-plane region."""

    id: str
    kind: str
    region: str


@dataclass(frozen=True)
class SpatialRegion:
    """Named region inside the gateway spatial frame."""

    id: str
    kind: str
    trust: str


@dataclass(frozen=True)
class SpatialBoundary:
    """Boundary separating two regions."""

    id: str
    separates: tuple[str, str]
    rule: BoundaryRule


@dataclass(frozen=True)
class SpatialPath:
    """Path from a source entity or region to a target."""

    id: str
    source: str
    target: str
    crosses: tuple[str, ...]


@dataclass(frozen=True)
class SpatialMetric:
    """Symbolic metric for an observed spatial relation."""

    id: str
    kind: str
    value: str


@dataclass(frozen=True)
class SpatialJudgment:
    """Judgment for one path."""

    path_id: str
    status: SpatialStatus
    reasons: tuple[str, ...]
    witness: tuple[str, ...]


@dataclass(frozen=True)
class SpatialMap:
    """Complete bounded spatial governance map."""

    frame: str
    entities: tuple[SpatialEntity, ...]
    regions: tuple[SpatialRegion, ...]
    boundaries: tuple[SpatialBoundary, ...]
    paths: tuple[SpatialPath, ...]
    metrics: tuple[SpatialMetric, ...]
    judgments: tuple[SpatialJudgment, ...]
    blockers: tuple[str, ...]
    witness: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe read model with enum values expanded."""
        payload = asdict(self)
        for boundary in payload["boundaries"]:
            boundary["rule"] = str(boundary["rule"])
        for judgment in payload["judgments"]:
            judgment["status"] = str(judgment["status"])
        return payload


def judge_path(path: SpatialPath, boundaries: Mapping[str, SpatialBoundary]) -> SpatialJudgment:
    """Judge a path against declared boundaries.

    Input contract: path crossings name boundary IDs, and boundaries maps those
    IDs to crossing rules.
    Output contract: one allowed, blocked, or unknown judgment.
    Error contract: missing boundary IDs are returned as explicit blockers.
    """
    reasons: list[str] = []
    witness: list[str] = [
        f"path:{path.id}",
        f"source:{path.source}",
        f"target:{path.target}",
    ]

    for boundary_id in path.crosses:
        boundary = boundaries.get(boundary_id)
        if boundary is None:
            witness.append(f"missing_boundary:{boundary_id}")
            reasons.append(f"dependency_missing:{boundary_id}")
            continue

        witness.append(f"crosses:{boundary.id}")
        if boundary.rule == BoundaryRule.BLOCK:
            reasons.append(f"blocked_boundary:{boundary.id}")
        elif boundary.rule == BoundaryRule.REQUIRES_EVIDENCE:
            reasons.append(f"evidence_required:{boundary.id}")

    if any(reason.startswith(("blocked_boundary", "dependency_missing")) for reason in reasons):
        return SpatialJudgment(path.id, SpatialStatus.BLOCKED, tuple(reasons), tuple(witness))

    if any(reason.startswith("evidence_required") for reason in reasons):
        return SpatialJudgment(path.id, SpatialStatus.UNKNOWN, tuple(reasons), tuple(witness))

    return SpatialJudgment(
        path.id,
        SpatialStatus.ALLOWED,
        tuple(),
        tuple([*witness, "path_valid"]),
    )


def build_gateway_spatial_map(readiness_checks: Mapping[str, bool]) -> SpatialMap:
    """Build the gateway spatial governance read model.

    Input contract: readiness_checks maps subsystem names to pass/fail booleans.
    Output contract: deterministic spatial map with explicit launch blockers.
    Error contract: non-boolean readiness values are treated as blocked evidence.
    """
    readiness_blockers = tuple(
        f"readiness_check:{name}"
        for name, passed in sorted(readiness_checks.items())
        if passed is not True
    )

    entities = (
        SpatialEntity("public_user", "actor", "public_browser"),
        SpatialEntity("browser", "client_runtime", "public_browser"),
        SpatialEntity("dashboard", "operator_surface", "dashboard_surface"),
        SpatialEntity("gateway_api", "fastapi_service", "api_boundary"),
        SpatialEntity("cors_policy", "boundary_policy", "api_boundary"),
        SpatialEntity("request_validator", "contract", "validation_zone"),
        SpatialEntity("governance_guard_chain", "decision_engine", "governance_core"),
        SpatialEntity("security_header_system", "response_boundary_guard", "response_header_zone"),
        SpatialEntity("readiness_contract", "launch_contract", "readiness_zone"),
        SpatialEntity("command_ledger", "persistence_runtime", "persistence_zone"),
        SpatialEntity("governed_cache", "ephemeral_cache_runtime", "cache_zone"),
        SpatialEntity("idempotency_store", "duplicate_suppression_runtime", "idempotency_zone"),
        SpatialEntity("request_deduplicator", "request_replay_guard", "request_dedup_zone"),
        SpatialEntity("rate_limiter", "token_bucket_guard", "rate_limit_zone"),
        SpatialEntity("backpressure_controller", "load_shedding_guard", "backpressure_zone"),
        SpatialEntity("tenant_identity", "identity_runtime", "identity_zone"),
        SpatialEntity("finance_approval", "approval_runtime", "finance_authority_zone"),
        SpatialEntity("payment_provider", "external_payment_authority", "payment_provider_zone"),
        SpatialEntity("capability_worker", "private_worker", "private_worker_zone"),
        SpatialEntity("observability_stack", "operator_evidence", "observability_zone"),
        SpatialEntity("support_flow", "operator_response", "support_zone"),
        SpatialEntity("secret_rotation", "secret_control", "secret_zone"),
        SpatialEntity("render_host", "deployment_host", "deployment_zone"),
        SpatialEntity("custom_domains", "external_authority", "dns_authority_zone"),
    )

    regions = (
        SpatialRegion("public_browser", "client", "untrusted"),
        SpatialRegion("dashboard_surface", "operator_ui", "semi_trusted"),
        SpatialRegion("api_boundary", "http_gateway", "guarded"),
        SpatialRegion("validation_zone", "schema_boundary", "guarded"),
        SpatialRegion("governance_core", "decision_boundary", "trusted"),
        SpatialRegion("response_header_zone", "response_boundary", "guarded"),
        SpatialRegion("readiness_zone", "launch_boundary", "guarded"),
        SpatialRegion("persistence_zone", "state_boundary", "guarded"),
        SpatialRegion("cache_zone", "ephemeral_cache_boundary", "guarded_ephemeral"),
        SpatialRegion("idempotency_zone", "duplicate_suppression_boundary", "guarded"),
        SpatialRegion("request_dedup_zone", "request_replay_boundary", "guarded"),
        SpatialRegion("rate_limit_zone", "throughput_guard_boundary", "guarded"),
        SpatialRegion("backpressure_zone", "load_control_boundary", "guarded"),
        SpatialRegion("identity_zone", "authority_boundary", "guarded"),
        SpatialRegion("finance_authority_zone", "approval_boundary", "guarded"),
        SpatialRegion("payment_provider_zone", "external_payment_boundary", "external_evidence_required"),
        SpatialRegion("private_worker_zone", "execution_boundary", "private"),
        SpatialRegion("observability_zone", "operator_evidence_boundary", "guarded"),
        SpatialRegion("support_zone", "incident_response_boundary", "external_evidence_required"),
        SpatialRegion("secret_zone", "credential_boundary", "restricted"),
        SpatialRegion("deployment_zone", "host_boundary", "external"),
        SpatialRegion("dns_authority_zone", "domain_boundary", "external"),
    )

    boundaries = (
        SpatialBoundary("cors", ("dashboard_surface", "api_boundary"), BoundaryRule.ALLOW),
        SpatialBoundary("validation", ("api_boundary", "validation_zone"), BoundaryRule.ALLOW),
        SpatialBoundary("governance", ("validation_zone", "governance_core"), BoundaryRule.ALLOW),
        SpatialBoundary("security_headers", ("governance_core", "response_header_zone"), BoundaryRule.ALLOW),
        SpatialBoundary("readiness", ("api_boundary", "readiness_zone"), BoundaryRule.REQUIRES_EVIDENCE),
        SpatialBoundary("persistence", ("api_boundary", "persistence_zone"), BoundaryRule.REQUIRES_EVIDENCE),
        SpatialBoundary("cache", ("api_boundary", "cache_zone"), BoundaryRule.ALLOW),
        SpatialBoundary("idempotency", ("api_boundary", "idempotency_zone"), BoundaryRule.ALLOW),
        SpatialBoundary("request_dedup", ("api_boundary", "request_dedup_zone"), BoundaryRule.ALLOW),
        SpatialBoundary("rate_limit", ("api_boundary", "rate_limit_zone"), BoundaryRule.ALLOW),
        SpatialBoundary("backpressure", ("api_boundary", "backpressure_zone"), BoundaryRule.ALLOW),
        SpatialBoundary("identity", ("public_browser", "identity_zone"), BoundaryRule.REQUIRES_EVIDENCE),
        SpatialBoundary("finance_approval", ("api_boundary", "finance_authority_zone"), BoundaryRule.REQUIRES_EVIDENCE),
        SpatialBoundary("payment_provider", ("finance_authority_zone", "payment_provider_zone"), BoundaryRule.REQUIRES_EVIDENCE),
        SpatialBoundary("worker_private", ("api_boundary", "private_worker_zone"), BoundaryRule.REQUIRES_EVIDENCE),
        SpatialBoundary("observability", ("api_boundary", "observability_zone"), BoundaryRule.REQUIRES_EVIDENCE),
        SpatialBoundary("support", ("readiness_zone", "support_zone"), BoundaryRule.REQUIRES_EVIDENCE),
        SpatialBoundary("secrets", ("source_code", "secret_zone"), BoundaryRule.BLOCK),
        SpatialBoundary("dns", ("deployment_zone", "dns_authority_zone"), BoundaryRule.REQUIRES_EVIDENCE),
    )
    boundary_index = {boundary.id: boundary for boundary in boundaries}

    paths = (
        SpatialPath("dashboard_health_check", "dashboard", "gateway_api.health", ("cors",)),
        SpatialPath("governed_request_flow", "dashboard", "governance_guard_chain", ("cors", "validation", "governance")),
        SpatialPath("bounded_exception_response", "governance_guard_chain", "client_error_response", ("security_headers",)),
        SpatialPath("readiness_launch_gate", "gateway_api", "public_launch", ("readiness", "dns", "identity")),
        SpatialPath("stateful_command_path", "gateway_api", "command_ledger", ("persistence",)),
        SpatialPath("cache_lookup_path", "gateway_api", "governed_cache", ("cache",)),
        SpatialPath("idempotency_suppression_path", "gateway_api", "idempotency_store", ("idempotency",)),
        SpatialPath("request_deduplication_path", "gateway_api", "request_deduplicator", ("request_dedup",)),
        SpatialPath("rate_limit_guard_path", "gateway_api", "rate_limiter", ("rate_limit",)),
        SpatialPath("backpressure_status_path", "gateway_api", "backpressure_controller", ("backpressure",)),
        SpatialPath("finance_approval_path", "gateway_api", "finance_approval", ("finance_approval",)),
        SpatialPath("payment_provider_handoff_path", "finance_approval", "payment_provider", ("payment_provider",)),
        SpatialPath("capability_execution_path", "gateway_api", "capability_worker", ("worker_private",)),
        SpatialPath("observability_evidence_path", "gateway_api", "observability_stack", ("observability",)),
        SpatialPath("support_escalation_path", "readiness_contract", "support_flow", ("support",)),
        SpatialPath("source_to_secret", "source_code", "secret_rotation", ("secrets",)),
    )

    judgments = tuple(judge_path(path, boundary_index) for path in paths)
    unresolved_paths = tuple(
        f"path:{judgment.path_id}:{judgment.status}"
        for judgment in judgments
        if judgment.status != SpatialStatus.ALLOWED
    )

    return SpatialMap(
        frame=(
            "gateway_architecture_space+security_boundary_space+deployment_topology_space+"
            "runtime_request_flow_space+governance_proof_space"
        ),
        entities=entities,
        regions=regions,
        boundaries=boundaries,
        paths=paths,
        metrics=(
            SpatialMetric("readiness_subsystems", "count", str(len(readiness_checks))),
            SpatialMetric("readiness_blockers", "count", str(len(readiness_blockers))),
            SpatialMetric("unresolved_paths", "count", str(len(unresolved_paths))),
        ),
        judgments=judgments,
        blockers=tuple([*readiness_blockers, *unresolved_paths]),
        witness=(
            "spatial_frame:gateway_control_plane_architecture",
            "health_is_not_launch_readiness",
            "every_path_crossing_is_witnessed",
            "bounded_exception_response_crosses_security_header_boundary",
            "cache_boundary_is_ephemeral_not_persistence",
            "idempotency_boundary_preserves_duplicate_suppression_before_side_effects",
            "request_dedup_boundary_preserves_tenant_scoped_replay_suppression",
            "rate_limit_boundary_preserves_token_bucket_throughput_control",
            "backpressure_boundary_preserves_load_shedding_control",
            "finance_and_payment_paths_require_approval_and_provider_evidence",
            "operational_launch_boundaries_require_observability_and_support_evidence",
            "secret_boundary_blocks_source_to_secret_path",
            "evidence_required_boundaries_are_unknown_not_allowed",
        ),
    )
