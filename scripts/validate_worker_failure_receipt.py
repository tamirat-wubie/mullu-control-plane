#!/usr/bin/env python3
"""Validate the worker failure receipt contract.

Purpose: verify worker failure receipts remain non-terminal, recovery-oriented,
source-hash-bound, and schema-valid before worker failures can be summarized.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS, Foundation Mode, and
worker recovery boundaries.
Dependencies: gateway/worker_failure_receipt.py, gateway/worker_mesh.py,
schemas/worker_failure_receipt.schema.json,
examples/worker_failure_receipt.foundation.json, and scripts/validate_schemas.py.
Invariants:
  - Failure receipts cannot claim terminal closure.
  - Partial completion defaults to safe halt.
  - Completed units never exceed attempted units.
  - Source worker receipt hashes are preserved.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from gateway.worker_failure_receipt import (  # noqa: E402
    WORKER_FAILURE_RECEIPT_SCHEMA_REF,
    build_worker_failure_receipt,
)
from gateway.worker_mesh import (  # noqa: E402
    NetworkedWorkerMesh,
    WorkerDispatchRequest,
    WorkerHandlerResult,
    WorkerLease,
    WorkerLeaseBudget,
    WorkerLeaseScope,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "worker_failure_receipt.schema.json"
DEFAULT_EXAMPLE_PATH = WORKSPACE_ROOT / "examples" / "worker_failure_receipt.foundation.json"


def load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object or raise a path-specific validation error."""
    if not path.exists():
        raise FileNotFoundError(f"missing worker failure receipt artifact: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"worker failure receipt artifact must be an object: {path}")
    return payload


def validate_worker_failure_receipt(
    payload: dict[str, Any],
    *,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> list[str]:
    """Return deterministic validation errors for a worker failure receipt."""
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, payload)

    if payload.get("schema_ref") != WORKER_FAILURE_RECEIPT_SCHEMA_REF:
        errors.append("schema_ref must remain worker-failure-receipt v1")
    if payload.get("terminal_closure_required") is not True:
        errors.append("terminal_closure_required must be true")
    if payload.get("receipt_is_not_terminal_closure") is not True:
        errors.append("receipt_is_not_terminal_closure must be true")
    attempted_units = payload.get("attempted_units")
    completed_units = payload.get("completed_units")
    if isinstance(attempted_units, int) and isinstance(completed_units, int):
        if completed_units > attempted_units:
            errors.append("completed_units cannot exceed attempted_units")
    if payload.get("failure_state") == "partial_completion":
        if payload.get("partial_completion") is not True:
            errors.append("partial_completion state requires partial_completion true")
        if payload.get("recovery_action") != "safe_halt":
            errors.append("partial_completion must default to safe_halt recovery")
    if not payload.get("source_receipt_hash"):
        errors.append("source_receipt_hash is required")
    if payload.get("metadata", {}).get("raw_error_payload_exposed") is not False:
        errors.append("metadata.raw_error_payload_exposed must be false")
    return errors


def validate_generated_worker_failure_scenarios() -> list[str]:
    """Return errors for runtime-built worker failure boundary scenarios."""
    errors: list[str] = []
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-16T13:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        lambda _request: WorkerHandlerResult(
            status="failed",
            error="worker_timeout",
            evidence_refs=["worker:evidence:partial"],
        ),
    )
    worker_receipt = mesh.dispatch(lease.lease_id, _request())
    failure_receipt = build_worker_failure_receipt(
        worker_receipt,
        attempted_units=5,
        completed_units=2,
        generated_at="2026-06-16T13:02:00+00:00",
        metadata={"foundation_mode": True, "raw_error_payload_exposed": False},
    )

    if failure_receipt.failure_state != "partial_completion":
        errors.append("runtime partial failure must classify as partial_completion")
    if failure_receipt.recovery_action != "safe_halt":
        errors.append("runtime partial failure must use safe_halt recovery")
    if failure_receipt.source_receipt_hash != worker_receipt.receipt_hash:
        errors.append("runtime failure receipt must preserve source receipt hash")
    if failure_receipt.receipt_is_not_terminal_closure is not True:
        errors.append("runtime failure receipt must remain non-terminal")
    try:
        build_worker_failure_receipt(worker_receipt, attempted_units=1, completed_units=2)
    except ValueError as exc:
        if "completed_units_exceed_attempted" not in str(exc):
            errors.append("impossible unit count must fail with causal unit error")
    else:
        errors.append("impossible unit count must fail closed")
    return errors


def _lease() -> WorkerLease:
    return WorkerLease(
        worker_id="worker-failure-foundation",
        capability="repository.inspect_read_only",
        tenant_id="tenant-worker-failure",
        lease_id="lease-worker-failure-foundation",
        allowed_operations=["inspect"],
        forbidden_operations=["write"],
        budget=WorkerLeaseBudget(max_operations=3, max_cost=0.0),
        scope=WorkerLeaseScope(
            resource_refs=["repository:local"],
            data_classes=["repository_metadata"],
            network_allowlist=[],
        ),
        timeout_seconds=30,
        sandbox="local-read-only-repository",
        policy_refs=["policy:worker-failure-foundation"],
        receipt_schema_ref="urn:mullusi:schema:worker-mesh:1",
        verification_ref="verification:worker-failure-foundation",
        recovery_ref="recovery:operator-review",
        expires_at="2026-06-16T13:30:00+00:00",
        issued_at="2026-06-16T13:00:00+00:00",
    )


def _request() -> WorkerDispatchRequest:
    return WorkerDispatchRequest(
        request_id="worker-failure-foundation-request",
        tenant_id="tenant-worker-failure",
        capability="repository.inspect_read_only",
        operation="inspect",
        command_id="cmd-worker-failure-foundation",
        input_hash="sha256:" + "8" * 64,
        requested_at="2026-06-16T13:01:00+00:00",
    )


def main() -> int:
    """Validate the foundation worker failure receipt artifact and runtime builder."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--receipt",
        type=Path,
        default=DEFAULT_EXAMPLE_PATH,
        help="Path to a worker failure receipt JSON artifact.",
    )
    args = parser.parse_args()

    try:
        payload = load_json_object(args.receipt)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] worker_failure_receipt_load: {exc}")
        return 1

    checks = {
        "worker_failure_receipt_schema": validate_worker_failure_receipt(payload),
        "worker_failure_runtime_scenarios": validate_generated_worker_failure_scenarios(),
    }
    failed = False
    for check_name, errors in checks.items():
        if errors:
            failed = True
            for error in errors:
                print(f"[FAIL] {check_name}: {error}")
        else:
            print(f"[PASS] {check_name}")

    if failed:
        print("STATUS: failed")
        return 1
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
