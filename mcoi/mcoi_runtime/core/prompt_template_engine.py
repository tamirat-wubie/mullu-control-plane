"""Phase 209C — Prompt Template Engine.

Purpose: Governed prompt construction with typed templates, variable
    substitution, and prompt versioning. Ensures LLM prompts follow
    organizational standards and are auditable.
Governance scope: prompt construction only — never invokes LLM.
Dependencies: none (pure string operations).
Invariants:
  - Templates are immutable once registered.
  - Variable substitution is deterministic.
  - Missing variables produce explicit errors, not empty strings.
  - Prompt output is always a plain string.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """Typed prompt template with named variables."""

    template_id: str
    name: str
    template: str  # Uses {{variable}} syntax
    variables: tuple[str, ...]  # Required variable names
    system_prompt: str = ""
    version: str = "1.0"
    category: str = "general"


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    """Result of rendering a template with variables."""

    template_id: str
    prompt: str
    system_prompt: str
    variables_used: dict[str, str]
    version: str


class PromptTemplateEngine:
    """Manages and renders governed prompt templates."""

    _VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")

    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}

    def register(self, template: PromptTemplate) -> None:
        """Register a prompt template."""
        if template.template_id in self._templates:
            raise ValueError("template already registered")
        self._templates[template.template_id] = template

    def get(self, template_id: str) -> PromptTemplate | None:
        return self._templates.get(template_id)

    def render(self, template_id: str, variables: dict[str, str]) -> RenderedPrompt:
        """Render a template with variables.

        All required variables must be provided. Extra variables are ignored.
        Missing variables raise ValueError.
        """
        template = self._templates.get(template_id)
        if template is None:
            raise ValueError("template unavailable")

        # Check required variables
        missing = [v for v in template.variables if v not in variables]
        if missing:
            raise ValueError("missing required template variables")

        # Substitute variables
        prompt = template.template
        system = template.system_prompt
        used: dict[str, str] = {}

        for var_name in template.variables:
            val = str(variables[var_name])
            prompt = prompt.replace(f"{{{{{var_name}}}}}", val)
            system = system.replace(f"{{{{{var_name}}}}}", val)
            used[var_name] = val

        return RenderedPrompt(
            template_id=template_id,
            prompt=prompt,
            system_prompt=system,
            variables_used=used,
            version=template.version,
        )

    def list_templates(self, category: str | None = None) -> list[PromptTemplate]:
        templates = sorted(self._templates.values(), key=lambda t: t.template_id)
        if category is not None:
            templates = [t for t in templates if t.category == category]
        return templates

    @property
    def count(self) -> int:
        return len(self._templates)

    def summary(self) -> dict[str, Any]:
        by_category: dict[str, int] = {}
        for t in self._templates.values():
            by_category[t.category] = by_category.get(t.category, 0) + 1
        return {"total": self.count, "by_category": by_category}
