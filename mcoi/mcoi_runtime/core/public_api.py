"""Purpose: public API / product surface runtime engine.
Governance scope: registering endpoints, validating/authenticating requests,
    enforcing rate limits and idempotency, routing into internal runtimes,
    emitting responses and audit records, detecting violations.
Dependencies: public_api contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise.
  - Cross-tenant requests are denied fail-closed.
  - Rate limits are enforced per caller+endpoint.
  - Idempotent mutations return cached responses.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.public_api import (
    ApiAssessment,
    ApiClosureReport,
    ApiErrorRecord,
    ApiRequest,
    ApiResponse,
    ApiSnapshot,
    ApiStatus,
    ApiViolation,
    ApiVisibility,
    AuthDisposition,
    EndpointDescriptor,
    EndpointKind,
    IdempotencyRecord,
    RateLimitDisposition,
    RateLimitRecord,
    RequestDisposition,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str = "") -> EventRecord:
    if not now:
        now = datetime.now(timezone.utc).isoformat()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-api", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_ENDPOINT_TERMINAL = frozenset({ApiStatus.RETIRED})


class PublicApiEngine:
    """Public API / product surface runtime engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._endpoints: dict[str, EndpointDescriptor] = {}
        self._requests: dict[str, ApiRequest] = {}
        self._responses: dict[str, ApiResponse] = {}
        self._errors: dict[str, ApiErrorRecord] = {}
        self._rate_limits: dict[str, RateLimitRecord] = {}
        self._idempotency: dict[str, IdempotencyRecord] = {}  # key -> record
        self._violations: dict[str, ApiViolation] = {}
        self._assessments: dict[str, ApiAssessment] = {}
        # Rate limit state: (tenant_id, caller_ref, endpoint_id) -> request count in window
        self._rate_counters: dict[tuple[str, str, str], int] = {}
        self._rate_limit_max: int = 100  # default max per window

    def _now(self) -> str:
        """Get current time from injected clock."""
        return self._clock.now_iso()

    # -- Properties ----------------------------------------------------------

    @property
    def endpoint_count(self) -> int:
        return len(self._endpoints)

    @property
    def request_count(self) -> int:
        return len(self._requests)

    @property
    def response_count(self) -> int:
        return len(self._responses)

    @property
    def error_count(self) -> int:
        return len(self._errors)

    @property
    def rate_limit_count(self) -> int:
        return len(self._rate_limits)

    @property
    def idempotency_count(self) -> int:
        return len(self._idempotency)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    # -- Endpoints -----------------------------------------------------------

    def register_endpoint(
        self,
        endpoint_id: str,
        tenant_id: str,
        path: str,
        kind: EndpointKind = EndpointKind.READ,
        visibility: ApiVisibility = ApiVisibility.PUBLIC,
        target_runtime: str = "unknown",
        target_action: str = "unknown",
    ) -> EndpointDescriptor:
        if endpoint_id in self._endpoints:
            raise RuntimeCoreInvariantError(f"duplicate endpoint_id: {endpoint_id}")
        now = self._now()
        ep = EndpointDescriptor(
            endpoint_id=endpoint_id,
            tenant_id=tenant_id,
            path=path,
            kind=kind,
            visibility=visibility,
            status=ApiStatus.ACTIVE,
            target_runtime=target_runtime,
            target_action=target_action,
            created_at=now,
        )
        self._endpoints[endpoint_id] = ep
        _emit(self._events, "register_endpoint", {"endpoint_id": endpoint_id, "path": path}, endpoint_id, now=self._now())
        return ep

    def get_endpoint(self, endpoint_id: str) -> EndpointDescriptor:
        if endpoint_id not in self._endpoints:
            raise RuntimeCoreInvariantError(f"unknown endpoint_id: {endpoint_id}")
        return self._endpoints[endpoint_id]

    def deprecate_endpoint(self, endpoint_id: str) -> EndpointDescriptor:
        ep = self.get_endpoint(endpoint_id)
        if ep.status in _ENDPOINT_TERMINAL:
            raise RuntimeCoreInvariantError(f"endpoint {endpoint_id} is retired")
        now = self._now()
        updated = EndpointDescriptor(
            endpoint_id=ep.endpoint_id, tenant_id=ep.tenant_id, path=ep.path,
            kind=ep.kind, visibility=ep.visibility, status=ApiStatus.DEPRECATED,
            target_runtime=ep.target_runtime, target_action=ep.target_action, created_at=now,
        )
        self._endpoints[endpoint_id] = updated
        _emit(self._events, "deprecate_endpoint", {"endpoint_id": endpoint_id}, endpoint_id, now=self._now())
        return updated

    def disable_endpoint(self, endpoint_id: str) -> EndpointDescriptor:
        ep = self.get_endpoint(endpoint_id)
        if ep.status in _ENDPOINT_TERMINAL:
            raise RuntimeCoreInvariantError(f"endpoint {endpoint_id} is retired")
        now = self._now()
        updated = EndpointDescriptor(
            endpoint_id=ep.endpoint_id, tenant_id=ep.tenant_id, path=ep.path,
            kind=ep.kind, visibility=ep.visibility, status=ApiStatus.DISABLED,
            target_runtime=ep.target_runtime, target_action=ep.target_action, created_at=now,
        )
        self._endpoints[endpoint_id] = updated
        _emit(self._events, "disable_endpoint", {"endpoint_id": endpoint_id}, endpoint_id, now=self._now())
        return updated

    def retire_endpoint(self, endpoint_id: str) -> EndpointDescriptor:
        ep = self.get_endpoint(endpoint_id)
        if ep.status == ApiStatus.RETIRED:
            raise RuntimeCoreInvariantError(f"endpoint {endpoint_id} already retired")
        now = self._now()
        updated = EndpointDescriptor(
            endpoint_id=ep.endpoint_id, tenant_id=ep.tenant_id, path=ep.path,
            kind=ep.kind, visibility=ep.visibility, status=ApiStatus.RETIRED,
            target_runtime=ep.target_runtime, target_action=ep.target_action, created_at=now,
        )
        self._endpoints[endpoint_id] = updated
        _emit(self._events, "retire_endpoint", {"endpoint_id": endpoint_id}, endpoint_id, now=self._now())
        return updated

    def endpoints_for_tenant(self, tenant_id: str) -> tuple[EndpointDescriptor, ...]:
        return tuple(e for e in self._endpoints.values() if e.tenant_id == tenant_id)

    def active_endpoints_for_tenant(self, tenant_id: str) -> tuple[EndpointDescriptor, ...]:
        return tuple(e for e in self._endpoints.values() if e.tenant_id == tenant_id and e.status == ApiStatus.ACTIVE)

    # -- Request processing --------------------------------------------------

    def process_request(
        self,
        request_id: str,
        tenant_id: str,
        endpoint_id: str,
        caller_ref: str,
        idempotency_key: str = "",
        caller_tenant_id: str = "",
    ) -> ApiRequest:
        if request_id in self._requests:
            raise RuntimeCoreInvariantError(f"duplicate request_id: {request_id}")

        now = self._now()
        ep = self._endpoints.get(endpoint_id)

        # Endpoint validation
        if ep is None:
            req = ApiRequest(
                request_id=request_id, tenant_id=tenant_id, endpoint_id=endpoint_id,
                caller_ref=caller_ref, disposition=RequestDisposition.REJECTED,
                auth_disposition=AuthDisposition.INVALID,
                idempotency_key=idempotency_key or "none", received_at=now,
            )
            self._requests[request_id] = req
            self._record_error(request_id, tenant_id, "ENDPOINT_NOT_FOUND", "unknown endpoint", 404)
            _emit(self._events, "process_request_rejected", {"request_id": request_id}, request_id, now=self._now())
            return req

        # Cross-tenant check — fail-closed
        effective_caller_tenant = caller_tenant_id or tenant_id
        if effective_caller_tenant != ep.tenant_id:
            req = ApiRequest(
                request_id=request_id, tenant_id=tenant_id, endpoint_id=endpoint_id,
                caller_ref=caller_ref, disposition=RequestDisposition.REJECTED,
                auth_disposition=AuthDisposition.DENIED,
                idempotency_key=idempotency_key or "none", received_at=now,
            )
            self._requests[request_id] = req
            self._record_error(request_id, tenant_id, "CROSS_TENANT_DENIED", "cross-tenant access denied", 403)
            _emit(self._events, "process_request_cross_tenant_denied", {"request_id": request_id}, request_id, now=self._now())
            return req

        # Disabled/retired endpoint check
        if ep.status in (ApiStatus.DISABLED, ApiStatus.RETIRED):
            req = ApiRequest(
                request_id=request_id, tenant_id=tenant_id, endpoint_id=endpoint_id,
                caller_ref=caller_ref, disposition=RequestDisposition.REJECTED,
                auth_disposition=AuthDisposition.AUTHENTICATED,
                idempotency_key=idempotency_key or "none", received_at=now,
            )
            self._requests[request_id] = req
            self._record_error(request_id, tenant_id, "ENDPOINT_UNAVAILABLE", f"endpoint {endpoint_id} is {ep.status.value}", 503)
            _emit(self._events, "process_request_unavailable", {"request_id": request_id}, request_id, now=self._now())
            return req

        # Rate limit check
        rate_key = (tenant_id, caller_ref, endpoint_id)
        current_count = self._rate_counters.get(rate_key, 0)
        if current_count >= self._rate_limit_max:
            req = ApiRequest(
                request_id=request_id, tenant_id=tenant_id, endpoint_id=endpoint_id,
                caller_ref=caller_ref, disposition=RequestDisposition.RATE_LIMITED,
                auth_disposition=AuthDisposition.AUTHENTICATED,
                idempotency_key=idempotency_key or "none", received_at=now,
            )
            self._requests[request_id] = req
            self._record_rate_limit(request_id, tenant_id, caller_ref, endpoint_id, RateLimitDisposition.THROTTLED, 0)
            _emit(self._events, "process_request_rate_limited", {"request_id": request_id}, request_id, now=self._now())
            return req

        # Idempotency check
        idem_key = idempotency_key or "none"
        if idem_key != "none" and idem_key in self._idempotency:
            existing = self._idempotency[idem_key]
            req = ApiRequest(
                request_id=request_id, tenant_id=tenant_id, endpoint_id=endpoint_id,
                caller_ref=caller_ref, disposition=RequestDisposition.DEDUPLICATED,
                auth_disposition=AuthDisposition.AUTHENTICATED,
                idempotency_key=idem_key, received_at=now,
            )
            self._requests[request_id] = req
            _emit(self._events, "process_request_deduplicated", {"request_id": request_id, "original": existing.request_id}, request_id, now=self._now())
            return req

        # Accept the request
        self._rate_counters[rate_key] = current_count + 1
        req = ApiRequest(
            request_id=request_id, tenant_id=tenant_id, endpoint_id=endpoint_id,
            caller_ref=caller_ref, disposition=RequestDisposition.ACCEPTED,
            auth_disposition=AuthDisposition.AUTHENTICATED,
            idempotency_key=idem_key, received_at=now,
        )
        self._requests[request_id] = req
        self._record_rate_limit(request_id, tenant_id, caller_ref, endpoint_id, RateLimitDisposition.ALLOWED, max(0, self._rate_limit_max - current_count - 1))
        _emit(self._events, "process_request_accepted", {"request_id": request_id}, request_id, now=self._now())
        return req

    def get_request(self, request_id: str) -> ApiRequest:
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown request_id: {request_id}")
        return self._requests[request_id]

    def requests_for_tenant(self, tenant_id: str) -> tuple[ApiRequest, ...]:
        return tuple(r for r in self._requests.values() if r.tenant_id == tenant_id)

    # -- Responses -----------------------------------------------------------

    def record_response(
        self,
        response_id: str,
        request_id: str,
        tenant_id: str,
        status_code: int = 200,
        payload_ref: str = "ok",
    ) -> ApiResponse:
        if response_id in self._responses:
            raise RuntimeCoreInvariantError(f"duplicate response_id: {response_id}")
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown request_id: {request_id}")
        req = self._requests[request_id]
        now = self._now()
        resp = ApiResponse(
            response_id=response_id, request_id=request_id, tenant_id=tenant_id,
            status_code=status_code, disposition=req.disposition,
            payload_ref=payload_ref, responded_at=now,
        )
        self._responses[response_id] = resp

        # Record idempotency if the request had a key
        if req.idempotency_key != "none" and req.disposition == RequestDisposition.ACCEPTED:
            if req.idempotency_key not in self._idempotency:
                idem = IdempotencyRecord(
                    idempotency_key=req.idempotency_key, request_id=request_id,
                    tenant_id=tenant_id, endpoint_id=req.endpoint_id,
                    original_response_id=response_id, created_at=now,
                )
                self._idempotency[req.idempotency_key] = idem

        _emit(self._events, "record_response", {"response_id": response_id, "status_code": status_code}, response_id, now=self._now())
        return resp

    def get_response(self, response_id: str) -> ApiResponse:
        if response_id not in self._responses:
            raise RuntimeCoreInvariantError(f"unknown response_id: {response_id}")
        return self._responses[response_id]

    def responses_for_request(self, request_id: str) -> tuple[ApiResponse, ...]:
        return tuple(r for r in self._responses.values() if r.request_id == request_id)

    # -- Internal helpers ----------------------------------------------------

    def _record_error(self, request_id: str, tenant_id: str, code: str, message: str, status_code: int) -> ApiErrorRecord:
        now = self._now()
        eid = stable_identifier("err-api", {"request_id": request_id, "code": code})
        error = ApiErrorRecord(
            error_id=eid, request_id=request_id, tenant_id=tenant_id,
            error_code=code, error_message=message, status_code=status_code, created_at=now,
        )
        self._errors[eid] = error
        return error

    def _record_rate_limit(self, request_id: str, tenant_id: str, caller_ref: str, endpoint_id: str, disposition: RateLimitDisposition, remaining: int) -> RateLimitRecord:
        now = self._now()
        lid = stable_identifier("rl-api", {"request_id": request_id})
        record = RateLimitRecord(
            limit_id=lid, tenant_id=tenant_id, caller_ref=caller_ref,
            endpoint_id=endpoint_id, disposition=disposition,
            requests_remaining=remaining, window_reset_at=now, checked_at=now,
        )
        self._rate_limits[lid] = record
        return record

    def errors_for_tenant(self, tenant_id: str) -> tuple[ApiErrorRecord, ...]:
        return tuple(e for e in self._errors.values() if e.tenant_id == tenant_id)

    # -- Snapshots -----------------------------------------------------------

    def api_snapshot(self, snapshot_id: str, tenant_id: str) -> ApiSnapshot:
        now = self._now()
        endpoints = self.endpoints_for_tenant(tenant_id)
        active = self.active_endpoints_for_tenant(tenant_id)
        reqs = self.requests_for_tenant(tenant_id)
        accepted = [r for r in reqs if r.disposition == RequestDisposition.ACCEPTED]
        rejected = [r for r in reqs if r.disposition == RequestDisposition.REJECTED]
        rate_limited = [r for r in reqs if r.disposition == RequestDisposition.RATE_LIMITED]
        deduped = [r for r in reqs if r.disposition == RequestDisposition.DEDUPLICATED]
        snap = ApiSnapshot(
            snapshot_id=snapshot_id, tenant_id=tenant_id,
            total_endpoints=len(endpoints), active_endpoints=len(active),
            total_requests=len(reqs), accepted_requests=len(accepted),
            rejected_requests=len(rejected), rate_limited_requests=len(rate_limited),
            deduplicated_requests=len(deduped), captured_at=now,
        )
        _emit(self._events, "api_snapshot", {"snapshot_id": snapshot_id}, snapshot_id, now=self._now())
        return snap

    # -- Assessment ----------------------------------------------------------

    def api_assessment(self, assessment_id: str, tenant_id: str) -> ApiAssessment:
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError(f"duplicate assessment_id: {assessment_id}")
        now = self._now()
        endpoints = self.endpoints_for_tenant(tenant_id)
        active = self.active_endpoints_for_tenant(tenant_id)
        reqs = self.requests_for_tenant(tenant_id)
        errors = self.errors_for_tenant(tenant_id)
        violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]

        total_ep = len(endpoints)
        avail = len(active) / total_ep if total_ep > 0 else 1.0
        total_req = len(reqs)
        err_rate = len(errors) / total_req if total_req > 0 else 0.0

        assessment = ApiAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_endpoints=total_ep, active_endpoints=len(active),
            availability_score=round(min(1.0, max(0.0, avail)), 4),
            error_rate=round(min(1.0, max(0.0, err_rate)), 4),
            total_violations=len(violations), assessed_at=now,
        )
        self._assessments[assessment_id] = assessment
        _emit(self._events, "api_assessment", {"assessment_id": assessment_id}, assessment_id, now=self._now())
        return assessment

    # -- Violations ----------------------------------------------------------

    def detect_api_violations(self, tenant_id: str) -> tuple[ApiViolation, ...]:
        now = self._now()
        new_violations: list[ApiViolation] = []

        # Disabled endpoints with recent requests
        for ep in self._endpoints.values():
            if ep.tenant_id != tenant_id:
                continue
            if ep.status == ApiStatus.DISABLED:
                has_reqs = any(r.endpoint_id == ep.endpoint_id for r in self._requests.values() if r.tenant_id == tenant_id and r.disposition == RequestDisposition.REJECTED)
                if has_reqs:
                    vid = stable_identifier("viol-api", {"op": "disabled_endpoint_hit", "ep": ep.endpoint_id})
                    if vid not in self._violations:
                        v = ApiViolation(
                            violation_id=vid, tenant_id=tenant_id,
                            operation="disabled_endpoint_hit",
                            reason=f"disabled endpoint {ep.endpoint_id} received requests",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # Cross-tenant denials
        cross_tenant_errors = [e for e in self._errors.values() if e.tenant_id == tenant_id and e.error_code == "CROSS_TENANT_DENIED"]
        if cross_tenant_errors:
            vid = stable_identifier("viol-api", {"op": "cross_tenant_attempt", "tenant": tenant_id})
            if vid not in self._violations:
                v = ApiViolation(
                    violation_id=vid, tenant_id=tenant_id,
                    operation="cross_tenant_attempt",
                    reason=f"cross-tenant access attempts detected for tenant {tenant_id}",
                    detected_at=now,
                )
                self._violations[vid] = v
                new_violations.append(v)

        # High error rate
        reqs = self.requests_for_tenant(tenant_id)
        errors = self.errors_for_tenant(tenant_id)
        if len(reqs) >= 5 and len(errors) / len(reqs) > 0.5:
            vid = stable_identifier("viol-api", {"op": "high_error_rate", "tenant": tenant_id})
            if vid not in self._violations:
                v = ApiViolation(
                    violation_id=vid, tenant_id=tenant_id,
                    operation="high_error_rate",
                    reason=f"error rate above 50% for tenant {tenant_id}",
                    detected_at=now,
                )
                self._violations[vid] = v
                new_violations.append(v)

        if new_violations:
            _emit(self._events, "detect_api_violations", {"tenant_id": tenant_id, "count": len(new_violations)}, tenant_id, now=self._now())
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[ApiViolation, ...]:
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # -- Closure report ------------------------------------------------------

    def closure_report(self, report_id: str, tenant_id: str) -> ApiClosureReport:
        now = self._now()
        report = ApiClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_endpoints=len(self.endpoints_for_tenant(tenant_id)),
            total_requests=len(self.requests_for_tenant(tenant_id)),
            total_responses=len([r for r in self._responses.values() if r.tenant_id == tenant_id]),
            total_errors=len(self.errors_for_tenant(tenant_id)),
            total_rate_limits=len([r for r in self._rate_limits.values() if r.tenant_id == tenant_id]),
            total_violations=len(self.violations_for_tenant(tenant_id)),
            created_at=now,
        )
        _emit(self._events, "closure_report", {"report_id": report_id}, report_id, now=self._now())
        return report

    # -- State hash ----------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._endpoints):
            parts.append(f"ep:{k}:{self._endpoints[k].status.value}")
        for k in sorted(self._requests):
            parts.append(f"req:{k}:{self._requests[k].disposition.value}")
        for k in sorted(self._responses):
            parts.append(f"resp:{k}:{self._responses[k].status_code}")
        for k in sorted(self._idempotency):
            parts.append(f"idem:{k}")
        for k in sorted(self._violations):
            parts.append(f"violation:{k}")
        return sha256("|".join(parts).encode()).hexdigest()

    # -- Snapshot / Restore --------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        return {
            "endpoints": self._endpoints,
            "requests": self._requests,
            "responses": self._responses,
            "errors": self._errors,
            "rate_limits": self._rate_limits,
            "idempotency": self._idempotency,
            "violations": self._violations,
            "assessments": self._assessments,
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
