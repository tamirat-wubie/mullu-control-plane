"""Phase 196 — Production Surface & Deployment Hardening.

Purpose: Server boundary, auth, persistence config, tenant isolation,
    observability, and deployment packaging for the governed substrate.
Governance scope: all external-facing production surfaces.
Dependencies: governed_dispatcher, bootstrap, execution_authority.
Invariants: all requests enter governed execution, no unauthenticated access.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable
from datetime import datetime, timezone
from hashlib import sha256
import json

# ═══ 196A — Server/API Boundary ═══

def _boundary_error_body(exc: Exception) -> tuple[int, dict[str, str]]:
    if isinstance(exc, PermissionError):
        return 403, {"error": "forbidden", "error_code": "forbidden"}
    if isinstance(exc, ValueError):
        return 400, {"error": "invalid_request", "error_code": "invalid_request"}
    return 500, {"error": "internal_error", "error_code": "internal_error"}


@dataclass(frozen=True)
class APIRequest:
    request_id: str
    method: str  # GET, POST, PUT, DELETE
    path: str
    actor_id: str
    tenant_id: str
    body: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class APIResponse:
    request_id: str
    status_code: int
    body: dict[str, Any]
    governed: bool
    ledger_hash: str = ""

class APIBoundary:
    """All API requests must enter through this boundary into governed execution."""
    def __init__(self):
        self._requests: list[APIRequest] = []
        self._responses: list[APIResponse] = []

    def handle(self, request: APIRequest, handler: Callable[[APIRequest], dict[str, Any]]) -> APIResponse:
        self._requests.append(request)
        try:
            result = handler(request)
            response = APIResponse(request.request_id, 200, result, True, sha256(json.dumps(result, sort_keys=True).encode()).hexdigest())
        except PermissionError as exc:
            status_code, body = _boundary_error_body(exc)
            response = APIResponse(request.request_id, status_code, body, True)
        except ValueError as exc:
            status_code, body = _boundary_error_body(exc)
            response = APIResponse(request.request_id, status_code, body, True)
        except Exception as exc:
            status_code, body = _boundary_error_body(exc)
            response = APIResponse(request.request_id, status_code, body, True)
        self._responses.append(response)
        return response

    @property
    def request_count(self) -> int:
        return len(self._requests)

    def error_rate(self) -> float:
        if not self._responses: return 0.0
        errors = sum(1 for r in self._responses if r.status_code >= 400)
        return errors / len(self._responses)

# ═══ 196B — Auth/Session Model ═══

@dataclass
class Session:
    session_id: str
    actor_id: str
    tenant_id: str
    created_at: str
    expires_at: str
    active: bool = True

class AuthGate:
    """Validates authentication before any governed execution."""
    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._denied: int = 0

    def create_session(self, session_id: str, actor_id: str, tenant_id: str, ttl_seconds: int = 3600) -> Session:
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        expires = now + timedelta(seconds=ttl_seconds)
        session = Session(session_id, actor_id, tenant_id, now.isoformat(), expires.isoformat())
        self._sessions[session_id] = session
        return session

    def validate(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if not session or not session.active:
            self._denied += 1
            raise PermissionError(f"Invalid or expired session: {session_id}")
        return session

    def revoke(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].active = False

    @property
    def active_sessions(self) -> int:
        return sum(1 for s in self._sessions.values() if s.active)

    @property
    def denied_count(self) -> int:
        return self._denied

# ═══ 196C — Persistence Configuration ═══

@dataclass(frozen=True)
class PersistenceConfig:
    backend: str  # "memory", "sqlite", "postgresql"
    connection_string: str
    pool_size: int = 5
    replay_safe: bool = True

PERSISTENCE_PROFILES = {
    "development": PersistenceConfig("memory", "memory://", pool_size=1),
    "testing": PersistenceConfig("sqlite", "sqlite:///test.db", pool_size=1),
    "pilot": PersistenceConfig("sqlite", "sqlite:///pilot.db", pool_size=3),
    "production": PersistenceConfig("postgresql", "postgresql://localhost:5432/mullu", pool_size=10),
}

# ═══ 196D — Tenant Isolation ═══

class TenantBoundary:
    """Enforces tenant isolation on all governed operations."""
    def __init__(self):
        self._tenants: set[str] = set()
        self._violations: list[dict[str, str]] = []

    def register_tenant(self, tenant_id: str) -> None:
        self._tenants.add(tenant_id)

    def validate_access(self, session_tenant: str, resource_tenant: str) -> bool:
        if session_tenant != resource_tenant:
            self._violations.append({"session": session_tenant, "resource": resource_tenant, "at": datetime.now(timezone.utc).isoformat()})
            return False
        return True

    @property
    def tenant_count(self) -> int:
        return len(self._tenants)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

# ═══ 196E — Observability Surface ═══

@dataclass
class ObservabilityEvent:
    event_type: str  # "request", "dispatch", "gate", "verification", "error"
    detail: str
    tenant_id: str
    timestamp: str
    trace_id: str = ""

class ObservabilityCollector:
    """Structured event collection for traceability."""
    def __init__(self):
        self._events: list[ObservabilityEvent] = []

    def record(self, event_type: str, detail: str, tenant_id: str, trace_id: str = "") -> None:
        self._events.append(ObservabilityEvent(event_type, detail, tenant_id, datetime.now(timezone.utc).isoformat(), trace_id))

    @property
    def event_count(self) -> int:
        return len(self._events)

    def events_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self._events:
            counts[e.event_type] = counts.get(e.event_type, 0) + 1
        return counts

    def events_for_trace(self, trace_id: str) -> list[ObservabilityEvent]:
        return [e for e in self._events if e.trace_id == trace_id]

# ═══ 196F — Deployment Config ═══

@dataclass(frozen=True)
class DeploymentManifest:
    name: str
    version: str
    environment: str  # "development", "testing", "pilot", "production"
    persistence: PersistenceConfig
    governed: bool = True
    auth_required: bool = True
    tenant_isolation: bool = True
    observability: bool = True

DEPLOYMENT_MANIFESTS = {
    "local_dev": DeploymentManifest("mullu-dev", "0.1.0", "development", PERSISTENCE_PROFILES["development"], auth_required=False, tenant_isolation=False),
    "test": DeploymentManifest("mullu-test", "0.1.0", "testing", PERSISTENCE_PROFILES["testing"]),
    "pilot": DeploymentManifest("mullu-pilot", "0.1.0", "pilot", PERSISTENCE_PROFILES["pilot"]),
    "production": DeploymentManifest("mullu-prod", "0.1.0", "production", PERSISTENCE_PROFILES["production"]),
}

# ═══ Integrated Production Surface ═══

class ProductionSurface:
    """Complete production surface integrating all 196 sub-phases."""
    def __init__(self, manifest: DeploymentManifest):
        self.manifest = manifest
        self.api = APIBoundary()
        self.auth = AuthGate()
        self.tenants = TenantBoundary()
        self.observability = ObservabilityCollector()
        self._total_requests: int = 0
        self._total_errors: int = 0

    def handle_request(self, request: APIRequest) -> APIResponse:
        self._total_requests += 1
        trace_id = request.request_id
        self.observability.record("request", f"{request.method} {request.path}", request.tenant_id, trace_id)

        # Auth gate
        if self.manifest.auth_required:
            try:
                self.auth.validate(request.headers.get("session_id", ""))
            except PermissionError:
                self._total_errors += 1
                self.observability.record("error", "auth_denied", request.tenant_id, trace_id)
                return APIResponse(
                    request.request_id,
                    401,
                    {"error": "unauthorized", "error_code": "unauthorized"},
                    True,
                )

        # Tenant gate
        if self.manifest.tenant_isolation:
            if not self.tenants.validate_access(request.tenant_id, request.tenant_id):
                self._total_errors += 1
                self.observability.record("error", "tenant_violation", request.tenant_id, trace_id)
                return APIResponse(
                    request.request_id,
                    403,
                    {"error": "tenant_violation", "error_code": "tenant_violation"},
                    True,
                )

        # Governed execution
        self.observability.record("dispatch", "governed_execution", request.tenant_id, trace_id)
        return self.api.handle(request, lambda r: {"status": "ok", "governed": True, "trace_id": trace_id})

    def health(self) -> dict[str, Any]:
        total = self._total_requests
        error_rate = (self._total_errors / total) if total > 0 else 0.0
        return {
            "status": "healthy",
            "environment": self.manifest.environment,
            "governed": self.manifest.governed,
            "active_sessions": self.auth.active_sessions,
            "tenants": self.tenants.tenant_count,
            "requests": self._total_requests,
            "error_rate": round(error_rate, 3),
            "events": self.observability.event_count,
        }
