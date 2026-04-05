"""Purpose: verify execution template validation for the MCOI runtime.
Governance scope: execution-slice tests only.
Dependencies: pytest and the execution-slice template validator.
Invariants: valid templates are admitted, malformed templates are rejected, and missing bindings never pass silently.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.template_validator import (
    ExecutionActionType,
    TemplateValidationError,
    TemplateValidator,
    ValidatedTemplate,
)


def test_template_validator_accepts_valid_shell_templates() -> None:
    validator = TemplateValidator()
    validated = validator.validate(
        {
            "template_id": "template-1",
            "action_type": "shell_command",
            "command_argv": ("python", "-c", "print('{message}')"),
            "required_parameters": ("message",),
            "timeout_seconds": 5,
        },
        {"message": "hello"},
    )

    assert validated.template_id == "template-1"
    assert validated.action_type is ExecutionActionType.SHELL_COMMAND
    assert validated.command_argv == ("python", "-c", "print('hello')")
    assert validated.timeout_seconds == 5.0


def test_template_validator_rejects_missing_required_parameters() -> None:
    validator = TemplateValidator()

    with pytest.raises(TemplateValidationError) as exc_info:
        validator.validate(
            {
                "template_id": "template-1",
                "action_type": "shell_command",
                "command_argv": ("python", "-c", "print('{message}')"),
                "required_parameters": ("message",),
            },
            {},
        )

    assert exc_info.value.code == "missing_parameter"
    assert "missing required parameters" in str(exc_info.value)
    assert "message" in str(exc_info.value)


def test_template_validator_rejects_malformed_templates() -> None:
    validator = TemplateValidator()

    with pytest.raises(TemplateValidationError) as exc_info:
        validator.validate(
            {
                "template_id": "template-1",
                "action_type": "shell_command",
                "command_argv": "python -c print('hello')",
            },
            {},
        )

    assert exc_info.value.code == "malformed_template"
    assert "command_argv" in str(exc_info.value)
    assert "sequence of strings" in str(exc_info.value)


def test_validated_template_rejects_blank_command_items_under_bounded_contract() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="^command_argv items must be non-empty strings$") as exc_info:
        ValidatedTemplate(
            template_id="template-1",
            action_type=ExecutionActionType.SHELL_COMMAND,
            command_argv=("python", " "),
        )

    assert "[1]" not in str(exc_info.value)
