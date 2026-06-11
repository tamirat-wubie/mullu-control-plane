#!/usr/bin/env python3
"""Validate the holistic loop kernel v1 contract freeze.

Purpose: prove the v1 read-model contract stays stable across report, schema,
HTTP, golden fixture, documentation, and proof-matrix witness surfaces.
Governance scope: holistic loop read-model freeze, additive-only v1 policy,
schema/report/HTTP parity, golden snapshot parity, and witness anchoring.
Dependencies: holistic loop reporter, HTTP surface validator, schema validator,
proof coverage matrix, and the v1 golden fixture.
Invariants:
  - Validation is read-only and deterministic.
  - The v1 contract can only be extended additively without a v2 boundary.
  - HTTP payloads normalize to the same loop summary contract as local reports.
  - Holistic loop proof labels must have zero unanchored witnesses.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from scripts.proof_coverage_matrix import (  # noqa: E402
    proof_coverage_matrix,
    witness_integrity_report,
)
from scripts.report_holistic_loop_read_model import build_report  # noqa: E402
from scripts.validate_holistic_loop_http_surface import (  # noqa: E402
    LOOP_READ_MODEL_PATH,
    build_default_app,
)
from scripts.validate_holistic_loop_read_model import validate_report  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "holistic_loop_read_model.schema.json"
DEFAULT_FIXTURE_PATH = WORKSPACE_ROOT / "tests" / "fixtures" / "holistic_loop_read_model_v1_golden.json"
DEFAULT_DOC_PATH = WORKSPACE_ROOT / "docs" / "HOLISTIC_LOOP_ENGINEERING_KERNEL.md"
HOLISTIC_SURFACE_ID = "holistic_loop_read_model_kernel"
READ_MODEL_VERSION = "holistic_loop_kernel.v1"
REPORT_ID = "holistic_loop_read_model"


class HolisticLoopKernelFreezeError(ValueError):
    """Raised when a freeze artifact cannot be read as a JSON object."""


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit artifact context."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HolisticLoopKernelFreezeError(f"{label} must be a JSON object")
    return payload


def fetch_http_payload(limit: int = 20) -> dict[str, Any]:
    """Fetch the default HTTP read-model payload without external network use."""

    response = TestClient(build_default_app()).get(LOOP_READ_MODEL_PATH, params={"limit": limit})
    if response.status_code != 200:
        raise HolisticLoopKernelFreezeError(
            f"HTTP loop read-model returned status {response.status_code}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise HolisticLoopKernelFreezeError("HTTP loop read-model payload must be an object")
    return payload


def normalize_http_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize HTTP route fields to the local report contract."""

    return {
        "report_id": payload.get("read_model_id"),
        "status": payload.get("status"),
        "generated_at": payload.get("generated_at"),
        "loop_count": payload.get("total_count"),
        "returned_count": payload.get("returned_count"),
        "blocked_count": payload.get("blocked_count"),
        "verified_count": payload.get("verified_count"),
        "truncated": payload.get("truncated"),
        "report_is_not_terminal_closure": payload.get("report_is_not_terminal_closure"),
        "terminal_closure_required": payload.get("terminal_closure_required"),
        "loops": payload.get("loops"),
    }


def validate_payload_parity(
    report: dict[str, Any],
    http_payload: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    """Return errors when report, schema, and HTTP payload drift apart."""

    errors: list[str] = []
    normalized_http_payload = normalize_http_payload(http_payload)
    if http_payload.get("read_model_id") != REPORT_ID:
        errors.append("HTTP payload read_model_id does not match report contract")
    if http_payload.get("read_model_version") != READ_MODEL_VERSION:
        errors.append("HTTP payload read_model_version does not match v1 contract")
    if http_payload.get("governed") is not True:
        errors.append("HTTP payload governed flag must be true")
    if http_payload.get("read_only") is not True:
        errors.append("HTTP payload read_only flag must be true")
    if normalized_http_payload != report:
        errors.append("HTTP payload does not normalize to the current report")
    errors.extend(
        f"report schema: {error}"
        for error in _validate_schema_instance(schema, report)
    )
    errors.extend(
        f"HTTP schema: {error}"
        for error in _validate_schema_instance(schema, normalized_http_payload)
    )
    return errors


def validate_golden_snapshot(
    current_report: dict[str, Any],
    golden_snapshot: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    """Return errors when the v1 golden fixture no longer matches the report."""

    errors: list[str] = []
    if golden_snapshot != current_report:
        errors.append("golden fixture does not match current report")
    errors.extend(
        f"golden schema: {error}"
        for error in _validate_schema_instance(schema, golden_snapshot)
    )
    errors.extend(
        f"golden report: {error}"
        for error in validate_report(golden_snapshot)
    )
    return errors


def validate_kernel_policy_doc(doc_text: str) -> list[str]:
    """Return errors when the v1 freeze policy is not documented."""

    required_fragments = (
        "Kernel v1 Stability Boundary",
        "v1 additive-only",
        "No v1 field may be removed",
        "a v2 contract boundary",
        "Extension Checklist",
        "proof matrix witness",
        "golden snapshot",
    )
    return [
        f"kernel policy doc missing required fragment: {fragment}"
        for fragment in required_fragments
        if fragment not in doc_text
    ]


def validate_holistic_witness_integrity(matrix: dict[str, Any] | None = None) -> list[str]:
    """Return errors when holistic loop proof labels are unanchored."""

    current_matrix = matrix or proof_coverage_matrix()
    surfaces = current_matrix.get("surfaces")
    if not isinstance(surfaces, list):
        return ["proof matrix surfaces must be a list"]
    integrity = witness_integrity_report(surfaces)
    surface_records = {
        record.get("surface_id"): record
        for record in integrity.get("surfaces", [])
        if isinstance(record, dict)
    }
    holistic_record = surface_records.get(HOLISTIC_SURFACE_ID)
    if not isinstance(holistic_record, dict):
        return ["holistic loop proof surface is missing from witness integrity report"]
    errors: list[str] = []
    if holistic_record.get("unanchored_witness_count") != 0:
        errors.append("holistic loop proof surface has unanchored witness labels")
    if holistic_record.get("unanchored_witnesses") != []:
        errors.append("holistic loop proof surface lists unanchored witnesses")
    if holistic_record.get("runtime_witness_count") != holistic_record.get("exact_test_anchor_count"):
        errors.append("holistic loop proof surface runtime witnesses must all have exact anchors")
    return errors


def validate_freeze_contract(
    *,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
    doc_path: Path = DEFAULT_DOC_PATH,
) -> list[str]:
    """Validate the holistic loop kernel v1 freeze contract."""

    schema = _load_schema(schema_path)
    current_report = build_report()
    golden_snapshot = load_json_object(fixture_path, "holistic loop v1 golden fixture")
    http_payload = fetch_http_payload()
    doc_text = doc_path.read_text(encoding="utf-8")

    errors: list[str] = []
    errors.extend(validate_golden_snapshot(current_report, golden_snapshot, schema))
    errors.extend(validate_payload_parity(current_report, http_payload, schema))
    errors.extend(validate_kernel_policy_doc(doc_text))
    errors.extend(validate_holistic_witness_integrity())
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate the holistic loop kernel v1 freeze contract."""

    parser = argparse.ArgumentParser(description="Validate holistic loop kernel v1 freeze.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH, help="schema JSON path")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE_PATH, help="golden fixture JSON path")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH, help="kernel documentation path")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)

    try:
        errors = validate_freeze_contract(
            schema_path=args.schema,
            fixture_path=args.fixture,
            doc_path=args.doc,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [f"load-holistic-loop-freeze: {exc}"]

    receipt = {
        "receipt_id": "holistic_loop_kernel_v1_freeze_validation",
        "status": "passed" if not errors else "blocked",
        "valid": not errors,
        "read_model_version": READ_MODEL_VERSION,
        "fixture_path": str(args.fixture),
        "receipt_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "errors": errors,
    }
    if args.json:
        sys.stdout.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        return 0 if receipt["valid"] else 1
    if errors:
        for error in errors:
            sys.stderr.write(f"[BLOCKED] holistic-loop-kernel-freeze: {error}\n")
        sys.stderr.write("STATUS: blocked\n")
        return 1
    sys.stdout.write("[PASS] holistic_loop_kernel_v1_golden_snapshot\n")
    sys.stdout.write("[PASS] holistic_loop_kernel_v1_schema_report_http_parity\n")
    sys.stdout.write("[PASS] holistic_loop_kernel_v1_extension_policy\n")
    sys.stdout.write("[PASS] holistic_loop_kernel_v1_witness_integrity\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
