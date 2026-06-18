"""Recursive Convergence Orchestration Kernel for CDG-RCCM.

The kernel schedules independent continuation frames, resolves exact projection
requests, recursively activates providers, certifies candidates outside component
code, invalidates causal consumers, classifies cycles, solves declared semantic
feedback regions, and certifies only the active required closure.
"""

from __future__ import annotations

from dataclasses import replace
import heapq
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from .contracts import (
    AuditEvent,
    Candidate,
    Cancelled,
    ComponentContract,
    ComponentProjectionRequest,
    Conflict,
    ContinuationFrame,
    CycleClass,
    DependencyGate,
    ExecutionJudgment,
    Fault,
    FrameStatus,
    Need,
    OutcomeCode,
    Progress,
    ProjectionCertificate,
    SettlementLevel,
    StepOutcome,
    Unknown,
    ValidationJudgment,
    canonical_json,
    stable_hash,
)
from .invalidation import ProjectionReadIndex, invalidate_certificate_closure
from .topology import ContainmentGraph, ConvergenceRegion, DependencyMesh


@runtime_checkable
class ConvergentComponent(Protocol):
    """Governed component protocol consumed by the convergence kernel."""

    @property
    def contract(self) -> ComponentContract: ...

    def initial_frame(
        self,
        *,
        epoch_id: str,
        root_component_id: str,
        target_projections: tuple[str, ...],
        depth: int,
        parent_frame_id: str,
    ) -> ContinuationFrame: ...

    def step(
        self,
        frame: ContinuationFrame,
        dependency_view: Mapping[str, ProjectionCertificate],
    ) -> StepOutcome: ...

    def validate_candidate(
        self,
        candidate: Candidate,
        dependency_view: Mapping[str, ProjectionCertificate],
    ) -> ValidationJudgment: ...

    def reconcile_candidate(
        self,
        candidate: Candidate,
        dependency_view: Mapping[str, ProjectionCertificate],
    ) -> ValidationJudgment: ...


class BaseConvergentComponent:
    """Convenience base with deterministic frame construction and pass validators."""

    contract: ComponentContract

    def initial_frame(
        self,
        *,
        epoch_id: str,
        root_component_id: str,
        target_projections: tuple[str, ...],
        depth: int,
        parent_frame_id: str,
    ) -> ContinuationFrame:
        frame_id = stable_hash(
            "cdg-frame",
            {
                "component_id": self.contract.component_id,
                "epoch_id": epoch_id,
                "root_component_id": root_component_id,
                "target_projections": target_projections,
                "depth": depth,
                "parent_frame_id": parent_frame_id,
            },
        )
        return ContinuationFrame(
            frame_id=frame_id,
            component_id=self.contract.component_id,
            epoch_id=epoch_id,
            root_component_id=root_component_id,
            phase="start",
            resume_token="start",
            target_projections=target_projections,
            depth=depth,
            parent_frame_id=parent_frame_id,
        )

    def validate_candidate(
        self,
        candidate: Candidate,
        dependency_view: Mapping[str, ProjectionCertificate],
    ) -> ValidationJudgment:
        del candidate, dependency_view
        return ValidationJudgment(passed=True)

    def reconcile_candidate(
        self,
        candidate: Candidate,
        dependency_view: Mapping[str, ProjectionCertificate],
    ) -> ValidationJudgment:
        del candidate, dependency_view
        return ValidationJudgment(passed=True)


ComponentFactory = Callable[[str, ComponentProjectionRequest], ConvergentComponent]


class RecursiveConvergenceOrchestrationKernel:
    """Deterministic in-memory CDG-RCCM reference runtime."""

    def __init__(self, *, maximum_global_steps: int = 10000) -> None:
        if type(maximum_global_steps) is not int or maximum_global_steps < 1:
            raise ValueError("maximum_global_steps must be a positive integer")
        self.maximum_global_steps = maximum_global_steps
        self.components: dict[str, ConvergentComponent] = {}
        self.component_factories: list[tuple[str, ComponentFactory]] = []
        self.containment = ContainmentGraph()
        self.dependencies = DependencyMesh()
        self.frames: dict[str, ContinuationFrame] = {}
        self.certificates: dict[str, ProjectionCertificate] = {}
        self.latest_certificates: dict[tuple[str, str, str], str] = {}
        self.requests: dict[str, ComponentProjectionRequest] = {}
        self.request_consumers: dict[str, str] = {}
        self.request_solutions: dict[str, tuple[str, ...]] = {}
        self.provider_frames: dict[tuple[str, str, str], str] = {}
        self.read_index = ProjectionReadIndex()
        self.audit_events: list[AuditEvent] = []
        self.invalidation_records: list[Any] = []
        self._ready: list[tuple[int, int, str]] = []
        self._queue_sequence = 0
        self._event_sequence = 0
        self._component_terminal: dict[str, tuple[OutcomeCode, str]] = {}
        self._replay_frames: dict[str, ContinuationFrame] = {}
        self._current_epoch_id: str | None = None
        self._current_root_component_id: str | None = None
        self._current_root_projections: tuple[str, ...] = ()
        self._executed_steps = 0

    # ------------------------------------------------------------------
    # Registration and topology
    # ------------------------------------------------------------------

    def register_component(self, component: ConvergentComponent) -> None:
        if not isinstance(component, ConvergentComponent):
            raise ValueError("component must implement ConvergentComponent")
        component_id = component.contract.component_id
        existing = self.components.get(component_id)
        if existing is not None and existing is not component:
            if existing.contract != component.contract:
                raise ValueError("component_id already registered with a different contract")
            return
        self.components[component_id] = component

    def register_component_factory(self, component_id_prefix: str, factory: ComponentFactory) -> None:
        if not component_id_prefix:
            raise ValueError("component_id_prefix must be non-empty")
        if not callable(factory):
            raise ValueError("factory must be callable")
        self.component_factories.append((component_id_prefix, factory))
        self.component_factories.sort(key=lambda item: (-len(item[0]), item[0]))

    def add_containment(self, parent_component_id: str, child_component_id: str) -> None:
        self.containment.add(parent_component_id, child_component_id)

    # ------------------------------------------------------------------
    # Public execution
    # ------------------------------------------------------------------

    def run(
        self,
        *,
        root_component_id: str,
        epoch_id: str,
        root_projections: tuple[str, ...] = ("result",),
    ) -> ExecutionJudgment:
        if not root_component_id or not epoch_id:
            raise ValueError("root_component_id and epoch_id must be non-empty")
        if not root_projections:
            raise ValueError("root_projections must not be empty")
        if self._current_epoch_id is not None and self._current_epoch_id != epoch_id:
            raise ValueError("kernel already contains a different active epoch")
        self._current_epoch_id = epoch_id
        self._current_root_component_id = root_component_id
        self._current_root_projections = tuple(root_projections)

        root_component = self._require_component(root_component_id, None)
        for projection in root_projections:
            if projection not in root_component.contract.output_projections:
                raise ValueError(f"root projection not declared by component: {projection}")

        if not self._has_component_frame(root_component_id, epoch_id, root_projections):
            root_frame = root_component.initial_frame(
                epoch_id=epoch_id,
                root_component_id=root_component_id,
                target_projections=tuple(root_projections),
                depth=0,
                parent_frame_id="",
            )
            self._admit_frame(root_frame)

        while self._executed_steps < self.maximum_global_steps:
            frame = self._take_ready()
            if frame is not None:
                self._execute_frame(frame)
                self._executed_steps += 1
                continue

            self._wake_satisfied_frames()
            if self._ready:
                continue

            closure = self._try_certify_root_closure()
            if closure is not None:
                return closure

            terminal = self._terminal_judgment_if_any()
            if terminal is not None:
                return terminal

            cycle_result = self._resolve_wait_cycles()
            if cycle_result is True:
                continue
            if isinstance(cycle_result, ExecutionJudgment):
                return cycle_result

            unresolved = self._unresolved_blocking_requests()
            if unresolved:
                return self._judgment(
                    OutcomeCode.BLOCKED,
                    reasons=tuple(
                        f"unresolved_dependency:{request.request_id}"
                        for request in unresolved
                    ),
                )

            return self._judgment(
                OutcomeCode.UNKNOWN,
                reasons=("quiescence_without_root_certificate",),
            )

        return self._judgment(
            OutcomeCode.UNKNOWN,
            reasons=("maximum_global_steps_exhausted",),
        )

    # ------------------------------------------------------------------
    # Frame execution
    # ------------------------------------------------------------------

    def _execute_frame(self, frame: ContinuationFrame) -> None:
        current = self.frames.get(frame.frame_id)
        if current is None or current.status is not FrameStatus.READY:
            return
        if current.epoch_id != self._current_epoch_id:
            self._fail_component(current, OutcomeCode.STALE, "frame_epoch_is_stale")
            return
        component = self.components[current.component_id]
        running = replace(current, status=FrameStatus.RUNNING)
        self.frames[running.frame_id] = running
        self._replay_frames[running.frame_id] = replace(running, status=FrameStatus.READY)
        self._audit(running, "frame_started", current.status, running.status, "scheduler")

        dependency_view = self._build_dependency_view(running)
        try:
            outcome = component.step(running, dependency_view)
        except Exception as exc:  # fail closed with bounded error type only
            self._fail_component(running, OutcomeCode.FAULT, f"component_step_fault:{type(exc).__name__}")
            return

        try:
            if isinstance(outcome, Need):
                self._handle_need(running, outcome)
            elif isinstance(outcome, Progress):
                self._handle_progress(running, outcome)
            elif isinstance(outcome, Candidate):
                self._handle_candidate(running, component, outcome, dependency_view)
            elif isinstance(outcome, Conflict):
                self._fail_component(running, OutcomeCode.UNSAT, outcome.explanation)
            elif isinstance(outcome, Unknown):
                self._fail_component(running, OutcomeCode.UNKNOWN, outcome.reason)
            elif isinstance(outcome, Fault):
                self._fail_component(running, OutcomeCode.FAULT, outcome.reason)
            elif isinstance(outcome, Cancelled):
                self._fail_component(running, OutcomeCode.CANCELLED, outcome.reason)
            else:
                self._fail_component(running, OutcomeCode.FAULT, "unsupported_step_outcome")
        except Exception as exc:
            self._fail_component(running, OutcomeCode.FAULT, f"outcome_handling_fault:{type(exc).__name__}")

    def _handle_need(self, running: ContinuationFrame, outcome: Need) -> None:
        continuation = self._normalize_continuation(running, outcome.continuation)
        self._admit_spawned_frames(outcome.spawned_frames, running)
        request_ids: list[str] = []
        dependency_certificate_ids: list[str] = []
        read_set: list[str] = []
        all_blocking_satisfied = True

        for request in outcome.requests:
            self._validate_request_against_frame(request, running)
            self.requests[request.request_id] = request
            self.request_consumers[request.request_id] = running.frame_id
            self.dependencies.add_request(request)
            request_ids.append(request.request_id)
            certificates = self._find_satisfying_certificates(request)
            if certificates:
                self.request_solutions[request.request_id] = tuple(
                    certificate.certificate_id for certificate in certificates
                )
                dependency_certificate_ids.extend(certificate.certificate_id for certificate in certificates)
                for certificate in certificates:
                    path = ProjectionReadIndex.path(certificate.component_id, certificate.projection_name)
                    read_set.append(path)
                    self.read_index.record_frame_read(running.frame_id, certificate.component_id, certificate.projection_name)
            elif self._request_blocks(request):
                all_blocking_satisfied = False
                self._schedule_provider(request, running)
            else:
                self.request_solutions[request.request_id] = ()

        continuation = replace(
            continuation,
            pending_request_ids=tuple(dict.fromkeys(request_ids)),
            dependency_certificate_ids=tuple(dict.fromkeys(dependency_certificate_ids)),
            read_set=tuple(dict.fromkeys(read_set)),
            status=FrameStatus.READY if all_blocking_satisfied else FrameStatus.SUSPENDED,
        )
        self.frames[continuation.frame_id] = continuation
        self._replay_frames[continuation.frame_id] = replace(continuation, status=FrameStatus.READY)
        if all_blocking_satisfied:
            self._enqueue(continuation)
        self._audit(
            continuation,
            "frame_dependency_wait" if not all_blocking_satisfied else "frame_dependency_satisfied",
            running.status,
            continuation.status,
            "component_need",
        )

    def _handle_progress(self, running: ContinuationFrame, outcome: Progress) -> None:
        continuation = self._normalize_continuation(running, outcome.continuation)
        continuation = replace(continuation, status=FrameStatus.READY)
        self.frames[continuation.frame_id] = continuation
        self._replay_frames[continuation.frame_id] = continuation
        self._admit_spawned_frames(outcome.spawned_frames, running)
        if outcome.changed_projections:
            self._invalidate_component_projections(
                component_id=running.component_id,
                projection_names=outcome.changed_projections,
            )
        self._audit(
            continuation,
            "frame_progressed",
            running.status,
            continuation.status,
            "component_progress",
            constructive_delta=outcome.constructive_delta,
            fracture_delta=outcome.fracture_delta,
        )
        self._enqueue(continuation)

    def _handle_candidate(
        self,
        running: ContinuationFrame,
        component: ConvergentComponent,
        candidate: Candidate,
        dependency_view: Mapping[str, ProjectionCertificate],
    ) -> None:
        undeclared = set(candidate.projections) - set(component.contract.output_projections)
        if undeclared:
            self._fail_component(running, OutcomeCode.FAULT, "candidate_contains_undeclared_projection")
            return
        missing_targets = set(running.target_projections) - set(candidate.projections)
        if missing_targets:
            self._fail_component(running, OutcomeCode.FAULT, "candidate_missing_target_projection")
            return

        try:
            local = component.validate_candidate(candidate, dependency_view)
            boundary = component.reconcile_candidate(candidate, dependency_view)
        except Exception as exc:
            self._fail_component(running, OutcomeCode.FAULT, f"candidate_validation_fault:{type(exc).__name__}")
            return
        if not local.passed:
            self._fail_component(running, OutcomeCode.UNSAT, "local_validation_failed:" + ",".join(local.reasons))
            return
        if not boundary.passed:
            self._fail_component(running, OutcomeCode.UNSAT, "boundary_reconciliation_failed:" + ",".join(boundary.reasons))
            return

        issued: list[str] = []
        for projection_name, value in candidate.projections.items():
            certificate = self._issue_certificate(
                component=component,
                frame=running,
                projection_name=projection_name,
                value=value,
                level=SettlementLevel.BOUNDARY_RECONCILED,
                candidate=candidate,
                evidence_refs=tuple(dict.fromkeys((*local.evidence_refs, *boundary.evidence_refs, *candidate.evidence_refs))),
            )
            issued.append(certificate.certificate_id)

        quiescent = replace(running, status=FrameStatus.QUIESCENT)
        self.frames[quiescent.frame_id] = quiescent
        self._audit(
            quiescent,
            "frame_candidate_certified",
            running.status,
            quiescent.status,
            "certificate_authority",
            judgment=",".join(issued),
        )
        self._wake_satisfied_frames()

    # ------------------------------------------------------------------
    # Dependency resolution
    # ------------------------------------------------------------------

    def _validate_request_against_frame(
        self,
        request: ComponentProjectionRequest,
        frame: ContinuationFrame,
    ) -> None:
        if request.consumer_component_id != frame.component_id:
            raise ValueError("dependency request consumer must match frame component")
        if request.epoch_id != frame.epoch_id:
            raise ValueError("dependency request epoch must match frame epoch")

    def _request_blocks(self, request: ComponentProjectionRequest) -> bool:
        return request.gate in {
            DependencyGate.HARD,
            DependencyGate.PROVISIONAL,
            DependencyGate.ALTERNATIVE,
            DependencyGate.QUORUM,
            DependencyGate.TEMPORAL,
        }

    def _find_satisfying_certificates(
        self,
        request: ComponentProjectionRequest,
    ) -> tuple[ProjectionCertificate, ...]:
        providers = (request.provider_component_id, *request.fallback_provider_ids)
        matches: list[ProjectionCertificate] = []
        for provider_id in providers:
            certificate_id = self.latest_certificates.get(
                (provider_id, request.projection_name, request.epoch_id)
            )
            if certificate_id is None:
                continue
            certificate = self.certificates[certificate_id]
            if not certificate.valid:
                continue
            if certificate.level < request.minimum_level:
                continue
            if not set(request.assumptions).issubset(set(certificate.assumptions)):
                continue
            matches.append(certificate)
            if request.gate is not DependencyGate.QUORUM:
                break
        required = request.quorum if request.gate is DependencyGate.QUORUM else 1
        if len(matches) < required:
            return ()
        return tuple(matches[:required])

    def _schedule_provider(
        self,
        request: ComponentProjectionRequest,
        consumer_frame: ContinuationFrame,
    ) -> None:
        provider_ids = (request.provider_component_id, *request.fallback_provider_ids)
        providers_to_schedule = provider_ids if request.gate in {DependencyGate.ALTERNATIVE, DependencyGate.QUORUM} else provider_ids[:1]
        scheduled_or_existing = 0
        unavailable_provider_ids: list[str] = []
        for provider_id in providers_to_schedule:
            try:
                provider = self._require_component(provider_id, request)
            except ValueError:
                unavailable_provider_ids.append(provider_id)
                continue
            if request.projection_name not in provider.contract.output_projections:
                unavailable_provider_ids.append(provider_id)
                if request.gate not in {DependencyGate.ALTERNATIVE, DependencyGate.QUORUM}:
                    self._component_terminal[provider_id] = (
                        OutcomeCode.FAULT,
                        "requested_projection_not_declared",
                    )
                continue
            if consumer_frame.depth + 1 > provider.contract.maximum_depth:
                self._component_terminal[provider_id] = (
                    OutcomeCode.UNKNOWN,
                    "maximum_component_depth_exceeded",
                )
                continue
            key = (provider_id, request.projection_name, request.epoch_id)
            existing_frame_id = self.provider_frames.get(key)
            if existing_frame_id is None:
                existing_frame_id = next(
                    (
                        frame.frame_id
                        for frame in self.frames.values()
                        if frame.component_id == provider_id
                        and frame.epoch_id == request.epoch_id
                        and request.projection_name in frame.target_projections
                        and frame.status not in {FrameStatus.FAILED, FrameStatus.CANCELLED}
                    ),
                    None,
                )
                if existing_frame_id is not None:
                    self.provider_frames[key] = existing_frame_id
            if existing_frame_id is not None:
                existing_frame = self.frames.get(existing_frame_id)
                if existing_frame is not None and existing_frame.status not in {
                    FrameStatus.FAILED,
                    FrameStatus.CANCELLED,
                }:
                    scheduled_or_existing += 1
                    continue
            provider_frame = provider.initial_frame(
                epoch_id=request.epoch_id,
                root_component_id=consumer_frame.root_component_id,
                target_projections=(request.projection_name,),
                depth=consumer_frame.depth + 1,
                parent_frame_id=consumer_frame.frame_id,
            )
            self.provider_frames[key] = provider_frame.frame_id
            self._admit_frame(provider_frame)
            scheduled_or_existing += 1

        required_provider_count = request.quorum if request.gate is DependencyGate.QUORUM else 1
        if scheduled_or_existing < required_provider_count:
            self._component_terminal[request.consumer_component_id] = (
                OutcomeCode.BLOCKED,
                "dependency_provider_unavailable:" + ",".join(unavailable_provider_ids),
            )

    def _build_dependency_view(
        self,
        frame: ContinuationFrame,
    ) -> Mapping[str, ProjectionCertificate]:
        view: dict[str, ProjectionCertificate] = {}
        certificate_ids: list[str] = []
        read_paths: list[str] = []
        for request_id in frame.pending_request_ids:
            request = self.requests.get(request_id)
            if request is None:
                continue
            certificates = self._find_satisfying_certificates(request)
            if certificates:
                self.request_solutions[request_id] = tuple(certificate.certificate_id for certificate in certificates)
            else:
                certificates = tuple(
                    self.certificates[certificate_id]
                    for certificate_id in self.request_solutions.get(request_id, ())
                    if certificate_id in self.certificates and self.certificates[certificate_id].valid
                )
            for certificate in certificates:
                projection_path = ProjectionReadIndex.path(
                    certificate.component_id,
                    certificate.projection_name,
                )
                view[projection_path] = certificate
                certificate_ids.append(certificate.certificate_id)
                read_paths.append(projection_path)
                self.read_index.record_frame_read(
                    frame.frame_id,
                    certificate.component_id,
                    certificate.projection_name,
                )
        if certificate_ids or read_paths:
            updated = replace(
                frame,
                dependency_certificate_ids=tuple(dict.fromkeys(certificate_ids)),
                read_set=tuple(dict.fromkeys(read_paths)),
            )
            self.frames[frame.frame_id] = updated
        return view

    def _wake_satisfied_frames(self) -> None:
        for frame_id in sorted(self.frames):
            frame = self.frames[frame_id]
            if frame.status is not FrameStatus.SUSPENDED:
                continue
            blocking_requests = [
                self.requests[request_id]
                for request_id in frame.pending_request_ids
                if request_id in self.requests and self._request_blocks(self.requests[request_id])
            ]
            solutions: list[ProjectionCertificate] = []
            all_satisfied = True
            for request in blocking_requests:
                certificates = self._find_satisfying_certificates(request)
                if not certificates:
                    all_satisfied = False
                    break
                self.request_solutions[request.request_id] = tuple(
                    certificate.certificate_id for certificate in certificates
                )
                solutions.extend(certificates)
            if not all_satisfied:
                continue
            ready = replace(
                frame,
                status=FrameStatus.READY,
                dependency_certificate_ids=tuple(
                    dict.fromkeys(certificate.certificate_id for certificate in solutions)
                ),
                read_set=tuple(
                    dict.fromkeys(
                        ProjectionReadIndex.path(
                            certificate.component_id,
                            certificate.projection_name,
                        )
                        for certificate in solutions
                    )
                ),
            )
            self.frames[frame_id] = ready
            for certificate in solutions:
                self.read_index.record_frame_read(
                    frame_id,
                    certificate.component_id,
                    certificate.projection_name,
                )
            self._audit(ready, "frame_resumed", frame.status, ready.status, "dependency_certificate")
            self._enqueue(ready)

    # ------------------------------------------------------------------
    # Certificates and invalidation
    # ------------------------------------------------------------------

    def _issue_certificate(
        self,
        *,
        component: ConvergentComponent,
        frame: ContinuationFrame,
        projection_name: str,
        value: Any,
        level: SettlementLevel,
        candidate: Candidate,
        evidence_refs: tuple[str, ...],
    ) -> ProjectionCertificate:
        state_hash = stable_hash(
            "cdg-state",
            {"state": candidate.state, "projection": projection_name, "value": value},
        )
        input_hash = stable_hash(
            "cdg-input",
            {
                "partial_state": frame.partial_state,
                "target_projections": frame.target_projections,
                "dependency_certificate_ids": frame.dependency_certificate_ids,
            },
        )
        rule_hash = stable_hash(
            "cdg-rule",
            {
                "component_id": component.contract.component_id,
                "rule_version": component.contract.rule_version,
                "protocol_version": component.contract.protocol_version,
            },
        )
        assumptions = tuple(
            dict.fromkeys(
                assumption
                for request_id in frame.pending_request_ids
                if request_id in self.requests
                for assumption in self.requests[request_id].assumptions
            )
        )
        certificate_payload = {
            "component_id": component.contract.component_id,
            "projection_name": projection_name,
            "level": int(level),
            "epoch_id": frame.epoch_id,
            "state_hash": state_hash,
            "rule_hash": rule_hash,
            "input_hash": input_hash,
            "dependency_certificate_ids": frame.dependency_certificate_ids,
            "assumptions": assumptions,
            "evidence_refs": evidence_refs,
            "evidence_scope": candidate.evidence_scope.value,
            "confidence": candidate.confidence,
            "value": value,
        }
        certificate_id = stable_hash("cdg-certificate", certificate_payload)
        audit_digest = self._audit_digest(extra=certificate_payload)
        certificate = ProjectionCertificate(
            certificate_id=certificate_id,
            component_id=component.contract.component_id,
            projection_name=projection_name,
            level=level,
            epoch_id=frame.epoch_id,
            state_hash=state_hash,
            rule_hash=rule_hash,
            input_hash=input_hash,
            dependency_certificate_ids=frame.dependency_certificate_ids,
            assumptions=assumptions,
            evidence_refs=evidence_refs,
            evidence_scope=candidate.evidence_scope,
            confidence=candidate.confidence,
            value=value,
            audit_digest=audit_digest,
        )
        key = (certificate.component_id, certificate.projection_name, certificate.epoch_id)
        previous_id = self.latest_certificates.get(key)
        if previous_id == certificate.certificate_id:
            previous = self.certificates[previous_id]
            if previous.valid and previous.level >= level:
                return previous
        if previous_id is not None:
            previous = self.certificates[previous_id]
            if previous.valid and previous.state_hash != certificate.state_hash:
                self._invalidate_certificate_ids(
                    provider_component_id=component.contract.component_id,
                    projection_names=(projection_name,),
                    certificate_ids=(previous_id,),
                )
        self.certificates[certificate.certificate_id] = certificate
        self.latest_certificates[key] = certificate.certificate_id
        self.read_index.record_certificate_lineage(certificate)
        return certificate

    def inject_certificate(self, certificate: ProjectionCertificate) -> None:
        """Admit an externally produced certificate after exact context validation."""

        if certificate.epoch_id != self._current_epoch_id and self._current_epoch_id is not None:
            raise ValueError("cannot inject a certificate from another epoch")
        key = (certificate.component_id, certificate.projection_name, certificate.epoch_id)
        previous_id = self.latest_certificates.get(key)
        if previous_id is not None and previous_id != certificate.certificate_id:
            previous = self.certificates[previous_id]
            if previous.valid and previous.state_hash != certificate.state_hash:
                self._invalidate_certificate_ids(
                    provider_component_id=certificate.component_id,
                    projection_names=(certificate.projection_name,),
                    certificate_ids=(previous_id,),
                )
        self.certificates[certificate.certificate_id] = certificate
        self.latest_certificates[key] = certificate.certificate_id
        self.read_index.record_certificate_lineage(certificate)
        self._wake_satisfied_frames()

    def _invalidate_component_projections(
        self,
        *,
        component_id: str,
        projection_names: tuple[str, ...],
    ) -> None:
        certificate_ids = tuple(
            certificate_id
            for projection_name in projection_names
            if (
                certificate_id := self.latest_certificates.get(
                    (component_id, projection_name, self._current_epoch_id or "")
                )
            )
        )
        if certificate_ids:
            self._invalidate_certificate_ids(
                provider_component_id=component_id,
                projection_names=projection_names,
                certificate_ids=certificate_ids,
            )

    def _invalidate_certificate_ids(
        self,
        *,
        provider_component_id: str,
        projection_names: tuple[str, ...],
        certificate_ids: tuple[str, ...],
    ) -> None:
        epoch_id = self._current_epoch_id or self.certificates[certificate_ids[0]].epoch_id
        paths = tuple(
            ProjectionReadIndex.path(provider_component_id, projection_name)
            for projection_name in projection_names
        )
        record = invalidate_certificate_closure(
            epoch_id=epoch_id,
            provider_component_id=provider_component_id,
            changed_projection_paths=paths,
            root_certificate_ids=certificate_ids,
            certificates=self.certificates,
            read_index=self.read_index,
        )
        self.invalidation_records.append(record)
        for frame_id in record.reactivated_frame_ids:
            replay = self._replay_frames.get(frame_id)
            if replay is None:
                continue
            ready = replace(replay, status=FrameStatus.READY)
            self.frames[frame_id] = ready
            self._enqueue(ready)
        stale_set = set(record.stale_certificate_ids)
        for key, certificate_id in tuple(self.latest_certificates.items()):
            if certificate_id in stale_set:
                self.latest_certificates.pop(key, None)

    # ------------------------------------------------------------------
    # Cycle diagnosis and convergence regions
    # ------------------------------------------------------------------

    def _resolve_wait_cycles(self) -> bool | ExecutionJudgment:
        suspended_components = {
            frame.component_id
            for frame in self.frames.values()
            if frame.status is FrameStatus.SUSPENDED
        }
        if not suspended_components:
            return False
        regions = self.dependencies.cyclic_regions(suspended_components)
        if not regions:
            return False
        progressed = False
        for region in regions:
            if region.cycle_class is not CycleClass.SEMANTIC_FEEDBACK:
                code = {
                    CycleClass.RESOURCE_DEADLOCK: OutcomeCode.BLOCKED,
                    CycleClass.AUTHORITY_DEADLOCK: OutcomeCode.BLOCKED,
                    CycleClass.TEMPORAL_FEEDBACK: OutcomeCode.BLOCKED,
                    CycleClass.ALTERNATIVE_SELECTION: OutcomeCode.UNKNOWN,
                    CycleClass.HIDDEN_SELF_DEPENDENCY: OutcomeCode.FAULT,
                    CycleClass.STRUCTURAL_CONTAINMENT: OutcomeCode.FAULT,
                }.get(region.cycle_class, OutcomeCode.UNKNOWN)
                return self._judgment(
                    code,
                    reasons=(f"cycle:{region.cycle_class.value}:{region.region_id}",),
                )
            result = self._solve_semantic_feedback_region(region)
            if result is None:
                return self._judgment(
                    OutcomeCode.UNKNOWN,
                    reasons=(f"semantic_cycle_not_solved:{region.region_id}",),
                )
            progressed = True
        if progressed:
            self._wake_satisfied_frames()
        return progressed

    def _solve_semantic_feedback_region(
        self,
        region: ConvergenceRegion,
    ) -> tuple[ProjectionCertificate, ...] | None:
        components = [self.components[component_id] for component_id in region.component_ids]
        if any(not callable(getattr(component, "region_seed", None)) for component in components):
            return None
        if any(not callable(getattr(component, "region_step", None)) for component in components):
            return None
        requests = [self.requests[request_id] for request_id in region.request_ids]
        values: dict[str, Any] = {}
        target_by_component: dict[str, set[str]] = {}
        for request in requests:
            target_by_component.setdefault(request.provider_component_id, set()).add(request.projection_name)
        for component in components:
            for projection_name in sorted(target_by_component.get(component.contract.component_id, set())):
                key = ProjectionReadIndex.path(component.contract.component_id, projection_name)
                values[key] = component.region_seed(projection_name)  # type: ignore[attr-defined]

        maximum_iterations = min(
            component.contract.convergence_policy.maximum_iterations
            for component in components
        )
        stable_required = max(
            component.contract.convergence_policy.stable_iterations
            for component in components
        )
        oscillation_detection = any(
            component.contract.convergence_policy.oscillation_detection
            for component in components
        )
        seen_signatures: set[str] = set()
        stable_count = 0
        last_candidates: dict[str, Candidate] = {}

        for generation in range(maximum_iterations):
            signature = stable_hash("cdg-region-state", values)
            if oscillation_detection and signature in seen_signatures:
                return None
            seen_signatures.add(signature)
            next_values = dict(values)
            candidates: dict[str, Candidate] = {}
            for component in sorted(components, key=lambda item: item.contract.component_id):
                candidate = component.region_step(dict(values), generation)  # type: ignore[attr-defined]
                if not isinstance(candidate, Candidate):
                    return None
                candidates[component.contract.component_id] = candidate
                for projection_name, value in candidate.projections.items():
                    if projection_name in target_by_component.get(component.contract.component_id, set()):
                        next_values[ProjectionReadIndex.path(component.contract.component_id, projection_name)] = value
            if canonical_json(next_values) == canonical_json(values):
                stable_count += 1
            else:
                stable_count = 0
            values = next_values
            last_candidates = candidates
            if stable_count >= stable_required:
                break
        else:
            return None

        issued: list[ProjectionCertificate] = []
        for component in sorted(components, key=lambda item: item.contract.component_id):
            candidate = last_candidates[component.contract.component_id]
            synthetic_frame = self._region_synthetic_frame(component.contract.component_id, region)
            for projection_name in sorted(target_by_component.get(component.contract.component_id, set())):
                certificate = self._issue_certificate(
                    component=component,
                    frame=synthetic_frame,
                    projection_name=projection_name,
                    value=values[ProjectionReadIndex.path(component.contract.component_id, projection_name)],
                    level=SettlementLevel.BOUNDARY_RECONCILED,
                    candidate=candidate,
                    evidence_refs=(f"region:{region.region_id}",),
                )
                issued.append(certificate)
        return tuple(issued)

    def _region_synthetic_frame(
        self,
        component_id: str,
        region: ConvergenceRegion,
    ) -> ContinuationFrame:
        frame = next(
            frame
            for frame in self.frames.values()
            if frame.component_id == component_id
            and frame.status is FrameStatus.SUSPENDED
        )
        dependency_ids = tuple(
            certificate_id
            for request_id in region.request_ids
            for certificate_id in self.request_solutions.get(request_id, ())
        )
        return replace(
            frame,
            frame_id=stable_hash("cdg-region-frame", {"region": region.region_id, "component": component_id}),
            phase="semantic_feedback_region",
            resume_token="region_certificate",
            dependency_certificate_ids=tuple(dict.fromkeys(dependency_ids)),
            status=FrameStatus.RUNNING,
        )

    # ------------------------------------------------------------------
    # Active closure certification
    # ------------------------------------------------------------------

    def _try_certify_root_closure(self) -> ExecutionJudgment | None:
        if self._current_root_component_id is None or self._current_epoch_id is None:
            return None
        root = self._current_root_component_id
        active = set(self.dependencies.active_required_closure(root))
        active.add(root)
        active_frames = [
            frame for frame in self.frames.values()
            if frame.root_component_id == root and frame.component_id in active
        ]
        if not active_frames:
            return None
        if any(frame.status is not FrameStatus.QUIESCENT for frame in active_frames):
            return None
        if self._unresolved_blocking_requests(active):
            return None

        boundary_certificates: list[ProjectionCertificate] = []
        for projection_name in self._current_root_projections:
            certificate_id = self.latest_certificates.get((root, projection_name, self._current_epoch_id))
            if certificate_id is None:
                return None
            certificate = self.certificates[certificate_id]
            if not certificate.valid or certificate.level < SettlementLevel.BOUNDARY_RECONCILED:
                return None
            boundary_certificates.append(certificate)

        closure_ids: list[str] = []
        for certificate in boundary_certificates:
            payload = {
                "source_certificate_id": certificate.certificate_id,
                "root_component_id": root,
                "epoch_id": self._current_epoch_id,
                "active_closure": sorted(active),
                "audit_digest": self._audit_digest(),
            }
            closure_id = stable_hash("cdg-closure-certificate", payload)
            closure = ProjectionCertificate(
                certificate_id=closure_id,
                component_id=certificate.component_id,
                projection_name=certificate.projection_name,
                level=SettlementLevel.CLOSURE_CERTIFIED,
                epoch_id=certificate.epoch_id,
                state_hash=certificate.state_hash,
                rule_hash=certificate.rule_hash,
                input_hash=certificate.input_hash,
                dependency_certificate_ids=tuple(
                    dict.fromkeys((*certificate.dependency_certificate_ids, certificate.certificate_id))
                ),
                assumptions=certificate.assumptions,
                evidence_refs=certificate.evidence_refs,
                evidence_scope=certificate.evidence_scope,
                confidence=certificate.confidence,
                value=certificate.value,
                audit_digest=self._audit_digest(extra=payload),
            )
            self.certificates[closure.certificate_id] = closure
            self.latest_certificates[(root, closure.projection_name, closure.epoch_id)] = closure.certificate_id
            self.read_index.record_certificate_lineage(closure)
            closure_ids.append(closure.certificate_id)
        return self._judgment(
            OutcomeCode.CERTIFIED,
            certificate_ids=tuple(closure_ids),
            reasons=("active_required_closure_certified",),
        )

    def _unresolved_blocking_requests(
        self,
        active_components: set[str] | None = None,
    ) -> tuple[ComponentProjectionRequest, ...]:
        unresolved: list[ComponentProjectionRequest] = []
        for request in self.requests.values():
            if active_components is not None and request.consumer_component_id not in active_components:
                continue
            if not self._request_blocks(request):
                continue
            if not self._find_satisfying_certificates(request):
                unresolved.append(request)
        return tuple(sorted(unresolved, key=lambda request: request.request_id))

    # ------------------------------------------------------------------
    # Scheduler and utilities
    # ------------------------------------------------------------------

    def _admit_frame(self, frame: ContinuationFrame) -> None:
        if frame.epoch_id != self._current_epoch_id:
            raise ValueError("frame epoch must match active epoch")
        component = self.components.get(frame.component_id)
        if component is None:
            raise ValueError("frame component is not registered")
        component_frames = sum(
            1 for existing in self.frames.values()
            if existing.component_id == frame.component_id
        )
        if component_frames >= component.contract.maximum_frames:
            self._component_terminal[frame.component_id] = (
                OutcomeCode.UNKNOWN,
                "maximum_component_frames_exceeded",
            )
            return
        existing = self.frames.get(frame.frame_id)
        if existing is not None and existing != frame:
            raise ValueError("frame_id identity collision")
        ready = replace(frame, status=FrameStatus.READY)
        self.frames[ready.frame_id] = ready
        self._replay_frames[ready.frame_id] = ready
        self._enqueue(ready)
        self._audit(ready, "frame_admitted", FrameStatus.READY, FrameStatus.READY, "component_activation")

    def _admit_spawned_frames(
        self,
        frames: tuple[ContinuationFrame, ...],
        parent: ContinuationFrame,
    ) -> None:
        for frame in frames:
            if frame.root_component_id != parent.root_component_id:
                raise ValueError("spawned frame root must match parent root")
            if frame.epoch_id != parent.epoch_id:
                raise ValueError("spawned frame epoch must match parent epoch")
            self._admit_frame(frame)

    def _normalize_continuation(
        self,
        running: ContinuationFrame,
        continuation: ContinuationFrame,
    ) -> ContinuationFrame:
        if continuation.frame_id != running.frame_id:
            raise ValueError("continuation must preserve frame_id")
        if continuation.component_id != running.component_id:
            raise ValueError("continuation must preserve component_id")
        if continuation.epoch_id != running.epoch_id:
            raise ValueError("continuation must preserve epoch_id")
        if continuation.root_component_id != running.root_component_id:
            raise ValueError("continuation must preserve root_component_id")
        if continuation.generation < running.generation:
            raise ValueError("continuation generation must not go backwards")
        return continuation

    def _enqueue(self, frame: ContinuationFrame) -> None:
        self._queue_sequence += 1
        heapq.heappush(
            self._ready,
            (-frame.priority, self._queue_sequence, frame.frame_id),
        )

    def _take_ready(self) -> ContinuationFrame | None:
        while self._ready:
            _, _, frame_id = heapq.heappop(self._ready)
            frame = self.frames.get(frame_id)
            if frame is not None and frame.status is FrameStatus.READY:
                return frame
        return None

    def _has_component_frame(
        self,
        component_id: str,
        epoch_id: str,
        target_projections: tuple[str, ...],
    ) -> bool:
        return any(
            frame.component_id == component_id
            and frame.epoch_id == epoch_id
            and set(target_projections).issubset(set(frame.target_projections))
            for frame in self.frames.values()
        )

    def _require_component(
        self,
        component_id: str,
        request: ComponentProjectionRequest | None,
    ) -> ConvergentComponent:
        component = self.components.get(component_id)
        if component is not None:
            return component
        if request is not None:
            for prefix, factory in self.component_factories:
                if component_id.startswith(prefix):
                    component = factory(component_id, request)
                    self.register_component(component)
                    return component
        raise ValueError(f"component_not_registered:{component_id}")

    def _fail_component(
        self,
        frame: ContinuationFrame,
        outcome: OutcomeCode,
        reason: str,
    ) -> None:
        failed_status = FrameStatus.CANCELLED if outcome is OutcomeCode.CANCELLED else FrameStatus.FAILED
        failed = replace(frame, status=failed_status)
        self.frames[failed.frame_id] = failed
        self._component_terminal[failed.component_id] = (outcome, reason)
        self._audit(
            failed,
            "frame_terminal",
            frame.status,
            failed.status,
            reason,
            judgment=outcome.value,
        )

    def _terminal_judgment_if_any(self) -> ExecutionJudgment | None:
        if self._current_root_component_id is None:
            return None
        active = set(self.dependencies.active_required_closure(self._current_root_component_id))
        active.add(self._current_root_component_id)
        failures = [
            (component_id, *self._component_terminal[component_id])
            for component_id in sorted(active)
            if component_id in self._component_terminal
        ]
        if not failures:
            return None
        precedence = {
            OutcomeCode.FAULT: 0,
            OutcomeCode.UNSAT: 1,
            OutcomeCode.BLOCKED: 2,
            OutcomeCode.UNKNOWN: 3,
            OutcomeCode.CANCELLED: 4,
            OutcomeCode.STALE: 5,
            OutcomeCode.DEGRADED: 6,
            OutcomeCode.RECOVERY_REQUIRED: 7,
            OutcomeCode.CERTIFIED: 8,
        }
        component_id, code, reason = sorted(
            failures,
            key=lambda item: (precedence[item[1]], item[0]),
        )[0]
        return self._judgment(code, reasons=(f"{component_id}:{reason}",))

    def _audit(
        self,
        frame: ContinuationFrame,
        event_type: str,
        previous_status: FrameStatus,
        new_status: FrameStatus,
        trigger: str,
        *,
        constructive_delta: Mapping[str, Any] | None = None,
        fracture_delta: Mapping[str, Any] | None = None,
        judgment: str = "",
    ) -> None:
        self._event_sequence += 1
        payload = {
            "epoch_id": frame.epoch_id,
            "sequence": self._event_sequence,
            "component_id": frame.component_id,
            "frame_id": frame.frame_id,
            "event_type": event_type,
            "trigger": trigger,
            "previous_status": previous_status.value,
            "new_status": new_status.value,
            "constructive_delta": constructive_delta or {},
            "fracture_delta": fracture_delta or {},
            "dependency_certificate_ids": frame.dependency_certificate_ids,
            "judgment": judgment,
        }
        event = AuditEvent(
            event_id=stable_hash("cdg-audit-event", payload),
            epoch_id=frame.epoch_id,
            sequence=self._event_sequence,
            component_id=frame.component_id,
            frame_id=frame.frame_id,
            event_type=event_type,
            trigger=trigger,
            previous_status=previous_status.value,
            new_status=new_status.value,
            constructive_delta=constructive_delta or {},
            fracture_delta=fracture_delta or {},
            dependency_certificate_ids=frame.dependency_certificate_ids,
            judgment=judgment,
        )
        self.audit_events.append(event)

    def _audit_digest(self, *, extra: Any | None = None) -> str:
        return stable_hash(
            "cdg-audit",
            {
                "events": self.audit_events,
                "extra": extra,
            },
        )

    def _judgment(
        self,
        outcome: OutcomeCode,
        *,
        certificate_ids: tuple[str, ...] = (),
        reasons: tuple[str, ...],
    ) -> ExecutionJudgment:
        return ExecutionJudgment(
            root_component_id=self._current_root_component_id or "unknown-root",
            epoch_id=self._current_epoch_id or "unknown-epoch",
            outcome=outcome,
            certificate_ids=certificate_ids,
            reasons=reasons,
            executed_steps=self._executed_steps,
            audit_digest=self._audit_digest(extra={"outcome": outcome.value, "reasons": reasons}),
        )

    # ------------------------------------------------------------------
    # Read-only inspection
    # ------------------------------------------------------------------

    def active_required_closure(self) -> tuple[str, ...]:
        if self._current_root_component_id is None:
            return ()
        closure = set(self.dependencies.active_required_closure(self._current_root_component_id))
        closure.add(self._current_root_component_id)
        return tuple(sorted(closure))

    def current_certificate(
        self,
        component_id: str,
        projection_name: str,
        epoch_id: str | None = None,
    ) -> ProjectionCertificate | None:
        epoch = epoch_id or self._current_epoch_id
        if epoch is None:
            return None
        certificate_id = self.latest_certificates.get((component_id, projection_name, epoch))
        if certificate_id is None:
            return None
        certificate = self.certificates[certificate_id]
        return certificate if certificate.valid else None

    def snapshot_payload(self) -> dict[str, Any]:
        """Return a deterministic persistence payload without component code."""

        return {
            "protocol_version": "cdg-rccm.v1",
            "current_epoch_id": self._current_epoch_id,
            "current_root_component_id": self._current_root_component_id,
            "current_root_projections": list(self._current_root_projections),
            "maximum_global_steps": self.maximum_global_steps,
            "executed_steps": self._executed_steps,
            "frames": [frame for _, frame in sorted(self.frames.items())],
            "requests": [request for _, request in sorted(self.requests.items())],
            "request_consumers": dict(sorted(self.request_consumers.items())),
            "request_solutions": {
                request_id: list(certificate_ids)
                for request_id, certificate_ids in sorted(self.request_solutions.items())
            },
            "provider_frames": [
                {
                    "component_id": key[0],
                    "projection_name": key[1],
                    "epoch_id": key[2],
                    "frame_id": frame_id,
                }
                for key, frame_id in sorted(self.provider_frames.items())
            ],
            "certificates": [certificate for _, certificate in sorted(self.certificates.items())],
            "latest_certificates": [
                {
                    "component_id": key[0],
                    "projection_name": key[1],
                    "epoch_id": key[2],
                    "certificate_id": certificate_id,
                }
                for key, certificate_id in sorted(self.latest_certificates.items())
            ],
            "audit_events": list(self.audit_events),
            "component_terminal": {
                component_id: [code.value, reason]
                for component_id, (code, reason) in sorted(self._component_terminal.items())
            },
            "containment_edges": list(self.containment.edges()),
            "read_index": self.read_index.snapshot(),
        }
