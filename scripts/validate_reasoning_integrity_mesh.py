#!/usr/bin/env python3
"""Validate the Reasoning Integrity Mesh governance pack.

Purpose: fail closed when the reasoning governance pack loses evidence-bound
completion checks, scope separation, high-confidence evidence requirements,
contradiction locality, recursive termination, or mechanism proof guards.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: docs/reasoning/MULLU_REASONING_INTEGRITY_MESH.md and the
governance/reasoning_*.yaml ledgers.
Invariants:
  - Validation is read-only and deterministic.
  - The pack does not authorize runtime behavior changes.
  - Unsupported completion claims fail closed without evidence.
  - Concept/spec/code/runtime scopes remain distinct.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "reasoning" / "MULLU_REASONING_INTEGRITY_MESH.md"
REGISTRY_PATH = REPO_ROOT / "governance" / "reasoning_method_registry.yaml"
GATE_PATH = REPO_ROOT / "governance" / "judgment_integrity_gate.yaml"
TAXONOMY_PATH = REPO_ROOT / "governance" / "weakness_taxonomy.yaml"
FORGE_PATH = REPO_ROOT / "governance" / "reasoning_edge_case_forge.yaml"

REQUIRED_DOC_SECTIONS: tuple[str, ...] = (
    "# Mullu Reasoning Integrity Mesh",
    "## 1. Decision",
    "## 2. Scope Boundary",
    "## 3. Method Registry Contract",
    "## 4. Judgment Integrity Gate",
    "## 5. Weakness Taxonomy",
    "## 6. Edge Case Forge",
    "## 7. Recursive Refinement Termination",
    "## 8. Acceptance Contract",
    "## 9. Proof-of-Resolution Stamp",
)

REQUIRED_ACCEPTANCE_ANCHORS: tuple[str, ...] = (
    "unsupported_completion_claim",
    "concept_spec_code_runtime_scope_separation",
    "high_confidence_requires_evidence_refs",
    "local_contradiction_cannot_be_global_truth",
    "recursive_refinement_stops_on_empty_delta",
    "metaphor_interface_language_cannot_override_mechanism",
)

REQUIRED_METHOD_IDS: tuple[str, ...] = (
    "scope_classifier",
    "evidence_bound_completion_check",
    "confidence_evidence_gate",
    "contradiction_scope_limiter",
    "recursive_delta_settlement",
    "metaphor_mechanism_guard",
)

REQUIRED_RULE_IDS: tuple[str, ...] = (
    "unsupported_completion_claim",
    "scope_confusion_claim",
    "high_confidence_without_evidence",
    "local_contradiction_globalized",
    "unbounded_recursive_refinement",
    "metaphor_over_mechanism",
)

REQUIRED_WEAKNESS_IDS: tuple[str, ...] = (
    "false_completion_claim",
    "scope_confusion",
    "confidence_overclaim",
    "contradiction_globalization",
    "recursive_nontermination",
    "metaphor_mechanism_override",
)

REQUIRED_CASE_IDS: tuple[str, ...] = (
    "concept_claims_runtime_completion",
    "spec_claims_code_implementation",
    "code_claims_live_runtime",
    "completion_claim_without_evidence",
    "high_confidence_without_evidence",
    "local_contradiction_claims_global_truth",
    "recursive_refinement_empty_delta_loop",
    "metaphor_replaces_mechanism",
    "evidence_bound_completion_claim",
)

REQUIRED_GOVERNANCE_LAWS: tuple[str, ...] = ("OCE", "RAG", "CDCV", "CQTE", "UWMA", "SRCA", "PRS")
FORBIDDEN_LITERAL_PARTS: tuple[str, str] = ("artificial", "intelligence")


class ReasoningIntegrityMeshError(ValueError):
    """Raised when a reasoning integrity pack artifact has invalid shape."""


def load_json_yaml_object(path: Path) -> dict[str, Any]:
    """Load a JSON-subset YAML object from disk."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReasoningIntegrityMeshError(
            f"{workspace_display_path(path)} must be a JSON-subset YAML object: {exc.msg}"
        ) from exc
    if not isinstance(payload, dict):
        raise ReasoningIntegrityMeshError(f"{workspace_display_path(path)} must contain an object")
    return payload


def validate_reasoning_doc_text(content: str) -> list[str]:
    """Validate required doctrine anchors with bounded errors."""

    errors: list[str] = []
    for section in REQUIRED_DOC_SECTIONS:
        if section not in content:
            errors.append(f"missing document section: {section}")
    for anchor in REQUIRED_ACCEPTANCE_ANCHORS:
        if anchor not in content:
            errors.append(f"missing acceptance anchor: {anchor}")
    forbidden_literal = " ".join(FORBIDDEN_LITERAL_PARTS)
    if forbidden_literal in content.lower():
        errors.append(f"forbidden literal present: {forbidden_literal}")
    if "STATUS:\n  Completeness: 100%" not in content:
        errors.append("document missing complete status block")
    if "Open issues: none" not in content:
        errors.append("document status block must close open issues")
    return errors


def validate_registry_payload(payload: dict[str, Any]) -> list[str]:
    """Validate the reasoning method registry payload."""

    errors: list[str] = []
    _require_common_header(payload, "reasoning.method_registry.v1", "registry", errors)
    if payload.get("runtime_behavior_change_allowed") is not False:
        errors.append("registry runtime_behavior_change_allowed must be false")
    methods = _require_list(payload, "methods", errors)
    method_ids = _ids_from_sequence(methods, "method_id")
    for method_id in REQUIRED_METHOD_IDS:
        if method_id not in method_ids:
            errors.append(f"registry missing method: {method_id}")
    for method in methods:
        if not isinstance(method, dict):
            errors.append("registry methods entries must be objects")
            continue
        _require_non_empty_list(method, "required_inputs", f"method {method.get('method_id')}", errors)
        _require_non_empty_list(method, "required_evidence_refs", f"method {method.get('method_id')}", errors)
        _require_non_empty_list(method, "output_contract", f"method {method.get('method_id')}", errors)
        _require_non_empty_list(method, "blocked_claims", f"method {method.get('method_id')}", errors)
        _require_non_empty_list(method, "governance_laws", f"method {method.get('method_id')}", errors)
        if not isinstance(method.get("failure_mode"), str) or not method["failure_mode"].startswith("Fail("):
            errors.append(f"method {method.get('method_id')} failure_mode must be Fail(...)")
    return errors


def validate_gate_payload(payload: dict[str, Any]) -> list[str]:
    """Validate the judgment integrity gate payload."""

    errors: list[str] = []
    _require_common_header(payload, "reasoning.judgment_integrity_gate.v1", "gate", errors)
    if payload.get("default_outcome") != "AwaitingEvidence":
        errors.append("gate default_outcome must be AwaitingEvidence")
    if payload.get("runtime_behavior_change_allowed") is not False:
        errors.append("gate runtime_behavior_change_allowed must be false")
    if payload.get("scope_boundaries") != ["concept", "spec", "code", "runtime"]:
        errors.append("gate scope_boundaries must be concept/spec/code/runtime")

    confidence = payload.get("confidence")
    if not isinstance(confidence, dict):
        errors.append("gate confidence must be an object")
    else:
        if confidence.get("high_confidence_floor") != 0.85:
            errors.append("gate confidence.high_confidence_floor must be 0.85")
        if confidence.get("high_confidence_requires_evidence_refs") is not True:
            errors.append("gate confidence.high_confidence_requires_evidence_refs must be true")

    completion = payload.get("completion_claim_policy")
    if not isinstance(completion, dict):
        errors.append("gate completion_claim_policy must be an object")
    else:
        for field_name in (
            "completion_claims_require_evidence_refs",
            "completion_claims_require_validator_refs",
            "implementation_claims_require_code_refs",
            "runtime_claims_require_runtime_witness_refs",
        ):
            if completion.get(field_name) is not True:
                errors.append(f"gate completion_claim_policy.{field_name} must be true")

    contradiction = payload.get("contradiction_policy")
    if not isinstance(contradiction, dict):
        errors.append("gate contradiction_policy must be an object")
    elif contradiction.get("local_contradiction_cannot_be_global_truth") is not True:
        errors.append("gate contradiction_policy.local_contradiction_cannot_be_global_truth must be true")

    recursion = payload.get("recursive_refinement_policy")
    if not isinstance(recursion, dict):
        errors.append("gate recursive_refinement_policy must be an object")
    elif recursion.get("stop_when_both_delta_sets_empty") is not True:
        errors.append("gate recursive_refinement_policy.stop_when_both_delta_sets_empty must be true")

    metaphor = payload.get("metaphor_policy")
    if not isinstance(metaphor, dict):
        errors.append("gate metaphor_policy must be an object")
    elif metaphor.get("metaphor_interface_language_cannot_override_mechanism") is not True:
        errors.append("gate metaphor_policy.metaphor_interface_language_cannot_override_mechanism must be true")

    rules = _require_list(payload, "fail_closed_rules", errors)
    rule_ids = _ids_from_sequence(rules, "rule_id")
    for rule_id in REQUIRED_RULE_IDS:
        if rule_id not in rule_ids:
            errors.append(f"gate fail_closed_rules missing rule: {rule_id}")
    for rule in rules:
        if not isinstance(rule, dict):
            errors.append("gate fail_closed_rules entries must be objects")
            continue
        if rule.get("blocked") is not True:
            errors.append(f"gate rule {rule.get('rule_id')} blocked must be true")
        _require_non_empty_list(rule, "requires", f"gate rule {rule.get('rule_id')}", errors)
        if not isinstance(rule.get("reject_reason"), str) or not rule["reject_reason"]:
            errors.append(f"gate rule {rule.get('rule_id')} reject_reason must be non-empty")
    return errors


def validate_taxonomy_payload(payload: dict[str, Any]) -> list[str]:
    """Validate the weakness taxonomy payload."""

    errors: list[str] = []
    _require_common_header(payload, "reasoning.weakness_taxonomy.v1", "taxonomy", errors)
    if payload.get("runtime_behavior_change_allowed") is not False:
        errors.append("taxonomy runtime_behavior_change_allowed must be false")
    weaknesses = _require_list(payload, "weaknesses", errors)
    weakness_ids = _ids_from_sequence(weaknesses, "weakness_id")
    for weakness_id in REQUIRED_WEAKNESS_IDS:
        if weakness_id not in weakness_ids:
            errors.append(f"taxonomy missing weakness: {weakness_id}")
    for weakness in weaknesses:
        if not isinstance(weakness, dict):
            errors.append("taxonomy weaknesses entries must be objects")
            continue
        if weakness.get("severity") != "hard":
            errors.append(f"weakness {weakness.get('weakness_id')} severity must be hard")
        _require_non_empty_list(weakness, "detects", f"weakness {weakness.get('weakness_id')}", errors)
        for field_name in ("repair", "proof_obligation", "fail_closed_rule"):
            if not isinstance(weakness.get(field_name), str) or not weakness[field_name]:
                errors.append(f"weakness {weakness.get('weakness_id')} {field_name} must be non-empty")
    return errors


def validate_forge_payload(payload: dict[str, Any], gate_payload: dict[str, Any] | None = None) -> list[str]:
    """Validate the edge-case forge payload."""

    errors: list[str] = []
    _require_common_header(payload, "reasoning.edge_case_forge.v1", "forge", errors)
    if payload.get("runtime_behavior_change_allowed") is not False:
        errors.append("forge runtime_behavior_change_allowed must be false")
    cases = _require_list(payload, "cases", errors)
    case_ids = _ids_from_sequence(cases, "case_id")
    for case_id in REQUIRED_CASE_IDS:
        if case_id not in case_ids:
            errors.append(f"edge forge missing case: {case_id}")

    gate_rule_ids = set(REQUIRED_RULE_IDS)
    if gate_payload is not None:
        gate_rules = gate_payload.get("fail_closed_rules")
        if isinstance(gate_rules, list):
            gate_rule_ids = set(_ids_from_sequence(gate_rules, "rule_id"))

    pass_cases = 0
    for case in cases:
        if not isinstance(case, dict):
            errors.append("edge forge cases entries must be objects")
            continue
        for field_name in ("case_id", "input_scope", "claim", "expected_outcome", "expected_rule_id"):
            if not isinstance(case.get(field_name), str) or not case[field_name]:
                errors.append(f"edge case {case.get('case_id')} {field_name} must be non-empty")
        expected_outcome = case.get("expected_outcome")
        expected_rule_id = case.get("expected_rule_id")
        if expected_outcome == "Pass":
            pass_cases += 1
            _require_non_empty_list(case, "evidence_refs", f"edge case {case.get('case_id')}", errors)
            _require_non_empty_list(case, "validator_refs", f"edge case {case.get('case_id')}", errors)
        elif isinstance(expected_rule_id, str) and expected_rule_id not in gate_rule_ids:
            errors.append(f"edge case {case.get('case_id')} references unknown gate rule: {expected_rule_id}")
    if pass_cases != 1:
        errors.append("edge forge must contain exactly one positive Pass case")
    return errors


def validate_reasoning_integrity_mesh(
    doc_path: Path = DOC_PATH,
    registry_path: Path = REGISTRY_PATH,
    gate_path: Path = GATE_PATH,
    taxonomy_path: Path = TAXONOMY_PATH,
    forge_path: Path = FORGE_PATH,
) -> list[str]:
    """Validate every artifact in the reasoning integrity pack."""

    errors: list[str] = []
    if not doc_path.exists():
        errors.append(f"missing document: {workspace_display_path(doc_path)}")
    else:
        errors.extend(validate_reasoning_doc_text(doc_path.read_text(encoding="utf-8")))

    try:
        registry = load_json_yaml_object(registry_path)
        gate = load_json_yaml_object(gate_path)
        taxonomy = load_json_yaml_object(taxonomy_path)
        forge = load_json_yaml_object(forge_path)
    except (FileNotFoundError, ReasoningIntegrityMeshError) as exc:
        return errors + [str(exc)]

    errors.extend(validate_registry_payload(registry))
    errors.extend(validate_gate_payload(gate))
    errors.extend(validate_taxonomy_payload(taxonomy))
    errors.extend(validate_forge_payload(forge, gate))
    return errors


def validation_report() -> dict[str, Any]:
    """Return a deterministic validation report for PRS evidence."""

    errors = validate_reasoning_integrity_mesh()
    return {
        "receipt_id": "reasoning_integrity_mesh_validation",
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "artifacts": [
            workspace_display_path(DOC_PATH),
            workspace_display_path(REGISTRY_PATH),
            workspace_display_path(GATE_PATH),
            workspace_display_path(TAXONOMY_PATH),
            workspace_display_path(FORGE_PATH),
        ],
        "required_methods": list(REQUIRED_METHOD_IDS),
        "required_rules": list(REQUIRED_RULE_IDS),
        "required_weaknesses": list(REQUIRED_WEAKNESS_IDS),
        "required_cases": list(REQUIRED_CASE_IDS),
    }


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else REPO_ROOT / path
    try:
        return resolved_path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _require_common_header(payload: dict[str, Any], schema_version: str, label: str, errors: list[str]) -> None:
    if payload.get("schema_version") != schema_version:
        errors.append(f"{label} schema_version must be {schema_version}")
    if payload.get("foundation_mode_required") is not True:
        errors.append(f"{label} foundation_mode_required must be true")
    scope = payload.get("governance_scope")
    if scope != list(REQUIRED_GOVERNANCE_LAWS):
        errors.append(f"{label} governance_scope must list all governance laws in canonical order")
    _require_non_empty_list(payload, "dependencies", label, errors)
    _require_non_empty_list(payload, "invariants", label, errors)


def _require_list(payload: dict[str, Any], field_name: str, errors: list[str]) -> list[Any]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        errors.append(f"{field_name} must be a list")
        return []
    return value


def _require_non_empty_list(payload: dict[str, Any], field_name: str, label: str, errors: list[str]) -> None:
    value = payload.get(field_name)
    if not isinstance(value, list) or not value:
        errors.append(f"{label} {field_name} must be a non-empty list")


def _ids_from_sequence(records: list[Any], id_field: str) -> set[str]:
    ids: set[str] = set()
    for record in records:
        if isinstance(record, dict) and isinstance(record.get(id_field), str):
            ids.add(record[id_field])
    return ids


def main() -> int:
    """Validate Reasoning Integrity Mesh artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate the Reasoning Integrity Mesh governance pack.")
    parser.add_argument("--json", action="store_true", help="Print a JSON validation report.")
    args = parser.parse_args()

    report = validation_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["errors"]:
        for error in report["errors"]:
            print(f"[FAIL] {error}")
    else:
        print("[PASS] reasoning_integrity_mesh")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
