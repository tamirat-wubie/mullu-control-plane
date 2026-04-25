"""Purpose: verify HTTP access to the data governance runtime.
Governance scope: endpoint wiring for classification, residency, privacy,
    redaction, retention, evaluation, and summary read models.
Dependencies: FastAPI server, data governance engine, proof bridge.
Invariants:
  - Data governance dependency is registered at server bootstrap.
  - Endpoint responses expose bounded enum values and proof receipts.
  - Denied evaluations become tenant-visible violations.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    from mcoi_runtime.app.server import app

    return TestClient(app)


class TestDataGovernanceEndpoints:
    def test_summary_endpoint_exposes_runtime_posture(self, client):
        resp = client.get("/api/v1/data-governance/summary")

        assert resp.status_code == 200
        assert resp.json()["governed"] is True
        assert "state_hash" in resp.json()["summary"]
        assert resp.json()["tenant"] is None

    def test_classify_and_register_controls(self, client):
        tenant_id = "dg-http-controls"

        record_resp = client.post("/api/v1/data-governance/classify", json={
            "data_id": "dg-http-record-controls",
            "tenant_id": tenant_id,
            "classification": "pii",
            "residency": "us",
            "privacy_basis": "consent",
            "domain": "pilot",
            "source_id": "case-1",
        })
        policy_resp = client.post("/api/v1/data-governance/policies", json={
            "policy_id": "dg-http-policy-controls",
            "tenant_id": tenant_id,
            "classification": "pii",
            "disposition": "redact",
            "residency": "us",
        })
        residency_resp = client.post("/api/v1/data-governance/residency-constraints", json={
            "constraint_id": "dg-http-residency-controls",
            "tenant_id": tenant_id,
            "allowed_regions": ["us"],
            "denied_regions": ["eu"],
        })

        assert record_resp.status_code == 200
        assert record_resp.json()["record"]["classification"] == "pii"
        assert policy_resp.status_code == 200
        assert policy_resp.json()["policy"]["disposition"] == "redact"
        assert residency_resp.status_code == 200
        assert residency_resp.json()["constraint"]["allowed_regions"] == ["us"]

    def test_rule_registration_and_redacted_evaluation(self, client):
        tenant_id = "dg-http-redaction"

        client.post("/api/v1/data-governance/classify", json={
            "data_id": "dg-http-record-redact",
            "tenant_id": tenant_id,
            "classification": "sensitive",
            "residency": "us",
            "privacy_basis": "legitimate_interest",
        })
        client.post("/api/v1/data-governance/redaction-rules", json={
            "rule_id": "dg-http-redaction-rule",
            "tenant_id": tenant_id,
            "classification": "sensitive",
            "redaction_level": "hash",
            "field_patterns": ["email", "account"],
        })
        retention_resp = client.post("/api/v1/data-governance/retention-rules", json={
            "rule_id": "dg-http-retention-rule",
            "tenant_id": tenant_id,
            "classification": "sensitive",
            "retention_days": 30,
            "disposition": "review",
        })
        eval_resp = client.post("/api/v1/data-governance/evaluate", json={
            "data_id": "dg-http-record-redact",
            "operation": "external_response",
            "target_region": "us",
        })

        assert retention_resp.status_code == 200
        assert retention_resp.json()["rule"]["retention_days"] == 30
        assert eval_resp.status_code == 200
        assert eval_resp.json()["decision"]["decision"] == "redacted"
        assert eval_resp.json()["decision"]["redaction_level"] == "hash"

    def test_residency_denial_is_visible_in_tenant_summary(self, client):
        tenant_id = "dg-http-denial"

        client.post("/api/v1/data-governance/classify", json={
            "data_id": "dg-http-record-denial",
            "tenant_id": tenant_id,
            "classification": "confidential",
            "residency": "us",
            "privacy_basis": "legitimate_interest",
        })
        client.post("/api/v1/data-governance/residency-constraints", json={
            "constraint_id": "dg-http-residency-denial",
            "tenant_id": tenant_id,
            "allowed_regions": ["us"],
            "denied_regions": ["eu"],
        })
        eval_resp = client.post("/api/v1/data-governance/evaluate", json={
            "data_id": "dg-http-record-denial",
            "operation": "connector_transfer",
            "target_region": "eu",
        })
        summary_resp = client.get(
            "/api/v1/data-governance/summary",
            params={"tenant_id": tenant_id},
        )

        assert eval_resp.status_code == 200
        assert eval_resp.json()["decision"]["decision"] == "denied"
        assert "residency constraint" in eval_resp.json()["decision"]["reason"]
        assert summary_resp.status_code == 200
        assert summary_resp.json()["tenant"]["violation_count"] == 1
        assert summary_resp.json()["tenant"]["records"][0]["data_id"] == "dg-http-record-denial"

