"""v4.16.0 — chain gating extends from /constructs/* writes to /domains/*/process runs.

The v4.15.0 bridge gated only construct-write paths. v4.16.0 wires the
same chain into every /domains/* endpoint (originally six; expanded to
fifteen as of v4.8.x) so a deployment can apply policy uniformly across
writes AND domain runs.

When the chain is detached (default), domain runs behave exactly as in
v4.15.x. When attached, the chain runs *before* the cycle. A rejection
returns a synthetic DomainOutcome with governance_status starting with
``blocked: chain_rejected`` — no cycle work happens, no constructs are
generated, no run is persisted.
"""
from __future__ import annotations

from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.constructs import reset_registry
from mcoi_runtime.app.routers.domains import router as domains_router
from mcoi_runtime.app.routers.musia_auth import configure_musia_auth
from mcoi_runtime.app.routers.musia_governance_bridge import (
    configure_musia_governance_chain,
    gate_domain_run,
)
from mcoi_runtime.governance.guards.chain import (
    GovernanceGuard,
    GovernanceGuardChain,
    GuardResult,
)


# ============================================================
# gate_domain_run unit tests
# ============================================================


def test_gate_domain_run_passes_when_chain_detached():
    """Default detached state — gate is a no-op pass."""
    configure_musia_governance_chain(None)
    ok, reason = gate_domain_run(
        domain="software_dev",
        tenant_id="acme",
        summary="anything",
    )
    assert ok is True
    assert reason == ""


def test_gate_domain_run_passes_when_chain_allows():
    chain = GovernanceGuardChain()
    chain.add(
        GovernanceGuard(
            "ok", lambda ctx: GuardResult(allowed=True, guard_name="ok")
        )
    )
    configure_musia_governance_chain(chain)
    try:
        ok, reason = gate_domain_run(
            domain="software_dev",
            tenant_id="acme",
            summary="benign",
        )
        assert ok is True
    finally:
        configure_musia_governance_chain(None)


def test_gate_domain_run_blocks_when_chain_denies():
    chain = GovernanceGuardChain()
    chain.add(
        GovernanceGuard(
            "deny",
            lambda ctx: GuardResult(
                allowed=False, guard_name="deny", reason="nope",
            ),
        )
    )
    configure_musia_governance_chain(chain)
    try:
        ok, reason = gate_domain_run(
            domain="healthcare",
            tenant_id="hospital",
            summary="prescribe",
        )
        assert ok is False
        assert "deny" in reason
        assert "nope" in reason
    finally:
        configure_musia_governance_chain(None)


def test_gate_domain_run_passes_domain_in_guard_ctx():
    """A guard can inspect ctx['domain'] to write per-domain policy."""
    seen: list[str] = []

    def capture(ctx: dict) -> GuardResult:
        seen.append(ctx.get("domain", ""))
        return GuardResult(allowed=True, guard_name="capture")

    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("capture", capture))
    configure_musia_governance_chain(chain)
    try:
        gate_domain_run(domain="software_dev", tenant_id="t", summary="a")
        gate_domain_run(domain="manufacturing", tenant_id="t", summary="b")
        gate_domain_run(domain="education", tenant_id="t", summary="c")
        assert seen == ["software_dev", "manufacturing", "education"]
    finally:
        configure_musia_governance_chain(None)


def test_gate_domain_run_passes_operation_marker():
    """``operation = "domain_run"`` distinguishes from construct writes."""
    seen: list[str] = []

    def capture(ctx: dict) -> GuardResult:
        seen.append(ctx.get("operation", ""))
        return GuardResult(allowed=True, guard_name="capture")

    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("capture", capture))
    configure_musia_governance_chain(chain)
    try:
        gate_domain_run(domain="software_dev", tenant_id="t", summary="x")
        assert seen == ["domain_run"]
    finally:
        configure_musia_governance_chain(None)


def test_gate_domain_run_passes_endpoint_path():
    seen: list[str] = []

    def capture(ctx: dict) -> GuardResult:
        seen.append(ctx.get("endpoint", ""))
        return GuardResult(allowed=True, guard_name="capture")

    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("capture", capture))
    configure_musia_governance_chain(chain)
    try:
        gate_domain_run(domain="healthcare", tenant_id="t", summary="x")
        assert seen == ["musia/domains/healthcare/process"]
    finally:
        configure_musia_governance_chain(None)


def test_gate_domain_run_omits_construct_fields():
    """Domain-run guard ctx must NOT carry construct_type / construct_tier
    — those are write-path only. Domain runs are not construct writes."""
    seen: list[dict] = []

    def capture(ctx: dict) -> GuardResult:
        seen.append(dict(ctx))
        return GuardResult(allowed=True, guard_name="capture")

    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("capture", capture))
    configure_musia_governance_chain(chain)
    try:
        gate_domain_run(domain="software_dev", tenant_id="t", summary="x")
        assert "construct_type" not in seen[0]
        assert "construct_tier" not in seen[0]
    finally:
        configure_musia_governance_chain(None)


def test_gate_domain_run_passes_summary_to_guards():
    seen: list[str] = []

    def capture(ctx: dict) -> GuardResult:
        seen.append(ctx.get("summary", ""))
        return GuardResult(allowed=True, guard_name="capture")

    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("capture", capture))
    configure_musia_governance_chain(chain)
    try:
        gate_domain_run(
            domain="software_dev",
            tenant_id="t",
            summary="urgent: rotate prod credentials",
        )
        assert seen == ["urgent: rotate prod credentials"]
    finally:
        configure_musia_governance_chain(None)


def test_gate_domain_run_propagates_actor_identifier_when_provided():
    seen: list[str] = []

    def capture(ctx: dict) -> GuardResult:
        seen.append(ctx.get("authenticated_subject", "<missing>"))
        return GuardResult(allowed=True, guard_name="capture")

    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("capture", capture))
    configure_musia_governance_chain(chain)
    try:
        gate_domain_run(
            domain="software_dev",
            tenant_id="t",
            summary="x",
            actor_identifier="alice",
        )
        assert seen == ["alice"]
    finally:
        configure_musia_governance_chain(None)


def test_gate_domain_run_no_actor_yields_no_subject_field():
    """When no actor is given, ``authenticated_subject`` must not appear."""
    seen: list[dict] = []

    def capture(ctx: dict) -> GuardResult:
        seen.append(dict(ctx))
        return GuardResult(allowed=True, guard_name="capture")

    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("capture", capture))
    configure_musia_governance_chain(chain)
    try:
        gate_domain_run(domain="software_dev", tenant_id="t", summary="x")
        assert "authenticated_subject" not in seen[0]
    finally:
        configure_musia_governance_chain(None)


# ============================================================
# Per-endpoint integration: each domain runs the gate
# ============================================================


@pytest.fixture
def client() -> Iterator[TestClient]:
    reset_registry()
    configure_musia_auth(None)
    configure_musia_governance_chain(None)
    app = FastAPI()
    app.include_router(domains_router)
    yield TestClient(app)
    configure_musia_governance_chain(None)
    reset_registry()


_VALID_PAYLOADS = {
    "software-dev": {
        "kind": "bug_fix",
        "summary": "fix the bug",
        "repository": "mullu",
        "target_branch": "main",
        "affected_files": ["a.py"],
        "acceptance_criteria": ["test_passes"],
        "blast_radius": "module",
        "reviewer_required": True,
    },
    "business-process": {
        "kind": "approval",
        "summary": "approve invoice",
        "process_id": "P-1",
        "initiator": "alice",
        "approval_chain": ["mgr"],
        "affected_systems": ["erp"],
        "acceptance_criteria": ["approved"],
        "dollar_impact": 100.0,
        "blast_radius": "department",
    },
    "scientific-research": {
        "kind": "analysis",
        "summary": "study x",
        "study_id": "S-1",
        "principal_investigator": "dr_a",
        "peer_reviewers": ["r1"],
        "affected_corpus": ["c1"],
        "acceptance_criteria": ["replicates"],
        "confidence_threshold": 0.95,
        "minimum_replications": 1,
        "statistical_power_target": 0.8,
        "blast_radius": "study",
    },
    "manufacturing": {
        "kind": "quality_inspection",
        "summary": "tweak line",
        "line_id": "L-1",
        "operator_id": "op-1",
        "quality_engineer": "qe-1",
        "iso_certifications": ["9001"],
        "affected_part_numbers": ["P-1"],
        "acceptance_criteria": ["yield_holds"],
        "expected_yield_pct": 0.97,
        "blast_radius": "line",
    },
    "healthcare": {
        "kind": "prescription",
        "summary": "treat patient",
        "encounter_id": "E-1",
        "primary_clinician": "dr_b",
        "consulting_specialists": [],
        "patient_consented": True,
        "consent_kind": "written",
        "affected_records": ["R-1"],
        "acceptance_criteria": ["safe"],
        "blast_radius": "encounter",
    },
    "education": {
        "kind": "grading",
        "summary": "update syllabus",
        "course_id": "C-1",
        "instructor": "prof_a",
        "curriculum_committee": ["m1"],
        "accreditation_body": "abet",
        "affected_learners": ["L-1"],
        "learning_objectives": ["objective_1"],
        "acceptance_criteria": ["aligned"],
        "blast_radius": "course",
    },
}


_DOMAIN_NAMES = {
    "software-dev": "software_dev",
    "business-process": "business_process",
    "scientific-research": "scientific_research",
    "manufacturing": "manufacturing",
    "healthcare": "healthcare",
    "education": "education",
}


@pytest.mark.parametrize("path", list(_VALID_PAYLOADS.keys()))
def test_domain_run_passes_when_chain_detached(client, path):
    """Default behavior preserved: with no chain attached, every
    /domains/<x>/process endpoint accepts a valid payload."""
    r = client.post(f"/domains/{path}/process", json=_VALID_PAYLOADS[path])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["domain"] == _DOMAIN_NAMES[path]
    # Chain didn't run, so the governance_status reflects the cycle's verdict
    assert "blocked: chain_rejected" not in body["governance_status"]


@pytest.mark.parametrize("path", list(_VALID_PAYLOADS.keys()))
def test_domain_run_blocked_when_chain_denies(client, path):
    """Every /domains/<x>/process endpoint short-circuits when the chain denies."""
    chain = GovernanceGuardChain()
    chain.add(
        GovernanceGuard(
            "deny_all",
            lambda ctx: GuardResult(
                allowed=False, guard_name="deny_all", reason="domain blocked",
            ),
        )
    )
    configure_musia_governance_chain(chain)

    r = client.post(f"/domains/{path}/process", json=_VALID_PAYLOADS[path])
    # 200 with synthetic blocked outcome — not 403, so callers get a
    # uniform shape regardless of whether chain or cycle blocked
    assert r.status_code == 200
    body = r.json()
    assert body["domain"] == _DOMAIN_NAMES[path]
    assert body["governance_status"].startswith("blocked: chain_rejected")
    assert "deny_all" in body["governance_status"]
    # Risk flags surface the rejection so it's discoverable in the array shape
    assert any("chain_gate_rejected" in f for f in body["risk_flags"])
    # No work happened — plan is empty, run_id is null
    assert body["plan"] == []
    assert body["run_id"] is None


def test_blocked_run_does_not_persist_when_persist_run_set(client):
    """Even with persist_run=true, a chain-blocked run must not leak constructs."""
    chain = GovernanceGuardChain()
    chain.add(
        GovernanceGuard(
            "deny",
            lambda ctx: GuardResult(
                allowed=False, guard_name="deny", reason="x",
            ),
        )
    )
    configure_musia_governance_chain(chain)

    from mcoi_runtime.substrate.registry_store import STORE
    pre_count = len(STORE.get_or_create("acme").graph.constructs)

    r = client.post(
        "/domains/software-dev/process?persist_run=true",
        headers={"X-Tenant-ID": "acme"},
        json=_VALID_PAYLOADS["software-dev"],
    )
    assert r.status_code == 200
    assert r.json()["governance_status"].startswith("blocked: chain_rejected")
    assert r.json()["run_id"] is None

    post_count = len(STORE.get_or_create("acme").graph.constructs)
    assert post_count == pre_count


def test_per_domain_policy_blocks_some_passes_others(client):
    """Guards can write per-domain policy via ctx['domain']: e.g.,
    "no healthcare runs from this tenant." Other domains pass."""

    def healthcare_only_blocker(ctx: dict) -> GuardResult:
        if ctx.get("domain") == "healthcare":
            return GuardResult(
                allowed=False,
                guard_name="hc_lockdown",
                reason="healthcare frozen for compliance review",
            )
        return GuardResult(allowed=True, guard_name="hc_lockdown")

    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("hc_lockdown", healthcare_only_blocker))
    configure_musia_governance_chain(chain)

    # Healthcare → blocked
    r_hc = client.post(
        "/domains/healthcare/process",
        json=_VALID_PAYLOADS["healthcare"],
    )
    assert r_hc.status_code == 200
    assert r_hc.json()["governance_status"].startswith("blocked: chain_rejected")
    assert "hc_lockdown" in r_hc.json()["governance_status"]

    # Software-dev → passes (chain says yes for non-healthcare)
    r_sw = client.post(
        "/domains/software-dev/process",
        json=_VALID_PAYLOADS["software-dev"],
    )
    assert r_sw.status_code == 200
    assert not r_sw.json()["governance_status"].startswith("blocked: chain_rejected")


def test_summary_reaches_guard_via_endpoint(client):
    """End-to-end: the payload's summary surfaces in the chain guard ctx,
    so policies can write summary-keyed rules ('block runs mentioning credentials')."""
    seen: list[str] = []

    def capture(ctx: dict) -> GuardResult:
        seen.append(ctx.get("summary", ""))
        return GuardResult(allowed=True, guard_name="capture")

    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("capture", capture))
    configure_musia_governance_chain(chain)

    r = client.post(
        "/domains/software-dev/process",
        json={
            **_VALID_PAYLOADS["software-dev"],
            "summary": "rotate stripe_secret_key in prod",
        },
    )
    assert r.status_code == 200
    assert seen == ["rotate stripe_secret_key in prod"]


def test_blocked_run_returns_audit_trail_id(client):
    """Operators correlate chain logs with HTTP responses by audit_trail_id;
    a blocked outcome must still carry one."""
    chain = GovernanceGuardChain()
    chain.add(
        GovernanceGuard(
            "deny",
            lambda ctx: GuardResult(
                allowed=False, guard_name="deny", reason="x",
            ),
        )
    )
    configure_musia_governance_chain(chain)

    r = client.post(
        "/domains/software-dev/process",
        json=_VALID_PAYLOADS["software-dev"],
    )
    body = r.json()
    assert body["audit_trail_id"]
    # UUIDs are 36 chars including hyphens
    assert len(body["audit_trail_id"]) == 36
