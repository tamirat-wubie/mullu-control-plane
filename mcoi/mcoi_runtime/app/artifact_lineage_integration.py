"""Artifact-lineage DAG + store integration for the control-plane app.

Purpose: build the artifact-lineage DAG and, when configured, restore it
from a hosted snapshot file before publication, plus produce a shutdown
callback that re-snapshots on close.
Governance scope: DAG construction boundary, hosted-store path validation,
restore-on-startup ordering, and save-on-shutdown lifecycle.
Dependencies: ArtifactLineageDAG runtime, JsonArtifactLineageStore
persistence, and standard filesystem access primitives.
Invariants: an unset env path means a fresh in-memory DAG, no store, and no
shutdown callback; when set the path must be absolute, must use a .json
extension, must not be a directory, and the parent directory must already
exist and be writable; ``store.load`` runs exactly once before publication
when the snapshot file exists; the shutdown callback returns the snapshot
summary as a plain mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from mcoi_runtime.core.artifact_lineage_dag import (
    ArtifactLineageDAG,
    JsonArtifactLineageStore,
)


ARTIFACT_LINEAGE_STORE_PATH_ENV = "MULLU_ARTIFACT_LINEAGE_STORE_PATH"


@dataclass(frozen=True)
class ArtifactLineageBootstrap:
    """Startup posture for the artifact-lineage integration."""

    dag: ArtifactLineageDAG
    store: JsonArtifactLineageStore | None
    path: str
    restored: bool
    save_on_shutdown: Callable[[], Mapping[str, Any]] | None


def bootstrap_artifact_lineage(
    runtime_env: Mapping[str, str],
    *,
    clock: Callable[[], str],
) -> ArtifactLineageBootstrap:
    """Build the artifact-lineage DAG and wire any configured persistence."""

    raw_value = runtime_env.get(ARTIFACT_LINEAGE_STORE_PATH_ENV)
    if raw_value is None or not str(raw_value).strip():
        return ArtifactLineageBootstrap(
            dag=ArtifactLineageDAG(clock=clock),
            store=None,
            path="",
            restored=False,
            save_on_shutdown=None,
        )

    path = validate_artifact_lineage_store_path(str(raw_value).strip())
    store = JsonArtifactLineageStore(path)
    if store.path.exists():
        dag = store.load(clock=clock)
        restored = True
    else:
        dag = ArtifactLineageDAG(clock=clock)
        restored = False

    def _save_on_shutdown() -> Mapping[str, Any]:
        snapshot = store.save(dag)
        return {
            "snapshot_id": snapshot.snapshot_id,
            "artifact_count": snapshot.artifact_count,
            "edge_count": snapshot.edge_count,
        }

    return ArtifactLineageBootstrap(
        dag=dag,
        store=store,
        path=str(path),
        restored=restored,
        save_on_shutdown=_save_on_shutdown,
    )


def validate_artifact_lineage_store_path(store_path: str | Path) -> Path:
    """Validate the hosted artifact-lineage snapshot path before use."""

    path = Path(store_path).expanduser()
    if not path.is_absolute():
        raise RuntimeError(
            f"{ARTIFACT_LINEAGE_STORE_PATH_ENV} must be an absolute file path"
        )
    if path.exists() and path.is_dir():
        raise RuntimeError(
            f"{ARTIFACT_LINEAGE_STORE_PATH_ENV} must point to a JSON file, not a directory"
        )
    if path.suffix.lower() != ".json":
        raise RuntimeError(
            f"{ARTIFACT_LINEAGE_STORE_PATH_ENV} must use a .json file extension"
        )
    parent = path.parent
    if not parent.exists():
        raise RuntimeError(
            f"{ARTIFACT_LINEAGE_STORE_PATH_ENV} parent directory must already exist"
        )
    if not parent.is_dir():
        raise RuntimeError(
            f"{ARTIFACT_LINEAGE_STORE_PATH_ENV} parent must be a directory"
        )
    if path.exists() and not path.is_file():
        raise RuntimeError(
            f"{ARTIFACT_LINEAGE_STORE_PATH_ENV} must point to a regular file"
        )
    writable_target = path if path.exists() else parent
    if not os.access(writable_target, os.W_OK):
        raise RuntimeError(
            f"{ARTIFACT_LINEAGE_STORE_PATH_ENV} must be writable by the control-plane process"
        )
    return path
