"""Runtime bootstrap helpers for the governed server.

Purpose: isolate validation, tool registration, and structured output bootstrap logic.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: FastAPI exceptions, input validation contracts, tool registry, structured output engine.
Invariants: validation payload shape stays stable, default tool set stays deterministic, structured output schema set stays deterministic.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import HTTPException

from mcoi_runtime.core.input_validation import (
    InputSchema,
    InputValidator,
    RuleType,
    ValidationRule,
)
from mcoi_runtime.core.structured_output import OutputSchema, StructuredOutputEngine
from mcoi_runtime.core.tool_use import ToolDefinition, ToolParameter, ToolRegistry


def build_default_input_validator() -> InputValidator:
    """Build the default server request validator registry."""
    input_validator = InputValidator()
    input_validator.register(
        InputSchema(
            "api_request",
            "API Request",
            rules=(
                ValidationRule("tenant_id", RuleType.REQUIRED),
                ValidationRule("tenant_id", RuleType.TYPE_CHECK, value=str),
            ),
        )
    )
    input_validator.register(
        InputSchema(
            "completion",
            "LLM Completion",
            rules=(
                ValidationRule("prompt", RuleType.REQUIRED),
                ValidationRule("prompt", RuleType.MIN_LENGTH, value=1),
                ValidationRule("prompt", RuleType.MAX_LENGTH, value=100_000),
                ValidationRule("max_tokens", RuleType.MIN_VALUE, value=1),
                ValidationRule("max_tokens", RuleType.MAX_VALUE, value=100_000),
                ValidationRule("temperature", RuleType.MIN_VALUE, value=0.0),
                ValidationRule("temperature", RuleType.MAX_VALUE, value=2.0),
            ),
        )
    )
    input_validator.register(
        InputSchema(
            "webhook",
            "Webhook Subscribe",
            rules=(
                ValidationRule("url", RuleType.REQUIRED),
                ValidationRule("url", RuleType.PATTERN, value=r"^https?://"),
                ValidationRule("event_types", RuleType.REQUIRED),
            ),
        )
    )
    return input_validator


def validate_or_raise(
    *,
    input_validator: InputValidator,
    schema_id: str,
    data: dict[str, Any],
) -> None:
    """Validate request data against a schema; raise 422 if invalid."""
    result = input_validator.validate(schema_id, data)
    if not result.valid:
        raise HTTPException(
            422,
            detail={
                "error": "Validation failed",
                "validation_errors": result.to_dict()["errors"],
                "governed": True,
            },
        )


def calculator_handler(
    args: dict[str, Any],
    *,
    evaluate_expression_fn: Callable[[str], Any],
) -> dict[str, str]:
    """Evaluate calculator tool input with the bounded arithmetic engine."""
    expression = str(args.get("expression", "0"))
    return {"result": str(evaluate_expression_fn(expression))}


def register_default_tools(
    *,
    tool_registry: ToolRegistry,
    clock: Callable[[], str],
    evaluate_expression_fn: Callable[[str], Any],
) -> None:
    """Register the default utility tool set."""
    tool_registry.register(
        ToolDefinition(
            tool_id="calculator",
            name="Calculator",
            description="Evaluate a math expression",
            parameters=(
                ToolParameter(
                    name="expression",
                    param_type="string",
                    description="Math expression",
                ),
            ),
            category="utility",
        ),
        handler=lambda args: calculator_handler(
            args,
            evaluate_expression_fn=evaluate_expression_fn,
        ),
    )
    tool_registry.register(
        ToolDefinition(
            tool_id="get_time",
            name="Get Time",
            description="Get the current time",
            parameters=(),
            category="utility",
        ),
        handler=lambda args: {"time": clock()},
    )


def register_default_output_schemas(structured_output: StructuredOutputEngine) -> None:
    """Register the default structured output schemas."""
    structured_output.register(
        OutputSchema(
            schema_id="analysis",
            name="Analysis Output",
            fields={"summary": "string", "key_points": "array", "confidence": "number"},
            required_fields=("summary", "key_points"),
        )
    )
