"""Gateway tenant identity tests.

Tests: durable identity store contract, revocation behavior, and router wiring.
"""

import os
import sys
import threading
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.router import GatewayRouter  # noqa: E402
import gateway.tenant_identity as tenant_identity_module  # noqa: E402
from gateway.tenant_identity import (  # noqa: E402
    InMemoryTenantIdentityStore,
    OidcJwksRefreshEvidence,
    PostgresTenantIdentityStore,
    TenantMapping,
    TenantIdentityConfigurationError,
    TrustedIdentityGatewayEvidence,
    TRUSTED_IDENTITY_HEADER_NAMES,
    assess_oidc_jwks_refresh_evidence,
    assess_trusted_identity_header_boundary,
    build_tenant_identity_store_from_env,
)


class StubPlatform:
    """Minimal platform stub for router construction."""

    def connect(self, *, identity_id: str, tenant_id: str):
        raise AssertionError("tenant identity tests should not open sessions")


class _CountingCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, *_args, **_kwargs):
        return None

    def fetchone(self):
        return (0,)


class _RollbackFailingConnection:
    def __init__(self):
        self.rollback_attempts = 0

    def rollback(self):
        self.rollback_attempts += 1
        raise RuntimeError("rollback failed")

    def cursor(self):
        return _CountingCursor()

    def close(self):
        return None


class _CloseFailingConnection:
    def close(self):
        raise RuntimeError("close failed")


def _postgres_store_for_fault_tests(conn):
    store = PostgresTenantIdentityStore.__new__(PostgresTenantIdentityStore)
    store._connection_string = "postgresql://example/mullu"
    store._clock = lambda: "2026-04-24T12:00:00+00:00"
    store._conn = conn
    store._lock = threading.Lock()
    store._available = True
    store._operation_failures = 0
    store._rollback_failures = 0
    store._close_failures = 0
    return store


def _valid_oidc_jwks_refresh_evidence(**overrides):
    payload = {
        "issuer": "https://login.example.com/tenant",
        "discovery_url": "https://login.example.com/tenant/.well-known/openid-configuration",
        "jwks_uri": "https://login.example.com/tenant/.well-known/jwks.json",
        "audiences": ("mullu-control-plane",),
        "allowed_algorithms": ("RS256", "RS512"),
        "discovery_hash": "sha256:discovery-config-hash",
        "jwks_hash": "sha256:jwks-document-hash",
        "key_count": 2,
        "cache_age_seconds": 60,
        "cache_ttl_seconds": 300,
        "issuer_pinned": True,
        "audience_bound": True,
        "https_enforced": True,
        "redirects_blocked": True,
        "rollback_or_bypass_protection": True,
        "evidence_refs": ("receipt://gateway/oidc-jwks-refresh/20260615",),
    }
    payload.update(overrides)
    return OidcJwksRefreshEvidence(**payload)


def test_in_memory_tenant_identity_store_resolves_active_mapping():
    store = InMemoryTenantIdentityStore(clock=lambda: "2026-04-24T12:00:00+00:00")
    store.save(TenantMapping(
        channel="slack",
        sender_id="U123",
        tenant_id="tenant-1",
        identity_id="identity-1",
        roles=("operator",),
        approval_authority=True,
    ))

    mapping = store.resolve("slack", "U123")

    assert mapping is not None
    assert mapping.tenant_id == "tenant-1"
    assert mapping.identity_id == "identity-1"
    assert mapping.roles == ("operator",)
    assert mapping.approval_authority is True
    assert mapping.created_at == "2026-04-24T12:00:00+00:00"


def test_in_memory_tenant_identity_store_does_not_resolve_revoked_mapping():
    store = InMemoryTenantIdentityStore(clock=lambda: "2026-04-24T12:00:00+00:00")
    store.save(TenantMapping(
        channel="telegram",
        sender_id="42",
        tenant_id="tenant-1",
        identity_id="identity-1",
        revoked_at="2026-04-24T13:00:00+00:00",
    ))

    mapping = store.resolve("telegram", "42")

    assert mapping is None
    assert store.count() == 0
    assert store.status()["active_mappings"] == 0


def test_build_tenant_identity_store_from_env_uses_memory_backend(monkeypatch):
    monkeypatch.setitem(os.environ, "MULLU_TENANT_IDENTITY_BACKEND", "memory")
    monkeypatch.delenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", raising=False)
    monkeypatch.setitem(os.environ, "MULLU_ENV", "local_dev")

    store = build_tenant_identity_store_from_env(clock=lambda: "2026-04-24T12:00:00+00:00")

    assert store.status()["backend"] == "memory"
    assert store.status()["persistent"] is False
    assert store.status()["available"] is True
    assert store.count() == 0


def test_build_tenant_identity_store_rejects_memory_when_persistent_required(monkeypatch):
    monkeypatch.setitem(os.environ, "MULLU_TENANT_IDENTITY_BACKEND", "memory")
    monkeypatch.setitem(os.environ, "MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "true")
    monkeypatch.setitem(os.environ, "MULLU_ENV", "local_dev")

    with pytest.raises(
        TenantIdentityConfigurationError,
        match="^persistent tenant identity store required$",
    ):
        build_tenant_identity_store_from_env(clock=lambda: "2026-04-24T12:00:00+00:00")


def test_build_tenant_identity_store_requires_persistence_in_pilot(monkeypatch):
    monkeypatch.setitem(os.environ, "MULLU_TENANT_IDENTITY_BACKEND", "memory")
    monkeypatch.delenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", raising=False)
    monkeypatch.setitem(os.environ, "MULLU_ENV", "pilot")

    with pytest.raises(
        TenantIdentityConfigurationError,
        match="^persistent tenant identity store required$",
    ):
        build_tenant_identity_store_from_env(clock=lambda: "2026-04-24T12:00:00+00:00")


def test_build_tenant_identity_store_rejects_unavailable_postgres_when_required(monkeypatch):
    class UnavailablePostgresStore:
        def __init__(self, *_args, **_kwargs):
            self.closed = False

        def status(self):
            return {
                "backend": "postgresql",
                "persistent": True,
                "available": False,
                "active_mappings": 0,
            }

        def close(self):
            self.closed = True

    monkeypatch.setitem(os.environ, "MULLU_TENANT_IDENTITY_BACKEND", "postgresql")
    monkeypatch.setitem(os.environ, "MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "true")
    monkeypatch.setitem(os.environ, "MULLU_TENANT_IDENTITY_DB_URL", "postgresql://example/mullu")
    monkeypatch.setattr(tenant_identity_module, "PostgresTenantIdentityStore", UnavailablePostgresStore)

    with pytest.raises(
        TenantIdentityConfigurationError,
        match="^persistent tenant identity store unavailable$",
    ):
        build_tenant_identity_store_from_env(clock=lambda: "2026-04-24T12:00:00+00:00")


def test_trusted_identity_headers_disabled_by_default():
    assessment = assess_trusted_identity_header_boundary(TrustedIdentityGatewayEvidence())

    assert assessment.trusted_headers_accepted is False
    assert assessment.trusted_identity_headers_disabled is True
    assert assessment.blocked_reasons == ()
    assert assessment.protected_headers == TRUSTED_IDENTITY_HEADER_NAMES
    assert assessment.evidence_refs == ()
    assert assessment.verifier_mode == "disabled"
    assert assessment.authentication_performed is False


def test_trusted_identity_headers_accept_complete_oidc_gateway_evidence():
    assessment = assess_trusted_identity_header_boundary(TrustedIdentityGatewayEvidence(
        trusted_identity_headers_enabled=True,
        client_header_strip_verified=True,
        verified_identity_injection=True,
        oidc_verified=True,
        issuer_pinned=True,
        audience_bound=True,
        jwks_fresh=True,
        rollback_or_bypass_protection=True,
        evidence_refs=(
            "receipt://gateway/header-strip/20260615",
            "receipt://gateway/oidc-jwks/20260615",
        ),
        header_names=(
            "X-Mullu-Authority-Sender-Id",
            "x-mullu-authority-sender-id",
            "X-Auth-Request-Email",
        ),
    ))

    assert assessment.trusted_headers_accepted is True
    assert assessment.trusted_identity_headers_disabled is False
    assert assessment.blocked_reasons == ()
    assert assessment.protected_headers == ("x-mullu-authority-sender-id", "x-auth-request-email")
    assert assessment.evidence_refs == (
        "receipt://gateway/header-strip/20260615",
        "receipt://gateway/oidc-jwks/20260615",
    )
    assert assessment.verifier_mode == "oidc"


def test_trusted_identity_headers_accept_complete_mtls_gateway_evidence():
    assessment = assess_trusted_identity_header_boundary(TrustedIdentityGatewayEvidence(
        trusted_identity_headers_enabled=True,
        client_header_strip_verified=True,
        verified_identity_injection=True,
        mtls_verified=True,
        mtls_certificate_chain_verified=True,
        rollback_or_bypass_protection=True,
        evidence_refs=("receipt://gateway/mtls-boundary/20260615",),
        header_names=("X-Forwarded-Email",),
    ))

    assert assessment.trusted_headers_accepted is True
    assert assessment.blocked_reasons == ()
    assert assessment.protected_headers == ("x-forwarded-email",)
    assert assessment.evidence_refs == ("receipt://gateway/mtls-boundary/20260615",)
    assert assessment.verifier_mode == "mtls"


def test_trusted_identity_headers_block_missing_gateway_evidence():
    assessment = assess_trusted_identity_header_boundary(TrustedIdentityGatewayEvidence(
        trusted_identity_headers_enabled=True,
        header_names=("X-Forwarded-User",),
    ))

    assert assessment.trusted_headers_accepted is False
    assert "client_header_strip_evidence_missing" in assessment.blocked_reasons
    assert "verified_identity_injection_missing" in assessment.blocked_reasons
    assert "verified_oidc_or_mtls_missing" in assessment.blocked_reasons
    assert "complete_verifier_path_missing" in assessment.blocked_reasons
    assert "rollback_or_bypass_protection_missing" in assessment.blocked_reasons
    assert "gateway_evidence_refs_missing" in assessment.blocked_reasons
    assert assessment.protected_headers == ("x-forwarded-user",)


def test_trusted_identity_headers_reject_malformed_evidence_refs():
    with pytest.raises(ValueError, match="^evidence_refs_invalid$"):
        assess_trusted_identity_header_boundary(TrustedIdentityGatewayEvidence(
            trusted_identity_headers_enabled=True,
            evidence_refs=("receipt://gateway/ok", 7),
        ))


def test_trusted_identity_headers_reject_non_boolean_evidence():
    with pytest.raises(ValueError, match="^oidc_verified_invalid$"):
        assess_trusted_identity_header_boundary(TrustedIdentityGatewayEvidence(
            trusted_identity_headers_enabled=True,
            oidc_verified="yes",
        ))


def test_oidc_jwks_refresh_evidence_accepts_fresh_https_receipt():
    assessment = assess_oidc_jwks_refresh_evidence(_valid_oidc_jwks_refresh_evidence())

    assert assessment.jwks_fresh is True
    assert assessment.blocked_reasons == ()
    assert assessment.issuer == "https://login.example.com/tenant"
    assert assessment.discovery_hash == "sha256:discovery-config-hash"
    assert assessment.jwks_hash == "sha256:jwks-document-hash"
    assert assessment.key_count == 2
    assert assessment.cache_age_seconds == 60
    assert assessment.cache_ttl_seconds == 300
    assert assessment.evidence_refs == ("receipt://gateway/oidc-jwks-refresh/20260615",)
    assert assessment.authentication_performed is False
    assert assessment.network_fetch_performed is False


def test_oidc_jwks_refresh_evidence_blocks_stale_cache_and_missing_refs():
    assessment = assess_oidc_jwks_refresh_evidence(_valid_oidc_jwks_refresh_evidence(
        cache_age_seconds=301,
        cache_ttl_seconds=300,
        evidence_refs=(),
    ))

    assert assessment.jwks_fresh is False
    assert "jwks_cache_stale" in assessment.blocked_reasons
    assert "oidc_refresh_evidence_refs_missing" in assessment.blocked_reasons
    assert assessment.cache_age_seconds == 301
    assert assessment.cache_ttl_seconds == 300
    assert assessment.evidence_refs == ()
    assert assessment.authentication_performed is False
    assert assessment.network_fetch_performed is False


def test_oidc_jwks_refresh_evidence_blocks_insecure_discovery_and_redirects():
    assessment = assess_oidc_jwks_refresh_evidence(_valid_oidc_jwks_refresh_evidence(
        discovery_url="http://login.example.com/tenant/.well-known/openid-configuration",
        jwks_uri="http://login.example.com/tenant/.well-known/jwks.json",
        https_enforced=False,
        redirects_blocked=False,
    ))

    assert assessment.jwks_fresh is False
    assert "oidc_discovery_https_required" in assessment.blocked_reasons
    assert "oidc_jwks_https_required" in assessment.blocked_reasons
    assert "https_enforcement_missing" in assessment.blocked_reasons
    assert "redirect_blocking_missing" in assessment.blocked_reasons
    assert assessment.discovery_url.startswith("http://")
    assert assessment.jwks_uri.startswith("http://")


def test_oidc_jwks_refresh_evidence_blocks_invalid_hashes_and_algorithms():
    assessment = assess_oidc_jwks_refresh_evidence(_valid_oidc_jwks_refresh_evidence(
        allowed_algorithms=("none", "HS256"),
        discovery_hash="discovery-config-hash",
        jwks_hash="",
        key_count=0,
    ))

    assert assessment.jwks_fresh is False
    assert "oidc_unsigned_algorithm_rejected" in assessment.blocked_reasons
    assert "oidc_allowed_algorithm_not_jwks_bound" in assessment.blocked_reasons
    assert "oidc_discovery_hash_invalid" in assessment.blocked_reasons
    assert "oidc_jwks_hash_invalid" in assessment.blocked_reasons
    assert "oidc_jwks_key_count_invalid" in assessment.blocked_reasons
    assert assessment.allowed_algorithms == ("none", "HS256")


def test_oidc_jwks_refresh_evidence_rejects_non_boolean_boundary_flags():
    with pytest.raises(ValueError, match="^redirects_blocked_invalid$"):
        assess_oidc_jwks_refresh_evidence(_valid_oidc_jwks_refresh_evidence(
            redirects_blocked="yes",
        ))


def test_trusted_identity_headers_accept_oidc_refresh_assessment_evidence():
    refresh = assess_oidc_jwks_refresh_evidence(_valid_oidc_jwks_refresh_evidence())
    assessment = assess_trusted_identity_header_boundary(TrustedIdentityGatewayEvidence(
        trusted_identity_headers_enabled=True,
        client_header_strip_verified=True,
        verified_identity_injection=True,
        oidc_verified=True,
        issuer_pinned=True,
        audience_bound=True,
        jwks_fresh=refresh.jwks_fresh,
        rollback_or_bypass_protection=True,
        evidence_refs=refresh.evidence_refs + ("receipt://gateway/header-strip/20260615",),
        header_names=("X-Mullu-Authority-Tenant-Id", "X-Auth-Request-User"),
    ))

    assert refresh.jwks_fresh is True
    assert assessment.trusted_headers_accepted is True
    assert assessment.blocked_reasons == ()
    assert assessment.verifier_mode == "oidc"
    assert assessment.evidence_refs == (
        "receipt://gateway/oidc-jwks-refresh/20260615",
        "receipt://gateway/header-strip/20260615",
    )
    assert assessment.protected_headers == ("x-mullu-authority-tenant-id", "x-auth-request-user")


def test_postgres_operation_failure_counts_rollback_failure():
    conn = _RollbackFailingConnection()
    store = _postgres_store_for_fault_tests(conn)

    result = store._safe_execute(lambda: (_ for _ in ()).throw(RuntimeError("write failed")))
    status = store.status()

    assert result is None
    assert conn.rollback_attempts == 1
    assert status["operation_failures"] == 1
    assert status["rollback_failures"] == 1
    assert status["active_mappings"] == 0


def test_postgres_close_failure_is_counted_and_connection_cleared():
    store = _postgres_store_for_fault_tests(_CloseFailingConnection())

    store.close()
    status = store.status()

    assert store._conn is None
    assert status["available"] is False
    assert status["close_failures"] == 1


def test_router_uses_injected_tenant_identity_store():
    store = InMemoryTenantIdentityStore(clock=lambda: "2026-04-24T12:00:00+00:00")
    router = GatewayRouter(
        platform=StubPlatform(),
        tenant_identity_store=store,
    )
    router.register_tenant_mapping(TenantMapping(
        channel="web",
        sender_id="subject-1",
        tenant_id="tenant-1",
        identity_id="identity-1",
    ))

    mapping = router.resolve_tenant("web", "subject-1")
    summary = router.summary()

    assert mapping is not None
    assert mapping.tenant_id == "tenant-1"
    assert summary["tenant_mappings"] == 1
    assert summary["tenant_identity_store"]["backend"] == "memory"
