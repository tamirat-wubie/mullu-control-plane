#!/usr/bin/env python3
"""Collect a Govern Cloud public route monitor receipt.

Purpose: turn public Govern Cloud read-route probing into a bounded evidence
artifact.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: standard-library HTTPS client, JSON receipt output, proxy policy.
Invariants:
  - Collection never mutates DNS, deployment state, workflows, or secrets.
  - Raw response bodies are not serialized; only digests and bounded public
    fields are recorded.
  - The monitor passes only when the two public read routes are healthy and the
    non-allowlisted evaluate route remains blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

try:
    from scripts.proxy_policy import ProxyEnvironmentBlocked, assert_proxy_environment_allowed
except ModuleNotFoundError:  # pragma: no cover - direct script execution path.
    from proxy_policy import ProxyEnvironmentBlocked, assert_proxy_environment_allowed


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "https://api.mullusi.com"
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "govern_cloud_public_route_monitor_receipt.json"
DEFAULT_SERVICE = "mullusi-govern-cloud-staging"
DEFAULT_API_VERSION = "2026.05.v1"
DEFAULT_EVALUATOR_VERSION = "govern-evaluator.v1"
MAX_BODY_BYTES = 65536

HttpRequester = Callable[[str, str], "HttpProbeResult"]


@dataclass(frozen=True, slots=True)
class HttpProbeResult:
    """Bounded HTTP response captured by one public route probe."""

    status_code: int | None
    headers: Mapping[str, str]
    body: bytes
    reached_endpoint: bool
    error: str


@dataclass(frozen=True, slots=True)
class RouteSpec:
    """Expected public route contract for one monitor probe."""

    route_id: str
    method: str
    path: str
    expected_status_code: int
    expected_fields: Mapping[str, str]


def collect_govern_cloud_public_route_monitor(
    *,
    base_url: str = DEFAULT_BASE_URL,
    expected_service: str = DEFAULT_SERVICE,
    expected_api: str = DEFAULT_API_VERSION,
    expected_evaluator: str = DEFAULT_EVALUATOR_VERSION,
    http_getter: HttpRequester | None = None,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Collect one Govern Cloud public route monitor receipt."""
    normalized_base_url = _require_base_url(base_url)
    observed_at = _format_utc(now_utc or datetime.now(UTC))
    route_specs = (
        RouteSpec(
            route_id="health",
            method="GET",
            path="/v1/health",
            expected_status_code=200,
            expected_fields={"status": "ok", "service": expected_service},
        ),
        RouteSpec(
            route_id="version",
            method="GET",
            path="/v1/version",
            expected_status_code=200,
            expected_fields={"api": expected_api, "evaluator": expected_evaluator},
        ),
        RouteSpec(
            route_id="blocked_evaluate",
            method="POST",
            path="/v1/govern/evaluate",
            expected_status_code=404,
            expected_fields={},
        ),
    )

    getter = http_getter or _urlopen_getter
    observations = [
        _route_observation(
            spec=spec,
            base_url=normalized_base_url,
            result=getter(spec.method, f"{normalized_base_url}{spec.path}"),
        )
        for spec in route_specs
    ]
    passed_route_count = sum(1 for item in observations if item["passed"] is True)
    failed_route_count = len(observations) - passed_route_count
    public_read_routes_verified = all(
        item["passed"] is True for item in observations if item["route_id"] in {"health", "version"}
    )
    blocked_route_guard_verified = any(
        item["route_id"] == "blocked_evaluate" and item["passed"] is True for item in observations
    )
    monitor_closed = public_read_routes_verified and blocked_route_guard_verified
    solver_outcome = "SolvedVerified" if monitor_closed else "AwaitingEvidence"
    proof_state = "Pass" if monitor_closed else "Fail"
    receipt_id = _receipt_id(
        observed_at=observed_at,
        base_url=normalized_base_url,
        monitor_closed=monitor_closed,
        observations=observations,
    )

    return {
        "schema_version": "govern_cloud.public_route_monitor_receipt.v1",
        "receipt_id": receipt_id,
        "generated_at": observed_at,
        "proof_state": proof_state,
        "solver_outcome": solver_outcome,
        "raw_secret_values_included": False,
        "monitor_surface": {
            "service": expected_service,
            "base_url": normalized_base_url,
            "public_routes": ["/v1/health", "/v1/version"],
            "blocked_routes": ["/v1/govern/evaluate"],
            "time_window": {"observed_at": observed_at},
        },
        "thresholds": {
            "health_status_code": 200,
            "version_status_code": 200,
            "blocked_route_status_code": 404,
            "missing_signal_policy": "explicit_not_observed",
        },
        "route_observations": observations,
        "summary": {
            "passed_route_count": passed_route_count,
            "failed_route_count": failed_route_count,
            "public_read_routes_verified": public_read_routes_verified,
            "blocked_route_guard_verified": blocked_route_guard_verified,
            "monitor_closed": monitor_closed,
        },
        "remediation": {
            "decision": "observe" if monitor_closed else "rollback_public_proxy",
            "rollback_path": (
                "If any public read-route monitor fails, set "
                "MULLU_GOVERN_CLOUD_PUBLIC_PROXY_ENABLED=false on the gateway, "
                "redeploy, and preserve the private Render service for evidence review."
            ),
        },
        "lineage": {
            "accepted_deltas": [
                {
                    "delta_id": f"delta-govern-cloud-public-route-monitor-{observed_at[:10]}",
                    "reason": _lineage_reason(monitor_closed),
                    "logged_in_lineage": True,
                }
            ],
            "rejected_deltas": [],
        },
    }


def write_monitor_receipt(receipt: Mapping[str, object], output_path: Path) -> Path:
    """Write one Govern Cloud public route monitor receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def _route_observation(*, spec: RouteSpec, base_url: str, result: HttpProbeResult) -> dict[str, object]:
    payload = _json_object(result.body)
    observed_fields = _bounded_observed_fields(payload, spec.expected_fields)
    status_matches = result.status_code == spec.expected_status_code
    fields_match = all(observed_fields.get(key) == expected for key, expected in spec.expected_fields.items())
    passed = result.reached_endpoint and status_matches and fields_match
    error = "" if passed else result.error
    if result.reached_endpoint and not status_matches:
        error = "unexpected_status_code"
    elif result.reached_endpoint and status_matches and not fields_match:
        error = "unexpected_response_contract"
    return {
        "route_id": spec.route_id,
        "method": spec.method,
        "url": f"{base_url}{spec.path}",
        "expected_status_code": spec.expected_status_code,
        "observed_status_code": result.status_code,
        "request_reached_endpoint": result.reached_endpoint,
        "passed": passed,
        "response_digest": _body_sha256(result.body) if result.body else "",
        "observed_json_fields": observed_fields,
        "error": error,
    }


def _urlopen_getter(method: str, url: str) -> HttpProbeResult:
    request = urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": "mullusi-govern-cloud-public-route-monitor/1.0"},
    )
    try:
        assert_proxy_environment_allowed()
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read(MAX_BODY_BYTES)
            return HttpProbeResult(
                status_code=int(response.status),
                headers={key.lower(): value for key, value in response.headers.items()},
                body=body,
                reached_endpoint=True,
                error="",
            )
    except urllib.error.HTTPError as exc:
        return HttpProbeResult(
            status_code=int(exc.code),
            headers={key.lower(): value for key, value in exc.headers.items()},
            body=exc.read(MAX_BODY_BYTES),
            reached_endpoint=True,
            error="http_error",
        )
    except ProxyEnvironmentBlocked:
        return HttpProbeResult(None, {}, b"", False, "proxy_environment_blocked")
    except (OSError, TimeoutError, urllib.error.URLError):
        return HttpProbeResult(None, {}, b"", False, "request_error")


def _json_object(body: bytes) -> Mapping[str, Any]:
    if not body:
        return {}
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _bounded_observed_fields(payload: Mapping[str, Any], expected_fields: Mapping[str, str]) -> dict[str, str]:
    allowed_fields = set(expected_fields) | {"detail"}
    observed: dict[str, str] = {}
    for key in sorted(allowed_fields):
        value = payload.get(key)
        if isinstance(value, str):
            observed[key] = value[:120]
    return observed


def _body_sha256(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _receipt_id(
    *,
    observed_at: str,
    base_url: str,
    monitor_closed: bool,
    observations: list[dict[str, object]],
) -> str:
    material = json.dumps(
        {
            "observed_at": observed_at,
            "base_url": base_url,
            "monitor_closed": monitor_closed,
            "route_statuses": [
                {
                    "route_id": item["route_id"],
                    "observed_status_code": item["observed_status_code"],
                    "passed": item["passed"],
                }
                for item in observations
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"govern-cloud-public-route-monitor-{hashlib.sha256(material).hexdigest()[:16]}"


def _lineage_reason(monitor_closed: bool) -> str:
    if monitor_closed:
        return "Recorded a non-mutating public route monitor with read routes healthy and evaluate route blocked."
    return "Recorded a non-mutating public route monitor and preserved the AwaitingEvidence boundary because route evidence was incomplete."


def _require_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    parsed = urllib.parse.urlsplit(normalized)
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError("base URL must include https scheme and hostname")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise RuntimeError("base URL must not include path, query, or fragment")
    if parsed.port is not None:
        raise RuntimeError("base URL must not include port")
    return f"https://{parsed.hostname.lower()}"


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse Govern Cloud public route monitor arguments."""
    parser = argparse.ArgumentParser(description="Collect Govern Cloud public route monitor evidence.")
    parser.add_argument("--base-url", default=os.environ.get("MULLU_GATEWAY_URL", DEFAULT_BASE_URL))
    parser.add_argument("--expected-service", default=os.environ.get("MULLU_GOVERN_CLOUD_EXPECTED_SERVICE", DEFAULT_SERVICE))
    parser.add_argument("--expected-api", default=os.environ.get("MULLU_GOVERN_CLOUD_EXPECTED_API", DEFAULT_API_VERSION))
    parser.add_argument(
        "--expected-evaluator",
        default=os.environ.get("MULLU_GOVERN_CLOUD_EXPECTED_EVALUATOR", DEFAULT_EVALUATOR_VERSION),
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    *,
    http_getter: HttpRequester | None = None,
    now_utc: datetime | None = None,
) -> int:
    """CLI entry point for Govern Cloud public route monitor collection."""
    args = parse_args(argv)
    receipt = collect_govern_cloud_public_route_monitor(
        base_url=args.base_url,
        expected_service=args.expected_service,
        expected_api=args.expected_api,
        expected_evaluator=args.expected_evaluator,
        http_getter=http_getter,
        now_utc=now_utc,
    )
    write_monitor_receipt(receipt, Path(args.output))
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=False))
    else:
        print(f"govern cloud public route monitor outcome: {receipt['solver_outcome']}")
    return 0 if receipt["solver_outcome"] == "SolvedVerified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
