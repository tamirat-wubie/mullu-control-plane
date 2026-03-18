"""Purpose: verify read-only filesystem observation for the MCOI runtime.
Governance scope: execution-slice tests only.
Dependencies: pytest temp paths and the execution-slice filesystem observer.
Invariants: filesystem observation is bounded, read-only, and encodes missing-path failures explicitly.
"""

from __future__ import annotations

from mcoi_runtime.adapters.filesystem_observer import (
    FilesystemObservationMode,
    FilesystemObservationRequest,
    FilesystemObserver,
)
from mcoi_runtime.adapters.observer_base import ObservationStatus


def test_filesystem_observer_reports_existing_paths_and_metadata_read_only(tmp_path) -> None:
    observer = FilesystemObserver()
    target = tmp_path / "sample.txt"
    target.write_text("hello", encoding="utf-8")

    exists_result = observer.observe(
        FilesystemObservationRequest(path=str(target), mode=FilesystemObservationMode.EXISTS)
    )
    metadata_result = observer.observe(
        FilesystemObservationRequest(path=str(target), mode=FilesystemObservationMode.METADATA)
    )

    assert exists_result.status is ObservationStatus.SUCCEEDED
    assert exists_result.evidence[0].details["exists"] is True
    assert metadata_result.evidence[0].details["size_bytes"] == 5
    assert target.read_text(encoding="utf-8") == "hello"


def test_filesystem_observer_lists_directories_without_mutation(tmp_path) -> None:
    observer = FilesystemObserver()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "b.txt").write_text("b", encoding="utf-8")
    (workspace / "a.txt").write_text("a", encoding="utf-8")

    result = observer.observe(
        FilesystemObservationRequest(
            path=str(workspace),
            mode=FilesystemObservationMode.LIST_DIRECTORY,
            max_entries=10,
        )
    )

    assert result.status is ObservationStatus.SUCCEEDED
    assert result.evidence[0].details["entries"] == ("a.txt", "b.txt")
    assert sorted(item.name for item in workspace.iterdir()) == ["a.txt", "b.txt"]


def test_filesystem_observer_encodes_missing_path_failures() -> None:
    observer = FilesystemObserver()
    result = observer.observe(
        FilesystemObservationRequest(
            path="C:/missing/path/for/mcoi-runtime",
            mode=FilesystemObservationMode.EXISTS,
        )
    )

    assert result.status is ObservationStatus.FAILED
    assert result.failures[0].code == "path_not_found"
    assert "does not exist" in result.failures[0].message
    assert result.evidence == ()
