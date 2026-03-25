"""Purpose: external agent / tool execution runtime engine.
Governance scope: governed execution of external tools and agents with
    sandboxing, retry, timeout, cancellation, and receipt tracking.
Dependencies: event_spine, invariants, stable_identifier, contracts.
Invariants:
  - Every execution references a tenant.
  - Duplicate IDs are rejected fail-closed.
  - Terminal states block further mutations.
  - Cross-tenant access is blocked fail-closed.
  - All outputs are frozen.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock
from mcoi_runtime.contracts.external_execution import (
    CredentialMode,
    ExecutionClosureReport,
    ExecutionFailure,
    ExecutionKind,
    ExecutionPolicy,
    ExecutionReceipt,
    ExecutionRequest,
    ExecutionResult,
    ExecutionRiskLevel,
    ExecutionSnapshot,
    ExecutionStatus,
    ExecutionTarget,
    ExecutionTrace,
    ExecutionViolation,
    RetryDisposition,
    SandboxDisposition,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CIRCUIT_OPEN_THRESHOLD = 3

_RISK_RANK = {
    ExecutionRiskLevel.LOW: 0,
    ExecutionRiskLevel.MEDIUM: 1,
    ExecutionRiskLevel.HIGH: 2,
    ExecutionRiskLevel.CRITICAL: 3,
}

_REQUEST_TERMINAL = frozenset({
    ExecutionStatus.COMPLETED,
    ExecutionStatus.FAILED,
    ExecutionStatus.CANCELLED,
    ExecutionStatus.TIMED_OUT,
})


def _emit(es: EventSpineEngine, action: str, payload: dict[str, Any], cid: str, now: str = "") -> None:
    if not now:
        now = datetime.now(timezone.utc).isoformat()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-exec", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class ExternalExecutionEngine:
    """Governed execution of external tools and agents."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._targets: dict[str, ExecutionTarget] = {}
        self._requests: dict[str, ExecutionRequest] = {}
        self._policies: dict[str, ExecutionPolicy] = {}
        self._receipts: dict[str, ExecutionReceipt] = {}
        self._results: dict[str, ExecutionResult] = {}
        self._failures: dict[str, ExecutionFailure] = {}
        self._traces: dict[str, ExecutionTrace] = {}
        self._violations: dict[str, ExecutionViolation] = {}
        self._consecutive_failures: dict[str, int] = {}

    def _now(self) -> str:
        """Get current time from injected clock."""
        return self._clock.now_iso()

    # -- Properties --
    @property
    def target_count(self) -> int:
        return len(self._targets)

    @property
    def request_count(self) -> int:
        return len(self._requests)

    @property
    def receipt_count(self) -> int:
        return len(self._receipts)

    @property
    def result_count(self) -> int:
        return len(self._results)

    @property
    def failure_count(self) -> int:
        return len(self._failures)

    @property
    def trace_count(self) -> int:
        return len(self._traces)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def policy_count(self) -> int:
        return len(self._policies)

    # -- Targets --
    def register_target(
        self,
        target_id: str,
        tenant_id: str,
        display_name: str,
        kind: ExecutionKind = ExecutionKind.TOOL,
        capability_ref: str = "default",
        sandbox_default: SandboxDisposition = SandboxDisposition.SANDBOXED,
        credential_mode: CredentialMode = CredentialMode.NONE,
        max_retries: int = 3,
        timeout_ms: int = 30000,
    ) -> ExecutionTarget:
        if target_id in self._targets:
            raise RuntimeCoreInvariantError(f"duplicate target_id: {target_id}")
        now = self._now()
        target = ExecutionTarget(
            target_id=target_id, tenant_id=tenant_id, display_name=display_name,
            kind=kind, capability_ref=capability_ref, sandbox_default=sandbox_default,
            credential_mode=credential_mode, max_retries=max_retries,
            timeout_ms=timeout_ms, registered_at=now,
        )
        self._targets[target_id] = target
        _emit(self._events, "register_target", {"target_id": target_id}, target_id, now=self._now())
        return target

    def get_target(self, target_id: str) -> ExecutionTarget:
        if target_id not in self._targets:
            raise RuntimeCoreInvariantError(f"unknown target_id: {target_id}")
        return self._targets[target_id]

    def targets_for_tenant(self, tenant_id: str) -> tuple[ExecutionTarget, ...]:
        return tuple(t for t in self._targets.values() if t.tenant_id == tenant_id)

    # -- Policies --
    def register_policy(
        self,
        policy_id: str,
        tenant_id: str,
        target_id: str,
        max_retries: int = 3,
        timeout_ms: int = 30000,
        sandbox_required: SandboxDisposition = SandboxDisposition.SANDBOXED,
        credential_mode: CredentialMode = CredentialMode.NONE,
        risk_threshold: ExecutionRiskLevel = ExecutionRiskLevel.HIGH,
    ) -> ExecutionPolicy:
        if policy_id in self._policies:
            raise RuntimeCoreInvariantError(f"duplicate policy_id: {policy_id}")
        if target_id not in self._targets:
            raise RuntimeCoreInvariantError(f"unknown target_id: {target_id}")
        now = self._now()
        policy = ExecutionPolicy(
            policy_id=policy_id, tenant_id=tenant_id, target_id=target_id,
            max_retries=max_retries, timeout_ms=timeout_ms,
            sandbox_required=sandbox_required, credential_mode=credential_mode,
            risk_threshold=risk_threshold, created_at=now,
        )
        self._policies[policy_id] = policy
        _emit(self._events, "register_policy", {"policy_id": policy_id}, policy_id, now=self._now())
        return policy

    def get_policy(self, policy_id: str) -> ExecutionPolicy:
        if policy_id not in self._policies:
            raise RuntimeCoreInvariantError(f"unknown policy_id: {policy_id}")
        return self._policies[policy_id]

    def policies_for_target(self, target_id: str) -> tuple[ExecutionPolicy, ...]:
        return tuple(p for p in self._policies.values() if p.target_id == target_id)

    # -- Requests --
    def request_execution(
        self,
        request_id: str,
        tenant_id: str,
        target_id: str,
        kind: ExecutionKind = ExecutionKind.TOOL,
        sandbox: SandboxDisposition = SandboxDisposition.SANDBOXED,
        credential_mode: CredentialMode = CredentialMode.NONE,
        risk_level: ExecutionRiskLevel = ExecutionRiskLevel.LOW,
    ) -> ExecutionRequest:
        if request_id in self._requests:
            raise RuntimeCoreInvariantError(f"duplicate request_id: {request_id}")
        if target_id not in self._targets:
            raise RuntimeCoreInvariantError(f"unknown target_id: {target_id}")
        target = self._targets[target_id]
        if target.tenant_id != tenant_id:
            # Cross-tenant blocked — record violation and return blocked request
            vid = stable_identifier("viol-exec", {"request_id": request_id, "reason": "cross_tenant"})
            now = self._now()
            violation = ExecutionViolation(
                violation_id=vid, tenant_id=tenant_id, request_id=request_id,
                operation="cross_tenant_blocked", reason=f"target {target_id} belongs to tenant {target.tenant_id}",
                detected_at=now,
            )
            self._violations[vid] = violation
            req = ExecutionRequest(
                request_id=request_id, tenant_id=tenant_id, target_id=target_id,
                kind=kind, status=ExecutionStatus.CANCELLED,
                sandbox=sandbox, credential_mode=credential_mode,
                risk_level=risk_level, requested_at=now,
            )
            self._requests[request_id] = req
            _emit(self._events, "cross_tenant_blocked", {"request_id": request_id}, request_id, now=self._now())
            return req

        # Check risk against policy
        policies = [p for p in self._policies.values() if p.target_id == target_id]
        for pol in policies:
            if _RISK_RANK.get(risk_level, 0) > _RISK_RANK.get(pol.risk_threshold, 0):
                vid = stable_identifier("viol-exec", {"request_id": request_id, "reason": "risk_exceeded"})
                now = self._now()
                violation = ExecutionViolation(
                    violation_id=vid, tenant_id=tenant_id, request_id=request_id,
                    operation="risk_exceeded", reason=f"risk {risk_level.value} exceeds threshold {pol.risk_threshold.value}",
                    detected_at=now,
                )
                self._violations[vid] = violation
                req = ExecutionRequest(
                    request_id=request_id, tenant_id=tenant_id, target_id=target_id,
                    kind=kind, status=ExecutionStatus.CANCELLED,
                    sandbox=sandbox, credential_mode=credential_mode,
                    risk_level=risk_level, requested_at=now,
                )
                self._requests[request_id] = req
                _emit(self._events, "risk_exceeded", {"request_id": request_id}, request_id, now=self._now())
                return req

        # Circuit breaker check
        if self._consecutive_failures.get(target_id, 0) >= CIRCUIT_OPEN_THRESHOLD:
            vid = stable_identifier("viol-exec", {"request_id": request_id, "reason": "circuit_breaker_open"})
            now = self._now()
            violation = ExecutionViolation(
                violation_id=vid, tenant_id=tenant_id, request_id=request_id,
                operation="circuit_breaker_open",
                reason=f"circuit breaker open for target {target_id} after {self._consecutive_failures[target_id]} consecutive failures",
                detected_at=now,
            )
            self._violations[vid] = violation
            req = ExecutionRequest(
                request_id=request_id, tenant_id=tenant_id, target_id=target_id,
                kind=kind, status=ExecutionStatus.CANCELLED,
                sandbox=sandbox, credential_mode=credential_mode,
                risk_level=risk_level, requested_at=now,
            )
            self._requests[request_id] = req
            _emit(self._events, "circuit_breaker_open", {"request_id": request_id, "target_id": target_id}, request_id, now=self._now())
            return req

        now = self._now()
        req = ExecutionRequest(
            request_id=request_id, tenant_id=tenant_id, target_id=target_id,
            kind=kind, status=ExecutionStatus.PENDING,
            sandbox=sandbox, credential_mode=credential_mode,
            risk_level=risk_level, requested_at=now,
        )
        self._requests[request_id] = req
        _emit(self._events, "request_execution", {"request_id": request_id}, request_id, now=self._now())
        return req

    def get_request(self, request_id: str) -> ExecutionRequest:
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown request_id: {request_id}")
        return self._requests[request_id]

    def requests_for_tenant(self, tenant_id: str) -> tuple[ExecutionRequest, ...]:
        return tuple(r for r in self._requests.values() if r.tenant_id == tenant_id)

    # -- Approve / Start / Cancel --
    def approve_execution(self, request_id: str) -> ExecutionRequest:
        req = self.get_request(request_id)
        if req.status in _REQUEST_TERMINAL:
            raise RuntimeCoreInvariantError(f"request {request_id} is terminal: {req.status.value}")
        if req.status != ExecutionStatus.PENDING:
            raise RuntimeCoreInvariantError(f"request {request_id} must be PENDING to approve")
        now = self._now()
        updated = ExecutionRequest(
            request_id=req.request_id, tenant_id=req.tenant_id, target_id=req.target_id,
            kind=req.kind, status=ExecutionStatus.APPROVED,
            sandbox=req.sandbox, credential_mode=req.credential_mode,
            risk_level=req.risk_level, requested_at=now,
        )
        self._requests[request_id] = updated
        _emit(self._events, "approve_execution", {"request_id": request_id}, request_id, now=self._now())
        return updated

    def start_execution(self, request_id: str) -> ExecutionRequest:
        req = self.get_request(request_id)
        if req.status in _REQUEST_TERMINAL:
            raise RuntimeCoreInvariantError(f"request {request_id} is terminal: {req.status.value}")
        if req.status not in (ExecutionStatus.PENDING, ExecutionStatus.APPROVED):
            raise RuntimeCoreInvariantError(f"request {request_id} must be PENDING or APPROVED to start")
        now = self._now()
        updated = ExecutionRequest(
            request_id=req.request_id, tenant_id=req.tenant_id, target_id=req.target_id,
            kind=req.kind, status=ExecutionStatus.RUNNING,
            sandbox=req.sandbox, credential_mode=req.credential_mode,
            risk_level=req.risk_level, requested_at=now,
        )
        self._requests[request_id] = updated
        _emit(self._events, "start_execution", {"request_id": request_id}, request_id, now=self._now())
        return updated

    def cancel_execution(self, request_id: str) -> ExecutionRequest:
        req = self.get_request(request_id)
        if req.status in _REQUEST_TERMINAL:
            raise RuntimeCoreInvariantError(f"request {request_id} is terminal: {req.status.value}")
        now = self._now()
        updated = ExecutionRequest(
            request_id=req.request_id, tenant_id=req.tenant_id, target_id=req.target_id,
            kind=req.kind, status=ExecutionStatus.CANCELLED,
            sandbox=req.sandbox, credential_mode=req.credential_mode,
            risk_level=req.risk_level, requested_at=now,
        )
        self._requests[request_id] = updated
        _emit(self._events, "cancel_execution", {"request_id": request_id}, request_id, now=self._now())
        return updated

    def timeout_execution(self, request_id: str) -> ExecutionRequest:
        req = self.get_request(request_id)
        if req.status != ExecutionStatus.RUNNING:
            raise RuntimeCoreInvariantError(f"request {request_id} must be RUNNING to timeout")
        now = self._now()
        updated = ExecutionRequest(
            request_id=req.request_id, tenant_id=req.tenant_id, target_id=req.target_id,
            kind=req.kind, status=ExecutionStatus.TIMED_OUT,
            sandbox=req.sandbox, credential_mode=req.credential_mode,
            risk_level=req.risk_level, requested_at=now,
        )
        self._requests[request_id] = updated
        # Increment circuit breaker failure count
        self._consecutive_failures[req.target_id] = self._consecutive_failures.get(req.target_id, 0) + 1
        _emit(self._events, "timeout_execution", {"request_id": request_id}, request_id, now=self._now())
        return updated

    def complete_execution(self, request_id: str) -> ExecutionRequest:
        req = self.get_request(request_id)
        if req.status != ExecutionStatus.RUNNING:
            raise RuntimeCoreInvariantError(f"request {request_id} must be RUNNING to complete")
        now = self._now()
        updated = ExecutionRequest(
            request_id=req.request_id, tenant_id=req.tenant_id, target_id=req.target_id,
            kind=req.kind, status=ExecutionStatus.COMPLETED,
            sandbox=req.sandbox, credential_mode=req.credential_mode,
            risk_level=req.risk_level, requested_at=now,
        )
        self._requests[request_id] = updated
        # Reset circuit breaker on success
        self._consecutive_failures[req.target_id] = 0
        _emit(self._events, "complete_execution", {"request_id": request_id}, request_id, now=self._now())
        return updated

    def fail_execution(self, request_id: str) -> ExecutionRequest:
        req = self.get_request(request_id)
        if req.status != ExecutionStatus.RUNNING:
            raise RuntimeCoreInvariantError(f"request {request_id} must be RUNNING to fail")
        now = self._now()
        updated = ExecutionRequest(
            request_id=req.request_id, tenant_id=req.tenant_id, target_id=req.target_id,
            kind=req.kind, status=ExecutionStatus.FAILED,
            sandbox=req.sandbox, credential_mode=req.credential_mode,
            risk_level=req.risk_level, requested_at=now,
        )
        self._requests[request_id] = updated
        # Increment circuit breaker failure count
        self._consecutive_failures[req.target_id] = self._consecutive_failures.get(req.target_id, 0) + 1
        _emit(self._events, "fail_execution", {"request_id": request_id}, request_id, now=self._now())
        return updated

    # -- Circuit breaker --
    def is_circuit_open(self, target_id: str) -> bool:
        """Return True if the circuit breaker is open for the given target."""
        return self._consecutive_failures.get(target_id, 0) >= CIRCUIT_OPEN_THRESHOLD

    def reset_circuit_breaker(self, target_id: str) -> None:
        """Manually reset the circuit breaker for a target."""
        self._consecutive_failures[target_id] = 0

    # -- Receipts --
    def record_receipt(
        self,
        receipt_id: str,
        request_id: str,
        tenant_id: str,
        status: ExecutionStatus = ExecutionStatus.COMPLETED,
        duration_ms: float = 0.0,
        output_ref: str = "none",
    ) -> ExecutionReceipt:
        if receipt_id in self._receipts:
            raise RuntimeCoreInvariantError(f"duplicate receipt_id: {receipt_id}")
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown request_id: {request_id}")
        now = self._now()
        receipt = ExecutionReceipt(
            receipt_id=receipt_id, request_id=request_id, tenant_id=tenant_id,
            status=status, duration_ms=duration_ms, output_ref=output_ref,
            completed_at=now,
        )
        self._receipts[receipt_id] = receipt
        _emit(self._events, "record_receipt", {"receipt_id": receipt_id}, receipt_id, now=self._now())
        return receipt

    def get_receipt(self, receipt_id: str) -> ExecutionReceipt:
        if receipt_id not in self._receipts:
            raise RuntimeCoreInvariantError(f"unknown receipt_id: {receipt_id}")
        return self._receipts[receipt_id]

    def receipts_for_request(self, request_id: str) -> tuple[ExecutionReceipt, ...]:
        return tuple(r for r in self._receipts.values() if r.request_id == request_id)

    # -- Results --
    def record_result(
        self,
        result_id: str,
        request_id: str,
        tenant_id: str,
        success: bool = True,
        output_summary: str = "completed",
        confidence: float = 1.0,
    ) -> ExecutionResult:
        if result_id in self._results:
            raise RuntimeCoreInvariantError(f"duplicate result_id: {result_id}")
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown request_id: {request_id}")
        now = self._now()
        result = ExecutionResult(
            result_id=result_id, request_id=request_id, tenant_id=tenant_id,
            success=success, output_summary=output_summary, confidence=confidence,
            created_at=now,
        )
        self._results[result_id] = result
        _emit(self._events, "record_result", {"result_id": result_id}, result_id, now=self._now())
        return result

    def get_result(self, result_id: str) -> ExecutionResult:
        if result_id not in self._results:
            raise RuntimeCoreInvariantError(f"unknown result_id: {result_id}")
        return self._results[result_id]

    def results_for_request(self, request_id: str) -> tuple[ExecutionResult, ...]:
        return tuple(r for r in self._results.values() if r.request_id == request_id)

    # -- Failures --
    def record_failure(
        self,
        failure_id: str,
        request_id: str,
        tenant_id: str,
        reason: str = "unknown",
        retry_disposition: RetryDisposition = RetryDisposition.NO_RETRY,
        retry_count: int = 0,
    ) -> ExecutionFailure:
        if failure_id in self._failures:
            raise RuntimeCoreInvariantError(f"duplicate failure_id: {failure_id}")
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown request_id: {request_id}")
        now = self._now()
        failure = ExecutionFailure(
            failure_id=failure_id, request_id=request_id, tenant_id=tenant_id,
            reason=reason, retry_disposition=retry_disposition,
            retry_count=retry_count, failed_at=now,
        )
        self._failures[failure_id] = failure
        _emit(self._events, "record_failure", {"failure_id": failure_id}, failure_id, now=self._now())
        return failure

    def get_failure(self, failure_id: str) -> ExecutionFailure:
        if failure_id not in self._failures:
            raise RuntimeCoreInvariantError(f"unknown failure_id: {failure_id}")
        return self._failures[failure_id]

    def failures_for_request(self, request_id: str) -> tuple[ExecutionFailure, ...]:
        return tuple(f for f in self._failures.values() if f.request_id == request_id)

    # -- Traces --
    def record_trace(
        self,
        trace_id: str,
        request_id: str,
        tenant_id: str,
        step_name: str = "execute",
        duration_ms: float = 0.0,
        status: ExecutionStatus = ExecutionStatus.COMPLETED,
    ) -> ExecutionTrace:
        if trace_id in self._traces:
            raise RuntimeCoreInvariantError(f"duplicate trace_id: {trace_id}")
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown request_id: {request_id}")
        now = self._now()
        trace = ExecutionTrace(
            trace_id=trace_id, request_id=request_id, tenant_id=tenant_id,
            step_name=step_name, duration_ms=duration_ms, status=status,
            created_at=now,
        )
        self._traces[trace_id] = trace
        _emit(self._events, "record_trace", {"trace_id": trace_id}, trace_id, now=self._now())
        return trace

    def get_trace(self, trace_id: str) -> ExecutionTrace:
        if trace_id not in self._traces:
            raise RuntimeCoreInvariantError(f"unknown trace_id: {trace_id}")
        return self._traces[trace_id]

    def traces_for_request(self, request_id: str) -> tuple[ExecutionTrace, ...]:
        return tuple(t for t in self._traces.values() if t.request_id == request_id)

    # -- Retry --
    def retry_execution(self, request_id: str) -> ExecutionRequest:
        """Retry a failed/timed-out execution. Resets to PENDING."""
        req = self.get_request(request_id)
        if req.status not in (ExecutionStatus.FAILED, ExecutionStatus.TIMED_OUT):
            raise RuntimeCoreInvariantError(
                f"request {request_id} must be FAILED or TIMED_OUT to retry"
            )
        # Check retry count against target max_retries
        target = self._targets.get(req.target_id)
        existing_failures = [f for f in self._failures.values() if f.request_id == request_id]
        retry_count = len(existing_failures)
        if target and retry_count >= target.max_retries:
            # Exhausted — record failure and keep terminal
            fid = stable_identifier("fail-exec", {"request_id": request_id, "retry": str(retry_count)})
            self.record_failure(
                fid, request_id, req.tenant_id,
                reason="retries_exhausted",
                retry_disposition=RetryDisposition.EXHAUSTED,
                retry_count=retry_count,
            )
            _emit(self._events, "retry_exhausted", {"request_id": request_id}, request_id, now=self._now())
            return req

        now = self._now()
        updated = ExecutionRequest(
            request_id=req.request_id, tenant_id=req.tenant_id, target_id=req.target_id,
            kind=req.kind, status=ExecutionStatus.PENDING,
            sandbox=req.sandbox, credential_mode=req.credential_mode,
            risk_level=req.risk_level, requested_at=now,
        )
        self._requests[request_id] = updated
        _emit(self._events, "retry_execution", {"request_id": request_id}, request_id, now=self._now())
        return updated

    # -- Snapshot --
    def execution_snapshot(self, snapshot_id: str, tenant_id: str) -> ExecutionSnapshot:
        now = self._now()
        targets = [t for t in self._targets.values() if t.tenant_id == tenant_id]
        requests = [r for r in self._requests.values() if r.tenant_id == tenant_id]
        receipts = [r for r in self._receipts.values() if r.tenant_id == tenant_id]
        failures = [f for f in self._failures.values() if f.tenant_id == tenant_id]
        results = [r for r in self._results.values() if r.tenant_id == tenant_id]
        traces = [t for t in self._traces.values() if t.tenant_id == tenant_id]
        violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]
        snap = ExecutionSnapshot(
            snapshot_id=snapshot_id, tenant_id=tenant_id,
            total_targets=len(targets), total_requests=len(requests),
            total_receipts=len(receipts), total_failures=len(failures),
            total_results=len(results), total_traces=len(traces),
            total_violations=len(violations), captured_at=now,
        )
        _emit(self._events, "execution_snapshot", {"snapshot_id": snapshot_id}, snapshot_id, now=self._now())
        return snap

    # -- Violations --
    def detect_execution_violations(self, tenant_id: str) -> tuple[ExecutionViolation, ...]:
        new_violations: list[ExecutionViolation] = []
        now = self._now()

        # 1. Running requests with no traces
        for req in self._requests.values():
            if req.tenant_id != tenant_id:
                continue
            if req.status == ExecutionStatus.RUNNING:
                traces = [t for t in self._traces.values() if t.request_id == req.request_id]
                if not traces:
                    vid = stable_identifier("viol-exec", {
                        "request_id": req.request_id, "reason": "running_no_trace",
                    })
                    if vid not in self._violations:
                        v = ExecutionViolation(
                            violation_id=vid, tenant_id=tenant_id, request_id=req.request_id,
                            operation="running_no_trace",
                            reason=f"running request {req.request_id} has no traces",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # 2. Failed requests with no failure record
        for req in self._requests.values():
            if req.tenant_id != tenant_id:
                continue
            if req.status == ExecutionStatus.FAILED:
                failures = [f for f in self._failures.values() if f.request_id == req.request_id]
                if not failures:
                    vid = stable_identifier("viol-exec", {
                        "request_id": req.request_id, "reason": "failed_no_failure_record",
                    })
                    if vid not in self._violations:
                        v = ExecutionViolation(
                            violation_id=vid, tenant_id=tenant_id, request_id=req.request_id,
                            operation="failed_no_failure_record",
                            reason=f"failed request {req.request_id} has no failure record",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # 3. Completed requests with no result
        for req in self._requests.values():
            if req.tenant_id != tenant_id:
                continue
            if req.status == ExecutionStatus.COMPLETED:
                results = [r for r in self._results.values() if r.request_id == req.request_id]
                if not results:
                    vid = stable_identifier("viol-exec", {
                        "request_id": req.request_id, "reason": "completed_no_result",
                    })
                    if vid not in self._violations:
                        v = ExecutionViolation(
                            violation_id=vid, tenant_id=tenant_id, request_id=req.request_id,
                            operation="completed_no_result",
                            reason=f"completed request {req.request_id} has no result",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        if new_violations:
            _emit(self._events, "detect_execution_violations", {
                "tenant_id": tenant_id, "count": len(new_violations),
            }, tenant_id, now=self._now())
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[ExecutionViolation, ...]:
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # -- Closure --
    def closure_report(self, report_id: str, tenant_id: str) -> ExecutionClosureReport:
        now = self._now()
        targets = [t for t in self._targets.values() if t.tenant_id == tenant_id]
        requests = [r for r in self._requests.values() if r.tenant_id == tenant_id]
        receipts = [r for r in self._receipts.values() if r.tenant_id == tenant_id]
        failures = [f for f in self._failures.values() if f.tenant_id == tenant_id]
        results = [r for r in self._results.values() if r.tenant_id == tenant_id]
        violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]
        report = ExecutionClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_targets=len(targets), total_requests=len(requests),
            total_receipts=len(receipts), total_failures=len(failures),
            total_results=len(results), total_violations=len(violations),
            created_at=now,
        )
        _emit(self._events, "closure_report", {"report_id": report_id}, report_id, now=self._now())
        return report

    # -- State hash --
    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._targets):
            parts.append(f"target:{k}:{self._targets[k].kind.value}")
        for k in sorted(self._requests):
            parts.append(f"request:{k}:{self._requests[k].status.value}")
        for k in sorted(self._receipts):
            parts.append(f"receipt:{k}:{self._receipts[k].status.value}")
        for k in sorted(self._results):
            parts.append(f"result:{k}:{self._results[k].success}")
        for k in sorted(self._failures):
            parts.append(f"failure:{k}:{self._failures[k].retry_disposition.value}")
        for k in sorted(self._traces):
            parts.append(f"trace:{k}:{self._traces[k].status.value}")
        for k in sorted(self._violations):
            parts.append(f"violation:{k}")
        for k in sorted(self._consecutive_failures):
            parts.append(f"circuit:{k}:{self._consecutive_failures[k]}")
        return sha256("|".join(parts).encode()).hexdigest()

    # -- Snapshot / Restore --------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        return {
            "targets": self._targets,
            "requests": self._requests,
            "policies": self._policies,
            "receipts": self._receipts,
            "results": self._results,
            "failures": self._failures,
            "traces": self._traces,
            "violations": self._violations,
            "consecutive_failures": self._consecutive_failures,
        }

    def snapshot(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result
