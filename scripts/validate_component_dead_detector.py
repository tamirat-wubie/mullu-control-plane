#!/usr/bin/env python3
"""Validate Component Harness dead-component detector artifacts.

Purpose: prove detector examples and runtime reports are schema-valid,
deterministic, and advisory-only.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_dead_component_detection.schema.json,
examples/component_dead_component_detection.foundation.json, component dead
detector runtime, and component graph validation.
Invariants:
  - Dead candidates are based on multiple missing relationship signals.
  - Blocked governed components remain visible and are not silently removed.
  - Detector output cannot grant execution, mutation, connector, or terminal
    closure authority.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from mcoi_runtime.app.component_dead_detector import (  # noqa: E402
    build_component_dead_component_report,
)
from scripts.validate_component_graph import validate_component_graph  # noqa: E402
from scripts.validate_component_read_model import validate_component_read_model  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_dead_component_detection.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "component_dead_component_detection.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_dead_detector_validation.json"


@dataclass(frozen=True, slots=True)
class ComponentDeadDetectorValidation:
    """Schema and semantic validation report for dead-component detection."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    component_count: int
    dead_candidate_count: int
    blocked_governed_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_dead_detector(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentDeadDetectorValidation:
    """Validate detector schema, example, and runtime report."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component dead detector schema", errors)
    example = _load_json_object(example_path, "component dead detector example", errors)

    graph_validation = validate_component_graph()
    if not graph_validation.ok:
        errors.extend(f"component graph validation failed: {error}" for error in graph_validation.errors)
    read_model_validation = validate_component_read_model()
    if not read_model_validation.ok:
        errors.extend(f"component read model validation failed: {error}" for error in read_model_validation.errors)

    runtime_report = build_component_dead_component_report()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_detector_semantics(example, errors, _path_label(example_path))
    _validate_detector_semantics(runtime_report, errors, "runtime component dead detector")

    summary = runtime_report.get("summary", {})
    return ComponentDeadDetectorValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        component_count=int(summary.get("component_count", 0)) if isinstance(summary, dict) else 0,
        dead_candidate_count=int(summary.get("dead_candidate_count", 0)) if isinstance(summary, dict) else 0,
        blocked_governed_count=int(summary.get("blocked_governed_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_dead_detector_validation(
    validation: ComponentDeadDetectorValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic dead detector validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_detector_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("detector_is_not_execution_authority") is not True:
        errors.append(f"{label}: detector must not be execution authority")
    for field_name in (
        "live_execution_enabled",
        "live_connector_send_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
    ):
        if report.get(field_name) is not False:
            errors.append(f"{label}: {field_name} must be false")
    if report.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")

    detections = report.get("detections")
    summary = report.get("summary")
    if not isinstance(detections, list) or not detections:
        errors.append(f"{label}: detections must be non-empty")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return

    component_ids = [str(detection.get("component_id")) for detection in detections if isinstance(detection, dict)]
    if len(component_ids) != len(set(component_ids)):
        errors.append(f"{label}: detection component_ids must be unique")
    if summary.get("component_count") != len(detections):
        errors.append(f"{label}: summary.component_count must match detections")

    classification_counts = {
        "active_governed": 0,
        "blocked_governed": 0,
        "dead_candidate": 0,
        "governed_watch": 0,
    }
    for detection in detections:
        if not isinstance(detection, dict):
            errors.append(f"{label}: detection entries must be objects")
            continue
        classification = str(detection.get("classification", ""))
        if classification in classification_counts:
            classification_counts[classification] += 1
        if detection.get("detection_is_not_execution_authority") is not True:
            errors.append(f"{label}: detection must not be execution authority")
        signals = set(_string_list(detection.get("signals")))
        if classification == "dead_candidate":
            required_dead_signals = {"no_mounted_route", "no_bundle_membership", "no_request_path_coverage"}
            if not required_dead_signals.issubset(signals):
                errors.append(f"{label}: dead_candidate must carry dead relationship signals")
        if classification == "blocked_governed" and not signals.intersection({"proof_binding_missing", "missing_evidence"}):
            errors.append(f"{label}: blocked_governed must carry evidence or proof signal")
        if not _string_list(detection.get("recommended_decisions")):
            errors.append(f"{label}: detection recommended_decisions must not be empty")

    for classification, count in classification_counts.items():
        summary_key = f"{classification}_count"
        if summary.get(summary_key) != count:
            errors.append(f"{label}: summary.{summary_key} must match detections")

    dead_candidates = _string_list(report.get("dead_component_candidates"))
    blocked_components = _string_list(report.get("blocked_governed_components"))
    if sorted(dead_candidates) != sorted(
        detection["component_id"]
        for detection in detections
        if isinstance(detection, dict) and detection.get("classification") == "dead_candidate"
    ):
        errors.append(f"{label}: dead_component_candidates must match detections")
    if sorted(blocked_components) != sorted(
        detection["component_id"]
        for detection in detections
        if isinstance(detection, dict) and detection.get("classification") == "blocked_governed"
    ):
        errors.append(f"{label}: blocked_governed_components must match detections")
    if "authority_denial_receipt" not in _string_list(report.get("expected_receipts")):
        errors.append(f"{label}: expected_receipts must include authority_denial_receipt")
    if report.get("outcome") not in {"AwaitingEvidence", "GovernanceBlocked", "SolvedUnverified"}:
        errors.append(f"{label}: outcome is not a governed solver outcome")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse component dead detector validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness dead-component detector.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for component dead detector validation."""

    args = parse_args(argv)
    validation = validate_component_dead_detector(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_dead_detector_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT DEAD DETECTOR VALID")
    else:
        print(f"COMPONENT DEAD DETECTOR INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
