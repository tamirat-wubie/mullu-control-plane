#!/usr/bin/env python3
"""Validate local public demo surfaces before publication.

Purpose: verify that the evaluator-facing sandbox, federation, replay, SDK,
benchmark, compliance, and proof-coverage witnesses agree.
Governance scope: public demo readiness validation only.
Dependencies: FastAPI TestClient, OpenAPI SDK source spec, proof matrix,
benchmark harness, and compliance alignment matrix.
Invariants: validation is local; no live provider calls are performed; failures
are bounded by check id and reason; the emitted report hash is deterministic.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = REPO_ROOT / "mcoi"
OPENAPI_SPEC_PATH = REPO_ROOT / "sdk" / "openapi" / "mullu.openapi.json"
SDK_MANIFEST_PATH = REPO_ROOT / "sdk" / "sdk-generation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "public_demo_surface_validation.json"

REQUIRED_OPENAPI_PATHS = (
    "/api/v1/sandbox/summary",
    "/api/v1/sandbox/traces",
    "/api/v1/sandbox/lineage/{trace_id}",
    "/api/v1/sandbox/policy-evaluations",
    "/api/v1/federation/summary",
    "/api/v1/replay/{trace_id}/determinism",
)
REQUIRED_PROOF_SURFACES = (
    "hosted_demo_sandbox",
    "federated_control_plane",
    "replay_determinism",
    "pilot_provisioning",
)

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass(frozen=True, slots=True)
class DemoSurfaceCheck:
    """Single public demo validation check result."""

    check_id: str
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "details": dict(self.details),
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class PublicDemoSurfaceReport:
    """Aggregated public demo validation report."""

    ready: bool
    checks: tuple[DemoSurfaceCheck, ...]
    report_hash: str = ""

    def __post_init__(self) -> None:
        if not self.report_hash:
            object.__setattr__(self, "report_hash", _stable_hash(self.to_dict(include_hash=False)))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        document = {
            "governed": True,
            "ready": self.ready,
            "check_count": len(self.checks),
            "passed_count": sum(1 for check in self.checks if check.passed),
            "failed_count": sum(1 for check in self.checks if not check.passed),
            "checks": [check.to_dict() for check in self.checks],
        }
        if include_hash:
            document["report_hash"] = self.report_hash
        return document


def validate_openapi_source() -> DemoSurfaceCheck:
    """Validate checked-in OpenAPI source spec contains demo surfaces."""
    errors: list[str] = []
    if not OPENAPI_SPEC_PATH.exists():
        return DemoSurfaceCheck("openapi_source", False, errors=("openapi_spec_missing",))

    spec = json.loads(OPENAPI_SPEC_PATH.read_text(encoding="utf-8"))
    paths = spec.get("paths", {})
    for required_path in REQUIRED_OPENAPI_PATHS:
        if required_path not in paths:
            errors.append(f"missing_openapi_path:{required_path}")

    info = spec.get("info", {})
    if info.get("title") != "Mullu Platform":
        errors.append("openapi_title_mismatch")
    if info.get("version") != "3.13.0":
        errors.append("openapi_version_mismatch")

    return DemoSurfaceCheck(
        "openapi_source",
        not errors,
        details={"path_count": len(paths), "required_paths": list(REQUIRED_OPENAPI_PATHS)},
        errors=tuple(errors),
    )


def validate_sdk_manifest() -> DemoSurfaceCheck:
    """Validate SDK generation remains bound to the checked-in OpenAPI spec."""
    errors: list[str] = []
    if not SDK_MANIFEST_PATH.exists():
        return DemoSurfaceCheck("sdk_manifest", False, errors=("sdk_manifest_missing",))

    manifest = json.loads(SDK_MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("governed") is not True:
        errors.append("sdk_manifest_not_governed")
    if manifest.get("source_spec") != "sdk/openapi/mullu.openapi.json":
        errors.append("sdk_source_spec_mismatch")
    languages = {item.get("language") for item in manifest.get("generators", [])}
    if languages != {"python", "typescript"}:
        errors.append("sdk_language_set_mismatch")

    return DemoSurfaceCheck(
        "sdk_manifest",
        not errors,
        details={"languages": sorted(str(language) for language in languages)},
        errors=tuple(errors),
    )


def validate_http_demo_routes() -> DemoSurfaceCheck:
    """Exercise local demo routes through FastAPI TestClient."""
    if str(MCOI_ROOT) not in sys.path:
        sys.path.insert(0, str(MCOI_ROOT))
    os.environ.setdefault("MULLU_ENV", "local_dev")
    os.environ.setdefault("MULLU_DB_BACKEND", "memory")
    os.environ.setdefault("MULLU_CERT_ENABLED", "true")
    os.environ.setdefault("MULLU_CERT_INTERVAL", "0")

    try:
        from fastapi.testclient import TestClient
        from mcoi_runtime.app.routers.deps import deps
        from mcoi_runtime.app.server import app
    except Exception:
        return DemoSurfaceCheck(
            "http_demo_routes",
            False,
            errors=("http_import_failed",),
        )

    trace_id = "public-demo-validator-trace"
    if deps.replay_recorder.get_trace(trace_id) is None:
        deps.replay_recorder.start_trace(trace_id)
        deps.replay_recorder.record_frame(trace_id, "add", {"a": 4, "b": 5}, {"result": 9})
        deps.replay_recorder.complete_trace(trace_id)

    client = TestClient(app)
    responses = {
        "sandbox_summary": client.get("/api/v1/sandbox/summary"),
        "sandbox_traces": client.get("/api/v1/sandbox/traces"),
        "sandbox_lineage": client.get("/api/v1/sandbox/lineage/sandbox-trace-budget-cutoff"),
        "sandbox_policy": client.get("/api/v1/sandbox/policy-evaluations"),
        "federation_summary": client.get("/api/v1/federation/summary"),
        "replay_determinism": client.post(
            f"/api/v1/replay/{trace_id}/determinism",
            json={"operations": {"add": {"kind": "add_numbers"}}},
        ),
    }

    errors: list[str] = []
    for route_id, response in responses.items():
        if response.status_code != 200:
            errors.append(f"{route_id}:status:{response.status_code}")
            continue
        payload = response.json()
        if payload.get("governed") is not True:
            errors.append(f"{route_id}:missing_governed_true")

    replay_payload = responses["replay_determinism"].json()
    if replay_payload.get("report", {}).get("deterministic") is not True:
        errors.append("replay_determinism:not_deterministic")

    federation_payload = responses["federation_summary"].json()
    if federation_payload.get("witness", {}).get("enforcement_receipt", {}).get("central_data_transfer") is not False:
        errors.append("federation_summary:central_transfer_not_false")

    return DemoSurfaceCheck(
        "http_demo_routes",
        not errors,
        details={"routes_checked": sorted(responses)},
        errors=tuple(errors),
    )


def validate_proof_coverage() -> DemoSurfaceCheck:
    """Validate proof matrix contains public demo surfaces and declared routes."""
    from scripts.proof_coverage_matrix import (
        discover_declared_routes,
        proof_coverage_matrix,
        validate_matrix_routes,
    )

    matrix = proof_coverage_matrix()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    errors = [f"missing_surface:{surface_id}" for surface_id in REQUIRED_PROOF_SURFACES if surface_id not in surfaces]
    errors.extend(f"missing_declared_route:{path}" for path in validate_matrix_routes(matrix, discover_declared_routes()))

    return DemoSurfaceCheck(
        "proof_coverage",
        not errors,
        details={
            "surface_count": matrix["coverage_summary"]["surface_count"],
            "required_surfaces": list(REQUIRED_PROOF_SURFACES),
        },
        errors=tuple(errors),
    )


def validate_benchmark_witness() -> DemoSurfaceCheck:
    """Validate offline gateway benchmark emits deterministic proof tradeoff witness."""
    from mcoi_runtime.core.gateway_benchmark_harness import GatewayBenchmarkHarness

    first = GatewayBenchmarkHarness().run()
    second = GatewayBenchmarkHarness().run()
    errors: list[str] = []
    if first != second:
        errors.append("benchmark_not_deterministic")
    if "proof_tradeoff_declared" not in first.get("invariants", []):
        errors.append("benchmark_missing_proof_tradeoff_invariant")
    if first.get("mode") != "offline_deterministic":
        errors.append("benchmark_mode_mismatch")

    return DemoSurfaceCheck(
        "benchmark_witness",
        not errors,
        details={"suite_id": first.get("suite_id"), "report_hash": first.get("report_hash")},
        errors=tuple(errors),
    )


def validate_compliance_alignment() -> DemoSurfaceCheck:
    """Validate compliance alignment matrix boundaries and evidence files."""
    from scripts.compliance_alignment_matrix import TARGET_FRAMEWORKS, load_matrix, validate_matrix

    matrix = load_matrix()
    errors = validate_matrix(matrix)
    return DemoSurfaceCheck(
        "compliance_alignment",
        not errors,
        details={
            "capability_count": len(matrix.get("capabilities", [])),
            "frameworks": sorted(TARGET_FRAMEWORKS),
            "claim_boundary": matrix.get("claim_boundary", {}),
        },
        errors=tuple(errors),
    )


def validate_public_demo_surfaces() -> PublicDemoSurfaceReport:
    """Run all local public demo validation checks."""
    checks = (
        validate_openapi_source(),
        validate_sdk_manifest(),
        validate_http_demo_routes(),
        validate_proof_coverage(),
        validate_benchmark_witness(),
        validate_compliance_alignment(),
    )
    return PublicDemoSurfaceReport(ready=all(check.passed for check in checks), checks=checks)


def write_report(path: Path, report: PublicDemoSurfaceReport) -> None:
    """Write a deterministic validation report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _stable_hash(document: dict[str, Any]) -> str:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{sha256(encoded.encode('utf-8')).hexdigest()}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local public demo surfaces.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Validation report output path.")
    args = parser.parse_args()

    report = validate_public_demo_surfaces()
    write_report(args.output, report)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
