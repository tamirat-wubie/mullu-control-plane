"""Agentic Service Harness status read model.

Purpose: project the validated harness foundation read model into the first
read-only gateway status route.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: examples/agentic_service_harness_read_models.foundation.json and
gateway.agentic_service_harness_live_task_run_producer.
Invariants:
  - The route projection is read-only and side-effect free.
  - High-risk authority, secret-like payloads, and terminal closure claims
    fail closed without echoing unsafe source collections.
  - Route implementation does not grant UI, mutation, adapter, branch, PR,
    merge, deploy, DNS, secret, or destructive-operation authority.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Protocol

from gateway.agentic_service_harness_live_task_run_producer import (
    AgenticServiceHarnessLocalTaskRunProducerRehearsal,
    REHEARSAL_REPORT_ID,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_READ_MODEL_PATH = REPO_ROOT / "examples" / "agentic_service_harness_read_models.foundation.json"

ROUTE_ID = "agentic_service_harness_status_read_model"
ROUTE_VERSION = 1
ROUTE_IMPLEMENTATION_VALIDATOR = {
    "validator_id": "agentic-service-harness-read-only-status-route",
    "command": "python scripts/validate_agentic_service_harness_read_only_status_route.py",
    "required_for_closure": True,
}
ROUTE_IMPLEMENTATION_BLOCKER = "read_only_status_route_implementation_pending"
RUNTIME_SOURCE_BLOCKER = "runtime_read_model_source_pending"
PRODUCER_REHEARSAL_BLOCKER = "local_producer_rehearsal_pending"
SAFE_STATUS_VALUES = {"SolvedVerified", "AwaitingEvidence", "GovernanceBlocked"}
COLLECTION_FIELDS = (
    "accounts",
    "projects",
    "repositories",
    "runs",
    "approvals",
    "receipts",
    "evidence",
    "result_summaries",
)
AUTHORITY_FALSE_PATHS = (
    ("projection_scope", "ui_created"),
    ("projection_scope", "mutation_endpoints_admitted"),
    ("projection_scope", "external_adapter_integrated"),
    ("projection_scope", "default_high_risk_authority"),
    ("permission_snapshot", "can_merge"),
    ("permission_snapshot", "can_deploy"),
    ("permission_snapshot", "can_mutate_dns"),
    ("permission_snapshot", "can_mutate_secrets"),
    ("permission_snapshot", "can_run_destructive_operations"),
)
RUN_AUTHORITY_FALSE_KEYS = (
    "executes_adapter",
    "creates_branch",
    "opens_pull_request",
    "permits_external_effect",
)
ALLOWED_SECRET_KEYS = {
    "can_mutate_secrets",
    "contains_secret_values",
    "secret_mutation_enabled",
    "secret_redaction_required",
    "secret_values_serialized",
}
FORBIDDEN_SECRET_KEY_TOKENS = (
    "access_token",
    "api_key",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "secret_value",
    "token",
)
FORBIDDEN_CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bsk-[A-Za-z0-9_=-]{8,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)


class HarnessReadModelSource(Protocol):
    """Read-only source protocol for harness status projections."""

    def read(self) -> dict[str, Any] | None:
        """Return one read-model snapshot or None when unavailable."""


class HarnessReadModelProducer(Protocol):
    """Read-only runtime producer protocol for harness status projections."""

    def produce(self) -> dict[str, Any] | None:
        """Produce one read-model snapshot or None when unavailable."""


class HarnessProducerRehearsalSource(Protocol):
    """Read-only producer rehearsal protocol for harness status projections."""

    def produce(self) -> dict[str, Any] | None:
        """Produce one local rehearsal report or None when unavailable."""


class AgenticServiceHarnessReadModelSource:
    """Runtime-local read-model source with foundation fixture fallback."""

    def __init__(
        self,
        *,
        foundation_path: Path = DEFAULT_READ_MODEL_PATH,
        runtime_producer: HarnessReadModelProducer | None = None,
    ) -> None:
        self._foundation_path = foundation_path
        self._runtime_read_model: dict[str, Any] | None = None
        self._runtime_producer = runtime_producer

    @property
    def has_runtime_read_model(self) -> bool:
        """Whether a runtime snapshot has been seeded in process memory."""
        return self._runtime_read_model is not None

    def replace_runtime_read_model(self, read_model: Mapping[str, Any]) -> None:
        """Seed one runtime snapshot without exposing an HTTP mutation route."""
        self._runtime_read_model = deepcopy(dict(read_model))

    def clear_runtime_read_model(self) -> None:
        """Return the source to foundation fixture fallback mode."""
        self._runtime_read_model = None

    def read(self) -> dict[str, Any] | None:
        """Read runtime snapshot or producer output, then fall back to fixture."""
        if self._runtime_read_model is not None:
            return deepcopy(self._runtime_read_model)
        if self._runtime_producer is not None:
            try:
                produced_read_model = self._runtime_producer.produce()
            except (OSError, ValueError, KeyError, TypeError, IndexError):
                produced_read_model = None
            if produced_read_model is not None:
                return deepcopy(produced_read_model)
        return _load_read_model(self._foundation_path)


def build_agentic_service_harness_status_projection(
    read_model_path: Path = DEFAULT_READ_MODEL_PATH,
    *,
    read_model_source: HarnessReadModelSource | Mapping[str, Any] | None = None,
    producer_rehearsal_source: HarnessProducerRehearsalSource | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the bounded read-only harness status route projection."""
    source = _read_source(read_model_path, read_model_source)
    producer_rehearsal, producer_rehearsal_blockers = _read_producer_rehearsal(
        producer_rehearsal_source,
    )
    if source is None:
        return _empty_projection(
            status="AwaitingEvidence",
            blockers=tuple(dict.fromkeys(("missing_read_model_source", *producer_rehearsal_blockers))),
            next_action="Restore validated harness read-model source before route closure.",
            producer_rehearsal=producer_rehearsal,
        )

    blockers = tuple(dict.fromkeys((*_source_blockers(source), *producer_rehearsal_blockers)))
    unsafe = any(
        blocker
        in {
            "high_risk_authority_not_allowed",
            "secret_value_serialization_not_allowed",
            "terminal_closure_claim_not_allowed",
            "local_producer_rehearsal_unsafe",
        }
        for blocker in blockers
    )
    status = _status_for_blockers(blockers)
    if unsafe:
        return _empty_projection(
            status=status,
            blockers=blockers,
            source=source,
            next_action="Repair unsafe harness read-model source before route projection.",
            producer_rehearsal=producer_rehearsal,
        )
    return _projection_from_source(
        source,
        status=status,
        blockers=blockers,
        producer_rehearsal=producer_rehearsal,
    )


def _read_source(
    read_model_path: Path,
    read_model_source: HarnessReadModelSource | Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if read_model_source is None:
        return _load_read_model(read_model_path)
    if isinstance(read_model_source, Mapping):
        return deepcopy(dict(read_model_source))
    return read_model_source.read()


def _load_read_model(read_model_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(read_model_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _read_producer_rehearsal(
    producer_rehearsal_source: HarnessProducerRehearsalSource | Mapping[str, Any] | None,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    if producer_rehearsal_source is None:
        producer_rehearsal_source = AgenticServiceHarnessLocalTaskRunProducerRehearsal()
    if isinstance(producer_rehearsal_source, Mapping):
        report = deepcopy(dict(producer_rehearsal_source))
    else:
        try:
            produced_report = producer_rehearsal_source.produce()
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            produced_report = None
        report = deepcopy(produced_report) if isinstance(produced_report, Mapping) else {}
    if not report:
        return _empty_producer_rehearsal(), (PRODUCER_REHEARSAL_BLOCKER,)
    blockers = _producer_rehearsal_blockers(report)
    if blockers:
        return _empty_producer_rehearsal(status="GovernanceBlocked"), blockers
    return _producer_rehearsal_projection(report), ()


def _source_blockers(source: Mapping[str, Any]) -> tuple[str, ...]:
    blockers: list[str] = []
    scope = source.get("projection_scope")
    if not isinstance(scope, Mapping) or not scope.get("tenant_id") or not scope.get("project_id"):
        blockers.append("missing_tenant_or_project_scope")
    blockers.extend(_source_summary_blockers(source))
    if _has_high_risk_authority(source):
        blockers.append("high_risk_authority_not_allowed")
    if _has_secret_like_payload(source):
        blockers.append("secret_value_serialization_not_allowed")
    if _has_terminal_closure_claim(source):
        blockers.append("terminal_closure_claim_not_allowed")
    return tuple(dict.fromkeys(blockers))


def _source_summary_blockers(source: Mapping[str, Any]) -> tuple[str, ...]:
    observed: list[str] = []
    for summary in _objects(source.get("result_summaries")):
        for blocker in _strings(summary.get("blockers")):
            if blocker not in {ROUTE_IMPLEMENTATION_BLOCKER}:
                observed.append(blocker)
    return tuple(observed)


def _producer_rehearsal_blockers(report: Mapping[str, Any]) -> tuple[str, ...]:
    blockers: list[str] = []
    if report.get("report_id") != REHEARSAL_REPORT_ID:
        blockers.append("local_producer_rehearsal_unsafe")
    if report.get("producer_state") != "local_dry_run_ready":
        blockers.append("local_producer_rehearsal_unsafe")
    if report.get("planning_only") is not True:
        blockers.append("local_producer_rehearsal_unsafe")
    if report.get("local_rehearsal_only") is not True:
        blockers.append("local_producer_rehearsal_unsafe")
    if report.get("live_producer_implemented") is not False:
        blockers.append("local_producer_rehearsal_unsafe")
    if report.get("terminal_closure") is not False:
        blockers.append("terminal_closure_claim_not_allowed")
    if report.get("report_is_not_terminal_closure") is not True:
        blockers.append("terminal_closure_claim_not_allowed")
    effect_boundary = _mapping(report.get("effect_boundary"))
    if effect_boundary.get("network_policy") != "none":
        blockers.append("local_producer_rehearsal_unsafe")
    for flag_name in (
        "ui_created",
        "mutation_endpoints_admitted",
        "external_adapter_integrated",
        "branch_write_enabled",
        "pull_request_creation_enabled",
        "deployment_enabled",
        "dns_mutation_enabled",
        "secret_mutation_enabled",
        "destructive_operation_enabled",
        "runtime_state_written",
    ):
        if effect_boundary.get(flag_name) is not False:
            blockers.append("local_producer_rehearsal_unsafe")
    if _has_secret_like_payload(report):
        blockers.append("secret_value_serialization_not_allowed")
    return tuple(dict.fromkeys(blockers))


def _has_high_risk_authority(source: Mapping[str, Any]) -> bool:
    for parent_key, flag_key in AUTHORITY_FALSE_PATHS:
        parent = source.get(parent_key)
        if isinstance(parent, Mapping) and parent.get(flag_key) is not False:
            return True
    for run in _objects(source.get("runs")):
        if any(run.get(flag_key) is not False for flag_key in RUN_AUTHORITY_FALSE_KEYS):
            return True
    return False


def _has_secret_like_payload(payload: Any) -> bool:
    for _path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if (
            any(token in key_lower for token in FORBIDDEN_SECRET_KEY_TOKENS)
            and key_lower not in ALLOWED_SECRET_KEYS
        ):
            return True
        if isinstance(value, str) and any(pattern.search(value) for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS):
            return True
    return False


def _has_terminal_closure_claim(source: Mapping[str, Any]) -> bool:
    if source.get("report_is_not_terminal_closure") is not True:
        return True
    if source.get("terminal_closure_required") is not True:
        return True
    for _path, key, value in _walk_json(source):
        key_lower = key.lower()
        if key_lower == "terminal_closure" and value is not False:
            return True
        if key_lower == "receipt_is_not_terminal_closure" and value is not True:
            return True
    return False


def _status_for_blockers(blockers: tuple[str, ...]) -> str:
    if any(
        blocker
        in {
            "high_risk_authority_not_allowed",
            "secret_value_serialization_not_allowed",
            "terminal_closure_claim_not_allowed",
            "local_producer_rehearsal_unsafe",
        }
        for blocker in blockers
    ):
        return "GovernanceBlocked"
    if blockers:
        return "AwaitingEvidence"
    return "SolvedVerified"


def _projection_from_source(
    source: Mapping[str, Any],
    *,
    status: str,
    blockers: tuple[str, ...],
    producer_rehearsal: Mapping[str, Any],
) -> dict[str, Any]:
    scope = _mapping(source.get("projection_scope"))
    payload: dict[str, Any] = {
        "route_id": ROUTE_ID,
        "route_version": ROUTE_VERSION,
        "generated_at": str(source.get("generated_at", "")),
        "tenant_id": str(scope.get("tenant_id", "")),
        "organization_id": str(scope.get("organization_id", "")),
        "project_id": str(scope.get("project_id", "")),
        "read_only": True,
        "report_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "status": _safe_status(status),
        "blockers": list(blockers),
        **{
            collection_field: deepcopy(list(_objects(source.get(collection_field))))
            for collection_field in COLLECTION_FIELDS
        },
        "permission_snapshot": deepcopy(_mapping(source.get("permission_snapshot"))),
        "producer_rehearsal": deepcopy(dict(producer_rehearsal)),
        "validators": _validators_with_route_implementation(source.get("validators")),
        "next_action": _next_action(source, blockers),
    }
    return payload


def _empty_projection(
    *,
    status: str,
    blockers: tuple[str, ...],
    next_action: str,
    source: Mapping[str, Any] | None = None,
    producer_rehearsal: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    scope = _mapping(source.get("projection_scope")) if isinstance(source, Mapping) else {}
    return {
        "route_id": ROUTE_ID,
        "route_version": ROUTE_VERSION,
        "generated_at": str(source.get("generated_at", "")) if isinstance(source, Mapping) else "",
        "tenant_id": str(scope.get("tenant_id", "")),
        "organization_id": str(scope.get("organization_id", "")),
        "project_id": str(scope.get("project_id", "")),
        "read_only": True,
        "report_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "status": _safe_status(status),
        "blockers": list(dict.fromkeys(blockers)),
        **{collection_field: [] for collection_field in COLLECTION_FIELDS},
        "permission_snapshot": {},
        "producer_rehearsal": dict(producer_rehearsal or _empty_producer_rehearsal()),
        "validators": [dict(ROUTE_IMPLEMENTATION_VALIDATOR)],
        "next_action": next_action,
    }


def _producer_rehearsal_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    effect_boundary = _mapping(report.get("effect_boundary"))
    scope = _mapping(report.get("scope"))
    run_projection = _mapping(report.get("run_projection"))
    return {
        "report_id": str(report.get("report_id", "")),
        "producer_state": str(report.get("producer_state", "")),
        "solver_outcome": str(report.get("solver_outcome", "")),
        "source_fixture_ref": str(report.get("source_fixture_ref", "")),
        "tenant_id": str(scope.get("tenant_id", "")),
        "project_id": str(scope.get("project_id", "")),
        "run_id": str(run_projection.get("run_id", "")),
        "read_only": True,
        "local_rehearsal_only": True,
        "live_producer_implemented": False,
        "terminal_closure": False,
        "network_policy": "none",
        "effect_boundary": {
            "ui_created": False,
            "mutation_endpoints_admitted": False,
            "external_adapter_integrated": False,
            "branch_write_enabled": False,
            "pull_request_creation_enabled": False,
            "deployment_enabled": False,
            "dns_mutation_enabled": False,
            "secret_mutation_enabled": False,
            "destructive_operation_enabled": False,
            "runtime_state_written": False,
            "network_policy": str(effect_boundary.get("network_policy", "")),
        },
        "next_action": str(report.get("next_action", "")),
    }


def _empty_producer_rehearsal(*, status: str = "AwaitingEvidence") -> dict[str, Any]:
    return {
        "report_id": REHEARSAL_REPORT_ID,
        "producer_state": status,
        "solver_outcome": "AwaitingEvidence",
        "source_fixture_ref": "",
        "tenant_id": "",
        "project_id": "",
        "run_id": "",
        "read_only": True,
        "local_rehearsal_only": True,
        "live_producer_implemented": False,
        "terminal_closure": False,
        "network_policy": "none",
        "effect_boundary": {
            "ui_created": False,
            "mutation_endpoints_admitted": False,
            "external_adapter_integrated": False,
            "branch_write_enabled": False,
            "pull_request_creation_enabled": False,
            "deployment_enabled": False,
            "dns_mutation_enabled": False,
            "secret_mutation_enabled": False,
            "destructive_operation_enabled": False,
            "runtime_state_written": False,
            "network_policy": "none",
        },
        "next_action": "Validate local producer rehearsal before live producer admission.",
    }


def _next_action(source: Mapping[str, Any], blockers: tuple[str, ...]) -> str:
    source_next_action = source.get("next_action")
    if isinstance(source_next_action, str) and source_next_action.strip():
        return source_next_action.strip()
    if not blockers:
        return "Runtime read-model source is bound; keep route read-only."
    return "Resolve harness status blockers before route closure."


def _validators_with_route_implementation(validators: Any) -> list[dict[str, Any]]:
    observed = [deepcopy(validator) for validator in _objects(validators)]
    if not any(validator.get("validator_id") == ROUTE_IMPLEMENTATION_VALIDATOR["validator_id"] for validator in observed):
        observed.append(dict(ROUTE_IMPLEMENTATION_VALIDATOR))
    return observed


def _safe_status(status: str) -> str:
    if status in SAFE_STATUS_VALUES:
        return status
    return "AwaitingEvidence"


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _objects(collection: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(collection, list):
        return ()
    return tuple(item for item in collection if isinstance(item, dict))


def _strings(collection: Any) -> tuple[str, ...]:
    if not isinstance(collection, list):
        return ()
    return tuple(str(item) for item in collection if str(item).strip())


def _walk_json(payload: Any, path: str = "$") -> Iterable[tuple[str, str, Any]]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), value
            yield from _walk_json(value, child_path)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            yield from _walk_json(item, f"{path}[{index}]")
