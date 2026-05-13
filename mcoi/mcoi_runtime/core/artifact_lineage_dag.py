"""Purpose: artifact lineage DAG for replay planning and impact analysis.
Governance scope: artifact dependency registration, cycle prevention,
replay eligibility, and transitive invalidation analysis.
Dependencies: runtime invariant helpers and Python standard library only.
Invariants:
  - Artifact identifiers are unique.
  - Dependency edges reference registered artifacts.
  - The artifact graph remains acyclic after every edge insertion.
  - Replay plans list dependencies before dependents.
  - Non-replayable artifacts block replay with explicit reasons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Callable, Mapping

from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


class ArtifactLineageRelation(StrEnum):
    """Allowed directed relations between artifacts."""

    DEPENDS_ON = "depends_on"
    DERIVED_FROM = "derived_from"
    SUPERSEDES = "supersedes"
    VERIFIES = "verifies"


@dataclass(frozen=True, slots=True)
class ArtifactLineageNode:
    """Registered artifact node bound to a producing event."""

    artifact_id: str
    artifact_hash: str
    artifact_type: str
    tenant_id: str
    produced_by_event_id: str
    created_at: str
    replayable: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "artifact_id",
            "artifact_hash",
            "artifact_type",
            "tenant_id",
            "produced_by_event_id",
            "created_at",
        ):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, str(getattr(self, field_name))),
            )
        if not isinstance(self.replayable, bool):
            raise RuntimeCoreInvariantError("replayable must be a bool")
        if not isinstance(self.metadata, Mapping):
            raise RuntimeCoreInvariantError("metadata must be an object")
        object.__setattr__(self, "metadata", _json_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class ArtifactLineageEdge:
    """Directed edge from an upstream artifact to a downstream artifact."""

    edge_id: str
    upstream_artifact_id: str
    downstream_artifact_id: str
    relation: ArtifactLineageRelation
    reason: str
    created_at: str

    def __post_init__(self) -> None:
        for field_name in (
            "edge_id",
            "upstream_artifact_id",
            "downstream_artifact_id",
            "reason",
            "created_at",
        ):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, str(getattr(self, field_name))),
            )
        if not isinstance(self.relation, ArtifactLineageRelation):
            raise RuntimeCoreInvariantError("relation must be an ArtifactLineageRelation value")
        if self.upstream_artifact_id == self.downstream_artifact_id:
            raise RuntimeCoreInvariantError("artifact lineage edge cannot point to itself")


@dataclass(frozen=True, slots=True)
class ArtifactReplayPlan:
    """Replay eligibility result for reconstructing one artifact."""

    target_artifact_id: str
    artifact_ids: tuple[str, ...]
    ready: bool
    blocked_reasons: tuple[str, ...]
    plan_hash: str


class ArtifactLineageDAG:
    """Acyclic artifact graph for dependency replay and change impact."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._nodes: dict[str, ArtifactLineageNode] = {}
        self._edges: dict[str, ArtifactLineageEdge] = {}
        self._outgoing: dict[str, set[str]] = {}
        self._incoming: dict[str, set[str]] = {}

    @property
    def artifact_count(self) -> int:
        """Return registered artifact count."""
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        """Return committed edge count."""
        return len(self._edges)

    def register_artifact(
        self,
        *,
        artifact_id: str,
        artifact_hash: str,
        artifact_type: str,
        tenant_id: str,
        produced_by_event_id: str,
        replayable: bool = True,
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactLineageNode:
        """Register one artifact node."""
        if artifact_id in self._nodes:
            raise RuntimeCoreInvariantError("artifact_id already exists")
        node = ArtifactLineageNode(
            artifact_id=artifact_id,
            artifact_hash=artifact_hash,
            artifact_type=artifact_type,
            tenant_id=tenant_id,
            produced_by_event_id=produced_by_event_id,
            created_at=ensure_non_empty_text("created_at", self._clock()),
            replayable=replayable,
            metadata=metadata or {},
        )
        self._nodes[node.artifact_id] = node
        self._outgoing.setdefault(node.artifact_id, set())
        self._incoming.setdefault(node.artifact_id, set())
        return node

    def add_edge(
        self,
        *,
        upstream_artifact_id: str,
        downstream_artifact_id: str,
        relation: ArtifactLineageRelation = ArtifactLineageRelation.DEPENDS_ON,
        reason: str,
    ) -> ArtifactLineageEdge:
        """Add one dependency edge after cycle validation."""
        self._require_artifact(upstream_artifact_id)
        self._require_artifact(downstream_artifact_id)
        if upstream_artifact_id == downstream_artifact_id:
            raise RuntimeCoreInvariantError("artifact lineage edge cannot point to itself")
        edge_id = stable_identifier(
            "artifact-edge",
            {
                "upstream_artifact_id": upstream_artifact_id,
                "downstream_artifact_id": downstream_artifact_id,
                "relation": relation.value,
            },
        )
        if edge_id in self._edges:
            raise RuntimeCoreInvariantError("artifact lineage edge already exists")
        self._outgoing.setdefault(upstream_artifact_id, set()).add(downstream_artifact_id)
        self._incoming.setdefault(downstream_artifact_id, set()).add(upstream_artifact_id)
        cycle_path = self.detect_cycle()
        if cycle_path:
            self._outgoing[upstream_artifact_id].remove(downstream_artifact_id)
            self._incoming[downstream_artifact_id].remove(upstream_artifact_id)
            raise RuntimeCoreInvariantError("artifact lineage cycle detected")
        edge = ArtifactLineageEdge(
            edge_id=edge_id,
            upstream_artifact_id=upstream_artifact_id,
            downstream_artifact_id=downstream_artifact_id,
            relation=relation,
            reason=reason,
            created_at=ensure_non_empty_text("created_at", self._clock()),
        )
        self._edges[edge.edge_id] = edge
        return edge

    def get_artifact(self, artifact_id: str) -> ArtifactLineageNode | None:
        """Return one registered artifact."""
        ensure_non_empty_text("artifact_id", artifact_id)
        return self._nodes.get(artifact_id)

    def ancestors_of(self, artifact_id: str) -> tuple[str, ...]:
        """Return transitive upstream artifacts in dependency-first order."""
        self._require_artifact(artifact_id)
        ordered: list[str] = []
        visited: set[str] = set()

        def walk(current_id: str) -> None:
            for upstream_id in sorted(self._incoming.get(current_id, ())):
                if upstream_id in visited:
                    continue
                visited.add(upstream_id)
                walk(upstream_id)
                ordered.append(upstream_id)

        walk(artifact_id)
        return tuple(ordered)

    def descendants_of(self, artifact_id: str) -> tuple[str, ...]:
        """Return transitive downstream artifacts impacted by an artifact."""
        self._require_artifact(artifact_id)
        ordered: list[str] = []
        visited: set[str] = set()

        def walk(current_id: str) -> None:
            for downstream_id in sorted(self._outgoing.get(current_id, ())):
                if downstream_id in visited:
                    continue
                visited.add(downstream_id)
                ordered.append(downstream_id)
                walk(downstream_id)

        walk(artifact_id)
        return tuple(ordered)

    def replay_plan(self, target_artifact_id: str) -> ArtifactReplayPlan:
        """Build a replay plan for reconstructing the target artifact."""
        self._require_artifact(target_artifact_id)
        artifact_ids = (*self.ancestors_of(target_artifact_id), target_artifact_id)
        blocked_reasons = tuple(
            f"{artifact_id}:not_replayable"
            for artifact_id in artifact_ids
            if not self._nodes[artifact_id].replayable
        )
        plan_payload = {
            "target_artifact_id": target_artifact_id,
            "artifact_ids": artifact_ids,
            "blocked_reasons": blocked_reasons,
        }
        return ArtifactReplayPlan(
            target_artifact_id=target_artifact_id,
            artifact_ids=artifact_ids,
            ready=not blocked_reasons,
            blocked_reasons=blocked_reasons,
            plan_hash=_hash_payload(plan_payload),
        )

    def topological_order(self) -> tuple[str, ...]:
        """Return all artifacts with upstream dependencies first."""
        in_degree = {artifact_id: len(self._incoming.get(artifact_id, ())) for artifact_id in self._nodes}
        ready = sorted(artifact_id for artifact_id, degree in in_degree.items() if degree == 0)
        ordered: list[str] = []
        while ready:
            artifact_id = ready.pop(0)
            ordered.append(artifact_id)
            for downstream_id in sorted(self._outgoing.get(artifact_id, ())):
                in_degree[downstream_id] -= 1
                if in_degree[downstream_id] == 0:
                    ready.append(downstream_id)
                    ready.sort()
        if len(ordered) != len(self._nodes):
            raise RuntimeCoreInvariantError("artifact lineage cycle detected")
        return tuple(ordered)

    def detect_cycle(self) -> tuple[str, ...]:
        """Return a cycle path if present, otherwise an empty tuple."""
        visited: set[str] = set()
        active: set[str] = set()
        path: list[str] = []

        def walk(artifact_id: str) -> tuple[str, ...]:
            visited.add(artifact_id)
            active.add(artifact_id)
            path.append(artifact_id)
            for downstream_id in sorted(self._outgoing.get(artifact_id, ())):
                if downstream_id not in visited:
                    found = walk(downstream_id)
                    if found:
                        return found
                elif downstream_id in active:
                    start = path.index(downstream_id)
                    return tuple(path[start:] + [downstream_id])
            path.pop()
            active.remove(artifact_id)
            return ()

        for artifact_id in sorted(self._nodes):
            if artifact_id not in visited:
                found = walk(artifact_id)
                if found:
                    return found
        return ()

    def _require_artifact(self, artifact_id: str) -> ArtifactLineageNode:
        normalized = ensure_non_empty_text("artifact_id", artifact_id)
        node = self._nodes.get(normalized)
        if node is None:
            raise RuntimeCoreInvariantError("artifact not found")
        return node


def hash_artifact_payload(payload: Any) -> str:
    """Return a stable artifact hash for lineage registration."""
    return _hash_payload(_json_value(payload))


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(_json_value(payload), sort_keys=True, separators=(",", ":"), default=str)
    return sha256(encoded.encode("utf-8")).hexdigest()


def _json_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return dict(_json_value(dict(value)))


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
