"""Replay report-store integration for the control-plane app.

Purpose: select replay determinism report history storage from runtime
environment and validate any hosted persistence path before construction.
Governance scope: file-vs-in-memory selection boundary, hosted-store path
validation, and fail-closed misconfiguration handling.
Dependencies: persistence replay report stores and shared integration path
validation.
Invariants: no env path means a non-persistent in-memory store; an env path
must be absolute, must use a .json extension, must not point to a directory,
and the parent directory must already exist and be writable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from mcoi_runtime.app._integration_paths import validate_hosted_store_path
from mcoi_runtime.persistence.replay_report_store import (
    FileReplayReportStore,
    ReplayReportStore,
)


REPLAY_REPORT_STORE_PATH_ENV = "MULLU_REPLAY_REPORT_STORE_PATH"


@dataclass(frozen=True)
class ReplayReportStoreBootstrap:
    """Startup posture for the replay determinism report store."""

    store: ReplayReportStore
    path: str
    persistent: bool


def select_replay_report_store(
    runtime_env: Mapping[str, str],
) -> ReplayReportStoreBootstrap:
    """Return the replay report store that matches the runtime environment."""

    raw_value = runtime_env.get(REPLAY_REPORT_STORE_PATH_ENV)
    if raw_value is None or not str(raw_value).strip():
        return ReplayReportStoreBootstrap(
            store=ReplayReportStore(),
            path="",
            persistent=False,
        )

    path = validate_replay_report_store_path(str(raw_value).strip())
    return ReplayReportStoreBootstrap(
        store=FileReplayReportStore(path),
        path=str(path),
        persistent=True,
    )


def validate_replay_report_store_path(store_path: str | Path) -> Path:
    """Validate the hosted replay report-store path before use."""

    return validate_hosted_store_path(
        store_path,
        env_name=REPLAY_REPORT_STORE_PATH_ENV,
        kind="file",
        required_suffix=".json",
    )
