"""LLM admin/observability endpoints: budget, history, bootstrap, circuit, models."""
from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, HTTPException

from mcoi_runtime.app.routers.llm._common import deps

router = APIRouter()
_MAX_LLM_HISTORY_READ_LIMIT = 500


def _llm_history_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


def _raise_llm_history_validation_error(error: ValueError) -> NoReturn:
    raise HTTPException(
        status_code=422,
        detail=_llm_history_error_detail("invalid llm history request", "llm_history_invalid_request"),
    ) from error


def _coerce_llm_history_limit(limit: object) -> int:
    if isinstance(limit, bool):
        raise ValueError("limit must be an integer")
    if isinstance(limit, int):
        value = limit
    elif isinstance(limit, str):
        normalized = limit.strip()
        if not normalized.isdecimal():
            raise ValueError("limit must be an integer")
        value = int(normalized)
    else:
        raise ValueError("limit must be an integer")
    if value < 0 or value > _MAX_LLM_HISTORY_READ_LIMIT:
        raise ValueError("limit is outside the allowed range")
    return value


# ═══ Budget & History ═══


@router.get("/api/v1/budget")
def budget_summary():
    """Budget status for all registered LLM budgets."""
    return deps.llm_bridge.budget_summary()


@router.get("/api/v1/llm/history")
def llm_history(limit: str = "50"):
    """Recent LLM invocation history."""
    try:
        read_limit = _coerce_llm_history_limit(limit)
    except ValueError as error:
        _raise_llm_history_validation_error(error)
    return {"invocations": deps.llm_bridge.invocation_history(limit=read_limit)}


# ═══ Phase 200A — Bootstrap Info Endpoint ═══


@router.get("/api/v1/bootstrap")
def bootstrap_info():
    """LLM bootstrap configuration and registered backends."""
    return {
        "default_backend": deps.llm_bootstrap_result.default_backend_name,
        "available_backends": list(deps.llm_bootstrap_result.backends.keys()),
        "registered_models": deps.llm_bootstrap_result.registered_models,
        "registered_providers": deps.llm_bootstrap_result.registered_providers,
        "skipped_model_registrations": deps.llm_bootstrap_result.skipped_model_registrations,
        "model_registration_failures": deps.llm_bootstrap_result.model_registration_failures,
        "field_encryption": deps.field_encryption_bootstrap,
        "config": {
            "default_model": deps.llm_bootstrap_result.config.default_model,
            "default_budget_max_cost": deps.llm_bootstrap_result.config.default_budget_max_cost,
            "max_tokens_per_call": deps.llm_bootstrap_result.config.max_tokens_per_call,
        },
    }


# ═══ Circuit Breaker Status ═══


@router.get("/api/v1/circuit-breaker")
def circuit_breaker_status():
    """LLM circuit breaker status."""
    return deps.llm_circuit.status()


# ═══ List Models ═══


@router.get("/api/v1/models")
def list_models():
    """List available models for routing."""
    return {
        "models": [
            {"id": p.model_id, "name": p.name, "provider": p.provider,
             "speed": p.speed_tier, "capability": p.capability_tier, "enabled": p.enabled}
            for p in sorted(deps.model_router._profiles.values(), key=lambda p: p.model_id)
        ],
        "summary": deps.model_router.summary(),
    }
