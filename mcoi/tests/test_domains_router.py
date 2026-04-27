"""HTTP tests for the /domains/* router — one endpoint per concrete adapter."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.constructs import reset_registry
from mcoi_runtime.app.routers.domains import router as domains_router
from mcoi_runtime.app.routers.musia_auth import configure_musia_auth


@pytest.fixture
def client() -> TestClient:
    reset_registry()
    configure_musia_auth(None)  # dev mode
    app = FastAPI()
    app.include_router(domains_router)
    return TestClient(app)


# ---- Index ----


def test_list_domains(client):
    r = client.get("/domains")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "software_dev",
        "business_process",
        "scientific_research",
        "manufacturing",
        "healthcare",
        "education",
    }


# ---- software_dev ----


def test_software_dev_process_complete_request(client):
    r = client.post(
        "/domains/software-dev/process",
        json={
            "kind": "bug_fix",
            "summary": "fix budget enforcement leak",
            "repository": "mullu-control-plane",
            "affected_files": ["mcoi/runtime/budget.py"],
            "acceptance_criteria": ["test_passes", "no_regression"],
            "blast_radius": "module",
            "reviewer_required": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["domain"] == "software_dev"
    assert body["governance_status"] == "approved"
    assert "code_reviewer" in body["metadata"]["required_reviewers"]
    assert any("Read current state" in s for s in body["plan"])
    assert body["tenant_id"] == "default"


def test_software_dev_unknown_kind_400(client):
    r = client.post(
        "/domains/software-dev/process",
        json={
            "kind": "miracle",
            "summary": "x",
            "repository": "y",
        },
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "unknown_kind"
    assert detail["value"] == "miracle"


def test_software_dev_missing_acceptance_criteria_blocked(client):
    r = client.post(
        "/domains/software-dev/process",
        json={
            "kind": "feature",
            "summary": "add thing",
            "repository": "x",
            "affected_files": ["a.py"],
            "acceptance_criteria": [],
        },
    )
    assert r.status_code == 200
    assert "Unknown" in r.json()["governance_status"]


# ---- business_process ----


def test_business_process_complete(client):
    r = client.post(
        "/domains/business-process/process",
        json={
            "kind": "approval",
            "summary": "approve marketing budget Q3",
            "process_id": "proc-001",
            "initiator": "alice",
            "approval_chain": ["manager-bob", "director-carol"],
            "sla_deadline_hours": 24.0,
            "affected_systems": ["erp"],
            "acceptance_criteria": ["budget_within_cap"],
            "dollar_impact": 50000.0,
            "blast_radius": "department",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["domain"] == "business_process"
    assert body["governance_status"] == "approved"
    assert "manager-bob" in body["metadata"]["required_approvals"]


def test_business_invalid_dollar_impact_400(client):
    r = client.post(
        "/domains/business-process/process",
        json={
            "kind": "approval",
            "summary": "x",
            "process_id": "p",
            "initiator": "a",
            "approval_chain": ["b"],
            "affected_systems": [],
            "acceptance_criteria": ["c"],
            "dollar_impact": -100.0,  # invalid
        },
    )
    assert r.status_code == 400


# ---- scientific_research ----


def test_scientific_research_complete(client):
    r = client.post(
        "/domains/scientific-research/process",
        json={
            "kind": "hypothesis_formation",
            "summary": "caffeine improves typing speed",
            "study_id": "study-001",
            "principal_investigator": "dr-alice",
            "peer_reviewers": ["dr-bob"],
            "affected_corpus": ["dataset_v1"],
            "acceptance_criteria": ["statistical_significance_reached"],
            "confidence_threshold": 0.95,
            "minimum_replications": 2,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["domain"] == "scientific_research"
    assert body["governance_status"] == "approved"
    assert body["metadata"]["confidence_threshold"] == 0.95
    assert body["metadata"]["minimum_replications"] == 2


def test_scientific_research_invalid_confidence_400(client):
    r = client.post(
        "/domains/scientific-research/process",
        json={
            "kind": "analysis",
            "summary": "x",
            "study_id": "s",
            "principal_investigator": "p",
            "affected_corpus": [],
            "acceptance_criteria": ["c"],
            "confidence_threshold": 1.5,
        },
    )
    assert r.status_code == 400


# ---- manufacturing ----


def test_manufacturing_complete(client):
    r = client.post(
        "/domains/manufacturing/process",
        json={
            "kind": "quality_inspection",
            "summary": "inspect bracket lot 42",
            "line_id": "line-3",
            "operator_id": "op-7",
            "quality_engineer": "qe-jane",
            "iso_certifications": ["9001"],
            "affected_part_numbers": ["PN-12345"],
            "acceptance_criteria": ["all_dimensions_within_spec"],
            "tolerance_microns": 10.0,
            "expected_yield_pct": 0.97,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["domain"] == "manufacturing"
    assert body["governance_status"] == "approved"
    assert body["metadata"]["tolerance_microns"] == 10.0


def test_manufacturing_invalid_yield_400(client):
    r = client.post(
        "/domains/manufacturing/process",
        json={
            "kind": "machining",
            "summary": "x",
            "line_id": "l",
            "operator_id": "o",
            "affected_part_numbers": ["p"],
            "acceptance_criteria": ["c"],
            "expected_yield_pct": 1.5,
        },
    )
    assert r.status_code == 400


# ---- healthcare ----


def test_healthcare_complete(client):
    r = client.post(
        "/domains/healthcare/process",
        json={
            "kind": "prescription",
            "summary": "start ACE inhibitor",
            "encounter_id": "enc-001",
            "primary_clinician": "dr-smith",
            "consulting_specialists": ["dr-cardio"],
            "patient_consented": True,
            "consent_kind": "written",
            "affected_records": ["mrn-12345"],
            "acceptance_criteria": ["clinical_indication_documented"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["domain"] == "healthcare"
    assert body["governance_status"] == "approved"
    assert body["metadata"]["consent_recorded"] is True


def test_healthcare_invalid_consent_kind_400(client):
    r = client.post(
        "/domains/healthcare/process",
        json={
            "kind": "diagnosis",
            "summary": "x",
            "encounter_id": "e",
            "primary_clinician": "c",
            "consent_kind": "psychic",
            "affected_records": ["r"],
            "acceptance_criteria": ["a"],
        },
    )
    assert r.status_code == 400


# ---- education ----


def test_education_complete(client):
    r = client.post(
        "/domains/education/process",
        json={
            "kind": "grading",
            "summary": "grade midterm",
            "course_id": "CS-101",
            "instructor": "prof-jones",
            "affected_learners": ["s1", "s2"],
            "learning_objectives": ["LO1"],
            "acceptance_criteria": ["rubric_applied"],
            "prerequisite_courses": ["CS-099"],
            "accessibility_requirements": ["extended_time"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["domain"] == "education"
    assert body["governance_status"] == "approved"
    assert "LO1" in body["metadata"]["learning_objectives"]


def test_education_certification_with_accreditor(client):
    r = client.post(
        "/domains/education/process",
        json={
            "kind": "certification",
            "summary": "issue cert",
            "course_id": "CS-Cert",
            "instructor": "prof-jones",
            "accreditation_body": "ABET",
            "affected_learners": ["s1"],
            "learning_objectives": ["LO1", "LO2"],
            "acceptance_criteria": ["passed_capstone"],
            "accessibility_requirements": ["captions"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "ABET" in str(body["metadata"]["required_signoffs"])


# ---- Cross-cutting ----


def test_all_six_domains_return_consistent_envelope_shape(client):
    """Every domain returns DomainOutcome with the same top-level fields.

    Surfaces shape mismatches if a domain's translate_from is changed in
    a way that doesn't fit the common envelope.
    """
    cases = [
        ("software-dev", {
            "kind": "feature", "summary": "x", "repository": "y",
            "affected_files": ["a.py"],
            "acceptance_criteria": ["test_passes"],
        }),
        ("business-process", {
            "kind": "approval", "summary": "x", "process_id": "p",
            "initiator": "i", "approval_chain": ["b"],
            "affected_systems": ["s"], "acceptance_criteria": ["c"],
        }),
        ("scientific-research", {
            "kind": "analysis", "summary": "x", "study_id": "s",
            "principal_investigator": "p", "peer_reviewers": ["r"],
            "affected_corpus": ["d"], "acceptance_criteria": ["c"],
        }),
        ("manufacturing", {
            "kind": "quality_inspection", "summary": "x", "line_id": "l",
            "operator_id": "o", "quality_engineer": "qe",
            "iso_certifications": ["9001"], "affected_part_numbers": ["pn"],
            "acceptance_criteria": ["c"],
        }),
        ("healthcare", {
            "kind": "assessment", "summary": "x", "encounter_id": "e",
            "primary_clinician": "c", "patient_consented": True,
            "consent_kind": "written", "affected_records": ["r"],
            "acceptance_criteria": ["c"],
        }),
        ("education", {
            "kind": "grading", "summary": "x", "course_id": "c",
            "instructor": "i", "affected_learners": ["s"],
            "learning_objectives": ["L"], "acceptance_criteria": ["c"],
            "accessibility_requirements": ["a"],
        }),
    ]
    expected_keys = {
        "domain", "governance_status", "audit_trail_id",
        "risk_flags", "plan", "metadata", "tenant_id",
        "run_id",  # v4.11.0 — null unless persist_run=true and merge succeeded
    }
    for path, payload in cases:
        r = client.post(f"/domains/{path}/process", json=payload)
        assert r.status_code == 200, f"{path} returned {r.status_code}: {r.text}"
        body = r.json()
        assert set(body.keys()) == expected_keys, f"{path} envelope mismatch"


def test_tenant_id_recorded_in_response(client):
    r = client.post(
        "/domains/software-dev/process",
        headers={"X-Tenant-ID": "acme-corp"},
        json={
            "kind": "bug_fix", "summary": "x", "repository": "r",
            "affected_files": ["a.py"], "acceptance_criteria": ["c"],
        },
    )
    assert r.status_code == 200
    assert r.json()["tenant_id"] == "acme-corp"
