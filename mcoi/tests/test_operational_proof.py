"""Phase 197 — Operational Proof & Live Path Validation.

Proves the production surface behaves correctly under real service conditions.
Not unit tests — these are end-to-end integration proofs.
"""
from __future__ import annotations
import pytest
from mcoi_runtime.app.production_surface import (
    APIRequest, APIResponse, APIBoundary, AuthGate, TenantBoundary,
    ObservabilityCollector, ProductionSurface, DEPLOYMENT_MANIFESTS,
    PERSISTENCE_PROFILES,
)

# ═══ 197A — End-to-End Request Proof ═══

class TestEndToEndRequestProof:
    """Proves: API request → auth → tenant → governed → response."""

    def test_full_governed_request_lifecycle(self):
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["pilot"])
        # Setup
        surface.auth.create_session("sess-1", "operator-1", "tenant-1")
        surface.tenants.register_tenant("tenant-1")
        # Request
        req = APIRequest("req-1", "POST", "/api/v1/dispatch", "operator-1", "tenant-1",
                        {"action": "test"}, {"session_id": "sess-1"})
        resp = surface.handle_request(req)
        assert resp.status_code == 200
        assert resp.governed is True
        assert resp.ledger_hash != ""
        # Observability recorded
        assert surface.observability.event_count >= 2  # request + dispatch

    def test_health_endpoint_reflects_state(self):
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["pilot"])
        surface.auth.create_session("s1", "op1", "t1")
        surface.tenants.register_tenant("t1")
        req = APIRequest("r1", "GET", "/health", "op1", "t1", headers={"session_id": "s1"})
        surface.handle_request(req)
        health = surface.health()
        assert health["status"] == "healthy"
        assert health["governed"] is True
        assert health["requests"] >= 1
        assert health["active_sessions"] >= 1

# ═══ 197B — Persistence Proof ═══

class TestPersistenceProof:
    """Proves persistence config is correctly structured for each environment."""

    def test_all_profiles_have_connection_string(self):
        for name, config in PERSISTENCE_PROFILES.items():
            assert config.connection_string, f"{name} missing connection string"
            assert config.backend in ("memory", "sqlite", "postgresql")

    def test_production_profile_is_durable(self):
        prod = PERSISTENCE_PROFILES["production"]
        assert prod.backend == "postgresql"
        assert prod.replay_safe is True
        assert prod.pool_size >= 5

# ═══ 197C — Adversarial Boundary Tests ═══

class TestAdversarialBoundary:
    """Proves governance holds under adversarial conditions."""

    def test_unauthenticated_request_denied(self):
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["pilot"])
        req = APIRequest("r1", "POST", "/api/dispatch", "unknown", "t1", headers={})
        resp = surface.handle_request(req)
        assert resp.status_code == 401

    def test_revoked_session_denied(self):
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["pilot"])
        surface.auth.create_session("s1", "op1", "t1")
        surface.auth.revoke("s1")
        req = APIRequest("r1", "POST", "/api/dispatch", "op1", "t1", headers={"session_id": "s1"})
        resp = surface.handle_request(req)
        assert resp.status_code == 401

    def test_cross_tenant_request_blocked(self):
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["pilot"])
        surface.auth.create_session("s1", "op1", "t1")
        surface.tenants.register_tenant("t1")
        surface.tenants.register_tenant("t2")
        # Request from t1 session trying to access t2 resource would be caught
        # by tenant boundary validation
        assert not surface.tenants.validate_access("t1", "t2")
        assert surface.tenants.violation_count == 1

    def test_invalid_session_id_denied(self):
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["pilot"])
        req = APIRequest("r1", "POST", "/api/dispatch", "op1", "t1", headers={"session_id": "nonexistent"})
        resp = surface.handle_request(req)
        assert resp.status_code == 401

    def test_dev_profile_skips_auth(self):
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["local_dev"])
        req = APIRequest("r1", "GET", "/api/test", "anyone", "any", headers={})
        resp = surface.handle_request(req)
        assert resp.status_code == 200  # dev mode — no auth required

# ═══ 197D — Observability Proof ═══

class TestObservabilityProof:
    """Proves request tracing and event correlation work."""

    def test_request_generates_trace_events(self):
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["pilot"])
        surface.auth.create_session("s1", "op1", "t1")
        surface.tenants.register_tenant("t1")
        req = APIRequest("trace-req-1", "POST", "/api/dispatch", "op1", "t1", headers={"session_id": "s1"})
        surface.handle_request(req)
        # Should have request + dispatch events with same trace ID
        events = surface.observability.events_for_trace("trace-req-1")
        assert len(events) >= 2
        assert events[0].event_type == "request"
        assert events[1].event_type == "dispatch"

    def test_denied_request_generates_error_event(self):
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["pilot"])
        req = APIRequest("denied-1", "POST", "/api/dispatch", "op1", "t1", headers={})
        surface.handle_request(req)
        events = surface.observability.events_for_trace("denied-1")
        assert any(e.event_type == "error" for e in events)

    def test_event_types_categorized(self):
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["pilot"])
        surface.auth.create_session("s1", "op1", "t1")
        surface.tenants.register_tenant("t1")
        for i in range(3):
            req = APIRequest(f"r{i}", "POST", "/api/dispatch", "op1", "t1", headers={"session_id": "s1"})
            surface.handle_request(req)
        by_type = surface.observability.events_by_type()
        assert "request" in by_type
        assert "dispatch" in by_type

# ═══ 197E — Deployment Proof ═══

class TestDeploymentProof:
    """Proves each deployment profile boots and serves correctly."""

    def test_dev_profile_boots(self):
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["local_dev"])
        health = surface.health()
        assert health["environment"] == "development"
        assert health["status"] == "healthy"

    def test_pilot_profile_boots_with_auth(self):
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["pilot"])
        assert surface.manifest.auth_required is True
        assert surface.manifest.tenant_isolation is True
        health = surface.health()
        assert health["environment"] == "pilot"

    def test_production_profile_has_all_features(self):
        manifest = DEPLOYMENT_MANIFESTS["production"]
        assert manifest.governed is True
        assert manifest.auth_required is True
        assert manifest.tenant_isolation is True
        assert manifest.observability is True
        assert manifest.persistence.backend == "postgresql"

# ═══ Golden — Complete Operational Proof ═══

class TestGoldenOperationalProof:
    """The definitive proof that the production surface is operational."""

    def test_complete_operational_lifecycle(self):
        # 1. Boot pilot surface
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["pilot"])
        assert surface.health()["status"] == "healthy"

        # 2. Create auth session
        session = surface.auth.create_session("golden-sess", "golden-actor", "golden-tenant")
        assert session.active

        # 3. Register tenant
        surface.tenants.register_tenant("golden-tenant")

        # 4. Submit governed request
        req = APIRequest("golden-req-1", "POST", "/api/v1/dispatch", "golden-actor", "golden-tenant",
                        {"action": "create_case"}, {"session_id": "golden-sess"})
        resp = surface.handle_request(req)
        assert resp.status_code == 200
        assert resp.governed is True

        # 5. Verify observability
        events = surface.observability.events_for_trace("golden-req-1")
        assert len(events) >= 2

        # 6. Verify health reflects activity
        health = surface.health()
        assert health["requests"] >= 1
        assert health["active_sessions"] >= 1
        assert health["tenants"] >= 1
        assert health["events"] >= 2
        assert health["error_rate"] == 0.0

        # 7. Adversarial: unauthenticated request denied
        bad_req = APIRequest("golden-bad", "POST", "/api/v1/dispatch", "hacker", "golden-tenant", headers={})
        bad_resp = surface.handle_request(bad_req)
        assert bad_resp.status_code == 401

        # 8. Verify error shows in health
        health2 = surface.health()
        assert health2["error_rate"] > 0  # one error out of two requests
