"""Purpose: provide default local capability metadata for autonomous request planning.
Governance scope: repository-local autonomous request plan compilation only.
Dependencies: autonomous request plan compiler contracts.
Invariants: default capabilities are local, deterministic, and dependency-validated.
"""

from __future__ import annotations

from typing import Mapping

from .autonomous_request import (
    AutonomousRequestCapabilityMetadata,
    AutonomousRequestIntent,
    AutonomousRequestPlanCompiler,
    AutonomousRequestEpisode,
)


def default_autonomous_capability_catalog() -> Mapping[str, AutonomousRequestCapabilityMetadata]:
    """Return the default local capability catalog for autonomous request compilation."""

    return {
        "local.inspect": AutonomousRequestCapabilityMetadata(
            capability_id="local.inspect",
            template={
                "template_id": "template-local-inspect",
                "action_type": "shell_command",
                "action_class": "execute_read",
                "command_argv": (
                    "python",
                    "-c",
                    "import sys; print('inspect:' + sys.argv[1])",
                    "{target}",
                ),
                "required_parameters": ("target",),
            },
            verification_keys=("operator_run_report", "local_observation"),
        ),
        "local.plan": AutonomousRequestCapabilityMetadata(
            capability_id="local.plan",
            template={
                "template_id": "template-local-plan",
                "action_type": "shell_command",
                "action_class": "plan",
                "command_argv": (
                    "python",
                    "-c",
                    "import sys; print('plan:' + sys.argv[1])",
                    "{objective}",
                ),
                "required_parameters": ("objective",),
            },
            predecessor_capability_ids=("local.inspect",),
            verification_keys=("operator_run_report", "plan_trace"),
        ),
        "local.apply": AutonomousRequestCapabilityMetadata(
            capability_id="local.apply",
            template={
                "template_id": "template-local-apply",
                "action_type": "shell_command",
                "action_class": "execute_write",
                "command_argv": (
                    "python",
                    "-c",
                    "import sys; print('apply:' + sys.argv[1])",
                    "{change}",
                ),
                "required_parameters": ("change",),
            },
            predecessor_capability_ids=("local.plan",),
            verification_keys=("operator_run_report", "local_effect_trace"),
        ),
    }


def default_autonomous_request_plan_compiler() -> AutonomousRequestPlanCompiler:
    """Return a compiler backed by the default local capability catalog."""

    return AutonomousRequestPlanCompiler(default_autonomous_capability_catalog())


def compile_default_autonomous_request_episode(
    intent: AutonomousRequestIntent,
) -> AutonomousRequestEpisode:
    """Compile an intent through the default local capability catalog."""

    return default_autonomous_request_plan_compiler().compile_episode(intent)


__all__ = [
    "compile_default_autonomous_request_episode",
    "default_autonomous_capability_catalog",
    "default_autonomous_request_plan_compiler",
]
