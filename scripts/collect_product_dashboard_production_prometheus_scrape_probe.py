#!/usr/bin/env python3
"""Collect a product dashboard production Prometheus scrape probe receipt.

Purpose: turn public dashboard metric endpoint probing into a bounded evidence
artifact.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: DNS resolution, standard-library HTTPS client, JSON receipt
output.
Invariants:
  - Collection never mutates DNS, deployment state, workflows, or secrets.
  - Endpoint errors are bounded before serialization.
  - Production closure is claimed only when DNS, health, and required
    Prometheus metric families are observed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "product_dashboard_production_prometheus_scrape_probe_receipt.json"
DEFAULT_GATEWAY_URL = "https://api.mullusi.com"
DEFAULT_HOST = "api.mullusi.com"
MAX_BODY_BYTES = 1_048_576

REQUIRED_METRIC_FAMILIES: tuple[str, ...] = (
    "mullu_requests_governed_total",
    "mullu_errors_total",
    "mullu_uptime_seconds",
    "mullu_health_score",
    "mullu_active_tenants",
    "mullu_llm_requests_total",
    "mullu_llm_latency_p99_seconds",
    "mullu_llm_tokens_total",
    "mullu_llm_budget_utilization_ratio",
    "mullu_policy_violations_total",
    "mullu_circuit_breaker_open",
    "mullu_audit_events_total",
    "mullu_active_agents",
    "mullu_tasks_completed_total",
    "mullu_memory_ops_total",
    "mullu_chain_success_rate",
)

Resolver = Callable[[str], tuple[str, ...]]
HttpGetter = Callable[[str], "HttpProbeResult"]


@dataclass(frozen=True, slots=True)
class HttpProbeResult:
    """Bounded HTTP response captured by one endpoint probe."""

    status_code: int | None
    headers: Mapping[str, str]
    body: bytes
    reached_endpoint: bool
    error: str


def collect_production_prometheus_scrape_probe(
    *,
    gateway_url: str = DEFAULT_GATEWAY_URL,
    host: str = DEFAULT_HOST,
    resolver: Resolver | None = None,
    http_getter: HttpGetter | None = None,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Collect one production dashboard Prometheus scrape probe receipt."""
    normalized_url = _require_gateway_url(gateway_url)
    normalized_host = _require_host(host)
    if _host_from_url(normalized_url) != normalized_host:
        raise RuntimeError("gateway URL host must match DNS probe host")

    observed_at = _format_utc(now_utc or datetime.now(UTC))
    dns_resolution = _resolve_dns(normalized_host, resolver or _socket_resolver)
    metrics_endpoint = f"{normalized_url}/metrics"
    health_endpoint = f"{normalized_url}/health"

    if dns_resolution["status"] == "resolved":
        metrics_result = (http_getter or _urlopen_getter)(metrics_endpoint)
        health_result = (http_getter or _urlopen_getter)(health_endpoint)
    else:
        metrics_result = HttpProbeResult(None, {}, b"", False, "dns_unresolved")
        health_result = HttpProbeResult(None, {}, b"", False, "dns_unresolved")

    metrics_probe = _metrics_probe_payload(metrics_result)
    health_probe = _health_probe_payload(health_result)
    observed_families = set(metrics_probe["observed_metric_families"])
    required_families = set(REQUIRED_METRIC_FAMILIES)
    missing_families = tuple(sorted(required_families - observed_families))
    production_claim_closed = (
        dns_resolution["status"] == "resolved"
        and metrics_probe["request_reached_endpoint"] is True
        and metrics_probe["status_code"] == 200
        and not missing_families
        and health_probe["request_reached_endpoint"] is True
        and health_probe["status_code"] == 200
    )

    blockers = _blockers(
        host=normalized_host,
        metrics_endpoint=metrics_endpoint,
        dns_resolution=dns_resolution,
        metrics_probe=metrics_probe,
        health_probe=health_probe,
        missing_families=missing_families,
    )
    closure_state = _closure_state(dns_resolution, production_claim_closed)
    proof_state = "Pass" if production_claim_closed else "Fail"
    solver_outcome = "SolvedVerified" if production_claim_closed else "AwaitingEvidence"
    receipt_id = _receipt_id(
        observed_at=observed_at,
        host=normalized_host,
        closure_state=closure_state,
        missing_families=missing_families,
    )

    return {
        "schema_version": "product_dashboard.production_prometheus_scrape_probe_receipt.v1",
        "receipt_id": receipt_id,
        "generated_at": observed_at,
        "proof_state": proof_state,
        "solver_outcome": solver_outcome,
        "raw_reasoning_included": False,
        "probe": {
            "probe_kind": "public_https_prometheus_scrape",
            "metrics_endpoint": metrics_endpoint,
            "health_endpoint": health_endpoint,
            "dns_name": normalized_host,
            "observed_at": observed_at,
            "dns_resolution": dns_resolution,
            "metrics_http_probe": metrics_probe,
            "health_http_probe": health_probe,
        },
        "production_boundary": {
            "public_production_claim": "claimed" if production_claim_closed else "not_claimed",
            "deployment_status_ref": "DEPLOYMENT_STATUS.md",
            "deployment_witness_state": "AwaitingEvidence" if production_claim_closed else "not-published",
            "api_health_endpoint_state": "observed" if production_claim_closed else "not-declared",
            "gateway_target_state": "SolvedVerified" if production_claim_closed else "AwaitingEvidence",
            "required_evidence": [
                "resolvable_dns_name",
                "production_https_scrape_sample",
                "health_endpoint_response_contract",
                "runtime_conformance_certificate",
                "deployment_witness",
                "operator_approval_ref",
            ],
        },
        "blockers": blockers,
        "summary": {
            "closure_state": closure_state,
            "required_family_count": len(REQUIRED_METRIC_FAMILIES),
            "observed_family_count": len(observed_families),
            "missing_family_count": len(missing_families),
            "production_claim_closed": production_claim_closed,
        },
        "lineage": {
            "accepted_deltas": [
                {
                    "delta_id": f"delta-product-dashboard-production-prometheus-scrape-probe-{observed_at[:10]}",
                    "reason": _lineage_reason(production_claim_closed, dns_resolution),
                    "logged_in_lineage": True,
                }
            ],
            "rejected_deltas": [],
        },
    }


def write_probe_receipt(receipt: Mapping[str, object], output_path: Path) -> Path:
    """Write one production Prometheus scrape probe receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def _resolve_dns(host: str, resolver: Resolver) -> dict[str, object]:
    try:
        addresses = resolver(host)
    except OSError:
        addresses = ()
        status = "unresolved"
        detail = "remote name could not be resolved"
    else:
        status = "resolved" if addresses else "unresolved"
        detail = "addresses resolved" if addresses else "remote name could not be resolved"
    return {
        "status": status,
        "resolver_result_count": len(addresses),
        "detail": detail,
    }


def _socket_resolver(host: str) -> tuple[str, ...]:
    addresses = {
        str(result[4][0])
        for result in socket.getaddrinfo(host, None)
        if result[4] and result[4][0]
    }
    return tuple(sorted(addresses))


def _urlopen_getter(url: str) -> HttpProbeResult:
    request = urllib.request.Request(url, headers={"User-Agent": "mullusi-product-dashboard-probe/1.0"})
    try:
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
    except (OSError, TimeoutError, urllib.error.URLError):
        return HttpProbeResult(None, {}, b"", False, "request_error")


def _metrics_probe_payload(result: HttpProbeResult) -> dict[str, object]:
    text = _decode_prometheus_body(result.body)
    observed = tuple(sorted(_metric_family_names_from_prometheus_text(text)))
    return {
        "attempted": True,
        "request_reached_endpoint": result.reached_endpoint,
        "status_code": result.status_code,
        "content_type": result.headers.get("content-type", ""),
        "body_sha256": _body_sha256(result.body) if result.body else "",
        "sample_family_count": len(observed),
        "observed_metric_families": list(observed),
        "missing_metric_families": sorted(set(REQUIRED_METRIC_FAMILIES) - set(observed)),
        "error": result.error,
    }


def _health_probe_payload(result: HttpProbeResult) -> dict[str, object]:
    return {
        "attempted": True,
        "request_reached_endpoint": result.reached_endpoint,
        "status_code": result.status_code,
        "content_type": result.headers.get("content-type", ""),
        "body_sha256": _body_sha256(result.body) if result.body else "",
        "error": result.error,
    }


def _metric_family_names_from_prometheus_text(text: str) -> set[str]:
    names: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"# TYPE\s+([a-zA-Z_:][a-zA-Z0-9_:]*)\s+", line)
        if match:
            names.add(match.group(1))
    return names


def _decode_prometheus_body(body: bytes) -> str:
    try:
        return body.decode("utf-8", errors="replace")
    except LookupError:
        return ""


def _body_sha256(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _blockers(
    *,
    host: str,
    metrics_endpoint: str,
    dns_resolution: Mapping[str, object],
    metrics_probe: Mapping[str, object],
    health_probe: Mapping[str, object],
    missing_families: tuple[str, ...],
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    if dns_resolution["status"] != "resolved":
        blockers.append(
            {
                "blocker_id": "product-dashboard-production-prometheus-dns-unresolved",
                "kind": "dns_unresolved",
                "surface": host,
                "detail": "DNS resolution returned no endpoint, so the production metrics scrape could not collect a sample.",
                "required_next_action": f"publish or repair the {host} DNS target, then rerun the production Prometheus scrape probe",
            }
        )
    if metrics_probe["request_reached_endpoint"] is not True:
        blockers.append(
            {
                "blocker_id": "product-dashboard-production-prometheus-endpoint-unreachable",
                "kind": "endpoint_unreachable",
                "surface": metrics_endpoint,
                "detail": "The metrics endpoint is unreachable until DNS and upstream gateway publication are closed.",
                "required_next_action": "collect a fresh HTTPS Prometheus sample after deployment witness publication",
            }
        )
    if metrics_probe["request_reached_endpoint"] is True and metrics_probe["status_code"] != 200:
        blockers.append(
            {
                "blocker_id": "product-dashboard-production-prometheus-status",
                "kind": "metrics_status_not_ok",
                "surface": metrics_endpoint,
                "detail": "The metrics endpoint responded but did not return HTTP 200.",
                "required_next_action": "repair the production metrics endpoint status, then rerun the scrape probe",
            }
        )
    if metrics_probe["request_reached_endpoint"] is True and missing_families:
        blockers.append(
            {
                "blocker_id": "product-dashboard-production-prometheus-missing-families",
                "kind": "missing_metric_families",
                "surface": metrics_endpoint,
                "detail": f"Missing required metric families: {', '.join(missing_families)}",
                "required_next_action": "deploy the dashboard metric projection and rerun the production scrape probe",
            }
        )
    if health_probe["request_reached_endpoint"] is True and health_probe["status_code"] != 200:
        blockers.append(
            {
                "blocker_id": "product-dashboard-production-health-status",
                "kind": "health_status_not_ok",
                "surface": metrics_endpoint.replace("/metrics", "/health"),
                "detail": "The health endpoint responded but did not return HTTP 200.",
                "required_next_action": "repair the production health endpoint, then rerun the scrape probe",
            }
        )
    return blockers


def _closure_state(dns_resolution: Mapping[str, object], production_claim_closed: bool) -> str:
    if production_claim_closed:
        return "production_scrape_verified"
    if dns_resolution["status"] != "resolved":
        return "production_scrape_awaiting_dns"
    return "production_scrape_awaiting_endpoint"


def _lineage_reason(production_claim_closed: bool, dns_resolution: Mapping[str, object]) -> str:
    if production_claim_closed:
        return "Recorded a non-mutating production Prometheus scrape probe with all required dashboard metric families observed."
    if dns_resolution["status"] != "resolved":
        return "Recorded a non-mutating production Prometheus scrape probe and preserved the AwaitingEvidence boundary because DNS did not resolve."
    return "Recorded a non-mutating production Prometheus scrape probe and preserved the AwaitingEvidence boundary because endpoint evidence was incomplete."


def _receipt_id(
    *,
    observed_at: str,
    host: str,
    closure_state: str,
    missing_families: tuple[str, ...],
) -> str:
    material = json.dumps(
        {
            "observed_at": observed_at,
            "host": host,
            "closure_state": closure_state,
            "missing_families": missing_families,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"product-dashboard-production-prometheus-scrape-probe-{hashlib.sha256(material).hexdigest()[:16]}"


def _require_gateway_url(gateway_url: str) -> str:
    normalized = gateway_url.strip().rstrip("/")
    parsed = urllib.parse.urlsplit(normalized)
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError("gateway URL must include https scheme and hostname")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise RuntimeError("gateway URL must not include path, query, or fragment")
    if parsed.port is not None:
        raise RuntimeError("gateway URL must not include port")
    return f"https://{parsed.hostname.lower()}"


def _require_host(host: str) -> str:
    normalized = host.strip().lower()
    if not normalized:
        raise RuntimeError("DNS probe host is required")
    if normalized.startswith(("https://", "http://")) or "/" in normalized or ":" in normalized:
        raise RuntimeError("DNS probe host must be a host name only")
    if "." not in normalized:
        raise RuntimeError("DNS probe host must be fully qualified")
    return normalized


def _host_from_url(gateway_url: str) -> str:
    parsed = urllib.parse.urlsplit(gateway_url)
    if not parsed.hostname:
        raise RuntimeError("gateway URL must include a host")
    return parsed.hostname.lower()


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse production scrape probe arguments."""
    parser = argparse.ArgumentParser(description="Collect product dashboard production Prometheus scrape evidence.")
    parser.add_argument("--gateway-url", default=os.environ.get("MULLU_GATEWAY_URL", DEFAULT_GATEWAY_URL))
    parser.add_argument("--host", default=os.environ.get("MULLU_GATEWAY_HOST", DEFAULT_HOST))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    *,
    resolver: Resolver | None = None,
    http_getter: HttpGetter | None = None,
    now_utc: datetime | None = None,
) -> int:
    """CLI entry point for production Prometheus scrape probe collection."""
    args = parse_args(argv)
    receipt = collect_production_prometheus_scrape_probe(
        gateway_url=args.gateway_url,
        host=args.host,
        resolver=resolver,
        http_getter=http_getter,
        now_utc=now_utc,
    )
    write_probe_receipt(receipt, Path(args.output))
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=False))
    else:
        print(f"production Prometheus scrape outcome: {receipt['solver_outcome']}")
    return 0 if receipt["solver_outcome"] == "SolvedVerified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
