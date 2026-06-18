#!/usr/bin/env python3
"""Collect a personal-assistant public console probe receipt.

Purpose: turn the public personal-assistant console route probe into a
schema-backed, repeatable witness artifact.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: standard-library HTTPS client, JSON receipt output, proxy policy.
Invariants:
  - Collection never mutates DNS, deployment state, workflows, connectors, or secrets.
  - Raw response bodies are not serialized; only digests and bounded public fields are recorded.
  - SolvedVerified requires the JSON and HTML routes to be reachable and the no-effect lane boundary to hold.
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
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "personal_assistant_public_console_probe_receipt.json"
JSON_ROUTE = "/api/v1/console/personal-assistant"
HTML_ROUTE = "/api/v1/console/personal-assistant/view"
EXPECTED_LANE_IDS = (
    "request_intake_whqr",
    "skill_registry",
    "approval_queue",
    "memory_observation",
    "read_only_projection",
    "draft_projection",
    "teamops_shared_inbox",
    "github_codex_review",
    "research_source_compare",
    "math_reasoning",
    "schedule_planning",
    "operator_console",
)
NO_EFFECT_FLAGS = (
    "execution_allowed",
    "live_connector_execution_allowed",
    "connector_mutation_allowed",
    "external_effect_allowed",
    "customer_readiness_claim_allowed",
    "nested_mind_live_activation_allowed",
)
MAX_BODY_BYTES = 65536

HttpRequester = Callable[[str, str], "HttpProbeResult"]


@dataclass(frozen=True, slots=True)
class HttpProbeResult:
    """Bounded HTTP response captured by one public console probe."""

    status_code: int | None
    headers: Mapping[str, str]
    body: bytes
    reached_endpoint: bool
    error: str


def collect_personal_assistant_public_console_probe(
    *,
    base_url: str = DEFAULT_BASE_URL,
    http_getter: HttpRequester | None = None,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Collect one personal-assistant public console probe receipt."""
    normalized_base_url = _require_base_url(base_url)
    observed_at = _format_utc(now_utc or datetime.now(UTC))
    getter = http_getter or _urlopen_getter
    json_result = getter("GET", f"{normalized_base_url}{JSON_ROUTE}")
    html_result = getter("GET", f"{normalized_base_url}{HTML_ROUTE}")
    json_observation, no_effect_boundary_verified, observed_lane_count = _json_observation(
        normalized_base_url,
        json_result,
    )
    html_observation = _html_observation(normalized_base_url, html_result)
    observations = [json_observation, html_observation]
    console_read_model_verified = json_observation["passed"] is True
    html_view_verified = html_observation["passed"] is True
    probe_closed = console_read_model_verified and html_view_verified and no_effect_boundary_verified
    proof_state = "Pass" if probe_closed else "Fail"
    solver_outcome = "SolvedVerified" if probe_closed else "AwaitingEvidence"
    receipt_id = _receipt_id(
        observed_at=observed_at,
        base_url=normalized_base_url,
        probe_closed=probe_closed,
        observations=observations,
    )

    return {
        "schema_version": "personal_assistant.public_console_probe_receipt.v1",
        "receipt_id": receipt_id,
        "generated_at": observed_at,
        "proof_state": proof_state,
        "solver_outcome": solver_outcome,
        "raw_secret_values_included": False,
        "probe_surface": {
            "surface_id": "personal_assistant_public_console",
            "base_url": normalized_base_url,
            "json_route": JSON_ROUTE,
            "html_route": HTML_ROUTE,
            "time_window": {"observed_at": observed_at},
        },
        "thresholds": {
            "json_status_code": 200,
            "html_status_code": 200,
            "expected_lane_count": len(EXPECTED_LANE_IDS),
            "missing_signal_policy": "explicit_not_observed",
        },
        "route_observations": observations,
        "summary": {
            "console_read_model_verified": console_read_model_verified,
            "html_view_verified": html_view_verified,
            "no_effect_boundary_verified": no_effect_boundary_verified,
            "expected_lane_count": len(EXPECTED_LANE_IDS),
            "observed_lane_count": observed_lane_count,
            "probe_closed": probe_closed,
        },
        "effect_boundary": {
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_effect_allowed": False,
            "customer_readiness_claim_allowed": False,
            "nested_mind_live_activation_allowed": False,
            "secret_values_serialized": False,
            "raw_response_bodies_serialized": False,
        },
        "remediation": {
            "decision": "observe" if probe_closed else "repair_console_route",
            "next_action": _next_action(probe_closed),
        },
        "lineage": {
            "accepted_deltas": [
                {
                    "delta_id": f"delta-personal-assistant-public-console-probe-{observed_at[:10]}",
                    "reason": _lineage_reason(probe_closed),
                    "logged_in_lineage": True,
                }
            ],
            "rejected_deltas": [],
        },
    }


def write_probe_receipt(receipt: Mapping[str, object], output_path: Path) -> Path:
    """Write one personal-assistant public console probe receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def _json_observation(base_url: str, result: HttpProbeResult) -> tuple[dict[str, object], bool, int]:
    payload = _json_object(result.body)
    lane_status = _object(payload.get("lane_status"))
    lanes = _list_of_objects(lane_status.get("lanes"))
    lane_ids = tuple(str(lane.get("lane_id")) for lane in lanes if isinstance(lane.get("lane_id"), str))
    observed_lane_count = _bounded_int(lane_status.get("lane_count"))
    root_flags_clear = all(lane_status.get(flag) is False for flag in NO_EFFECT_FLAGS)
    lane_flags_clear = all(all(lane.get(flag) is False for flag in NO_EFFECT_FLAGS) for lane in lanes)
    receipt_required = bool(lanes) and all(lane.get("receipt_required") is True for lane in lanes)
    no_effect_boundary_verified = (
        observed_lane_count == len(EXPECTED_LANE_IDS)
        and lane_ids == EXPECTED_LANE_IDS
        and root_flags_clear
        and lane_flags_clear
        and receipt_required
    )
    public_fields = {
        "console_id": _bounded_text(payload.get("console_id")),
        "status": _bounded_text(payload.get("status")),
        "solver_outcome": _bounded_text(payload.get("solver_outcome")),
        "lane_count": observed_lane_count,
    }
    passed = (
        result.reached_endpoint
        and result.status_code == 200
        and public_fields["console_id"] == "personal_assistant_console_foundation"
        and public_fields["status"] == "foundation_read_only"
        and public_fields["solver_outcome"] == "SolvedVerified"
        and payload.get("governed") is True
        and no_effect_boundary_verified
    )
    error = "" if passed else _route_error(result, status_matched=result.status_code == 200)
    if result.reached_endpoint and result.status_code == 200 and not no_effect_boundary_verified:
        error = "no_effect_boundary_mismatch"
    return (
        {
            "route_id": "console_json",
            "method": "GET",
            "url": f"{base_url}{JSON_ROUTE}",
            "expected_status_code": 200,
            "observed_status_code": result.status_code,
            "request_reached_endpoint": result.reached_endpoint,
            "passed": passed,
            "response_digest": _body_sha256(result.body) if result.body else "",
            "observed_public_fields": public_fields,
            "error": error,
        },
        no_effect_boundary_verified,
        observed_lane_count,
    )


def _html_observation(base_url: str, result: HttpProbeResult) -> dict[str, object]:
    body = _bounded_body_text(result.body)
    public_fields = {
        "title_present": "Mullu Personal Assistant Console" in body,
        "foundation_lanes_present": "Foundation Lanes" in body,
        "read_only_status_present": "foundation_read_only" in body,
        "json_link_present": JSON_ROUTE in body,
        "execution_allowed_false_present": "Execution Allowed" in body and "False" in body,
    }
    passed = result.reached_endpoint and result.status_code == 200 and all(public_fields.values())
    return {
        "route_id": "console_html",
        "method": "GET",
        "url": f"{base_url}{HTML_ROUTE}",
        "expected_status_code": 200,
        "observed_status_code": result.status_code,
        "request_reached_endpoint": result.reached_endpoint,
        "passed": passed,
        "response_digest": _body_sha256(result.body) if result.body else "",
        "observed_public_fields": public_fields,
        "error": "" if passed else _route_error(result, status_matched=result.status_code == 200),
    }


def _urlopen_getter(method: str, url: str) -> HttpProbeResult:
    request = urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": "mullusi-personal-assistant-public-console-probe/1.0"},
    )
    try:
        assert_proxy_environment_allowed()
        with urllib.request.urlopen(request, timeout=10) as response:
            return HttpProbeResult(
                status_code=int(response.status),
                headers={key.lower(): value for key, value in response.headers.items()},
                body=response.read(MAX_BODY_BYTES),
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


def _route_error(result: HttpProbeResult, *, status_matched: bool) -> str:
    if not result.reached_endpoint:
        return result.error or "endpoint_not_reached"
    if not status_matched:
        return "unexpected_status_code"
    return "unexpected_response_contract"


def _json_object(body: bytes) -> Mapping[str, Any]:
    if not body:
        return {}
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _object(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_objects(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _bounded_body_text(body: bytes) -> str:
    try:
        return body.decode("utf-8", errors="replace")[:8192]
    except AttributeError:
        return ""


def _bounded_int(value: Any) -> int:
    return max(value, 0) if isinstance(value, int) else 0


def _bounded_text(value: Any) -> str:
    return str(value)[:160] if isinstance(value, str) else ""


def _body_sha256(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _receipt_id(
    *,
    observed_at: str,
    base_url: str,
    probe_closed: bool,
    observations: list[dict[str, object]],
) -> str:
    material = json.dumps(
        {
            "observed_at": observed_at,
            "base_url": base_url,
            "probe_closed": probe_closed,
            "routes": [
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
    return f"personal-assistant-public-console-probe-{hashlib.sha256(material).hexdigest()[:16]}"


def _next_action(probe_closed: bool) -> str:
    if probe_closed:
        return "continue observing the public read-only console route; do not infer live execution authority"
    return "repair or deploy the read-only console route, then rerun this probe before claiming closure"


def _lineage_reason(probe_closed: bool) -> str:
    if probe_closed:
        return "Recorded a non-mutating personal-assistant public console probe with JSON and HTML read routes verified."
    return "Recorded a non-mutating personal-assistant public console probe and preserved AwaitingEvidence because route evidence was incomplete."


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
    """Parse personal-assistant public console probe arguments."""
    parser = argparse.ArgumentParser(description="Collect personal-assistant public console probe evidence.")
    parser.add_argument("--base-url", default=os.environ.get("MULLU_GATEWAY_URL", DEFAULT_BASE_URL))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    *,
    http_getter: HttpRequester | None = None,
    now_utc: datetime | None = None,
) -> int:
    """CLI entry point for personal-assistant public console probe collection."""
    args = parse_args(argv)
    receipt = collect_personal_assistant_public_console_probe(
        base_url=args.base_url,
        http_getter=http_getter,
        now_utc=now_utc,
    )
    write_probe_receipt(receipt, Path(args.output))
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=False))
    else:
        print(f"personal-assistant public console probe outcome: {receipt['solver_outcome']}")
    return 0 if receipt["solver_outcome"] == "SolvedVerified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
