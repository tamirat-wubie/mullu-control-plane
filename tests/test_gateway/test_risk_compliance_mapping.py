"""Gateway risk and compliance mapping tests.

Purpose: verify framework control mapping, evidence coverage, risk register
review, certification-claim boundaries, and public snapshot schema behavior.
Governance scope: control mappings, evidence refs, risk registers, external
publication review, and compliance report generation.
Dependencies: gateway.risk_compliance_mapping and its public JSON schema.
Invariants:
  - Missing required evidence creates a gap.
  - Open high-risk control entries require review.
  - Certification is never claimed by alignment reports.
  - Snapshot output is schema-valid and hash-bearing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from gateway.risk_compliance_mapping import (
    ComplianceEvidenceRecord,
    ComplianceFramework,
    ControlMapping,
    EvidenceKind,
    MappingDisposition,
    RiskComplianceMapper,
    RiskRegisterEntry,
    RiskSeverity,
    SymbolicSystemInventoryItem,
    risk_compliance_mapping_snapshot_to_json_dict,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "risk_compliance_mapping_snapshot.schema.json"
NOW = "2026-05-05T12:00:00Z"


def test_complete_evidence_maps_controls_without_certification_claim() -> None:
    mapper = _mapper()
    mapper.add_evidence(_evidence("ev-policy", EvidenceKind.POLICY_DECISION, "policy:decision-1"))
    mapper.add_evidence(_evidence("ev-approval", EvidenceKind.APPROVAL_RECORD, "approval:case-1"))
    report = mapper.generate_report(tenant_id="tenant-a", framework=ComplianceFramework.SOC2, generated_at=NOW)

    assert report.mapped_control_count == 1
    assert report.gap_control_count == 0
    assert report.review_control_count == 0
    assert report.evidence_coverage_percent == 100.0
    assert report.certification_claimed is False
    assert report.external_publication_review_required is True
    assert report.publication_allowed is False
    assert report.results[0].disposition is MappingDisposition.MAPPED


def test_missing_required_evidence_creates_gap_result() -> None:
    mapper = _mapper()
    mapper.add_evidence(_evidence("ev-policy", EvidenceKind.POLICY_DECISION, "policy:decision-1"))
    report = mapper.generate_report(tenant_id="tenant-a", framework=ComplianceFramework.SOC2, generated_at=NOW)
    result = report.results[0]

    assert report.mapped_control_count == 0
    assert report.gap_control_count == 1
    assert report.evidence_coverage_percent == 0.0
    assert result.disposition is MappingDisposition.GAP
    assert EvidenceKind.APPROVAL_RECORD in result.missing_evidence_kinds
    assert "approval:case-1" not in result.evidence_refs


def test_open_high_risk_on_control_requires_review_even_with_evidence() -> None:
    mapper = _mapper()
    mapper.add_evidence(_evidence("ev-policy", EvidenceKind.POLICY_DECISION, "policy:decision-1"))
    mapper.add_evidence(_evidence("ev-approval", EvidenceKind.APPROVAL_RECORD, "approval:case-1"))
    mapper.register_risk(
        RiskRegisterEntry(
            risk_id="risk-payment-approval",
            tenant_id="tenant-a",
            title="Approval workflow open risk",
            severity=RiskSeverity.HIGH,
            control_ids=("SOC2-CC6.1",),
            mitigation_refs=("case:risk-review-1",),
            owner="compliance",
            status="open",
        )
    )
    report = mapper.generate_report(tenant_id="tenant-a", framework=ComplianceFramework.SOC2, generated_at=NOW)
    snapshot = mapper.snapshot()

    assert report.mapped_control_count == 0
    assert report.review_control_count == 1
    assert report.high_or_critical_risk_count == 1
    assert report.results[0].disposition is MappingDisposition.REVIEW
    assert snapshot.open_gap_count == 1
    assert snapshot.high_or_critical_risk_count == 1


def test_failed_evidence_does_not_satisfy_control_mapping() -> None:
    mapper = _mapper()
    mapper.add_evidence(_evidence("ev-policy", EvidenceKind.POLICY_DECISION, "policy:decision-1", passed=False))
    mapper.add_evidence(_evidence("ev-approval", EvidenceKind.APPROVAL_RECORD, "approval:case-1"))
    report = mapper.generate_report(tenant_id="tenant-a", framework=ComplianceFramework.SOC2, generated_at=NOW)

    assert report.gap_control_count == 1
    assert EvidenceKind.POLICY_DECISION in report.results[0].missing_evidence_kinds
    assert "policy:decision-1" not in report.results[0].evidence_refs


def test_certification_claims_are_rejected() -> None:
    mapper = _mapper()
    report = mapper.generate_report(tenant_id="tenant-a", framework=ComplianceFramework.SOC2, generated_at=NOW)

    with pytest.raises(ValueError, match="certification_claim_must_be_false"):
        type(report)(**{**report.to_json_dict(), "certification_claimed": True, "framework": ComplianceFramework.SOC2, "results": report.results})


def test_risk_compliance_mapping_snapshot_schema_exposes_control_contract() -> None:
    mapper = _mapper()
    mapper.add_evidence(_evidence("ev-policy", EvidenceKind.POLICY_DECISION, "policy:decision-1"))
    mapper.add_evidence(_evidence("ev-approval", EvidenceKind.APPROVAL_RECORD, "approval:case-1"))
    mapper.generate_report(tenant_id="tenant-a", framework=ComplianceFramework.SOC2, generated_at=NOW)
    snapshot = mapper.snapshot()
    payload = risk_compliance_mapping_snapshot_to_json_dict(snapshot)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(payload)
    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:risk-compliance-mapping-snapshot:1"
    assert "SOC2" in schema["$defs"]["framework"]["enum"]
    assert payload["reports"][0]["certification_claimed"] is False
    assert payload["reports"][0]["publication_allowed"] is False
    assert snapshot.snapshot_hash


def _mapper() -> RiskComplianceMapper:
    mapper = RiskComplianceMapper()
    mapper.register_inventory_item(
        SymbolicSystemInventoryItem(
            item_id="system-governed-actions",
            item_type="capability",
            tenant_id="tenant-a",
            owner="platform",
            risk_tier=RiskSeverity.HIGH,
            evidence_refs=("capability:evidence-1",),
        )
    )
    mapper.register_mapping(
        ControlMapping(
            mapping_id="map-soc2-approval",
            framework=ComplianceFramework.SOC2,
            control_id="SOC2-CC6.1",
            control_area="logical_access_and_approval",
            mullu_evidence_surface="approval_and_policy",
            required_evidence_kinds=(EvidenceKind.POLICY_DECISION, EvidenceKind.APPROVAL_RECORD),
            owner="compliance",
        )
    )
    return mapper


def _evidence(
    evidence_id: str,
    kind: EvidenceKind,
    source_ref: str,
    *,
    passed: bool = True,
) -> ComplianceEvidenceRecord:
    return ComplianceEvidenceRecord(
        evidence_id=evidence_id,
        tenant_id="tenant-a",
        kind=kind,
        source_ref=source_ref,
        observed_at=NOW,
        passed=passed,
    )
