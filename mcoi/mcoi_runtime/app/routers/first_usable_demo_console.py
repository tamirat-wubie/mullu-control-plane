"""Read-only First Usable Demo console route.

Purpose: expose the already-composed First Usable Demo console binding as a
standalone operator read model before mounting it into the default console.
Governance scope: static read-model projection only; no connector execution,
provider draft creation, external send, payment, memory write, deployment
mutation, worker dispatch, or live receipt append.
Invariants:
  - The route returns a governed, read-only, fixture-backed payload.
  - All effect-bearing authority fields remain false.
  - POST or other mutating methods are not registered.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from fastapi import APIRouter, HTTPException

from scripts.build_first_usable_demo_console_binding import build_first_usable_demo_console_binding

ROUTE_PATH = "/api/v1/console/personal-assistant/first-usable-demo"
_AUTHORITY_DRIFT_MESSAGE = "first usable demo console authority fields must remain false"
_FALSE_EFFECT_FIELDS = (
    "execution_allowed",
    "live_connector_execution_allowed",
    "external_send_allowed",
    "connector_mutation_allowed",
    "memory_write_allowed",
    "deployment_mutation_allowed",
    "customer_readiness_claim_allowed",
)

router = APIRouter()


def first_usable_demo_console_read_model() -> dict[str, Any]:
    """Return the static no-effect first-demo console binding read model."""

    payload = build_first_usable_demo_console_binding(generated_at=_utc_timestamp())
    return _with_route_boundary(payload)


def _with_route_boundary(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    binding = _mapping(data.get("first_usable_demo_binding"))
    effect_boundary = _mapping(data.get("effect_boundary"))
    first_demo = _mapping(data.get("first_usable_demo"))
    first_demo_effect_boundary = _mapping(first_demo.get("effect_boundary"))

    failures: list[str] = []
    failures.extend(_false_field_failures(binding, _FALSE_EFFECT_FIELDS))
    failures.extend(
        _false_field_failures(
            effect_boundary,
            (
                "execution_allowed",
                "live_connector_execution_allowed",
                "external_send_allowed",
                "memory_write_allowed",
                "deployment_mutation_allowed",
            ),
        )
    )
    failures.extend(
        _false_field_failures(
            first_demo_effect_boundary,
            (
                "execution_allowed",
                "live_connector_execution_allowed",
                "connector_mutation_allowed",
                "external_send_allowed",
                "money_movement_allowed",
                "memory_write_allowed",
                "deployment_mutation_allowed",
                "customer_readiness_claim_allowed",
                "public_launch_claim_allowed",
                "approval_is_execution",
            ),
        )
    )
    if failures:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "first_usable_demo_console_authority_drift",
                "message": _AUTHORITY_DRIFT_MESSAGE,
            },
        )

    data["route_boundary"] = {
        "route_path": ROUTE_PATH,
        "read_only": True,
        "fixture_backed": True,
        "governed": True,
        "method": "GET",
        "default_mounted": False,
        "execution_allowed": False,
        "live_connector_execution_allowed": False,
        "external_send_allowed": False,
        "provider_draft_creation_allowed": False,
        "payment_allowed": False,
        "memory_write_allowed": False,
        "deployment_mutation_allowed": False,
        "worker_dispatch_allowed": False,
        "live_receipt_append_allowed": False,
        "customer_readiness_claim_allowed": False,
        "next_action": "mount_into_default_console_after_standalone_route_green",
    }
    return data


def _false_field_failures(payload: Mapping[str, Any], fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if payload.get(field) is not False]


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


router.add_api_route(
    ROUTE_PATH,
    first_usable_demo_console_read_model,
    methods=["GET"],
    name="first_usable_demo_console_read_model",
)
