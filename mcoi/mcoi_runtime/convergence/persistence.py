"""Deterministic snapshot and recovery for the CDG-RCCM reference kernel."""

from __future__ import annotations

from dataclasses import replace
import json
from typing import Iterable

from .contracts import (
    AuditEvent,
    ComponentProjectionRequest,
    ConsistencyMode,
    DependencyGate,
    DependencyRelation,
    EvidenceScope,
    FrameStatus,
    OutcomeCode,
    ProjectionCertificate,
    SettlementLevel,
    ContinuationFrame,
    canonical_json,
)
from .invalidation import ProjectionReadIndex
from .kernel import ConvergentComponent, RecursiveConvergenceOrchestrationKernel


class ConvergenceSnapshotError(ValueError):
    """Raised when a persisted convergence snapshot is malformed or incompatible."""


def dump_kernel_snapshot(kernel: RecursiveConvergenceOrchestrationKernel) -> str:
    """Serialize a kernel state without serializing executable component code."""

    if not isinstance(kernel, RecursiveConvergenceOrchestrationKernel):
        raise ConvergenceSnapshotError("kernel must be a RecursiveConvergenceOrchestrationKernel")
    return canonical_json(kernel.snapshot_payload())


def restore_kernel_snapshot(
    snapshot_json: str,
    *,
    components: Iterable[ConvergentComponent],
) -> RecursiveConvergenceOrchestrationKernel:
    """Restore persisted runtime state and rebind separately supplied component code."""

    try:
        payload = json.loads(snapshot_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ConvergenceSnapshotError("snapshot must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ConvergenceSnapshotError("snapshot root must be a JSON object")
    if payload.get("protocol_version") != "cdg-rccm.v1":
        raise ConvergenceSnapshotError("snapshot protocol version is incompatible")

    kernel = RecursiveConvergenceOrchestrationKernel(
        maximum_global_steps=_positive_int(payload.get("maximum_global_steps"), "maximum_global_steps")
    )
    for component in components:
        kernel.register_component(component)

    epoch_id = payload.get("current_epoch_id")
    root_component_id = payload.get("current_root_component_id")
    if epoch_id is not None and not isinstance(epoch_id, str):
        raise ConvergenceSnapshotError("current_epoch_id must be a string or null")
    if root_component_id is not None and not isinstance(root_component_id, str):
        raise ConvergenceSnapshotError("current_root_component_id must be a string or null")
    kernel._current_epoch_id = epoch_id
    kernel._current_root_component_id = root_component_id
    kernel._current_root_projections = tuple(
        _text_list(payload.get("current_root_projections", []), "current_root_projections")
    )
    kernel._executed_steps = _non_negative_int(payload.get("executed_steps", 0), "executed_steps")

    for edge in payload.get("containment_edges", []):
        if not isinstance(edge, list) or len(edge) != 2:
            raise ConvergenceSnapshotError("containment edge must be a two-item array")
        kernel.containment.add(str(edge[0]), str(edge[1]))

    for request_payload in _object_list(payload.get("requests", []), "requests"):
        request = _request_from_dict(request_payload)
        kernel.requests[request.request_id] = request
        kernel.dependencies.add_request(request)

    request_consumers = payload.get("request_consumers", {})
    if not isinstance(request_consumers, dict):
        raise ConvergenceSnapshotError("request_consumers must be an object")
    kernel.request_consumers = {
        str(request_id): str(frame_id)
        for request_id, frame_id in request_consumers.items()
    }

    request_solutions = payload.get("request_solutions", {})
    if not isinstance(request_solutions, dict):
        raise ConvergenceSnapshotError("request_solutions must be an object")
    kernel.request_solutions = {
        str(request_id): tuple(_text_list(certificate_ids, f"request_solutions.{request_id}"))
        for request_id, certificate_ids in request_solutions.items()
    }

    for frame_payload in _object_list(payload.get("frames", []), "frames"):
        frame = _frame_from_dict(frame_payload)
        if frame.component_id not in kernel.components:
            raise ConvergenceSnapshotError(
                f"snapshot references unregistered component: {frame.component_id}"
            )
        kernel.frames[frame.frame_id] = frame
        kernel._replay_frames[frame.frame_id] = replace(frame, status=FrameStatus.READY)
        if frame.status is FrameStatus.READY:
            kernel._enqueue(frame)

    for provider_payload in _object_list(payload.get("provider_frames", []), "provider_frames"):
        key = (
            _text(provider_payload.get("component_id"), "provider_frames.component_id"),
            _text(provider_payload.get("projection_name"), "provider_frames.projection_name"),
            _text(provider_payload.get("epoch_id"), "provider_frames.epoch_id"),
        )
        kernel.provider_frames[key] = _text(provider_payload.get("frame_id"), "provider_frames.frame_id")

    for certificate_payload in _object_list(payload.get("certificates", []), "certificates"):
        certificate = _certificate_from_dict(certificate_payload)
        kernel.certificates[certificate.certificate_id] = certificate

    for latest_payload in _object_list(payload.get("latest_certificates", []), "latest_certificates"):
        key = (
            _text(latest_payload.get("component_id"), "latest_certificates.component_id"),
            _text(latest_payload.get("projection_name"), "latest_certificates.projection_name"),
            _text(latest_payload.get("epoch_id"), "latest_certificates.epoch_id"),
        )
        certificate_id = _text(
            latest_payload.get("certificate_id"),
            "latest_certificates.certificate_id",
        )
        if certificate_id not in kernel.certificates:
            raise ConvergenceSnapshotError("latest certificate references missing certificate")
        kernel.latest_certificates[key] = certificate_id

    kernel.audit_events = [
        _audit_event_from_dict(event_payload)
        for event_payload in _object_list(payload.get("audit_events", []), "audit_events")
    ]
    kernel._event_sequence = max((event.sequence for event in kernel.audit_events), default=0)

    terminal_payload = payload.get("component_terminal", {})
    if not isinstance(terminal_payload, dict):
        raise ConvergenceSnapshotError("component_terminal must be an object")
    for component_id, terminal_value in terminal_payload.items():
        if not isinstance(terminal_value, list) or len(terminal_value) != 2:
            raise ConvergenceSnapshotError("component_terminal value must contain code and reason")
        kernel._component_terminal[str(component_id)] = (
            OutcomeCode(str(terminal_value[0])),
            _text(terminal_value[1], "component_terminal.reason"),
        )

    read_index_payload = payload.get("read_index", {})
    if not isinstance(read_index_payload, dict):
        raise ConvergenceSnapshotError("read_index must be an object")
    kernel.read_index = ProjectionReadIndex.restore(read_index_payload)

    for certificate in kernel.certificates.values():
        kernel.read_index.record_certificate_lineage(certificate)

    return kernel


def _frame_from_dict(payload: dict[str, object]) -> ContinuationFrame:
    return ContinuationFrame(
        frame_id=_text(payload.get("frame_id"), "frame_id"),
        component_id=_text(payload.get("component_id"), "component_id"),
        epoch_id=_text(payload.get("epoch_id"), "epoch_id"),
        root_component_id=_text(payload.get("root_component_id"), "root_component_id"),
        phase=_text(payload.get("phase"), "phase"),
        resume_token=_text(payload.get("resume_token"), "resume_token"),
        partial_state=_object(payload.get("partial_state", {}), "partial_state"),
        target_projections=tuple(_text_list(payload.get("target_projections", []), "target_projections")),
        pending_request_ids=tuple(_text_list(payload.get("pending_request_ids", []), "pending_request_ids")),
        dependency_certificate_ids=tuple(
            _text_list(payload.get("dependency_certificate_ids", []), "dependency_certificate_ids")
        ),
        read_set=tuple(_text_list(payload.get("read_set", []), "read_set")),
        generation=_non_negative_int(payload.get("generation", 0), "generation"),
        depth=_non_negative_int(payload.get("depth", 0), "depth"),
        priority=_integer(payload.get("priority", 0), "priority"),
        status=FrameStatus(_text(payload.get("status"), "status")),
        parent_frame_id=str(payload.get("parent_frame_id") or ""),
    )


def _request_from_dict(payload: dict[str, object]) -> ComponentProjectionRequest:
    maximum_age = payload.get("maximum_age_seconds")
    return ComponentProjectionRequest(
        request_id=_text(payload.get("request_id"), "request_id"),
        consumer_component_id=_text(payload.get("consumer_component_id"), "consumer_component_id"),
        provider_component_id=_text(payload.get("provider_component_id"), "provider_component_id"),
        projection_name=_text(payload.get("projection_name"), "projection_name"),
        minimum_level=SettlementLevel(_integer(payload.get("minimum_level"), "minimum_level")),
        gate=DependencyGate(_text(payload.get("gate"), "gate")),
        epoch_id=_text(payload.get("epoch_id"), "epoch_id"),
        relation=DependencyRelation(_text(payload.get("relation"), "relation")),
        consistency=ConsistencyMode(_text(payload.get("consistency"), "consistency")),
        assumptions=tuple(_text_list(payload.get("assumptions", []), "assumptions")),
        maximum_age_seconds=(float(maximum_age) if maximum_age is not None else None),
        fallback_provider_ids=tuple(
            _text_list(payload.get("fallback_provider_ids", []), "fallback_provider_ids")
        ),
        quorum=_positive_int(payload.get("quorum", 1), "quorum"),
    )


def _certificate_from_dict(payload: dict[str, object]) -> ProjectionCertificate:
    confidence = payload.get("confidence")
    if type(confidence) not in (int, float):
        raise ConvergenceSnapshotError("certificate confidence must be numeric")
    return ProjectionCertificate(
        certificate_id=_text(payload.get("certificate_id"), "certificate_id"),
        component_id=_text(payload.get("component_id"), "component_id"),
        projection_name=_text(payload.get("projection_name"), "projection_name"),
        level=SettlementLevel(_integer(payload.get("level"), "level")),
        epoch_id=_text(payload.get("epoch_id"), "epoch_id"),
        state_hash=_text(payload.get("state_hash"), "state_hash"),
        rule_hash=_text(payload.get("rule_hash"), "rule_hash"),
        input_hash=_text(payload.get("input_hash"), "input_hash"),
        dependency_certificate_ids=tuple(
            _text_list(payload.get("dependency_certificate_ids", []), "dependency_certificate_ids")
        ),
        assumptions=tuple(_text_list(payload.get("assumptions", []), "assumptions")),
        evidence_refs=tuple(_text_list(payload.get("evidence_refs", []), "evidence_refs")),
        evidence_scope=EvidenceScope(_text(payload.get("evidence_scope"), "evidence_scope")),
        confidence=float(confidence),
        value=payload.get("value"),
        audit_digest=_text(payload.get("audit_digest"), "audit_digest"),
        valid=_boolean(payload.get("valid", True), "valid"),
    )


def _audit_event_from_dict(payload: dict[str, object]) -> AuditEvent:
    return AuditEvent(
        event_id=_text(payload.get("event_id"), "event_id"),
        epoch_id=_text(payload.get("epoch_id"), "epoch_id"),
        sequence=_non_negative_int(payload.get("sequence"), "sequence"),
        component_id=_text(payload.get("component_id"), "component_id"),
        frame_id=_text(payload.get("frame_id"), "frame_id"),
        event_type=_text(payload.get("event_type"), "event_type"),
        trigger=_text(payload.get("trigger"), "trigger"),
        previous_status=_text(payload.get("previous_status"), "previous_status"),
        new_status=_text(payload.get("new_status"), "new_status"),
        constructive_delta=_object(payload.get("constructive_delta", {}), "constructive_delta"),
        fracture_delta=_object(payload.get("fracture_delta", {}), "fracture_delta"),
        dependency_certificate_ids=tuple(
            _text_list(payload.get("dependency_certificate_ids", []), "dependency_certificate_ids")
        ),
        judgment=str(payload.get("judgment") or ""),
    )


def _object(value: object, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ConvergenceSnapshotError(f"{field_name} must be an object")
    return dict(value)


def _object_list(value: object, field_name: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ConvergenceSnapshotError(f"{field_name} must be an array")
    result: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ConvergenceSnapshotError(f"{field_name} entries must be objects")
        result.append(dict(item))
    return result


def _text_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ConvergenceSnapshotError(f"{field_name} must be an array")
    return [_text(item, f"{field_name}[]") for item in value]


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConvergenceSnapshotError(f"{field_name} must be a non-empty string")
    return value


def _integer(value: object, field_name: str) -> int:
    if type(value) is not int:
        raise ConvergenceSnapshotError(f"{field_name} must be an integer")
    return value


def _non_negative_int(value: object, field_name: str) -> int:
    integer = _integer(value, field_name)
    if integer < 0:
        raise ConvergenceSnapshotError(f"{field_name} must be non-negative")
    return integer


def _positive_int(value: object, field_name: str) -> int:
    integer = _integer(value, field_name)
    if integer < 1:
        raise ConvergenceSnapshotError(f"{field_name} must be positive")
    return integer


def _boolean(value: object, field_name: str) -> bool:
    if type(value) is not bool:
        raise ConvergenceSnapshotError(f"{field_name} must be a bool")
    return value
