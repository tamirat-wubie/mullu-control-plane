"""Purpose: validate execution templates before any adapter dispatch.
Governance scope: execution-slice template admission only.
Dependencies: Python string formatting utilities and runtime-core invariant helpers.
Invariants: allowed actions are explicit, required bindings are complete, and validation never executes or mutates state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re
from string import Formatter
from typing import Any, Mapping, Sequence

from .invariants import RuntimeCoreInvariantError, freeze_mapping


_FIELD_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TEMPLATE_VALIDATION_SUMMARIES = {
    "malformed_template": "template is malformed",
    "unsupported_template_field": "template contains unsupported fields",
    "unsupported_action_type": "template action type is not supported",
    "missing_parameter": "required parameters are missing",
    "malformed_bindings": "bindings are malformed",
    "missing_binding": "binding resolution failed",
    "unsupported_binding_expression": "binding expression is not supported",
}


class ExecutionActionType(StrEnum):
    SHELL_COMMAND = "shell_command"


@dataclass(frozen=True, slots=True)
class ValidatedTemplate:
    template_id: str
    action_type: ExecutionActionType
    command_argv: tuple[str, ...]
    cwd: str | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.template_id, str) or not self.template_id.strip():
            raise RuntimeCoreInvariantError("template_id must be a non-empty string")
        if not isinstance(self.action_type, ExecutionActionType):
            raise RuntimeCoreInvariantError("action_type must be an ExecutionActionType value")
        if not self.command_argv:
            raise RuntimeCoreInvariantError("command_argv must contain at least one item")
        for item in self.command_argv:
            if not isinstance(item, str) or not item.strip():
                raise RuntimeCoreInvariantError("command_argv items must be non-empty strings")
        if self.cwd is not None and (not isinstance(self.cwd, str) or not self.cwd.strip()):
            raise RuntimeCoreInvariantError("cwd must be a non-empty string when provided")
        environment = dict(self.environment)
        for key, value in environment.items():
            if not isinstance(key, str) or not key.strip():
                raise RuntimeCoreInvariantError("environment keys must be non-empty strings")
            if not isinstance(value, str):
                raise RuntimeCoreInvariantError("environment values must be strings")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise RuntimeCoreInvariantError("timeout_seconds must be greater than zero when provided")
        object.__setattr__(self, "environment", freeze_mapping(environment))


class TemplateValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def summarize_template_validation_error(exc: TemplateValidationError) -> str:
    """Return a bounded summary for template validation failures."""
    return _TEMPLATE_VALIDATION_SUMMARIES.get(exc.code, "template validation failed")


def format_template_validation_error(exc: TemplateValidationError) -> str:
    """Return a stable code-prefixed validation summary."""
    return f"{exc.code}:{summarize_template_validation_error(exc)}"


class TemplateValidator:
    _allowed_keys = {
        "template_id",
        "action_type",
        "command_argv",
        "required_parameters",
        "cwd",
        "environment",
        "timeout_seconds",
    }

    def validate(self, template: Mapping[str, Any], bindings: Mapping[str, str]) -> ValidatedTemplate:
        if not isinstance(template, Mapping):
            raise TemplateValidationError("malformed_template", "template must be a mapping")

        unknown_keys = sorted(set(template) - self._allowed_keys)
        if unknown_keys:
            raise TemplateValidationError(
                "unsupported_template_field",
                f"template contains unsupported fields: {', '.join(unknown_keys)}",
            )

        template_id = self._required_text(template.get("template_id"), "template_id")
        action_type_text = self._required_text(template.get("action_type"), "action_type")
        try:
            action_type = ExecutionActionType(action_type_text)
        except ValueError as exc:
            raise TemplateValidationError("unsupported_action_type", "action_type is not supported") from exc

        command_argv_raw = template.get("command_argv")
        if not isinstance(command_argv_raw, Sequence) or isinstance(command_argv_raw, (str, bytes)):
            raise TemplateValidationError("malformed_template", "command_argv must be a sequence of strings")
        if not command_argv_raw:
            raise TemplateValidationError("malformed_template", "command_argv must contain at least one item")

        required_parameters = self._sequence_of_text(
            template.get("required_parameters", ()),
            field_name="required_parameters",
            allow_empty=True,
        )
        normalized_bindings = self._normalized_bindings(bindings)

        missing_parameters = [name for name in required_parameters if name not in normalized_bindings]
        if missing_parameters:
            raise TemplateValidationError(
                "missing_parameter",
                f"missing required parameters: {', '.join(sorted(missing_parameters))}",
            )

        command_argv = tuple(
            self._bind_text(self._required_text(item, "command_argv item"), normalized_bindings)
            for item in command_argv_raw
        )
        cwd = template.get("cwd")
        bound_cwd = None
        if cwd is not None:
            bound_cwd = self._bind_text(self._required_text(cwd, "cwd"), normalized_bindings)

        environment_raw = template.get("environment", {})
        if not isinstance(environment_raw, Mapping):
            raise TemplateValidationError("malformed_template", "environment must be a mapping")
        environment = {
            self._required_text(key, "environment key"): self._bind_text(
                self._required_text(value, f"environment[{key}]"),
                normalized_bindings,
            )
            for key, value in environment_raw.items()
        }

        timeout_seconds = template.get("timeout_seconds")
        if timeout_seconds is not None and (
            not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or timeout_seconds <= 0
        ):
            raise TemplateValidationError(
                "malformed_template",
                "timeout_seconds must be a positive number when provided",
            )

        return ValidatedTemplate(
            template_id=template_id,
            action_type=action_type,
            command_argv=command_argv,
            cwd=bound_cwd,
            environment=environment,
            timeout_seconds=float(timeout_seconds) if timeout_seconds is not None else None,
        )

    def _normalized_bindings(self, bindings: Mapping[str, str]) -> dict[str, str]:
        if not isinstance(bindings, Mapping):
            raise TemplateValidationError("malformed_bindings", "bindings must be a mapping")
        normalized: dict[str, str] = {}
        for key, value in bindings.items():
            binding_name = self._required_text(key, "binding name")
            normalized[binding_name] = self._required_text(value, f"binding[{binding_name}]")
        return normalized

    def _bind_text(self, value: str, bindings: Mapping[str, str]) -> str:
        for field_name in self._field_names(value):
            if field_name not in bindings:
                raise TemplateValidationError(
                    "missing_binding",
                    f"missing binding for field: {field_name}",
                )
        return self._required_text(value.format_map(bindings), "bound value")

    def _field_names(self, value: str) -> tuple[str, ...]:
        fields: list[str] = []
        for _, field_name, _, _ in Formatter().parse(value):
            if field_name is None:
                continue
            if not _FIELD_PATTERN.fullmatch(field_name):
                raise TemplateValidationError(
                    "unsupported_binding_expression",
                    f"unsupported binding expression: {field_name}",
                )
            fields.append(field_name)
        return tuple(fields)

    @staticmethod
    def _required_text(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise TemplateValidationError("malformed_template", f"{field_name} must be a non-empty string")
        return value

    @staticmethod
    def _sequence_of_text(value: Any, *, field_name: str, allow_empty: bool) -> tuple[str, ...]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise TemplateValidationError("malformed_template", f"{field_name} must be a sequence of strings")
        values = tuple(TemplateValidator._required_text(item, field_name) for item in value)
        if not allow_empty and not values:
            raise TemplateValidationError("malformed_template", f"{field_name} must contain at least one item")
        return values
