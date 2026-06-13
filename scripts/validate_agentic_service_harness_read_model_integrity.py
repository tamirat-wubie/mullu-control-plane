#!/usr/bin/env python3
"""Validate Agentic Service Harness read-model identity integrity.

Purpose: prove read-only Agentic Service Harness projections preserve the
identity mesh between source contract fixtures and display-only read models.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: examples/agentic_service_harness.*.json,
scripts.validate_agentic_service_harness_read_model_projections, and
schemas/agentic_service_harness_read_models.schema.json.
Invariants:
  - Read-model projection remains planning-only and read-only.
  - Source run, approval, receipt, evidence, and summary identities are
    preserved by projection.
  - Cross-collection references are bijective where the read model claims a
    direct identity link.
  - No UI, mutation endpoint, adapter execution, branch write, PR creation, or
    terminal closure authority is introduced.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_contract import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_CONTRACT_EXAMPLES,
    EXPECTED_SCENARIOS,
)
from scripts.validate_agentic_service_harness_read_model_projections import (  # noqa: E402
    project_contract_to_read_model,
    validate_agentic_service_harness_read_model_projections,
)


DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_read_model_integrity_validation.json"
)


@dataclass(frozen=True, slots=True)
class AgenticServiceHarnessReadModelIntegrityValidation:
    """Validation result for harness read-model identity integrity."""

    ok: bool
    errors: tuple[str, ...]
    source_paths: tuple[str, ...]
    source_count: int
    projection_count: int
    scenario_count: int
    checked_link_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["source_paths"] = list(self.source_paths)
        return payload


def validate_agentic_service_harness_read_model_integrity(
    *,
    source_paths: Sequence[Path] = DEFAULT_CONTRACT_EXAMPLES,
) -> AgenticServiceHarnessReadModelIntegrityValidation:
    """Validate identity and reference integrity across generated read models."""
    errors: list[str] = []
    projection_validation = validate_agentic_service_harness_read_model_projections(
        source_paths=source_paths,
    )
    errors.extend(f"projection validator: {error}" for error in projection_validation.errors)

    checked_link_count = 0
    projection_count = 0
    observed_scenarios: set[str] = set()
    for source_path in source_paths:
        source = _load_json_object(source_path, errors)
        if not source:
            continue
        label = _path_label(source_path)
        observed_scenarios.add(str(source.get("scenario", "")))
        projection = project_contract_to_read_model(source, label)
        projection_count += 1
        checked_link_count += _validate_source_projection_identity(
            source,
            projection,
            errors,
            label,
        )
        checked_link_count += _validate_projection_identity_mesh(
            projection,
            errors,
            label,
        )

    missing = sorted(set(EXPECTED_SCENARIOS) - observed_scenarios)
    extra = sorted(observed_scenarios - set(EXPECTED_SCENARIOS))
    if missing:
        errors.append(f"source scenarios missing {missing}")
    if extra:
        errors.append(f"source scenarios unknown {extra}")

    return AgenticServiceHarnessReadModelIntegrityValidation(
        ok=not errors,
        errors=tuple(errors),
        source_paths=tuple(_path_label(path) for path in source_paths),
        source_count=len(source_paths),
        projection_count=projection_count,
        scenario_count=len(observed_scenarios),
        checked_link_count=checked_link_count,
    )


def write_read_model_integrity_validation(
    validation: AgenticServiceHarnessReadModelIntegrityValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic read-model integrity validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_source_projection_identity(
    source: dict[str, Any],
    projection: dict[str, Any],
    errors: list[str],
    label: str,
) -> int:
    checked = 0
    source_runs = _by_id(source.get("agent_runs"), "run_id", errors, f"{label}: source agent_runs")
    projected_runs = _by_id(projection.get("runs"), "run_id", errors, f"{label}: projected runs")
    source_receipts = _by_id(source.get("receipts"), "receipt_id", errors, f"{label}: source receipts")
    projected_receipts = _by_id(projection.get("receipts"), "receipt_id", errors, f"{label}: projected receipts")

    if set(source_runs) != set(projected_runs):
        errors.append(f"{label}: source/projected run id set mismatch")
    checked += 1
    if set(source_receipts) != set(projected_receipts):
        errors.append(f"{label}: source/projected receipt id set mismatch")
    checked += 1

    source_tasks = _by_id(source.get("agent_tasks"), "task_id", errors, f"{label}: source agent_tasks")
    for run_id, source_run in source_runs.items():
        projected_run = projected_runs.get(run_id)
        if not projected_run:
            continue
        task_id = str(source_run.get("task_id", ""))
        source_task = source_tasks.get(task_id, {})
        _compare_field(source_run, projected_run, "adapter_id", errors, label, run_id)
        _compare_field(source_run, projected_run, "sandbox_id", errors, label, run_id)
        _compare_field(source_run, projected_run, "mode", errors, label, run_id)
        _compare_field(source_run, projected_run, "status", errors, label, run_id)
        _compare_field(source_run, projected_run, "receipt_id", errors, label, run_id)
        _compare_field(source_run, projected_run, "evidence_bundle_id", errors, label, run_id)
        _compare_field(source_run, projected_run, "result_summary_id", errors, label, run_id)
        _compare_list_field(source_run, projected_run, "approval_gate_ids", errors, label, run_id)
        _compare_list_field(source_run, projected_run, "blocked_actions", errors, label, run_id)
        if projected_run.get("task_request_ref") != f"task://{task_id}":
            errors.append(f"{label}: run {run_id} task_request_ref mismatch")
        if source_task and projected_run.get("risk_level") != source_task.get("risk_level"):
            errors.append(f"{label}: run {run_id} risk_level mismatch")
        checked += 11

    for receipt_id, source_receipt in source_receipts.items():
        projected_receipt = projected_receipts.get(receipt_id)
        if not projected_receipt:
            continue
        _compare_field(source_receipt, projected_receipt, "run_id", errors, label, receipt_id)
        _compare_field(source_receipt, projected_receipt, "policy_result", errors, label, receipt_id)
        _compare_field(source_receipt, projected_receipt, "risk_level", errors, label, receipt_id)
        _compare_field(source_receipt, projected_receipt, "next_action", errors, label, receipt_id)
        _compare_list_field(source_receipt, projected_receipt, "evidence_refs", errors, label, receipt_id)
        checked += 5

    return checked


def _validate_projection_identity_mesh(
    projection: dict[str, Any],
    errors: list[str],
    label: str,
) -> int:
    checked = 0
    projects = _by_id(projection.get("projects"), "project_id", errors, f"{label}: projects")
    repositories = _by_id(projection.get("repositories"), "connection_id", errors, f"{label}: repositories")
    runs = _by_id(projection.get("runs"), "run_id", errors, f"{label}: runs")
    approvals = _by_id(projection.get("approvals"), "gate_id", errors, f"{label}: approvals")
    receipts = _by_id(projection.get("receipts"), "receipt_id", errors, f"{label}: receipts")
    evidence = _by_id(projection.get("evidence"), "bundle_id", errors, f"{label}: evidence")
    summaries = _by_id(projection.get("result_summaries"), "summary_id", errors, f"{label}: result_summaries")

    scope = projection.get("projection_scope") if isinstance(projection.get("projection_scope"), dict) else {}
    for project_id, project in projects.items():
        if project_id == scope.get("project_id"):
            if project.get("tenant_id") != scope.get("tenant_id"):
                errors.append(f"{label}: scope tenant_id does not match project {project_id}")
            if project.get("organization_id") != scope.get("organization_id"):
                errors.append(f"{label}: scope organization_id does not match project {project_id}")
            checked += 2
        project_repository_ids = {
            connection_id
            for connection_id, repository in repositories.items()
            if repository.get("project_id") == project_id
        }
        project_run_ids = {
            run_id
            for run_id, run in runs.items()
            if run.get("project_id") == project_id
        }
        _require_exact_refs(
            project.get("repository_connection_ids"),
            project_repository_ids,
            errors,
            f"{label}: project {project_id} repository_connection_ids",
        )
        _require_exact_refs(
            project.get("agent_run_ids"),
            project_run_ids,
            errors,
            f"{label}: project {project_id} agent_run_ids",
        )
        checked += 2

    for run_id, run in runs.items():
        if run.get("project_id") not in projects:
            errors.append(f"{label}: run {run_id} project_id missing")
        run_approval_ids = {
            gate_id
            for gate_id, approval in approvals.items()
            if approval.get("run_id") == run_id
        }
        _require_exact_refs(
            run.get("approval_gate_ids"),
            run_approval_ids,
            errors,
            f"{label}: run {run_id} approval_gate_ids",
        )
        receipt = receipts.get(str(run.get("receipt_id")))
        bundle = evidence.get(str(run.get("evidence_bundle_id")))
        summary = summaries.get(str(run.get("result_summary_id")))
        _require_backref(receipt, "run_id", run_id, errors, f"{label}: run {run_id} receipt")
        _require_backref(bundle, "run_id", run_id, errors, f"{label}: run {run_id} evidence")
        _require_backref(summary, "run_id", run_id, errors, f"{label}: run {run_id} summary")
        if receipt and not _is_task_ref(receipt.get("task_request_ref")):
            errors.append(f"{label}: run {run_id} receipt task_request_ref must be task:// ref")
        if receipt and receipt.get("risk_level") != run.get("risk_level"):
            errors.append(f"{label}: run {run_id} receipt risk_level mismatch")
        if receipt and bundle:
            _require_exact_refs(
                receipt.get("evidence_refs"),
                set(str(ref) for ref in bundle.get("evidence_refs", ())),
                errors,
                f"{label}: run {run_id} receipt/evidence refs",
            )
        if receipt and summary:
            changed_files = receipt.get("files_changed")
            if isinstance(changed_files, dict):
                if summary.get("changed_file_count") != changed_files.get("changed_file_count"):
                    errors.append(f"{label}: run {run_id} changed_file_count mismatch")
                changed_refs = changed_files.get("changed_file_refs")
                if isinstance(changed_refs, list) and changed_files.get("changed_file_count") != len(changed_refs):
                    errors.append(f"{label}: run {run_id} changed_file_refs count mismatch")
        checked += 10

    for gate_id, approval in approvals.items():
        run_id = str(approval.get("run_id"))
        run = runs.get(run_id)
        if not run:
            errors.append(f"{label}: approval {gate_id} run_id missing")
            continue
        if gate_id not in set(str(item) for item in run.get("approval_gate_ids", ())):
            errors.append(f"{label}: approval {gate_id} missing from run {run_id}")
        checked += 1

    return checked


def _compare_field(
    source: dict[str, Any],
    projection: dict[str, Any],
    field_name: str,
    errors: list[str],
    label: str,
    identity: str,
) -> None:
    if source.get(field_name) != projection.get(field_name):
        errors.append(f"{label}: {identity} {field_name} mismatch")


def _compare_list_field(
    source: dict[str, Any],
    projection: dict[str, Any],
    field_name: str,
    errors: list[str],
    label: str,
    identity: str,
) -> None:
    if list(source.get(field_name, ())) != list(projection.get(field_name, ())):
        errors.append(f"{label}: {identity} {field_name} mismatch")


def _is_task_ref(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("task://") and len(value) > len("task://")


def _require_backref(
    item: dict[str, Any] | None,
    ref_name: str,
    expected: str,
    errors: list[str],
    label: str,
) -> None:
    if not item:
        errors.append(f"{label} missing")
    elif item.get(ref_name) != expected:
        errors.append(f"{label} {ref_name} mismatch")


def _require_exact_refs(
    observed: Any,
    expected: set[str],
    errors: list[str],
    label: str,
) -> None:
    if not isinstance(observed, list):
        errors.append(f"{label} must be a list")
        return
    observed_set = set(str(item) for item in observed)
    if observed_set != expected:
        errors.append(
            f"{label} mismatch observed={sorted(observed_set)} expected={sorted(expected)}"
        )


def _by_id(
    collection: Any,
    key: str,
    errors: list[str],
    label: str,
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in _objects(collection):
        identity = item.get(key)
        if not isinstance(identity, str) or not identity:
            errors.append(f"{label}: item missing {key}")
            continue
        if identity in indexed:
            errors.append(f"{label}: duplicate {key} {identity}")
            continue
        indexed[identity] = item
    return indexed


def _objects(collection: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(collection, list):
        return ()
    return tuple(item for item in collection if isinstance(item, dict))


def _load_json_object(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{_path_label(path)} file missing")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{_path_label(path)} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{_path_label(path)} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse harness read-model integrity validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate Agentic Service Harness read-model identity integrity."
    )
    parser.add_argument("--source", action="append", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for harness read-model identity validation."""
    args = parse_args(argv)
    source_paths = (
        tuple(Path(source) for source in args.source)
        if args.source
        else DEFAULT_CONTRACT_EXAMPLES
    )
    validation = validate_agentic_service_harness_read_model_integrity(
        source_paths=source_paths,
    )
    write_read_model_integrity_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS READ MODEL INTEGRITY VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS READ MODEL INTEGRITY INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
