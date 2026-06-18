"""Projection-scoped causal invalidation for CDG-RCCM."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import replace
from typing import Iterable, Mapping

from .contracts import (
    InvalidationReason,
    InvalidationRecord,
    ProjectionCertificate,
    stable_hash,
)


class ProjectionReadIndex:
    """Index exact provider projection paths to consuming frames and certificates."""

    def __init__(self) -> None:
        self._frames_by_path: dict[str, set[str]] = defaultdict(set)
        self._paths_by_frame: dict[str, set[str]] = defaultdict(set)
        self._certificates_by_dependency: dict[str, set[str]] = defaultdict(set)

    @staticmethod
    def path(component_id: str, projection_name: str) -> str:
        return f"{component_id}/{projection_name}"

    def record_frame_read(self, frame_id: str, component_id: str, projection_name: str) -> None:
        projection_path = self.path(component_id, projection_name)
        self._frames_by_path[projection_path].add(frame_id)
        self._paths_by_frame[frame_id].add(projection_path)

    def clear_frame(self, frame_id: str) -> None:
        for projection_path in self._paths_by_frame.pop(frame_id, set()):
            self._frames_by_path.get(projection_path, set()).discard(frame_id)

    def frames_for_paths(self, projection_paths: Iterable[str]) -> tuple[str, ...]:
        frame_ids: set[str] = set()
        for projection_path in projection_paths:
            frame_ids.update(self._frames_by_path.get(projection_path, set()))
        return tuple(sorted(frame_ids))

    def record_certificate_lineage(self, certificate: ProjectionCertificate) -> None:
        for dependency_certificate_id in certificate.dependency_certificate_ids:
            self._certificates_by_dependency[dependency_certificate_id].add(certificate.certificate_id)

    def dependent_certificates(self, certificate_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._certificates_by_dependency.get(certificate_id, set())))

    def snapshot(self) -> dict[str, object]:
        return {
            "frames_by_path": {
                path: sorted(frame_ids)
                for path, frame_ids in sorted(self._frames_by_path.items())
            },
            "paths_by_frame": {
                frame_id: sorted(paths)
                for frame_id, paths in sorted(self._paths_by_frame.items())
            },
            "certificates_by_dependency": {
                certificate_id: sorted(dependents)
                for certificate_id, dependents in sorted(self._certificates_by_dependency.items())
            },
        }

    @classmethod
    def restore(cls, payload: Mapping[str, object]) -> "ProjectionReadIndex":
        index = cls()
        for path, frame_ids in dict(payload.get("frames_by_path", {})).items():
            for frame_id in frame_ids:
                index._frames_by_path[str(path)].add(str(frame_id))
        for frame_id, paths in dict(payload.get("paths_by_frame", {})).items():
            for path in paths:
                index._paths_by_frame[str(frame_id)].add(str(path))
        for certificate_id, dependents in dict(payload.get("certificates_by_dependency", {})).items():
            for dependent in dependents:
                index._certificates_by_dependency[str(certificate_id)].add(str(dependent))
        return index


def invalidate_certificate_closure(
    *,
    epoch_id: str,
    provider_component_id: str,
    changed_projection_paths: tuple[str, ...],
    root_certificate_ids: tuple[str, ...],
    certificates: dict[str, ProjectionCertificate],
    read_index: ProjectionReadIndex,
) -> InvalidationRecord:
    """Mark a certificate and its causal dependents stale without deleting history."""

    queue: deque[str] = deque(root_certificate_ids)
    stale: set[str] = set()
    while queue:
        certificate_id = queue.popleft()
        if certificate_id in stale:
            continue
        certificate = certificates.get(certificate_id)
        if certificate is None:
            continue
        stale.add(certificate_id)
        if certificate.valid:
            certificates[certificate_id] = replace(certificate, valid=False)
        queue.extend(read_index.dependent_certificates(certificate_id))

    reactivated_frames = read_index.frames_for_paths(changed_projection_paths)
    invalidation_id = stable_hash(
        "cdg-invalidation",
        {
            "epoch_id": epoch_id,
            "provider_component_id": provider_component_id,
            "changed_projection_paths": changed_projection_paths,
            "stale_certificate_ids": sorted(stale),
            "reactivated_frame_ids": reactivated_frames,
        },
    )
    return InvalidationRecord(
        invalidation_id=invalidation_id,
        epoch_id=epoch_id,
        provider_component_id=provider_component_id,
        changed_projection_paths=changed_projection_paths,
        stale_certificate_ids=tuple(sorted(stale)),
        reactivated_frame_ids=reactivated_frames,
        reason=InvalidationReason.PROJECTION_CHANGED,
    )
