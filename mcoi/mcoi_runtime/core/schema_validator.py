"""Phase 208D — Schema Validation Engine.

Purpose: Runtime contract enforcement — validates data shapes against
    registered schemas before processing. Catches malformed inputs
    before they reach business logic.
Governance scope: schema validation only.
Dependencies: none (pure validation logic).
Invariants:
  - Schemas are immutable once registered.
  - Validation never modifies the data being validated.
  - All validation results include the schema that was checked.
  - Unknown schemas produce explicit errors, not silent passes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class SchemaRule:
    """Single validation rule within a schema."""

    field: str
    rule_type: str  # "required", "type", "min_length", "max_length", "min_value", "max_value", "pattern", "enum"
    value: Any  # Expected value for the rule (type name, min, max, pattern, etc.)
    message: str = ""


@dataclass(frozen=True, slots=True)
class SchemaDefinition:
    """A named schema with validation rules."""

    schema_id: str
    name: str
    rules: tuple[SchemaRule, ...]
    description: str = ""


@dataclass(frozen=True, slots=True)
class ValidationError:
    """Single validation failure."""

    field: str
    rule_type: str
    message: str
    expected: Any = None
    actual: Any = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of validating data against a schema."""

    schema_id: str
    valid: bool
    errors: tuple[ValidationError, ...]


class SchemaValidator:
    """Validates data against registered schemas."""

    def __init__(self) -> None:
        self._schemas: dict[str, SchemaDefinition] = {}

    def register(self, schema: SchemaDefinition) -> None:
        """Register a schema."""
        if schema.schema_id in self._schemas:
            raise ValueError("schema already registered")
        self._schemas[schema.schema_id] = schema

    def get(self, schema_id: str) -> SchemaDefinition | None:
        return self._schemas.get(schema_id)

    def validate(self, schema_id: str, data: dict[str, Any]) -> ValidationResult:
        """Validate data against a registered schema."""
        schema = self._schemas.get(schema_id)
        if schema is None:
            return ValidationResult(
                schema_id=schema_id, valid=False,
                errors=(ValidationError(
                    field="", rule_type="schema",
                    message="schema unavailable",
                ),),
            )

        errors: list[ValidationError] = []
        for rule in schema.rules:
            error = self._check_rule(rule, data)
            if error is not None:
                errors.append(error)

        return ValidationResult(
            schema_id=schema_id,
            valid=len(errors) == 0,
            errors=tuple(errors),
        )

    def _check_rule(self, rule: SchemaRule, data: dict[str, Any]) -> ValidationError | None:
        """Check a single rule against data."""
        value = data.get(rule.field)

        if rule.rule_type == "required":
            if value is None or (isinstance(value, str) and not value.strip()):
                return ValidationError(
                    field=rule.field, rule_type="required",
                    message=rule.message or f"{rule.field} is required",
                )

        elif rule.rule_type == "type":
            if value is not None:
                expected_type = {"str": str, "int": int, "float": (int, float), "bool": bool, "dict": dict, "list": list}.get(rule.value)
                if expected_type and not isinstance(value, expected_type):
                    return ValidationError(
                        field=rule.field, rule_type="type",
                        message=rule.message or f"{rule.field} must be {rule.value}",
                        expected=rule.value, actual=type(value).__name__,
                    )

        elif rule.rule_type == "min_length":
            if value is not None and isinstance(value, (str, list)) and len(value) < rule.value:
                return ValidationError(
                    field=rule.field, rule_type="min_length",
                    message=rule.message or f"{rule.field} must be at least {rule.value} characters",
                    expected=rule.value, actual=len(value),
                )

        elif rule.rule_type == "max_length":
            if value is not None and isinstance(value, (str, list)) and len(value) > rule.value:
                return ValidationError(
                    field=rule.field, rule_type="max_length",
                    message=rule.message or f"{rule.field} must be at most {rule.value} characters",
                    expected=rule.value, actual=len(value),
                )

        elif rule.rule_type == "min_value":
            if value is not None and isinstance(value, (int, float)) and value < rule.value:
                return ValidationError(
                    field=rule.field, rule_type="min_value",
                    message=rule.message or f"{rule.field} must be >= {rule.value}",
                    expected=rule.value, actual=value,
                )

        elif rule.rule_type == "max_value":
            if value is not None and isinstance(value, (int, float)) and value > rule.value:
                return ValidationError(
                    field=rule.field, rule_type="max_value",
                    message=rule.message or f"{rule.field} must be <= {rule.value}",
                    expected=rule.value, actual=value,
                )

        elif rule.rule_type == "enum":
            if value is not None and value not in rule.value:
                return ValidationError(
                    field=rule.field, rule_type="enum",
                    message=rule.message or f"{rule.field} must be one of {rule.value}",
                    expected=rule.value, actual=value,
                )

        return None

    def list_schemas(self) -> list[SchemaDefinition]:
        return sorted(self._schemas.values(), key=lambda s: s.schema_id)

    @property
    def count(self) -> int:
        return len(self._schemas)

    def summary(self) -> dict[str, Any]:
        return {
            "schemas": self.count,
            "schema_ids": sorted(self._schemas.keys()),
        }
