#!/usr/bin/env python3
"""Validate intelligence coordination episode receipt artifacts.

Purpose: bind the implemented coordination episode contracts to a persisted
JSON receipt schema and operator-facing summary fixture.
Governance scope: OCE field completeness, RAG episode-summary linkage, CDCV
method and branch causality, CQTE schema-decidable checks, UWMA receipt refs,
and PRS closure for the coordination-layer implementation gap.
Dependencies: Python standard library, scripts/validate_schemas.py, and
mcoi_runtime.contracts.intelligence_coordination.
Invariants:
  - Validation is read-only and deterministic.
  - The persisted episode reconstructs the runtime contract dataclass.
  - Operator summary fields mirror the underlying episode.
  - Private reasoning fields are not admitted into public receipts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from mcoi_runtime.contracts.intelligence_coordination import (  # noqa: E402
    CounterfactualBranch,
    IntelligenceCoordinationEpisode,
    MethodCandidate,
    MethodFamily,
    MethodProblemSignature,
    SolverTerminalOutcome,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "intelligence_coordination_episode_receipt.schema.json"
DEFAULT_EXAMPLE_PATH = WORKSPACE_ROOT / "examples" / "intelligence_coordination_episode_receipt.json"
DEFAULT_DOC_PATH = WORKSPACE_ROOT / "docs" / "71_intelligence_coordination_layer.md"
PROHIBITED_PRIVATE_REASONING_FIELDS = frozenset(
    {
        "chain_of_thought",
        "raw_chain_of_thought",
        "private_reasoning",
        "hidden_reasoning",
        "scratchpad",
    }
)
REQUIRED_DOC_TERMS = (
    "schemas/intelligence_coordination_episode_receipt.schema.json",
    "examples/intelligence_coordination_episode_receipt.json",
    "scripts/validate_intelligence_coordination_episode_receipt.py",
    "operator-facing episode summary implemented",
    "persisted episode receipt schema defined",
)


class IntelligenceCoordinationReceiptError(ValueError):
    """Raised when the coordination episode receipt is invalid."""


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object and reject non-finite JSON constants."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            IntelligenceCoordinationReceiptError(f"{label} must not contain non-finite JSON constant: {value}")
        ),
    )
    if not isinstance(payload, dict):
        raise IntelligenceCoordinationReceiptError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic errors for the public schema artifact."""

    errors: list[str] = []
    if schema.get("$id") != "urn:mullusi:schema:intelligence-coordination-episode-receipt:1":
        errors.append("schema $id does not identify intelligence coordination episode receipt")
    if schema.get("title") != "Intelligence Coordination Episode Receipt":
        errors.append("schema title does not identify intelligence coordination episode receipt")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    required_fields = schema.get("required")
    if not isinstance(required_fields, list):
        errors.append("schema required field must be a list")
    else:
        for field_name in ("receipt_id", "generated_at", "episode", "operator_summary", "receipt_refs"):
            if field_name not in required_fields:
                errors.append(f"schema missing required receipt field: {field_name}")
    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        errors.append("schema $defs must be an object")
    else:
        for definition_name in ("episode", "operator_summary", "method_candidate", "counterfactual_branch"):
            if definition_name not in defs:
                errors.append(f"schema missing definition: {definition_name}")
    return errors


def validate_receipt_payload(payload: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate one receipt payload against schema and runtime contracts."""

    errors = list(_validate_schema_instance(schema, payload))
    errors.extend(_find_private_reasoning_fields(payload))
    if errors:
        return errors

    try:
        episode = build_episode_from_payload(payload["episode"])
    except (KeyError, TypeError, ValueError) as exc:
        return [f"episode runtime contract rejected payload: {_bounded_error(exc)}"]

    errors.extend(_validate_operator_summary(payload["operator_summary"], episode))
    if not payload.get("receipt_refs"):
        errors.append("receipt_refs must contain at least one receipt reference")
    return errors


def build_episode_from_payload(episode_payload: dict[str, Any]) -> IntelligenceCoordinationEpisode:
    """Reconstruct the runtime episode contract from its JSON form."""

    candidates = tuple(_build_method_candidate(item) for item in episode_payload["method_candidates"])
    branches = tuple(_build_counterfactual_branch(item) for item in episode_payload["counterfactual_branches"])
    return IntelligenceCoordinationEpisode(
        episode_id=episode_payload["episode_id"],
        goal_id=episode_payload["goal_id"],
        input_symbol_mesh_ref=episode_payload["input_symbol_mesh_ref"],
        world_snapshot_ref=episode_payload["world_snapshot_ref"],
        active_constraints_ref=episode_payload["active_constraints_ref"],
        causal_graph_ref=episode_payload["causal_graph_ref"],
        uncertainty_envelope_ref=episode_payload["uncertainty_envelope_ref"],
        problem_signature=MethodProblemSignature(episode_payload["problem_signature"]),
        method_candidates=candidates,
        selected_method_id=episode_payload["selected_method_id"],
        rejected_method_ids=tuple(episode_payload["rejected_method_ids"]),
        counterfactual_branches=branches,
        failure_map_ref=episode_payload["failure_map_ref"],
        tradeoff_report_ref=episode_payload["tradeoff_report_ref"],
        execution_plan_ref=episode_payload["execution_plan_ref"],
        diagnosis_report_ref=episode_payload["diagnosis_report_ref"],
        world_model_delta_ref=episode_payload["world_model_delta_ref"],
        proof_record_ref=episode_payload["proof_record_ref"],
        terminal_outcome=SolverTerminalOutcome(episode_payload["terminal_outcome"]),
        created_at=episode_payload["created_at"],
        coordination_depth=episode_payload["coordination_depth"],
        metadata=episode_payload["metadata"],
    )


def validate_contract(
    receipt_path: Path = DEFAULT_EXAMPLE_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    doc_path: Path = DEFAULT_DOC_PATH,
) -> list[str]:
    """Validate schema, receipt example, runtime contract, and doc closure."""

    schema = _load_schema(schema_path)
    payload = load_json_object(receipt_path, "intelligence coordination episode receipt")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_receipt_payload(payload, schema))
    errors.extend(validate_documentation(doc_path))
    return errors


def validate_documentation(doc_path: Path = DEFAULT_DOC_PATH) -> list[str]:
    """Validate that the coordination-layer document references closure artifacts."""

    if not doc_path.exists():
        return [f"missing coordination-layer document: {doc_path}"]
    text = doc_path.read_text(encoding="utf-8")
    errors: list[str] = []
    for term in REQUIRED_DOC_TERMS:
        if term not in text:
            errors.append(f"coordination document missing required term: {term}")
    if "operator-facing episode summary not implemented" in text:
        errors.append("coordination document still reports operator-facing episode summary as unimplemented")
    if "persisted episode receipt schema not yet defined" in text:
        errors.append("coordination document still reports persisted episode receipt schema as undefined")
    return errors


def _build_method_candidate(payload: dict[str, Any]) -> MethodCandidate:
    return MethodCandidate(
        method_id=payload["method_id"],
        family=MethodFamily(payload["family"]),
        compatible_signatures=tuple(MethodProblemSignature(item) for item in payload["compatible_signatures"]),
        estimated_cost=payload["estimated_cost"],
        confidence=payload["confidence"],
        resource_requirement=payload["resource_requirement"],
    )


def _build_counterfactual_branch(payload: dict[str, Any]) -> CounterfactualBranch:
    return CounterfactualBranch(
        branch_id=payload["branch_id"],
        baseline_snapshot_ref=payload["baseline_snapshot_ref"],
        intervention=payload["intervention"],
        affected_entity_ids=tuple(payload["affected_entity_ids"]),
        affected_relation_ids=tuple(payload["affected_relation_ids"]),
        predicted_delta_refs=tuple(payload["predicted_delta_refs"]),
        reversible_step_ids=tuple(payload["reversible_step_ids"]),
        irreversible_risk_ids=tuple(payload["irreversible_risk_ids"]),
        confidence_lower=payload["confidence_lower"],
        confidence_upper=payload["confidence_upper"],
    )


def _validate_operator_summary(
    summary: dict[str, Any],
    episode: IntelligenceCoordinationEpisode,
) -> list[str]:
    errors: list[str] = []
    if summary["episode_id"] != episode.episode_id:
        errors.append("operator_summary.episode_id must match episode.episode_id")
    if summary["terminal_outcome"] != episode.terminal_outcome.value:
        errors.append("operator_summary.terminal_outcome must match episode.terminal_outcome")
    if summary["selected_method_id"] != episode.selected_method_id:
        errors.append("operator_summary.selected_method_id must match episode.selected_method_id")
    if tuple(summary["rejected_method_ids"]) != episode.rejected_method_ids:
        errors.append("operator_summary.rejected_method_ids must match episode.rejected_method_ids")
    if summary["world_model_delta_ref"] != episode.world_model_delta_ref:
        errors.append("operator_summary.world_model_delta_ref must match episode.world_model_delta_ref")

    metadata = dict(episode.metadata)
    if summary["summary_id"] != metadata.get("operator_summary_ref"):
        errors.append("operator_summary.summary_id must match episode.metadata.operator_summary_ref")
    blocked_branch_ids = metadata.get("blocked_branch_ids")
    if not isinstance(blocked_branch_ids, tuple):
        errors.append("episode.metadata.blocked_branch_ids must be an array")
    elif summary["blocked_branch_count"] != len(blocked_branch_ids):
        errors.append("operator_summary.blocked_branch_count must match episode.metadata.blocked_branch_ids")
    return errors


def _find_private_reasoning_fields(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in PROHIBITED_PRIVATE_REASONING_FIELDS:
                errors.append(f"{path}: prohibited private reasoning field: {key}")
            errors.extend(_find_private_reasoning_fields(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_find_private_reasoning_fields(item, f"{path}[{index}]"))
    return errors


def _bounded_error(exc: BaseException) -> str:
    text = str(exc).replace("\\", "/")
    return text.splitlines()[0][:180]


def main(argv: list[str] | None = None) -> int:
    """Validate intelligence coordination episode receipt artifacts."""

    parser = argparse.ArgumentParser(description="Validate intelligence coordination episode receipt artifacts.")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_EXAMPLE_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    args = parser.parse_args(argv)

    try:
        errors = validate_contract(args.receipt, args.schema, args.doc)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(f"[FAIL] load-intelligence-coordination-receipt: {_bounded_error(exc)}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[FAIL] intelligence-coordination-receipt: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] intelligence_coordination_episode_receipt_schema\n")
    sys.stdout.write("[PASS] intelligence_coordination_episode_receipt_example\n")
    sys.stdout.write("[PASS] intelligence_coordination_operator_summary\n")
    sys.stdout.write("[PASS] intelligence_coordination_documentation_closure\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
