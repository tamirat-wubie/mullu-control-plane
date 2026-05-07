"""Claim verification graph tests.

Purpose: verify sourced claims are classified, freshness-checked,
contradiction-checked, and evidence-bound before planning or execution use.
Governance scope: claim provenance, source evidence, support graph,
contradiction graph, freshness windows, high-risk review, and schema anchoring.
Dependencies: gateway.claim_verification and claim verification schema.
Invariants:
  - Claims require evidence-backed sources.
  - Contradicted and stale claims cannot execute.
  - High-risk claims require independent support.
  - Reports are hash-bound public contracts.
"""

from __future__ import annotations

from pathlib import Path

from gateway.claim_verification import (
    ClaimKind,
    ClaimNode,
    ClaimRisk,
    ClaimSource,
    ClaimVerificationEngine,
    ClaimVerificationStatus,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "claim_verification_report.schema.json"


def test_observed_fact_with_source_evidence_verifies_for_execution() -> None:
    report = ClaimVerificationEngine().verify(
        _claim(),
        checked_at="2026-05-06T12:00:00Z",
    )
    assert report.status == ClaimVerificationStatus.VERIFIED
    assert report.allowed_for_planning is True
    assert report.allowed_for_execution is True
    assert report.evidence_refs == ("proof://source-a",)


def test_user_claim_without_support_is_not_execution_eligible() -> None:
    report = ClaimVerificationEngine().verify(
        _claim(claim_kind=ClaimKind.USER_CLAIM, supported_by=()),
        checked_at="2026-05-06T12:00:00Z",
    )
    assert report.status == ClaimVerificationStatus.UNSUPPORTED
    assert report.allowed_for_planning is True
    assert report.allowed_for_execution is False
    assert "supporting_claim_or_source_required" in report.missing_requirements


def test_contradicted_claim_blocks_planning_and_execution() -> None:
    report = ClaimVerificationEngine().verify(
        _claim(contradicted_by=("claim-b",)),
        checked_at="2026-05-06T12:00:00Z",
    )
    assert report.status == ClaimVerificationStatus.CONTRADICTED
    assert report.allowed_for_planning is False
    assert report.allowed_for_execution is False
    assert "claim-b" in report.contradicted_by


def test_stale_claim_blocks_execution() -> None:
    report = ClaimVerificationEngine().verify(
        _claim(observed_at="2026-03-01T12:00:00Z", freshness_window_days=10),
        checked_at="2026-05-06T12:00:00Z",
    )
    assert report.status == ClaimVerificationStatus.STALE
    assert report.allowed_for_planning is False
    assert report.allowed_for_execution is False
    assert report.metadata["stale_claims_block_execution"] is True


def test_high_risk_claim_requires_independent_support_sources() -> None:
    report = ClaimVerificationEngine().verify(
        _claim(domain_risk=ClaimRisk.HIGH, supported_by=("claim-a",)),
        checked_at="2026-05-06T12:00:00Z",
    )
    assert report.status == ClaimVerificationStatus.REQUIRES_REVIEW
    assert report.allowed_for_execution is False
    assert "independent_support_sources_required" in report.missing_requirements
    assert report.metadata["high_risk_requires_independent_support"] is True


def test_high_risk_claim_with_two_sources_verifies() -> None:
    report = ClaimVerificationEngine().verify(
        _claim(
            domain_risk=ClaimRisk.HIGH,
            supported_by=("claim-a", "claim-b"),
            sources=(
                _source("source-a", "proof://source-a"),
                _source("source-b", "proof://source-b"),
            ),
        ),
        checked_at="2026-05-06T12:00:00Z",
    )
    assert report.status == ClaimVerificationStatus.VERIFIED
    assert report.allowed_for_execution is True
    assert report.evidence_refs == ("proof://source-a", "proof://source-b")
    assert report.report_hash


def test_claim_verification_report_schema_validates() -> None:
    report = ClaimVerificationEngine().verify(
        _claim(),
        checked_at="2026-05-06T12:00:00Z",
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), report.to_json_dict())
    assert errors == []
    assert report.to_json_dict()["metadata"]["claim_type_declared"] is True
    assert report.to_json_dict()["status"] == "verified"
    assert report.report_id.startswith("claim-verification-")


def _claim(**overrides: object) -> ClaimNode:
    payload = {
        "claim_id": "claim-vendor-bank-verified",
        "tenant_id": "tenant-a",
        "claim_text": "Vendor A bank account was verified by finance operations.",
        "claim_kind": ClaimKind.OBSERVED_FACT,
        "domain_risk": ClaimRisk.LOW,
        "confidence": 0.94,
        "observed_at": "2026-05-06T10:00:00Z",
        "freshness_window_days": 30,
        "sources": (_source("source-a", "proof://source-a"),),
        "supported_by": ("source-a",),
    }
    payload.update(overrides)
    return ClaimNode(**payload)


def _source(source_id: str, evidence_ref: str) -> ClaimSource:
    return ClaimSource(
        source_id=source_id,
        source_type="operator_receipt",
        observed_at="2026-05-06T10:00:00Z",
        evidence_refs=(evidence_ref,),
        uri="proof://claim-source",
    )
