#!/usr/bin/env python3
"""Validate Agentic Service Harness read-only status route implementation.

Purpose: prove the implemented harness status endpoint is a read-only gateway
projection and does not admit UI, mutation endpoints, external adapters, or
high-risk authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway/server.py, gateway/agentic_service_harness_status.py,
gateway/agentic_service_harness_read_model_producer.py, and
gateway/agentic_service_harness_live_task_run_producer.py.
Invariants:
  - Exactly one GET route exposes /api/v1/harness/status.
  - No POST, PUT, PATCH, or DELETE route is admitted under /api/v1/harness.
  - The route reads through the runtime source binding, not directly from the
    static foundation fixture.
  - The projected payload is read-only, non-terminal, and free of the former
    route-implementation-pending blocker.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.agentic_service_harness_status import (  # noqa: E402
    ROUTE_ID,
    ROUTE_IMPLEMENTATION_BLOCKER,
    ROUTE_VERSION,
    build_agentic_service_harness_status_projection,
)


DEFAULT_SERVER = REPO_ROOT / "gateway" / "server.py"
DEFAULT_ROUTE_MODULE = REPO_ROOT / "gateway" / "agentic_service_harness_status.py"
DEFAULT_PRODUCER_MODULE = REPO_ROOT / "gateway" / "agentic_service_harness_read_model_producer.py"
ROUTE_PATH = "/api/v1/harness/status"
REQUIRED_RESPONSE_FIELDS = (
    "route_id",
    "route_version",
    "generated_at",
    "tenant_id",
    "organization_id",
    "project_id",
    "read_only",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
    "status",
    "blockers",
    "accounts",
    "projects",
    "repositories",
    "runs",
    "approvals",
    "receipts",
    "evidence",
    "result_summaries",
    "permission_snapshot",
    "producer_rehearsal",
    "validators",
    "next_action",
)
REQUIRED_ROUTE_MODULE_TERMS = (
    "AgenticServiceHarnessReadModelSource",
    "HarnessReadModelSource",
    "HarnessReadModelProducer",
    "HarnessProducerRehearsalSource",
    "AgenticServiceHarnessLocalTaskRunProducerRehearsal",
    "build_agentic_service_harness_status_projection",
    "ROUTE_ID",
    "ROUTE_VERSION",
    "ROUTE_IMPLEMENTATION_BLOCKER",
    "RUNTIME_SOURCE_BLOCKER",
    "PRODUCER_REHEARSAL_BLOCKER",
    "high_risk_authority_not_allowed",
    "secret_value_serialization_not_allowed",
    "terminal_closure_claim_not_allowed",
    "local_producer_rehearsal_unsafe",
    "producer_rehearsal",
)
REQUIRED_SERVER_TERMS = (
    "AgenticServiceHarnessReadModelSource",
    "AgenticServiceHarnessRuntimeReadModelProducer",
    "agentic_service_harness_read_model_source = AgenticServiceHarnessReadModelSource(",
    "runtime_producer=AgenticServiceHarnessRuntimeReadModelProducer()",
    "read_model_source=agentic_service_harness_read_model_source",
    "app.state.agentic_service_harness_read_model_source = agentic_service_harness_read_model_source",
)
REQUIRED_PRODUCER_MODULE_TERMS = (
    "AgenticServiceHarnessRuntimeReadModelProducer",
    "project_contract_to_read_model",
    "DEFAULT_CONTRACT_PATH",
    "examples/agentic_service_harness.read_only.json",
    "Runtime read-model producer is bound; keep route read-only.",
)
FORBIDDEN_ROUTE_PATTERNS = (
    ("harness_mutation_route", re.compile(r"@app\.(?:post|put|patch|delete)\(\"/api/v1/harness", re.IGNORECASE)),
    ("route_implementation_blocker_returned", re.compile(r"read_only_status_route_implementation_pending")),
)


@dataclass(frozen=True, slots=True)
class ReadOnlyStatusRouteValidation:
    """Deterministic validation result for the harness status route."""

    ok: bool
    errors: tuple[str, ...]
    route_path: str
    server_path: str
    route_module_path: str
    producer_module_path: str
    required_response_field_count: int
    validator_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_read_only_status_route(
    *,
    server_path: Path = DEFAULT_SERVER,
    route_module_path: Path = DEFAULT_ROUTE_MODULE,
    producer_module_path: Path = DEFAULT_PRODUCER_MODULE,
) -> ReadOnlyStatusRouteValidation:
    """Validate the route implementation and generated projection."""
    errors: list[str] = []
    try:
        server_text = server_path.read_text(encoding="utf-8")
        module_text = route_module_path.read_text(encoding="utf-8")
        producer_text = producer_module_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ReadOnlyStatusRouteValidation(
            ok=False,
            errors=(f"route implementation load failed: {exc}",),
            route_path=ROUTE_PATH,
            server_path=_path_label(server_path),
            route_module_path=_path_label(route_module_path),
            producer_module_path=_path_label(producer_module_path),
            required_response_field_count=0,
            validator_count=0,
        )

    _validate_server_route(server_text, errors)
    _require_all(server_text, REQUIRED_SERVER_TERMS, "server_runtime_source_term", errors)
    _require_all(module_text, REQUIRED_ROUTE_MODULE_TERMS, "route_module_term", errors)
    _require_all(producer_text, REQUIRED_PRODUCER_MODULE_TERMS, "producer_module_term", errors)
    _validate_forbidden_patterns(server_text, errors)
    payload = build_agentic_service_harness_status_projection()
    _validate_projection_payload(payload, errors)

    return ReadOnlyStatusRouteValidation(
        ok=not errors,
        errors=tuple(errors),
        route_path=ROUTE_PATH,
        server_path=_path_label(server_path),
        route_module_path=_path_label(route_module_path),
        producer_module_path=_path_label(producer_module_path),
        required_response_field_count=len(REQUIRED_RESPONSE_FIELDS),
        validator_count=len(payload.get("validators", ())) if isinstance(payload.get("validators"), list) else 0,
    )


def _validate_server_route(server_text: str, errors: list[str]) -> None:
    get_route_count = server_text.count(f'@app.get("{ROUTE_PATH}")')
    if get_route_count != 1:
        errors.append(f"GET route must appear exactly once, observed {get_route_count}")
    if "build_agentic_service_harness_status_projection" not in server_text:
        errors.append("server missing harness status projection builder import or call")


def _validate_forbidden_patterns(server_text: str, errors: list[str]) -> None:
    for pattern_name, pattern in FORBIDDEN_ROUTE_PATTERNS:
        if pattern.search(server_text):
            errors.append(f"forbidden {pattern_name}")


def _validate_projection_payload(payload: MappingLike, errors: list[str]) -> None:
    if not isinstance(payload, dict):
        errors.append("projection payload must be an object")
        return
    _require_all(payload.keys(), REQUIRED_RESPONSE_FIELDS, "response_field", errors)
    if payload.get("route_id") != ROUTE_ID:
        errors.append("route_id mismatch")
    if payload.get("route_version") != ROUTE_VERSION:
        errors.append("route_version mismatch")
    if payload.get("read_only") is not True:
        errors.append("read_only must be true")
    if payload.get("report_is_not_terminal_closure") is not True:
        errors.append("report_is_not_terminal_closure must be true")
    if payload.get("terminal_closure_required") is not True:
        errors.append("terminal_closure_required must be true")
    blockers = payload.get("blockers")
    if not isinstance(blockers, list):
        errors.append("blockers must be a list")
    elif ROUTE_IMPLEMENTATION_BLOCKER in blockers:
        errors.append("route implementation blocker must not be returned")
    validators = payload.get("validators")
    if not isinstance(validators, list) or not any(
        isinstance(validator, dict)
        and validator.get("validator_id") == "agentic-service-harness-read-only-status-route"
        for validator in validators
    ):
        errors.append("route implementation validator must be retained")
    producer_rehearsal = payload.get("producer_rehearsal")
    if not isinstance(producer_rehearsal, dict):
        errors.append("producer_rehearsal must be an object")
    elif producer_rehearsal.get("read_only") is not True:
        errors.append("producer_rehearsal.read_only must be true")
    elif producer_rehearsal.get("live_producer_implemented") is not False:
        errors.append("producer_rehearsal.live_producer_implemented must be false")
    elif producer_rehearsal.get("terminal_closure") is not False:
        errors.append("producer_rehearsal.terminal_closure must be false")


MappingLike = Any


def _require_all(
    observed: Any,
    required_values: Sequence[str],
    label: str,
    errors: list[str],
) -> None:
    for required_value in required_values:
        if required_value not in observed:
            errors.append(f"missing {label}: {required_value}")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the read-only status route validator."""
    args = build_arg_parser().parse_args(argv)
    validation = validate_read_only_status_route()
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS READ ONLY STATUS ROUTE VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS READ ONLY STATUS ROUTE INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
