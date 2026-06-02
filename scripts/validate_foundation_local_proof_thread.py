#!/usr/bin/env python3
"""Validate the Foundation Mode local proof-thread descriptor.

Purpose: keep the first local proof thread small, local-only, approval-gated,
receipt-bound, and rollback-aware.
Governance scope: Foundation Mode workflow composition, local evidence,
approval boundary, rollback note, and no external-effect claims.
Dependencies: docs/FOUNDATION_LOCAL_PROOF_THREAD.md,
examples/foundation_local_proof_thread.workflow.json, and
schemas/workflow.schema.json.
Invariants:
  - The proof thread is descriptor-only and read-only during validation.
  - The workflow graph is acyclic and all bindings resolve.
  - Local approval precedes harmless local result creation.
  - Rollback/recovery is named before closure.
  - No public endpoint, deployment, payment, customer-access, or live credential
    dependency is introduced by the descriptor.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_LOCAL_PROOF_THREAD.md"
DEFAULT_DESCRIPTOR_PATH = REPO_ROOT / "examples" / "foundation_local_proof_thread.workflow.json"
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "workflow.schema.json"
DEFAULT_RUNNER_PATH = REPO_ROOT / "scripts" / "run_foundation_local_proof_thread.py"

EXPECTED_WORKFLOW_ID = "foundation_local_proof_thread.v1"
EXPECTED_STAGES: tuple[tuple[str, str, tuple[str, ...], str | None], ...] = (
    ("stage_intake", "observation", (), None),
    ("stage_classify_intent", "skill_execution", ("stage_intake",), "foundation.intent_classification.local.v1"),
    (
        "stage_policy_authority_check",
        "skill_execution",
        ("stage_classify_intent",),
        "foundation.policy_authority_check.local.v1",
    ),
    ("stage_local_approval", "approval_gate", ("stage_policy_authority_check",), None),
    (
        "stage_create_local_result",
        "skill_execution",
        ("stage_local_approval",),
        "foundation.local_document_receipt.v1",
    ),
    ("stage_verify_local_result", "observation", ("stage_create_local_result",), None),
    (
        "stage_record_rollback_note",
        "skill_execution",
        ("stage_verify_local_result",),
        "foundation.rollback_recovery_note.local.v1",
    ),
    ("stage_close_receipt", "observation", ("stage_record_rollback_note",), None),
)
REQUIRED_DOC_PHRASES = (
    "Foundation Local Proof Thread",
    "Descriptor: [`../examples/foundation_local_proof_thread.workflow.json`]",
    "python scripts/run_foundation_local_proof_thread.py",
    ".change_assurance/foundation_local_proof_thread_receipt.json",
    "approval_gate",
    "Rollback note reference",
    "Rule: No customer access or deployment claim.",
    "The default receipt is local evidence only",
)
REQUIRED_RUNNER_PHRASES = (
    "No network, deployment, DNS, payment, customer-access, or credential action.",
    "DEFAULT_RECEIPT_OUTPUT",
    "foundation_local_proof_thread_receipt",
    "external_effects",
    "safe_to_delete",
)
FORBIDDEN_DESCRIPTOR_TERMS = (
    "http://",
    "https://",
    "api.mullusi.com",
    "dashboard.mullusi.com",
    "sandbox.mullusi.com",
    "stripe",
    "paypal",
    "live credential",
    "production-ready",
    "customer access is open",
    "request pilot access",
)


@dataclass(frozen=True, slots=True)
class FoundationProofFinding:
    """One deterministic local proof-thread validation finding."""

    rule_id: str
    message: str


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load a JSON object with explicit path and type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def load_text(path: Path, label: str) -> str:
    """Load text with explicit path errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def validate_doc_text(text: str) -> list[FoundationProofFinding]:
    """Return findings for missing proof-thread documentation anchors."""

    findings: list[FoundationProofFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                FoundationProofFinding(
                    "foundation_local_proof_doc_phrase_missing",
                    f"local proof-thread doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_runner_text(text: str) -> list[FoundationProofFinding]:
    """Return findings for missing local proof-thread runner anchors."""

    findings: list[FoundationProofFinding] = []
    for phrase in REQUIRED_RUNNER_PHRASES:
        if phrase not in text:
            findings.append(
                FoundationProofFinding(
                    "foundation_local_proof_runner_phrase_missing",
                    f"local proof-thread runner missing required phrase: {phrase}",
                )
            )
    return findings


def validate_schema_anchor(schema: dict[str, Any]) -> list[FoundationProofFinding]:
    """Return findings when the local workflow schema is not the expected surface."""

    findings: list[FoundationProofFinding] = []
    if schema.get("title") != "Workflow":
        findings.append(FoundationProofFinding("workflow_schema_title_invalid", "workflow schema title must be Workflow"))
    stage_type_enum = (
        schema.get("properties", {})
        .get("stages", {})
        .get("items", {})
        .get("properties", {})
        .get("stage_type", {})
        .get("enum")
    )
    for required_stage_type in ("skill_execution", "approval_gate", "observation"):
        if not isinstance(stage_type_enum, list) or required_stage_type not in stage_type_enum:
            findings.append(
                FoundationProofFinding(
                    "workflow_schema_stage_type_missing",
                    f"workflow schema missing stage type: {required_stage_type}",
                )
            )
    return findings


def validate_descriptor(descriptor: dict[str, Any]) -> list[FoundationProofFinding]:
    """Return findings for local proof-thread descriptor violations."""

    findings: list[FoundationProofFinding] = []
    findings.extend(validate_descriptor_root(descriptor))
    findings.extend(validate_descriptor_forbidden_terms(descriptor))
    stages = descriptor.get("stages")
    bindings = descriptor.get("bindings")
    if not isinstance(stages, list) or not all(isinstance(stage, dict) for stage in stages):
        findings.append(FoundationProofFinding("workflow_stages_invalid", "descriptor stages must be objects"))
        return findings
    if not isinstance(bindings, list) or not all(isinstance(binding, dict) for binding in bindings):
        findings.append(FoundationProofFinding("workflow_bindings_invalid", "descriptor bindings must be objects"))
        return findings

    findings.extend(validate_stage_contract(stages))
    findings.extend(validate_bindings(stages, bindings))
    findings.extend(validate_acyclic_graph(stages))
    return findings


def validate_descriptor_root(descriptor: dict[str, Any]) -> list[FoundationProofFinding]:
    """Return findings for descriptor root contract violations."""

    findings: list[FoundationProofFinding] = []
    if descriptor.get("workflow_id") != EXPECTED_WORKFLOW_ID:
        findings.append(
            FoundationProofFinding(
                "workflow_id_invalid",
                f"workflow_id must be {EXPECTED_WORKFLOW_ID}",
            )
        )
    if descriptor.get("name") != "Foundation Local Proof Thread":
        findings.append(FoundationProofFinding("workflow_name_invalid", "workflow name must identify the proof thread"))
    created_at = descriptor.get("created_at")
    if not isinstance(created_at, str):
        findings.append(FoundationProofFinding("workflow_created_at_invalid", "created_at must be a string"))
    else:
        try:
            datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            findings.append(FoundationProofFinding("workflow_created_at_invalid", "created_at must be ISO date-time"))
    return findings


def validate_descriptor_forbidden_terms(descriptor: dict[str, Any]) -> list[FoundationProofFinding]:
    """Return findings if the descriptor introduces blocked external-effect terms."""

    serialized_descriptor = json.dumps(descriptor, sort_keys=True).casefold()
    findings: list[FoundationProofFinding] = []
    for term in FORBIDDEN_DESCRIPTOR_TERMS:
        if term.casefold() in serialized_descriptor:
            findings.append(
                FoundationProofFinding(
                    "workflow_forbidden_external_term",
                    f"descriptor contains blocked external-effect term: {term}",
                )
            )
    return findings


def validate_stage_contract(stages: list[dict[str, Any]]) -> list[FoundationProofFinding]:
    """Return findings for stage topology and contract mismatches."""

    findings: list[FoundationProofFinding] = []
    observed_stage_ids = [stage.get("stage_id") for stage in stages]
    if len(set(observed_stage_ids)) != len(observed_stage_ids):
        findings.append(FoundationProofFinding("workflow_stage_duplicate", "stage ids must be unique"))
    expected_stage_ids = [stage_id for stage_id, _, _, _ in EXPECTED_STAGES]
    if observed_stage_ids != expected_stage_ids:
        findings.append(
            FoundationProofFinding(
                "workflow_stage_order_invalid",
                f"stage order must be: {', '.join(expected_stage_ids)}",
            )
        )

    stage_by_id = {stage.get("stage_id"): stage for stage in stages if isinstance(stage.get("stage_id"), str)}
    for stage_id, stage_type, predecessors, skill_id in EXPECTED_STAGES:
        stage = stage_by_id.get(stage_id)
        if stage is None:
            findings.append(FoundationProofFinding("workflow_stage_missing", f"missing stage: {stage_id}"))
            continue
        if stage.get("stage_type") != stage_type:
            findings.append(
                FoundationProofFinding(
                    "workflow_stage_type_invalid",
                    f"{stage_id} stage_type must be {stage_type}",
                )
            )
        if tuple(stage.get("predecessors", ())) != predecessors:
            findings.append(
                FoundationProofFinding(
                    "workflow_stage_predecessors_invalid",
                    f"{stage_id} predecessors must be {predecessors}",
                )
            )
        if skill_id is not None and stage.get("skill_id") != skill_id:
            findings.append(
                FoundationProofFinding(
                    "workflow_stage_skill_invalid",
                    f"{stage_id} skill_id must be {skill_id}",
                )
            )
        if stage_type != "skill_execution" and "skill_id" in stage:
            findings.append(
                FoundationProofFinding(
                    "workflow_stage_skill_invalid",
                    f"{stage_id} must not declare skill_id",
                )
            )
    return findings


def validate_bindings(stages: list[dict[str, Any]], bindings: list[dict[str, Any]]) -> list[FoundationProofFinding]:
    """Return findings for binding references and identity."""

    stage_ids = {stage["stage_id"] for stage in stages if isinstance(stage.get("stage_id"), str)}
    findings: list[FoundationProofFinding] = []
    observed_binding_ids = [binding.get("binding_id") for binding in bindings]
    if len(set(observed_binding_ids)) != len(observed_binding_ids):
        findings.append(FoundationProofFinding("workflow_binding_duplicate", "binding ids must be unique"))
    if len(bindings) != len(EXPECTED_STAGES) - 1:
        findings.append(
            FoundationProofFinding(
                "workflow_binding_count_invalid",
                f"descriptor must have {len(EXPECTED_STAGES) - 1} bindings",
            )
        )
    for binding in bindings:
        source_stage_id = binding.get("source_stage_id")
        target_stage_id = binding.get("target_stage_id")
        if source_stage_id not in stage_ids:
            findings.append(
                FoundationProofFinding(
                    "workflow_binding_source_missing",
                    f"binding source stage does not exist: {source_stage_id}",
                )
            )
        if target_stage_id not in stage_ids:
            findings.append(
                FoundationProofFinding(
                    "workflow_binding_target_missing",
                    f"binding target stage does not exist: {target_stage_id}",
                )
            )
        if source_stage_id == target_stage_id:
            findings.append(
                FoundationProofFinding(
                    "workflow_binding_self_loop",
                    f"binding must not self-loop: {binding.get('binding_id')}",
                )
            )
    return findings


def validate_acyclic_graph(stages: list[dict[str, Any]]) -> list[FoundationProofFinding]:
    """Return findings if stage predecessors contain missing edges or cycles."""

    stage_ids = {stage["stage_id"] for stage in stages if isinstance(stage.get("stage_id"), str)}
    predecessors_by_stage = {
        stage["stage_id"]: tuple(stage.get("predecessors", ()))
        for stage in stages
        if isinstance(stage.get("stage_id"), str)
    }
    findings: list[FoundationProofFinding] = []
    for stage_id, predecessors in predecessors_by_stage.items():
        for predecessor in predecessors:
            if predecessor not in stage_ids:
                findings.append(
                    FoundationProofFinding(
                        "workflow_predecessor_missing",
                        f"{stage_id} predecessor does not exist: {predecessor}",
                    )
                )
    if findings:
        return findings

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(stage_id: str) -> bool:
        if stage_id in visited:
            return False
        if stage_id in visiting:
            return True
        visiting.add(stage_id)
        for predecessor in predecessors_by_stage[stage_id]:
            if visit(predecessor):
                return True
        visiting.remove(stage_id)
        visited.add(stage_id)
        return False

    for stage_id in predecessors_by_stage:
        if visit(stage_id):
            findings.append(FoundationProofFinding("workflow_cycle_detected", "descriptor stage graph must be acyclic"))
            break
    return findings


def validate_foundation_local_proof_thread(
    doc_path: Path = DEFAULT_DOC_PATH,
    descriptor_path: Path = DEFAULT_DESCRIPTOR_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    runner_path: Path = DEFAULT_RUNNER_PATH,
) -> list[FoundationProofFinding]:
    """Validate the first Foundation Mode local proof-thread artifacts."""

    findings: list[FoundationProofFinding] = []
    doc_text = load_text(doc_path, "local proof-thread doc")
    runner_text = load_text(runner_path, "local proof-thread runner")
    schema = load_json_object(schema_path, "workflow schema")
    descriptor = load_json_object(descriptor_path, "local proof-thread descriptor")
    findings.extend(validate_doc_text(doc_text))
    findings.extend(validate_runner_text(runner_text))
    findings.extend(validate_schema_anchor(schema))
    findings.extend(validate_descriptor(descriptor))
    return findings


def main(argv: list[str] | None = None) -> int:
    """Validate the local proof-thread artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode local proof-thread artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--descriptor", type=Path, default=DEFAULT_DESCRIPTOR_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--runner", type=Path, default=DEFAULT_RUNNER_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_local_proof_thread(args.doc, args.descriptor, args.schema, args.runner)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_local_proof_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_local_proof_thread_doc")
    print("[PASS] foundation_local_proof_thread_descriptor")
    print("[PASS] foundation_local_proof_thread_topology")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
