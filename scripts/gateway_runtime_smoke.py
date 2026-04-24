#!/usr/bin/env python3
"""Smoke probe for gateway runtime witness and capability worker signing.

Purpose: Verifies live gateway health, runtime witness publication, restricted
capability worker health, and signed capability request/response transport.
Governance scope: pilot/production gateway readiness claims.
Dependencies: standard-library HTTP client and gateway capability contracts.
Invariants:
  - Gateway health must be reachable before readiness can be claimed.
  - Runtime witness must expose signature and closure/anchor fields.
  - Capability worker must reject unsigned bypass by requiring signed requests.
  - Worker response signatures must verify before receipt content is trusted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from gateway.capability_isolation import (  # noqa: E402
    CapabilityIsolationPolicy,
    build_capability_execution_request,
    sign_capability_payload,
    verify_capability_signature,
)
from gateway.command_spine import capability_passport_for  # noqa: E402
from gateway.skill_dispatch import SkillIntent  # noqa: E402


@dataclass(frozen=True, slots=True)
class SmokeProbeResult:
    """One bounded smoke-probe result."""

    step: str
    passed: bool
    detail: str
    duration_ms: float


def run_probe(
    *,
    gateway_url: str,
    worker_url: str,
    worker_secret: str,
    tenant_id: str = "smoke-tenant",
    identity_id: str = "smoke-identity",
) -> list[SmokeProbeResult]:
    """Run gateway and capability-worker smoke checks."""
    results: list[SmokeProbeResult] = []

    def step(name: str, fn) -> None:
        started = time.monotonic()
        try:
            passed, detail = fn()
        except Exception as exc:
            passed = False
            detail = f"{type(exc).__name__}: {exc}"
        results.append(
            SmokeProbeResult(
                step=name,
                passed=passed,
                detail=detail,
                duration_ms=(time.monotonic() - started) * 1000,
            )
        )

    gateway_base = gateway_url.rstrip("/")
    worker_execute_url = worker_url.rstrip("/")
    worker_base = _worker_base_url(worker_execute_url)

    def gateway_health() -> tuple[bool, str]:
        status, payload, _ = _get_json(f"{gateway_base}/health")
        return status == 200 and payload.get("status") == "healthy", f"status={status} body_status={payload.get('status')}"

    def gateway_witness() -> tuple[bool, str]:
        status, payload, _ = _get_json(f"{gateway_base}/gateway/witness")
        required = (
            "witness_id",
            "gateway_status",
            "latest_command_event_hash",
            "latest_terminal_certificate_id",
            "signature_key_id",
            "signature",
        )
        missing = tuple(name for name in required if name not in payload)
        signature = str(payload.get("signature", ""))
        passed = status == 200 and not missing and signature.startswith("hmac-sha256:")
        return passed, f"status={status} missing={list(missing)} gateway_status={payload.get('gateway_status')}"

    def worker_health() -> tuple[bool, str]:
        status, payload, _ = _get_json(f"{worker_base}/health")
        return status == 200 and payload.get("status") == "healthy", f"status={status} worker_id={payload.get('worker_id')}"

    def worker_signed_execution() -> tuple[bool, str]:
        body = _capability_smoke_body(tenant_id=tenant_id, identity_id=identity_id)
        signature = sign_capability_payload(body, worker_secret)
        status, payload, headers, raw = _post_signed_json(
            worker_execute_url,
            body=body,
            signature=signature,
        )
        response_signature = _header_value(headers, "X-Mullu-Capability-Response-Signature")
        signature_valid = verify_capability_signature(raw, response_signature, worker_secret)
        result_payload = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        receipt = payload.get("receipt") if isinstance(payload.get("receipt"), dict) else {}
        passed = bool(
            status == 200
            and payload.get("status") == "succeeded"
            and signature_valid
            and receipt.get("evidence_refs")
        )
        detail = (
            f"status={status} worker_status={payload.get('status')} "
            f"receipt_id={receipt.get('receipt_id')} "
            f"receipt_status={result_payload.get('receipt_status')} "
            f"signature_valid={signature_valid}"
        )
        return passed, detail

    step("gateway health", gateway_health)
    step("gateway runtime witness", gateway_witness)
    step("capability worker health", worker_health)
    step("signed capability execution", worker_signed_execution)
    return results


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for runtime smoke probing."""
    parser = argparse.ArgumentParser(description="Probe Mullu gateway runtime and capability worker.")
    parser.add_argument("--gateway-url", default=os.environ.get("MULLU_GATEWAY_URL", "http://localhost:8001"))
    parser.add_argument(
        "--worker-url",
        default=os.environ.get("MULLU_CAPABILITY_WORKER_URL", "http://localhost:8010/capability/execute"),
    )
    parser.add_argument("--worker-secret", default=os.environ.get("MULLU_CAPABILITY_WORKER_SECRET", ""))
    parser.add_argument("--tenant-id", default="smoke-tenant")
    parser.add_argument("--identity-id", default="smoke-identity")
    args = parser.parse_args(argv)
    if not args.worker_secret:
        print("error: MULLU_CAPABILITY_WORKER_SECRET or --worker-secret is required", file=sys.stderr)
        return 2
    results = run_probe(
        gateway_url=args.gateway_url,
        worker_url=args.worker_url,
        worker_secret=args.worker_secret,
        tenant_id=args.tenant_id,
        identity_id=args.identity_id,
    )
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} {result.step} ({result.duration_ms:.1f} ms): {result.detail}")
    return 0 if all(result.passed for result in results) else 1


def _get_json(url: str) -> tuple[int, dict[str, Any], dict[str, str]]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            raw = response.read()
            return response.status, _loads_json(raw), dict(response.headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, _loads_json(raw), dict(exc.headers)


def _post_signed_json(
    url: str,
    *,
    body: bytes,
    signature: str,
) -> tuple[int, dict[str, Any], dict[str, str], bytes]:
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Mullu-Capability-Signature": signature,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
            return response.status, _loads_json(raw), dict(response.headers), raw
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, _loads_json(raw), dict(exc.headers), raw


def _loads_json(raw: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _header_value(headers: dict[str, str], name: str) -> str:
    """Return a header value using case-insensitive matching."""
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return ""


def _worker_base_url(worker_execute_url: str) -> str:
    parsed = urllib.parse.urlparse(worker_execute_url)
    path = parsed.path
    if path.endswith("/capability/execute"):
        path = path[: -len("/capability/execute")]
    rebuilt = parsed._replace(path=path.rstrip("/"), params="", query="", fragment="")
    return urllib.parse.urlunparse(rebuilt).rstrip("/")


def _capability_smoke_body(*, tenant_id: str, identity_id: str) -> bytes:
    intent = SkillIntent("financial", "send_payment", {"amount": "50"})
    boundary = CapabilityIsolationPolicy(environment="pilot").boundary_for(
        capability_passport_for("financial.send_payment")
    )
    request = build_capability_execution_request(
        intent=intent,
        tenant_id=tenant_id,
        identity_id=identity_id,
        boundary=boundary,
    )
    payload = {
        "request_id": request.request_id,
        "tenant_id": request.tenant_id,
        "identity_id": request.identity_id,
        "intent": dict(request.intent),
        "boundary": {
            "capability_id": request.boundary.capability_id,
            "execution_plane": request.boundary.execution_plane,
            "isolation_required": request.boundary.isolation_required,
            "network_policy": list(request.boundary.network_policy),
            "filesystem_policy": request.boundary.filesystem_policy,
            "max_runtime_seconds": request.boundary.max_runtime_seconds,
            "max_memory_mb": request.boundary.max_memory_mb,
            "service_account": request.boundary.service_account,
            "evidence_required": list(request.boundary.evidence_required),
        },
        "input_hash": request.input_hash,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
