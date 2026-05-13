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
