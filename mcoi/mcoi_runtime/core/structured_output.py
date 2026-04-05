"""Purpose: Structured output contracts for governed JSON-mode responses.
Governance scope: output parsing and schema validation only.
Dependencies: Python standard library only.
Invariants:
  - Output schemas are validated at registration time.
  - Parsing failures produce explicit errors with context.
  - Valid outputs are returned as typed dicts.
  - Raw LLM text is always preserved alongside parsed output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

_SUPPORTED_FIELD_TYPES = frozenset({
    "string",
    "number",
    "boolean",
    "array",
    "object",
})


@dataclass(frozen=True, slots=True)
class OutputSchema:
    """Schema for structured LLM output."""

    schema_id: str
    name: str
    fields: dict[str, str]
    required_fields: tuple[str, ...]
    description: str = ""


@dataclass(frozen=True, slots=True)
class ParsedOutput:
    """Result of parsing structured LLM output."""

    schema_id: str
    raw_text: str
    parsed: dict[str, Any] | None
    valid: bool
    errors: tuple[str, ...]


class StructuredOutputEngine:
    """Parses and validates structured LLM outputs."""

    def __init__(self) -> None:
        self._schemas: dict[str, OutputSchema] = {}

    def register(self, schema: OutputSchema) -> None:
        if schema.schema_id in self._schemas:
            raise ValueError("schema already registered")
        self._validate_schema(schema)
        self._schemas[schema.schema_id] = schema

    def get(self, schema_id: str) -> OutputSchema | None:
        return self._schemas.get(schema_id)

    def parse(self, schema_id: str, raw_text: str) -> ParsedOutput:
        """Parse LLM output against a registered schema."""
        schema = self._schemas.get(schema_id)
        if schema is None:
            return ParsedOutput(
                schema_id=schema_id,
                raw_text=raw_text,
                parsed=None,
                valid=False,
                errors=("schema unavailable",),
            )

        parsed_json = self._extract_json(raw_text)
        if parsed_json is None:
            return ParsedOutput(
                schema_id=schema_id,
                raw_text=raw_text,
                parsed=None,
                valid=False,
                errors=("could not parse JSON from LLM output",),
            )

        errors: list[str] = []
        for field_name in schema.required_fields:
            if field_name not in parsed_json:
                errors.append(f"missing required field: {field_name}")

        for field_name, expected_type in schema.fields.items():
            if field_name in parsed_json:
                actual = parsed_json[field_name]
                if not self._check_type(actual, expected_type):
                    errors.append(
                        f"field '{field_name}' expected {expected_type}, "
                        f"got {type(actual).__name__}"
                    )

        return ParsedOutput(
            schema_id=schema_id,
            raw_text=raw_text,
            parsed=parsed_json,
            valid=len(errors) == 0,
            errors=tuple(errors),
        )

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        """Extract JSON from LLM text, including markdown code blocks."""
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        if "```json" in text:
            start = text.index("```json") + len("```json")
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except (json.JSONDecodeError, ValueError):
                pass

        if "```" in text:
            parts = text.split("```")
            for part in parts[1::2]:
                clean = part.strip()
                if clean.startswith("json"):
                    clean = clean[4:].strip()
                try:
                    return json.loads(clean)
                except json.JSONDecodeError:
                    continue

        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start : brace_end + 1])
            except json.JSONDecodeError:
                pass

        return None

    def _check_type(self, value: Any, expected: str) -> bool:
        type_map = {
            "string": str,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        expected_type = type_map.get(expected)
        if expected_type is None:
            return False
        return isinstance(value, expected_type)

    def _validate_schema(self, schema: OutputSchema) -> None:
        for field_name, expected_type in schema.fields.items():
            if not isinstance(field_name, str) or not field_name.strip():
                raise ValueError("schema field names must be non-empty strings")
            if expected_type not in _SUPPORTED_FIELD_TYPES:
                raise ValueError("unsupported field type")

        for field_name in schema.required_fields:
            if field_name not in schema.fields:
                raise ValueError("required field not declared in schema fields")

    def list_schemas(self) -> list[OutputSchema]:
        return sorted(self._schemas.values(), key=lambda schema: schema.schema_id)

    @property
    def count(self) -> int:
        return len(self._schemas)

    def summary(self) -> dict[str, Any]:
        return {"schemas": self.count, "schema_ids": sorted(self._schemas.keys())}
