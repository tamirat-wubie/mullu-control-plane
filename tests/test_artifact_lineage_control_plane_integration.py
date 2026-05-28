"""Tests for artifact-lineage control-plane integration.

Purpose: verify that the lineage-bootstrap helper builds a fresh DAG when no
hosted store is configured, restores from disk exactly once when a snapshot
file exists, and produces a shutdown callback that re-snapshots correctly.
Governance scope: DAG construction boundary, hosted-store path validation,
restore-on-startup ordering, and save-on-shutdown lifecycle.
Dependencies: artifact_lineage_integration helper, ArtifactLineageDAG, and
JsonArtifactLineageStore.
Invariants: unset env yields a DAG with no store and no callback; set env
validates the path, builds the store, loads from disk iff the file exists,
and emits a callback whose return mapping carries the snapshot fields;
invalid paths fail closed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from mcoi_runtime.app.artifact_lineage_integration import (
    ARTIFACT_LINEAGE_STORE_PATH_ENV,
    ArtifactLineageBootstrap,
    bootstrap_artifact_lineage,
    validate_artifact_lineage_store_path,
)
from mcoi_runtime.core.artifact_lineage_dag import (
    ArtifactLineageDAG,
    JsonArtifactLineageStore,
)


def _frozen_clock() -> str:
    return datetime(2026, 5, 28, 0, 0, 0, tzinfo=timezone.utc).isoformat()


def test_bootstrap_returns_fresh_dag_when_env_unset() -> None:
    bootstrap = bootstrap_artifact_lineage({}, clock=_frozen_clock)

    assert isinstance(bootstrap, ArtifactLineageBootstrap)
    assert isinstance(bootstrap.dag, ArtifactLineageDAG)
    assert bootstrap.store is None
    assert bootstrap.restored is False
    assert bootstrap.path == ""
    assert bootstrap.save_on_shutdown is None


def test_bootstrap_returns_fresh_dag_when_env_blank() -> None:
    bootstrap = bootstrap_artifact_lineage(
        {ARTIFACT_LINEAGE_STORE_PATH_ENV: "   "},
        clock=_frozen_clock,
    )

    assert bootstrap.store is None
    assert bootstrap.restored is False
    assert bootstrap.save_on_shutdown is None


def test_bootstrap_attaches_store_without_restoring_missing_file(tmp_path: Path) -> None:
    target = tmp_path / "artifact-lineage.json"

    bootstrap = bootstrap_artifact_lineage(
        {ARTIFACT_LINEAGE_STORE_PATH_ENV: str(target)},
        clock=_frozen_clock,
    )

    assert isinstance(bootstrap.store, JsonArtifactLineageStore)
    assert bootstrap.store.path == target.expanduser()
    assert bootstrap.restored is False
    assert bootstrap.path == str(target.expanduser())
    assert bootstrap.save_on_shutdown is not None


def test_bootstrap_restores_when_snapshot_file_present(tmp_path: Path) -> None:
    target = tmp_path / "artifact-lineage.json"
    seed_dag = ArtifactLineageDAG(clock=_frozen_clock)
    JsonArtifactLineageStore(target).save(seed_dag)

    bootstrap = bootstrap_artifact_lineage(
        {ARTIFACT_LINEAGE_STORE_PATH_ENV: str(target)},
        clock=_frozen_clock,
    )

    assert bootstrap.restored is True
    assert bootstrap.store is not None
    assert target.is_file()


def test_save_on_shutdown_returns_snapshot_summary(tmp_path: Path) -> None:
    target = tmp_path / "artifact-lineage.json"

    bootstrap = bootstrap_artifact_lineage(
        {ARTIFACT_LINEAGE_STORE_PATH_ENV: str(target)},
        clock=_frozen_clock,
    )

    assert bootstrap.save_on_shutdown is not None
    summary = bootstrap.save_on_shutdown()

    assert set(summary.keys()) == {"snapshot_id", "artifact_count", "edge_count"}
    assert summary["artifact_count"] == 0
    assert summary["edge_count"] == 0
    assert isinstance(summary["snapshot_id"], str) and summary["snapshot_id"]
    assert target.is_file()


def test_validate_rejects_relative_path() -> None:
    with pytest.raises(RuntimeError, match="absolute file path"):
        validate_artifact_lineage_store_path("relative/lineage.json")


def test_validate_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not a directory"):
        validate_artifact_lineage_store_path(tmp_path)


def test_validate_rejects_wrong_extension(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=".json file extension"):
        validate_artifact_lineage_store_path(tmp_path / "lineage.txt")


def test_validate_rejects_missing_parent(tmp_path: Path) -> None:
    missing_parent = tmp_path / "missing" / "lineage.json"

    with pytest.raises(RuntimeError, match="parent directory must already exist"):
        validate_artifact_lineage_store_path(missing_parent)

    assert not missing_parent.parent.exists()
