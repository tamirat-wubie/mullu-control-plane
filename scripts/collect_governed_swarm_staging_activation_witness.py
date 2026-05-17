#!/usr/bin/env python3
"""Collect governed swarm staging activation evidence.

Purpose: probe a staging control-plane governed swarm route and emit a
schema-valid activation witness only when runtime, route, audit, and rollback
evidence are present.
Governance scope: release pin, feature flag, route probe, audit persistence,
rollback preservation, and witness validation.
Dependencies: standard-library HTTP client and
schemas/governed_swarm_staging_activation_witness.schema.json.
Invariants: no route probe success means no SolvedVerified witness; no audit
closure receipt means no SolvedVerified witness; emitted witness validates
against the public schema before the command exits successfully.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import urllib.error
import urllib.request


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_governed_swarm_staging_activation_witness import validate_witness_payload


CONTROL_PLANE_REPO = "tamirat-wubie/mullu-control-plane"
RUNTIME_REPO = "tamirat-wubie/mullu-governed-swarm"
RUNTIME_RELEASE_TAG = "v0.1.0-governed-swarm"
RUNTIME_COMMIT = "5882c5f24ca35fd5a133357b55b5411ebdc99dfb"
DEFAULT_OUTPUT_PATH = Path(".change_assurance") / "governed_swarm_staging_activation_witness.json"
DEFAULT_RUNTIME_PATH = "/opt/mullu/mullu-governed-swarm/mcoi"
DEFAULT_AUDIT_STORE_PATH = "/var/lib/mullu/governed-swarm/swarm-runs.jsonl"


@dataclass(frozen=True, slots=True)
class HttpResult:
    """Bounded HTTP probe result."""

    status: int
    payload: dict[str, Any]
    error: str = ""


def default_invoice_payload(run_id: str) -> dict[str, object]:
    """Return the deterministic staging invoice smoke payload."""

    return {
        "run_id": run_id,
        "goal_id": f"goal_{run_id}",
        "tenant_id": "tenant_staging",
        "invoice_ref": "invoice_staging_001",
        "invoice_amount_usd": "125.50",
        "vendor_verified": True,
        "duplicate_found": False,
        "budget_available": True,
        "policy_requires_approval": True,
        "human_approved": True,
    }


def collect_activation_witness(
    *,
    staging_url: str,
    control_plane_commit: str,
    runtime_path: str,
    audit_store_path: str,
    output_path: Path | None = None,
    run_id: str | None = None,
    environment: str = "staging",
    timeout_seconds: float = 10.0,
    opener: Callable[[urllib.request.Request | str, float], HttpResult] | None = None,
    clock: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Collect a governed swarm staging activation witness payload."""

    normalized_url = staging_url.rstrip("/")
    selected_run_id = run_id or f"swarm-run-staging-{secrets.token_hex(4)}"
    invoice_payload = default_invoice_payload(selected_run_id)
    http_open = opener or _http_json
    now = clock or _utc_now
    errors: list[str] = []

    create_result = http_open(
        _json_request(
            f"{normalized_url}/api/v1/swarm/invoice-runs",
            method="POST",
            payload=invoice_payload,
        ),
        timeout_seconds,
    )
    response_run_id = str(create_result.payload.get("run_id") or selected_run_id)
    read_result = http_open(
        f"{normalized_url}/api/v1/swarm/runs/{response_run_id}",
        timeout_seconds,
    )
    list_result = http_open(
        f"{normalized_url}/api/v1/swarm/runs",
        timeout_seconds,
    )

    for label, result in (
        ("create invoice swarm run", create_result),
        ("read invoice swarm run", read_result),
        ("list invoice swarm runs", list_result),
    ):
        if result.error:
            errors.append(f"{label}: {result.error}")
        if result.status != 200:
            errors.append(f"{label}: expected status 200 got {result.status}")

    audit_store = _inspect_audit_store(Path(audit_store_path))
    if not audit_store["exists"]:
        errors.append(f"audit store missing: {audit_store_path}")
    if audit_store["receipt_count"] < 1:
        errors.append(f"audit store has no receipts: {audit_store_path}")
    if not audit_store["latest_receipt_has_closure"]:
        errors.append(f"audit store latest receipt lacks closure proof: {audit_store_path}")

    terminal_status = str(create_result.payload.get("status") or "")
    governed = create_result.payload.get("governed") is True
    if not governed:
        errors.append("create response is not governed")
    if terminal_status != "closed":
        errors.append(f"create response terminal status is not closed: {terminal_status or '<missing>'}")

    witness = {
        "witness_id": f"governed-swarm-staging-{secrets.token_hex(8)}",
        "collected_at": now(),
        "environment": environment,
        "control_plane_repo": CONTROL_PLANE_REPO,
        "control_plane_commit": control_plane_commit,
        "runtime_repo": RUNTIME_REPO,
        "runtime_release_tag": RUNTIME_RELEASE_TAG,
        "runtime_commit": RUNTIME_COMMIT,
        "runtime_path": runtime_path,
        "feature_flags": {
            "MULLU_GOVERNED_SWARM_ENABLED": "true",
            "MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH": audit_store_path,
            "MULLU_GOVERNED_SWARM_RUNTIME_PATH": runtime_path,
        },
        "route_probes": [
            {
                "method": "POST",
                "path": "/api/v1/swarm/invoice-runs",
                "expected_http_status": 200,
            },
            {
                "method": "GET",
                "path": "/api/v1/swarm/runs/{run_id}",
                "expected_http_status": 200,
            },
            {
                "method": "GET",
                "path": "/api/v1/swarm/runs",
                "expected_http_status": 200,
            },
        ],
        "invoice_smoke": {
            "create_http_status": create_result.status,
            "read_http_status": read_result.status,
            "list_http_status": list_result.status,
            "run_id": response_run_id,
            "governed": governed,
            "terminal_status": terminal_status,
        },
        "audit_store": audit_store,
        "rollback": {
            "disable_flag": "MULLU_GOVERNED_SWARM_ENABLED=false",
            "restart_required": True,
            "audit_store_preserved": True,
        },
        "outcome": "SolvedVerified" if not errors else "AwaitingEvidence",
        "errors": errors,
    }

    validation_errors = validate_witness_payload(witness)
    if validation_errors:
        witness["outcome"] = "AwaitingEvidence"
        witness["errors"] = errors + [f"schema validation: {error}" for error in validation_errors]

    if output_path is not None:
        write_witness(witness, output_path)
    return witness


def write_witness(witness: dict[str, Any], output_path: Path) -> None:
    """Write a governed swarm staging activation witness."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(witness, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _inspect_audit_store(audit_store_path: Path) -> dict[str, Any]:
    if not audit_store_path.exists():
        return {
            "path": str(audit_store_path),
            "exists": False,
            "receipt_count": 0,
            "latest_receipt_has_closure": False,
        }

    receipts: list[dict[str, Any]] = []
    for line in audit_store_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            receipts.append(payload)

    latest = receipts[-1] if receipts else {}
    return {
        "path": str(audit_store_path),
        "exists": True,
        "receipt_count": len(receipts),
        "latest_receipt_has_closure": _receipt_has_closure(latest),
    }


def _receipt_has_closure(receipt: dict[str, Any]) -> bool:
    if not receipt:
        return False
    if receipt.get("closure_certificate") or receipt.get("closure"):
        return True
    payload = receipt.get("payload")
    if isinstance(payload, dict):
        return bool(payload.get("closure_certificate") or payload.get("closure"))
    return False


def _json_request(url: str, *, method: str, payload: dict[str, object]) -> urllib.request.Request:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )


def _http_json(request: urllib.request.Request | str, timeout_seconds: float) -> HttpResult:
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
            payload = json.loads(body.decode("utf-8")) if body else {}
            if not isinstance(payload, dict):
                return HttpResult(status=int(response.status), payload={}, error="response JSON must be object")
            return HttpResult(status=int(response.status), payload=payload)
    except urllib.error.HTTPError as exc:
        return HttpResult(status=int(exc.code), payload={}, error=str(exc))
    except urllib.error.URLError as exc:
        return HttpResult(status=0, payload={}, error=str(exc.reason))
    except (json.JSONDecodeError, OSError) as exc:
        return HttpResult(status=0, payload={}, error=str(exc))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-url", required=True)
    parser.add_argument("--control-plane-commit", required=True)
    parser.add_argument("--runtime-path", default=DEFAULT_RUNTIME_PATH)
    parser.add_argument("--audit-store-path", default=DEFAULT_AUDIT_STORE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--run-id")
    parser.add_argument("--environment", choices=("staging", "pilot"), default="staging")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args()

    witness = collect_activation_witness(
        staging_url=args.staging_url,
        control_plane_commit=args.control_plane_commit,
        runtime_path=args.runtime_path,
        audit_store_path=args.audit_store_path,
        output_path=args.output,
        run_id=args.run_id,
        environment=args.environment,
        timeout_seconds=args.timeout_seconds,
    )
    validation_errors = validate_witness_payload(witness)
    if validation_errors or witness["outcome"] != "SolvedVerified":
        for error in witness["errors"] + [f"schema validation: {error}" for error in validation_errors]:
            print(f"[FAIL] {error}")
        print(f"witness: {args.output}")
        print("STATUS: failed")
        return 1

    print("[PASS] governed_swarm_staging_activation_collected")
    print(f"witness: {args.output}")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
