"""Purpose: verify artifact lineage DAG replay and impact behavior.
Governance scope: artifact dependency ordering, cycle blocking, and replay
eligibility classification.
Dependencies: mcoi_runtime.core.artifact_lineage_dag.
Invariants: lineage remains acyclic; blocked replay is explicit.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.artifact_lineage_dag import (
    ArtifactLineageDAG,
    ArtifactLineageRelation,
    ArtifactLineageSnapshot,
    JsonArtifactLineageStore,
    hash_artifact_payload,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


def _clock() -> str:
    return "2026-05-13T13:00:00+00:00"


def _dag() -> ArtifactLineageDAG:
    return ArtifactLineageDAG(clock=_clock)


def _register(
    dag: ArtifactLineageDAG,
    artifact_id: str,
    *,
    replayable: bool = True,
) -> None:
    dag.register_artifact(
        artifact_id=artifact_id,
        artifact_hash=hash_artifact_payload({"artifact_id": artifact_id}),
        artifact_type="json",
        tenant_id="tenant-1",
        produced_by_event_id=f"event-{artifact_id}",
        replayable=replayable,
    )


def test_replay_plan_orders_dependencies_before_target() -> None:
    dag = _dag()
    _register(dag, "source")
    _register(dag, "normalized")
    _register(dag, "report")
    dag.add_edge(upstream_artifact_id="source", downstream_artifact_id="normalized", reason="parse input")
    dag.add_edge(upstream_artifact_id="normalized", downstream_artifact_id="report", reason="render report")

    plan = dag.replay_plan("report")

    assert plan.ready is True
    assert plan.artifact_ids == ("source", "normalized", "report")
    assert plan.blocked_reasons == ()
    assert dag.topological_order() == ("source", "normalized", "report")


def test_lineage_blocks_cycles_and_preserves_existing_edges() -> None:
    dag = _dag()
    _register(dag, "source")
    _register(dag, "report")
    dag.add_edge(upstream_artifact_id="source", downstream_artifact_id="report", reason="derive report")

    with pytest.raises(RuntimeCoreInvariantError, match="cycle detected"):
        dag.add_edge(
            upstream_artifact_id="report",
            downstream_artifact_id="source",
            relation=ArtifactLineageRelation.DERIVED_FROM,
            reason="invalid back edge",
        )

    assert dag.edge_count == 1
    assert dag.detect_cycle() == ()
    assert dag.replay_plan("report").artifact_ids == ("source", "report")


def test_descendants_identify_transitive_change_impact() -> None:
    dag = _dag()
    _register(dag, "raw")
    _register(dag, "normalized")
    _register(dag, "summary")
    _register(dag, "dashboard")
    dag.add_edge(upstream_artifact_id="raw", downstream_artifact_id="normalized", reason="clean input")
    dag.add_edge(upstream_artifact_id="normalized", downstream_artifact_id="summary", reason="aggregate")
    dag.add_edge(upstream_artifact_id="summary", downstream_artifact_id="dashboard", reason="publish")

    impacted = dag.descendants_of("raw")

    assert impacted == ("normalized", "summary", "dashboard")
    assert dag.ancestors_of("dashboard") == ("raw", "normalized", "summary")
    assert dag.artifact_count == 4
    assert dag.edge_count == 3


def test_replay_plan_blocks_non_replayable_artifact() -> None:
    dag = _dag()
    _register(dag, "external-upload", replayable=False)
    _register(dag, "report")
    dag.add_edge(upstream_artifact_id="external-upload", downstream_artifact_id="report", reason="manual upload")

    plan = dag.replay_plan("report")

    assert plan.ready is False
    assert plan.artifact_ids == ("external-upload", "report")
    assert plan.blocked_reasons == ("external-upload:not_replayable",)
    assert len(plan.plan_hash) == 64


def test_registration_and_edge_shape_violations_fail_closed() -> None:
    dag = _dag()
    _register(dag, "source")
    _register(dag, "report")

    with pytest.raises(RuntimeCoreInvariantError, match="artifact_id"):
        dag.register_artifact(
            artifact_id="",  # type: ignore[arg-type]
            artifact_hash=hash_artifact_payload({"artifact_id": "empty"}),
            artifact_type="json",
            tenant_id="tenant-1",
            produced_by_event_id="event-empty",
        )
    with pytest.raises(RuntimeCoreInvariantError, match="relation must be an ArtifactLineageRelation"):
        dag.add_edge(
            upstream_artifact_id="source",
            downstream_artifact_id="report",
            relation="depends_on",  # type: ignore[arg-type]
            reason="invalid relation shape",
        )
    with pytest.raises(RuntimeCoreInvariantError, match="artifact not found"):
        dag.replay_plan("missing")

    assert dag.artifact_count == 2
    assert dag.edge_count == 0


def test_snapshot_roundtrip_preserves_replay_plan_and_impact() -> None:
    dag = _dag()
    _register(dag, "raw")
    _register(dag, "summary")
    _register(dag, "dashboard")
    dag.add_edge(upstream_artifact_id="raw", downstream_artifact_id="summary", reason="summarize")
    dag.add_edge(upstream_artifact_id="summary", downstream_artifact_id="dashboard", reason="publish")

    snapshot = dag.export_snapshot()
    restored = ArtifactLineageDAG.from_snapshot(snapshot.to_json_dict(), clock=_clock)

    assert snapshot.snapshot_id.startswith("artifact-lineage-snapshot-")
    assert snapshot.artifact_count == 3
    assert snapshot.edge_count == 2
    assert restored.replay_plan("dashboard").artifact_ids == ("raw", "summary", "dashboard")
    assert restored.descendants_of("raw") == ("summary", "dashboard")
    assert restored.topological_order() == ("raw", "summary", "dashboard")


def test_json_artifact_lineage_store_survives_process_restart(tmp_path) -> None:
    dag = _dag()
    _register(dag, "source")
    _register(dag, "report", replayable=False)
    dag.add_edge(upstream_artifact_id="source", downstream_artifact_id="report", reason="manual report")
    store = JsonArtifactLineageStore(tmp_path / "artifact-lineage.json")

    saved = store.save(dag)
    restored = store.load(clock=_clock)
    plan = restored.replay_plan("report")

    assert store.path.exists()
    assert saved.snapshot_hash == restored.export_snapshot().snapshot_hash
    assert plan.ready is False
    assert plan.blocked_reasons == ("report:not_replayable",)
    assert restored.dependencies_of("report") == ("source",)


def test_snapshot_hash_is_deterministic_for_same_graph_and_clock() -> None:
    first = _dag()
    second = _dag()
    for dag in (first, second):
        _register(dag, "source")
        _register(dag, "report")
        dag.add_edge(upstream_artifact_id="source", downstream_artifact_id="report", reason="derive")

    first_snapshot = first.export_snapshot()
    second_snapshot = second.export_snapshot()

    assert first_snapshot.snapshot_hash == second_snapshot.snapshot_hash
    assert first_snapshot.snapshot_id == second_snapshot.snapshot_id
    assert first_snapshot.to_json_dict() == second_snapshot.to_json_dict()


def test_snapshot_restore_rejects_tampered_hash() -> None:
    dag = _dag()
    _register(dag, "source")
    snapshot = dag.export_snapshot().to_json_dict()
    snapshot["artifacts"][0]["artifact_hash"] = "tampered"

    with pytest.raises(RuntimeCoreInvariantError, match="snapshot hash mismatch"):
        ArtifactLineageSnapshot.from_json_dict(snapshot)


def test_snapshot_restore_rejects_loose_snapshot_counts() -> None:
    dag = _dag()
    _register(dag, "source")
    snapshot = dag.export_snapshot().to_json_dict()
    snapshot["artifact_count"] = "1"

    with pytest.raises(RuntimeCoreInvariantError, match="artifact_count must be an integer"):
        ArtifactLineageSnapshot.from_json_dict(snapshot)


def test_snapshot_restore_rejects_loose_artifact_identifier() -> None:
    row = {
        "artifact_id": 7,
        "artifact_hash": hash_artifact_payload({"artifact_id": 7}),
        "artifact_type": "json",
        "tenant_id": "tenant-1",
        "produced_by_event_id": "event-7",
        "created_at": _clock(),
        "replayable": True,
        "metadata": {},
    }
    snapshot = ArtifactLineageSnapshot.build(
        created_at=_clock(),
        artifacts=(row,),
        edges=(),
    ).to_json_dict()

    with pytest.raises(RuntimeCoreInvariantError, match="artifact_id must be a string"):
        ArtifactLineageDAG.from_snapshot(snapshot, clock=_clock)


def test_snapshot_restore_rejects_loose_edge_relation() -> None:
    dag = _dag()
    _register(dag, "source")
    _register(dag, "report")
    dag.add_edge(upstream_artifact_id="source", downstream_artifact_id="report", reason="derive")
    snapshot = dag.export_snapshot().to_json_dict()
    snapshot["edges"][0]["relation"] = 3
    repaired_snapshot = ArtifactLineageSnapshot.build(
        created_at=snapshot["created_at"],
        artifacts=tuple(snapshot["artifacts"]),
        edges=tuple(snapshot["edges"]),
    )

    with pytest.raises(RuntimeCoreInvariantError, match="relation must be a string"):
        ArtifactLineageDAG.from_snapshot(repaired_snapshot, clock=_clock)


def test_snapshot_restore_rejects_missing_edge_endpoint() -> None:
    dag = _dag()
    _register(dag, "source")
    _register(dag, "report")
    dag.add_edge(upstream_artifact_id="source", downstream_artifact_id="report", reason="derive")
    snapshot = dag.export_snapshot().to_json_dict()
    snapshot["edges"][0]["downstream_artifact_id"] = "missing-report"
    repaired_snapshot = ArtifactLineageSnapshot.build(
        created_at=snapshot["created_at"],
        artifacts=tuple(snapshot["artifacts"]),
        edges=tuple(snapshot["edges"]),
    )

    with pytest.raises(RuntimeCoreInvariantError, match="artifact not found"):
        ArtifactLineageDAG.from_snapshot(repaired_snapshot, clock=_clock)
