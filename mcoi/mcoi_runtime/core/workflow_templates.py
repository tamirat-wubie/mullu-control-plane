"""Phase 221C — Workflow Templates.

Purpose: Reusable governed workflow chain definitions.
    Templates define multi-step agent chains that can be
    instantiated with parameters for repeated use.
Governance scope: template management only.
Invariants:
  - Templates are immutable once registered.
  - Instantiation validates all required parameters.
  - Templates produce deterministic chain definitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mcoi_runtime.core.agent_chain import ChainStep


@dataclass(frozen=True, slots=True)
class WorkflowTemplate:
    """Reusable workflow chain definition."""

    template_id: str
    name: str
    description: str
    steps: tuple[ChainStep, ...]
    parameters: tuple[str, ...]  # Required parameter names
    category: str = "general"


class WorkflowTemplateRegistry:
    """Manages reusable workflow templates."""

    def __init__(self) -> None:
        self._templates: dict[str, WorkflowTemplate] = {}

    def register(self, template: WorkflowTemplate) -> None:
        if template.template_id in self._templates:
            raise ValueError(f"template already registered: {template.template_id}")
        self._templates[template.template_id] = template

    def get(self, template_id: str) -> WorkflowTemplate | None:
        return self._templates.get(template_id)

    def instantiate(self, template_id: str, params: dict[str, str]) -> list[ChainStep]:
        """Create chain steps from a template with parameter substitution."""
        template = self._templates.get(template_id)
        if template is None:
            raise ValueError(f"unknown template: {template_id}")

        missing = [p for p in template.parameters if p not in params]
        if missing:
            raise ValueError(f"missing parameters: {', '.join(missing)}")

        steps: list[ChainStep] = []
        for step in template.steps:
            prompt = step.prompt_template
            for key, val in params.items():
                prompt = prompt.replace(f"{{{{{key}}}}}", val)
            steps.append(ChainStep(
                step_id=step.step_id, name=step.name,
                prompt_template=prompt, on_failure=step.on_failure,
            ))
        return steps

    def list_templates(self, category: str | None = None) -> list[WorkflowTemplate]:
        templates = sorted(self._templates.values(), key=lambda t: t.template_id)
        if category is not None:
            templates = [t for t in templates if t.category == category]
        return templates

    @property
    def count(self) -> int:
        return len(self._templates)

    def summary(self) -> dict[str, Any]:
        by_cat: dict[str, int] = {}
        for t in self._templates.values():
            by_cat[t.category] = by_cat.get(t.category, 0) + 1
        return {"total": self.count, "by_category": by_cat}
