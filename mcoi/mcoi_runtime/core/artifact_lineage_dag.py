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
from pathlib import Path
from typing import Any, Callable, Mapping

from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier

ARTIFACT_LINEAGE_SNAPSHOT_SCHEMA_VERSION = 1


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
                ensure_non_empty_text(field_name, getattr(self, field_name)),
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
                ensure_non_empty_text(field_name, getattr(self, field_name)),
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


@dataclass(frozen=True, slots=True)
class ArtifactLineageSnapshot:
    """Deterministic export of one artifact lineage graph."""

    schema_version: int
    snapshot_id: str
    snapshot_hash: str
    created_at: str
    artifact_count: int
    edge_count: int
    artifacts: tuple[Mapping[str, Any], ...]
    edges: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        if self.schema_version != ARTIFACT_LINEAGE_SNAPSHOT_SCHEMA_VERSION:
            raise RuntimeCoreInvariantError("artifact lineage snapshot schema_version unsupported")
        object.__setattr__(self, "snapshot_id", ensure_non_empty_text("snapshot_id", self.snapshot_id))
        object.__setattr__(self, "snapshot_hash", ensure_non_empty_text("snapshot_hash", self.snapshot_hash))
        object.__setattr__(self, "created_at", ensure_non_empty_text("created_at", self.created_at))
        if self.artifact_count < 0:
            raise RuntimeCoreInvariantError("artifact_count must be non-negative")
        if self.edge_count < 0:
            raise RuntimeCoreInvariantError("edge_count must be non-negative")
        artifacts = _mapping_tuple("artifacts", self.artifacts)
        edges = _mapping_tuple("edges", self.edges)
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "edges", edges)
        if self.artifact_count != len(artifacts):
            raise RuntimeCoreInvariantError("artifact_count mismatch")
        if self.edge_count != len(edges):
            raise RuntimeCoreInvariantError("edge_count mismatch")
        expected_hash = _hash_payload(self._hash_body())
        if self.snapshot_hash != expected_hash:
            raise RuntimeCoreInvariantError("artifact lineage snapshot hash mismatch")
        if self.snapshot_id != f"artifact-lineage-snapshot-{self.snapshot_hash[:16]}":
            raise RuntimeCoreInvariantError("artifact lineage snapshot_id mismatch")

    @classmethod
    def build(
        cls,
        *,
        created_at: str,
        artifacts: tuple[Mapping[str, Any], ...],
        edges: tuple[Mapping[str, Any], ...],
    ) -> "ArtifactLineageSnapshot":
        """Build a validated snapshot from canonical artifact and edge rows."""
        body = _snapshot_hash_body(
            created_at=created_at,
            artifacts=artifacts,
            edges=edges,
        )
        snapshot_hash = _hash_payload(body)
        return cls(
            schema_version=ARTIFACT_LINEAGE_SNAPSHOT_SCHEMA_VERSION,
            snapshot_id=f"artifact-lineage-snapshot-{snapshot_hash[:16]}",
            snapshot_hash=snapshot_hash,
            created_at=created_at,
            artifact_count=len(artifacts),
            edge_count=len(edges),
            artifacts=artifacts,
            edges=edges,
        )

    @classmethod
    def from_json_dict(cls, payload: Mapping[str, Any]) -> "ArtifactLineageSnapshot":
        """Restore a snapshot contract from JSON-decoded data."""
        if not isinstance(payload, Mapping):
            raise RuntimeCoreInvariantError("artifact lineage snapshot must be an object")
        return cls(
            schema_version=int(payload.get("schema_version", 0)),
            snapshot_id=str(payload.get("snapshot_id", "")),
            snapshot_hash=str(payload.get("snapshot_hash", "")),
            created_at=str(payload.get("created_at", "")),
            artifact_count=int(payload.get("artifact_count", -1)),
            edge_count=int(payload.get("edge_count", -1)),
            artifacts=_mapping_tuple("artifacts", payload.get("artifacts", ())),
            edges=_mapping_tuple("edges", payload.get("edges", ())),
        )

    def to_json_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready snapshot document."""
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "snapshot_hash": self.snapshot_hash,
            "created_at": self.created_at,
            "artifact_count": self.artifact_count,
            "edge_count": self.edge_count,
            "artifacts": [dict(artifact) for artifact in self.artifacts],
            "edges": [dict(edge) for edge in self.edges],
        }

    def _hash_body(self) -> dict[str, Any]:
        return _snapshot_hash_body(
            created_at=self.created_at,
            artifacts=self.artifacts,
            edges=self.edges,
        )


class JsonArtifactLineageStore:
    """Single-file JSON store for artifact lineage snapshots."""

    def __init__(self, path: str | Path) -> None:
        path_text = str(path).strip()
        if not path_text:
            raise RuntimeCoreInvariantError("artifact lineage store path is required")
        resolved_path = Path(path_text)
        if resolved_path.exists() and resolved_path.is_dir():
            raise RuntimeCoreInvariantError("artifact lineage store path must be a file")
        self._path = resolved_path

    @property
    def path(self) -> Path:
        """Return the configured snapshot file path."""
        return self._path

    def save(self, dag: "ArtifactLineageDAG") -> ArtifactLineageSnapshot:
        """Persist one DAG snapshot as canonical JSON."""
        if not isinstance(dag, ArtifactLineageDAG):
            raise RuntimeCoreInvariantError("dag must be an ArtifactLineageDAG")
        snapshot = dag.export_snapshot()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(snapshot.to_json_dict(), sort_keys=True, separators=(",", ":"), indent=2)
        self._path.write_text(f"{encoded}\n", encoding="utf-8")
        return snapshot

    def load(self, *, clock: Callable[[], str]) -> "ArtifactLineageDAG":
        """Load and validate a DAG snapshot from disk."""
        if not self._path.exists():
            raise RuntimeCoreInvariantError("artifact lineage snapshot not found")
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeCoreInvariantError("artifact lineage snapshot invalid JSON") from exc
        return ArtifactLineageDAG.from_snapshot(payload, clock=clock)


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

    @classmethod
    def from_snapshot(
        cls,
        snapshot: ArtifactLineageSnapshot | Mapping[str, Any],
        *,
        clock: Callable[[], str],
    ) -> "ArtifactLineageDAG":
        """Restore a DAG from a validated snapshot without mutating source state."""
        checked_snapshot = (
            snapshot
            if isinstance(snapshot, ArtifactLineageSnapshot)
            else ArtifactLineageSnapshot.from_json_dict(snapshot)
        )
        dag = cls(clock=clock)
        for artifact_payload in checked_snapshot.artifacts:
            node = _node_from_json_dict(artifact_payload)
            if node.artifact_id in dag._nodes:
                raise RuntimeCoreInvariantError("artifact_id already exists")
            dag._nodes[node.artifact_id] = node
            dag._outgoing.setdefault(node.artifact_id, set())
            dag._incoming.setdefault(node.artifact_id, set())
        for edge_payload in checked_snapshot.edges:
            edge = _edge_from_json_dict(edge_payload)
            if edge.edge_id in dag._edges:
                raise RuntimeCoreInvariantError("artifact lineage edge already exists")
            dag._require_artifact(edge.upstream_artifact_id)
            dag._require_artifact(edge.downstream_artifact_id)
            dag._edges[edge.edge_id] = edge
            dag._outgoing.setdefault(edge.upstream_artifact_id, set()).add(edge.downstream_artifact_id)
            dag._incoming.setdefault(edge.downstream_artifact_id, set()).add(edge.upstream_artifact_id)
        if dag.detect_cycle():
            raise RuntimeCoreInvariantError("artifact lineage cycle detected")
        if dag.artifact_count != checked_snapshot.artifact_count:
            raise RuntimeCoreInvariantError("artifact_count mismatch")
        if dag.edge_count != checked_snapshot.edge_count:
            raise RuntimeCoreInvariantError("edge_count mismatch")
        return dag

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
        if not isinstance(relation, ArtifactLineageRelation):
            raise RuntimeCoreInvariantError("relation must be an ArtifactLineageRelation value")
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

    def dependencies_of(self, artifact_id: str) -> tuple[str, ...]:
        """Return direct upstream artifacts for one artifact."""
        self._require_artifact(artifact_id)
        return tuple(sorted(self._incoming.get(artifact_id, ())))

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

    def export_snapshot(self) -> ArtifactLineageSnapshot:
        """Export a deterministic snapshot suitable for durable storage."""
        artifacts = tuple(
            _node_to_json_dict(self._nodes[artifact_id])
            for artifact_id in sorted(self._nodes)
        )
        edges = tuple(
            _edge_to_json_dict(self._edges[edge_id])
            for edge_id in sorted(self._edges)
        )
        return ArtifactLineageSnapshot.build(
            created_at=ensure_non_empty_text("created_at", self._clock()),
            artifacts=artifacts,
            edges=edges,
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


def _snapshot_hash_body(
    *,
    created_at: str,
    artifacts: tuple[Mapping[str, Any], ...],
    edges: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    return {
        "schema_version": ARTIFACT_LINEAGE_SNAPSHOT_SCHEMA_VERSION,
        "created_at": created_at,
        "artifact_count": len(artifacts),
        "edge_count": len(edges),
        "artifacts": [dict(artifact) for artifact in artifacts],
        "edges": [dict(edge) for edge in edges],
    }


def _node_to_json_dict(node: ArtifactLineageNode) -> dict[str, Any]:
    return {
        "artifact_id": node.artifact_id,
        "artifact_hash": node.artifact_hash,
        "artifact_type": node.artifact_type,
        "tenant_id": node.tenant_id,
        "produced_by_event_id": node.produced_by_event_id,
        "created_at": node.created_at,
        "replayable": node.replayable,
        "metadata": dict(node.metadata),
    }


def _edge_to_json_dict(edge: ArtifactLineageEdge) -> dict[str, Any]:
    return {
        "edge_id": edge.edge_id,
        "upstream_artifact_id": edge.upstream_artifact_id,
        "downstream_artifact_id": edge.downstream_artifact_id,
        "relation": edge.relation.value,
        "reason": edge.reason,
        "created_at": edge.created_at,
    }


def _node_from_json_dict(payload: Mapping[str, Any]) -> ArtifactLineageNode:
    if not isinstance(payload, Mapping):
        raise RuntimeCoreInvariantError("artifact snapshot row must be an object")
    replayable = payload.get("replayable", True)
    if not isinstance(replayable, bool):
        raise RuntimeCoreInvariantError("replayable must be a bool")
    return ArtifactLineageNode(
        artifact_id=str(payload.get("artifact_id", "")),
        artifact_hash=str(payload.get("artifact_hash", "")),
        artifact_type=str(payload.get("artifact_type", "")),
        tenant_id=str(payload.get("tenant_id", "")),
        produced_by_event_id=str(payload.get("produced_by_event_id", "")),
        created_at=str(payload.get("created_at", "")),
        replayable=replayable,
        metadata=_json_mapping(_mapping_value(payload, "metadata")),
    )


def _edge_from_json_dict(payload: Mapping[str, Any]) -> ArtifactLineageEdge:
    if not isinstance(payload, Mapping):
        raise RuntimeCoreInvariantError("artifact edge snapshot row must be an object")
    relation_raw = str(payload.get("relation", ""))
    try:
        relation = ArtifactLineageRelation(relation_raw)
    except ValueError as exc:
        raise RuntimeCoreInvariantError("relation must be an ArtifactLineageRelation value") from exc
    return ArtifactLineageEdge(
        edge_id=str(payload.get("edge_id", "")),
        upstream_artifact_id=str(payload.get("upstream_artifact_id", "")),
        downstream_artifact_id=str(payload.get("downstream_artifact_id", "")),
        relation=relation,
        reason=str(payload.get("reason", "")),
        created_at=str(payload.get("created_at", "")),
    )


def _mapping_tuple(field_name: str, value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise RuntimeCoreInvariantError(f"{field_name} must be an array")
    rows: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise RuntimeCoreInvariantError(f"{field_name} entries must be objects")
        rows.append(_json_mapping(item))
    return tuple(rows)


def _mapping_value(payload: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = payload.get(field_name, {})
    if not isinstance(value, Mapping):
        raise RuntimeCoreInvariantError(f"{field_name} must be an object")
    return value


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
