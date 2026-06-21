"""Tests for the Reasoning Integrity Mesh governance pack.

Purpose: prove the pack rejects unsupported completion claims, scope
confusion, confidence overclaims, local contradiction globalization,
unbounded refinement, and metaphor-over-mechanism drift.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_reasoning_integrity_mesh and governance
reasoning pack ledgers.
Invariants:
  - The default pack validates.
  - Hard gate drift is reported with deterministic error messages.
  - The edge-case forge contains both negative and positive evidence cases.
"""

from __future__ import annotations

from copy import deepcopy

from scripts.validate_reasoning_integrity_mesh import (
    DOC_PATH,
    FORGE_PATH,
    GATE_PATH,
    REGISTRY_PATH,
    REQUIRED_CASE_IDS,
    REQUIRED_METHOD_IDS,
    REQUIRED_RULE_IDS,
    REQUIRED_WEAKNESS_IDS,
    TAXONOMY_PATH,
    load_json_yaml_object,
    validate_forge_payload,
    validate_gate_payload,
    validate_reasoning_doc_text,
    validate_reasoning_integrity_mesh,
    validate_registry_payload,
    validate_taxonomy_payload,
    validation_report,
)


def test_reasoning_integrity_mesh_default_pack_validates() -> None:
    errors = validate_reasoning_integrity_mesh()
    report = validation_report()

    assert errors == []
    assert report["status"] == "passed"
    assert report["errors"] == []
    assert "docs/reasoning/MULLU_REASONING_INTEGRITY_MESH.md" in report["artifacts"]


def test_reasoning_integrity_document_reports_missing_acceptance_anchor() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    broken = content.replace("high_confidence_requires_evidence_refs", "high_confidence_removed")

    errors = validate_reasoning_doc_text(broken)

    assert len(errors) == 1
    assert errors[0] == "missing acceptance anchor: high_confidence_requires_evidence_refs"
    assert "high_confidence_removed" not in errors[0]


def test_registry_reports_missing_method_and_incomplete_contract() -> None:
    registry = load_json_yaml_object(REGISTRY_PATH)
    broken = deepcopy(registry)
    broken["methods"] = broken["methods"][1:]
    broken["methods"][0]["required_evidence_refs"] = []

    errors = validate_registry_payload(broken)

    assert "registry missing method: scope_classifier" in errors
    assert "method evidence_bound_completion_check required_evidence_refs must be a non-empty list" in errors
    assert len(REQUIRED_METHOD_IDS) == 6


def test_gate_rejects_high_confidence_and_completion_policy_drift() -> None:
    gate = load_json_yaml_object(GATE_PATH)
    broken = deepcopy(gate)
    broken["confidence"]["high_confidence_requires_evidence_refs"] = False
    broken["completion_claim_policy"]["completion_claims_require_evidence_refs"] = False
    broken["fail_closed_rules"][0]["blocked"] = False

    errors = validate_gate_payload(broken)

    assert "gate confidence.high_confidence_requires_evidence_refs must be true" in errors
    assert "gate completion_claim_policy.completion_claims_require_evidence_refs must be true" in errors
    assert "gate rule unsupported_completion_claim blocked must be true" in errors


def test_taxonomy_requires_hard_weakness_detection_and_repair() -> None:
    taxonomy = load_json_yaml_object(TAXONOMY_PATH)
    broken = deepcopy(taxonomy)
    broken["weaknesses"][0]["severity"] = "soft"
    broken["weaknesses"][1]["detects"] = []
    broken["weaknesses"][2]["repair"] = ""

    errors = validate_taxonomy_payload(broken)

    assert "weakness false_completion_claim severity must be hard" in errors
    assert "weakness scope_confusion detects must be a non-empty list" in errors
    assert "weakness confidence_overclaim repair must be non-empty" in errors


def test_edge_case_forge_requires_gate_rule_alignment_and_positive_case() -> None:
    gate = load_json_yaml_object(GATE_PATH)
    forge = load_json_yaml_object(FORGE_PATH)
    broken = deepcopy(forge)
    broken["cases"][0]["expected_rule_id"] = "unknown_rule"
    broken["cases"] = [case for case in broken["cases"] if case["case_id"] != "evidence_bound_completion_claim"]

    errors = validate_forge_payload(broken, gate)

    assert "edge forge missing case: evidence_bound_completion_claim" in errors
    assert "edge case concept_claims_runtime_completion references unknown gate rule: unknown_rule" in errors
    assert "edge forge must contain exactly one positive Pass case" in errors


def test_default_artifacts_expose_required_ids() -> None:
    registry = load_json_yaml_object(REGISTRY_PATH)
    gate = load_json_yaml_object(GATE_PATH)
    taxonomy = load_json_yaml_object(TAXONOMY_PATH)
    forge = load_json_yaml_object(FORGE_PATH)

    assert {method["method_id"] for method in registry["methods"]} == set(REQUIRED_METHOD_IDS)
    assert {rule["rule_id"] for rule in gate["fail_closed_rules"]} == set(REQUIRED_RULE_IDS)
    assert {weakness["weakness_id"] for weakness in taxonomy["weaknesses"]} == set(REQUIRED_WEAKNESS_IDS)
    assert {case["case_id"] for case in forge["cases"]} == set(REQUIRED_CASE_IDS)
