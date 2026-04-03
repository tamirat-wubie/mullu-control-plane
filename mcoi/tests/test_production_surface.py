"""Tests for Phase 196 — Production Surface & Deployment Hardening."""
import pytest
from mcoi_runtime.app.production_surface import (
    APIBoundary, APIRequest, APIResponse,
    AuthGate, Session,
    PersistenceConfig, PERSISTENCE_PROFILES,
    TenantBoundary,
    ObservabilityCollector,
    DeploymentManifest, DEPLOYMENT_MANIFESTS,
    ProductionSurface,
)


# ─── helpers ───

def _req(rid="r1", method="GET", path="/test", actor="a1", tenant="t1", body=None, headers=None):
    return APIRequest(rid, method, path, actor, tenant, body or {}, headers or {})


# ═══ 196A — API Boundary ═══

class TestAPIBoundary:
    def test_handle_success(self):
        api = APIBoundary()
        resp = api.handle(_req(), lambda r: {"ok": True})
        assert resp.status_code == 200
        assert resp.body == {"ok": True}
        assert resp.governed is True
        assert resp.ledger_hash != ""

    def test_handle_value_error_returns_400(self):
        api = APIBoundary()
        resp = api.handle(_req(), lambda r: (_ for _ in ()).throw(ValueError("bad")))
        assert resp.status_code == 400
        assert resp.body["error"] == "invalid_request"
        assert resp.body["error_code"] == "invalid_request"
        assert "bad" not in str(resp.body)

    def test_handle_permission_error_returns_403(self):
        api = APIBoundary()
        resp = api.handle(_req(), lambda r: (_ for _ in ()).throw(PermissionError("denied")))
        assert resp.status_code == 403
        assert resp.body["error"] == "forbidden"
        assert resp.body["error_code"] == "forbidden"
        assert "denied" not in str(resp.body)

    def test_error_rate(self):
        api = APIBoundary()
        api.handle(_req(rid="ok"), lambda r: {"ok": True})
        api.handle(_req(rid="bad"), lambda r: (_ for _ in ()).throw(ValueError("x")))
        assert api.error_rate() == 0.5
        assert api.request_count == 2


# ═══ 196B — Auth/Session ═══

class TestAuthGate:
    def test_create_session(self):
        auth = AuthGate()
        s = auth.create_session("s1", "actor1", "tenant1")
        assert s.session_id == "s1"
        assert s.active is True
        assert auth.active_sessions == 1

    def test_validate_existing(self):
        auth = AuthGate()
        auth.create_session("s1", "a1", "t1")
        s = auth.validate("s1")
        assert s.actor_id == "a1"

    def test_revoke_invalidates(self):
        auth = AuthGate()
        auth.create_session("s1", "a1", "t1")
        auth.revoke("s1")
        assert auth.active_sessions == 0
        with pytest.raises(PermissionError):
            auth.validate("s1")

    def test_denied_count(self):
        auth = AuthGate()
        for _ in range(3):
            with pytest.raises(PermissionError):
                auth.validate("nonexistent")
        assert auth.denied_count == 3


# ═══ 196C — Persistence Configuration ═══

class TestPersistenceConfig:
    def test_profiles_exist(self):
        assert set(PERSISTENCE_PROFILES.keys()) == {"development", "testing", "pilot", "production"}

    def test_production_uses_postgresql(self):
        prod = PERSISTENCE_PROFILES["production"]
        assert prod.backend == "postgresql"
        assert prod.pool_size == 10
        assert prod.replay_safe is True


# ═══ 196D — Tenant Isolation ═══

class TestTenantBoundary:
    def test_register_tenant(self):
        tb = TenantBoundary()
        tb.register_tenant("t1")
        tb.register_tenant("t2")
        assert tb.tenant_count == 2

    def test_same_tenant_access_allowed(self):
        tb = TenantBoundary()
        assert tb.validate_access("t1", "t1") is True
        assert tb.violation_count == 0

    def test_cross_tenant_denied(self):
        tb = TenantBoundary()
        assert tb.validate_access("t1", "t2") is False
        assert tb.violation_count == 1


# ═══ 196E — Observability ═══

class TestObservabilityCollector:
    def test_record_event(self):
        obs = ObservabilityCollector()
        obs.record("request", "GET /api", "t1", "trace-1")
        assert obs.event_count == 1

    def test_events_by_type(self):
        obs = ObservabilityCollector()
        obs.record("request", "a", "t1")
        obs.record("request", "b", "t1")
        obs.record("error", "c", "t1")
        assert obs.events_by_type() == {"request": 2, "error": 1}

    def test_events_for_trace(self):
        obs = ObservabilityCollector()
        obs.record("request", "a", "t1", "tr-1")
        obs.record("dispatch", "b", "t1", "tr-1")
        obs.record("request", "c", "t1", "tr-2")
        assert len(obs.events_for_trace("tr-1")) == 2
        assert len(obs.events_for_trace("tr-2")) == 1


# ═══ 196F — Deployment Config ═══

class TestDeploymentManifest:
    def test_manifests_exist(self):
        assert set(DEPLOYMENT_MANIFESTS.keys()) == {"local_dev", "test", "pilot", "production"}

    def test_production_features(self):
        prod = DEPLOYMENT_MANIFESTS["production"]
        assert prod.governed is True
        assert prod.auth_required is True
        assert prod.tenant_isolation is True
        assert prod.observability is True
        assert prod.persistence.backend == "postgresql"


# ═══ Golden — Integrated Surface ═══

class TestProductionSurfaceGolden:
    def test_full_lifecycle(self):
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["production"])
        surface.tenants.register_tenant("t1")
        session = surface.auth.create_session("s1", "actor1", "t1")

        req = _req(rid="r1", method="POST", path="/action", actor="actor1", tenant="t1",
                    headers={"session_id": "s1"})
        resp = surface.handle_request(req)

        assert resp.status_code == 200
        assert resp.body["governed"] is True

        h = surface.health()
        assert h["status"] == "healthy"
        assert h["environment"] == "production"
        assert h["active_sessions"] == 1
        assert h["requests"] == 1
        assert h["events"] >= 2  # request + dispatch at minimum

    def test_unauthenticated_denied(self):
        surface = ProductionSurface(DEPLOYMENT_MANIFESTS["production"])
        req = _req(rid="r2", headers={})
        resp = surface.handle_request(req)

        assert resp.status_code == 401
        assert resp.body["error"] == "unauthorized"
        assert resp.body["error_code"] == "unauthorized"
