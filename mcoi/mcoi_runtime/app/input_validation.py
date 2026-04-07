"""Input Validation — Centralized request validation for all API endpoints.

Purpose: Reject malformed, oversized, or potentially malicious payloads
    before they reach business logic.  Catches injection patterns, schema
    violations, and resource abuse at the API boundary.
Governance scope: request ingress validation only.
Dependencies: Starlette/FastAPI middleware.
Invariants:
  - Validation runs before any business logic (middleware layer).
  - Oversized payloads are rejected without reading the full body.
  - Field-level constraints are configurable per endpoint.
  - Rejection responses never echo back the invalid input.
  - Thread-safe — stateless per-request.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


@dataclass(frozen=True)
class ValidationRule:
    """A single field validation rule."""

    field_name: str
    max_length: int = 0  # 0 = no limit
    min_length: int = 0
    pattern: str = ""  # Regex pattern the field must match
    required: bool = False
    forbidden_patterns: tuple[str, ...] = ()  # Patterns that must NOT match


@dataclass(frozen=True)
class EndpointValidation:
    """Validation rules for a specific endpoint."""

    path_prefix: str  # e.g., "/api/v1/llm"
    methods: frozenset[str] = frozenset({"POST", "PUT", "PATCH"})
    max_body_size: int = 1_048_576  # 1MB default
    rules: tuple[ValidationRule, ...] = ()
    max_json_depth: int = 10


# ── Common dangerous patterns ──────────────────────────────────

_SQL_INJECTION_PATTERNS = (
    r"(?i)\b(union\s+select|drop\s+table|insert\s+into|delete\s+from|update\s+.*set)\b",
    r"(?i)(\bor\b\s+\d+\s*=\s*\d+)",
    r";\s*--",
)

_COMMAND_INJECTION_PATTERNS = (
    r"[;&|`]",  # Shell metacharacters
    r"\$\(",  # Command substitution
    r"\beval\b",
)

_PATH_TRAVERSAL_PATTERNS = (
    r"\.\./",
    r"\.\.\\",
)

COMMON_INJECTION_PATTERNS = _SQL_INJECTION_PATTERNS + _COMMAND_INJECTION_PATTERNS + _PATH_TRAVERSAL_PATTERNS


@dataclass(frozen=True)
class ValidationResult:
    """Result of request validation."""

    valid: bool
    error: str = ""
    field: str = ""


def validate_json_depth(data: Any, max_depth: int, _current: int = 0) -> bool:
    """Check that JSON nesting depth doesn't exceed max_depth."""
    if _current > max_depth:
        return False
    if isinstance(data, dict):
        return all(validate_json_depth(v, max_depth, _current + 1) for v in data.values())
    if isinstance(data, list):
        return all(validate_json_depth(v, max_depth, _current + 1) for v in data)
    return True


def validate_field(value: Any, rule: ValidationRule) -> ValidationResult:
    """Validate a single field against a rule."""
    if value is None or value == "":
        if rule.required:
            return ValidationResult(valid=False, error="required field missing", field=rule.field_name)
        return ValidationResult(valid=True)

    str_value = str(value)

    if rule.max_length > 0 and len(str_value) > rule.max_length:
        return ValidationResult(
            valid=False, error="field exceeds maximum length",
            field=rule.field_name,
        )

    if rule.min_length > 0 and len(str_value) < rule.min_length:
        return ValidationResult(
            valid=False, error="field below minimum length",
            field=rule.field_name,
        )

    if rule.pattern:
        if not re.match(rule.pattern, str_value):
            return ValidationResult(
                valid=False, error="field format invalid",
                field=rule.field_name,
            )

    for forbidden in rule.forbidden_patterns:
        if re.search(forbidden, str_value):
            return ValidationResult(
                valid=False, error="field contains forbidden pattern",
                field=rule.field_name,
            )

    return ValidationResult(valid=True)


def validate_body(body: dict[str, Any], rules: tuple[ValidationRule, ...]) -> ValidationResult:
    """Validate a request body against a set of rules."""
    for rule in rules:
        value = body.get(rule.field_name)
        result = validate_field(value, rule)
        if not result.valid:
            return result
    return ValidationResult(valid=True)


class RequestValidator:
    """Configurable request validation engine.

    Usage:
        validator = RequestValidator()
        validator.register(EndpointValidation(
            path_prefix="/api/v1/llm",
            max_body_size=512_000,
            rules=(
                ValidationRule("prompt", max_length=50000, required=True),
                ValidationRule("tenant_id", max_length=128, pattern=r"^[a-zA-Z0-9_-]+$"),
            ),
        ))

        result = validator.validate(path="/api/v1/llm", method="POST", body={"prompt": "test"})
    """

    DEFAULT_MAX_BODY_SIZE = 1_048_576  # 1MB

    def __init__(
        self,
        *,
        default_max_body_size: int = DEFAULT_MAX_BODY_SIZE,
        global_forbidden_patterns: tuple[str, ...] = (),
    ) -> None:
        self._endpoints: list[EndpointValidation] = []
        self._default_max_body_size = default_max_body_size
        self._global_forbidden = global_forbidden_patterns
        self._validated_count = 0
        self._rejected_count = 0

    def register(self, endpoint: EndpointValidation) -> None:
        """Register validation rules for an endpoint."""
        self._endpoints.append(endpoint)

    def _find_endpoint(self, path: str, method: str) -> EndpointValidation | None:
        for ep in self._endpoints:
            if path.startswith(ep.path_prefix) and method.upper() in ep.methods:
                return ep
        return None

    def validate(
        self,
        *,
        path: str,
        method: str,
        body: dict[str, Any] | None = None,
        body_size: int = 0,
    ) -> ValidationResult:
        """Validate a request against registered rules."""
        ep = self._find_endpoint(path, method)

        # Body size check (applies even without endpoint-specific rules)
        max_size = ep.max_body_size if ep else self._default_max_body_size
        if body_size > max_size:
            self._rejected_count += 1
            return ValidationResult(
                valid=False, error="request body too large",
            )

        if body is None or ep is None:
            self._validated_count += 1
            return ValidationResult(valid=True)

        # JSON depth check
        if not validate_json_depth(body, ep.max_json_depth):
            self._rejected_count += 1
            return ValidationResult(
                valid=False, error="JSON nesting too deep",
            )

        # Field rules
        result = validate_body(body, ep.rules)
        if not result.valid:
            self._rejected_count += 1
            return result

        # Global forbidden patterns on string values
        if self._global_forbidden:
            for key, value in body.items():
                if isinstance(value, str):
                    for pattern in self._global_forbidden:
                        if re.search(pattern, value):
                            self._rejected_count += 1
                            return ValidationResult(
                                valid=False,
                                error="request contains forbidden pattern",
                                field=key,
                            )

        self._validated_count += 1
        return ValidationResult(valid=True)

    @property
    def validated_count(self) -> int:
        return self._validated_count

    @property
    def rejected_count(self) -> int:
        return self._rejected_count

    def summary(self) -> dict[str, Any]:
        return {
            "registered_endpoints": len(self._endpoints),
            "total_validated": self._validated_count,
            "total_rejected": self._rejected_count,
        }


class InputValidationMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware for request validation.

    Rejects malformed requests before they reach route handlers.
    Rejection responses never echo back the invalid input.
    """

    EXEMPT_PATHS = {"/health", "/ready", "/docs", "/openapi.json", "/redoc"}

    def __init__(self, app: Any, *, validator: RequestValidator) -> None:
        super().__init__(app)
        self._validator = validator

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        path = request.url.path
        method = request.method

        if path in self.EXEMPT_PATHS or method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        # Read body for validation
        body_bytes = await request.body()
        body_size = len(body_bytes)

        body_dict = None
        if body_bytes:
            try:
                body_dict = json.loads(body_bytes)
                if not isinstance(body_dict, dict):
                    body_dict = None
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JSONResponse(
                    status_code=400,
                    content={"error": "invalid JSON"},
                )

        result = self._validator.validate(
            path=path, method=method, body=body_dict, body_size=body_size,
        )

        if not result.valid:
            # Never echo back the invalid input
            return JSONResponse(
                status_code=400,
                content={"error": result.error},
            )

        return await call_next(request)
