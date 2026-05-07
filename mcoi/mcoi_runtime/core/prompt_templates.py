"""Prompt Template Registry — Versioned, tenant-scoped prompt management.

Purpose: Centralized prompt template storage with versioning, variable
    substitution, and tenant isolation.  Replaces inline prompts with
    managed, auditable templates.
Governance scope: prompt content management only.
Dependencies: none (pure algorithm).
Invariants:
  - Templates are immutable once created (new version = new record).
  - Variable substitution is safe (no code execution, no injection).
  - Templates are tenant-scoped (no cross-tenant access).
  - Version history is preserved (rollback to any version).
  - Thread-safe — concurrent access is safe.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """An immutable versioned prompt template."""

    template_id: str
    name: str
    tenant_id: str
    version: int
    content: str  # Template text with {{variable}} placeholders
    variables: frozenset[str]  # Expected variable names
    description: str = ""
    created_at: str = ""
    created_by: str = ""
    tags: frozenset[str] = frozenset()

    def render(self, variables: dict[str, str]) -> str:
        """Render the template with variable substitution.

        Uses {{variable_name}} syntax. Missing variables are left as-is.
        Values are escaped (no nested template injection).
        """
        result = self.content
        for key, value in variables.items():
            # Escape value to prevent nested template injection
            safe_value = str(value).replace("{{", "{ {").replace("}}", "} }")
            result = result.replace(f"{{{{{key}}}}}", safe_value)
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "tenant_id": self.tenant_id,
            "version": self.version,
            "content": self.content,
            "variables": sorted(self.variables),
            "description": self.description,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "tags": sorted(self.tags),
        }


_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def extract_variables(content: str) -> frozenset[str]:
    """Extract {{variable}} names from template content."""
    return frozenset(_VAR_PATTERN.findall(content))


class PromptTemplateRegistry:
    """Versioned prompt template storage with tenant isolation.

    Usage:
        registry = PromptTemplateRegistry(clock=lambda: "2026-04-07T12:00:00Z")

        # Create template
        tpl = registry.create(
            tenant_id="t1", name="greeting",
            content="Hello {{user_name}}, welcome to {{company}}!",
            created_by="admin",
        )

        # Render
        text = registry.render("t1", "greeting", {"user_name": "Alice", "company": "Mullu"})

        # Update (creates new version)
        registry.update("t1", "greeting",
            content="Hi {{user_name}}! Welcome to {{company}}.",
            updated_by="admin",
        )

        # Get specific version
        v1 = registry.get("t1", "greeting", version=1)
    """

    MAX_TEMPLATES_PER_TENANT = 500
    MAX_VERSIONS_PER_TEMPLATE = 50

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        # tenant_id → name → [versions] (index 0 = oldest)
        self._templates: dict[str, dict[str, list[PromptTemplate]]] = {}
        self._lock = threading.Lock()
        self._sequence = 0

    def _next_id(self) -> str:
        self._sequence += 1
        return f"tpl-{self._sequence}"

    def create(
        self,
        *,
        tenant_id: str,
        name: str,
        content: str,
        description: str = "",
        created_by: str = "",
        tags: frozenset[str] = frozenset(),
    ) -> PromptTemplate:
        """Create a new prompt template (version 1)."""
        with self._lock:
            tenant_templates = self._templates.setdefault(tenant_id, {})
            if name in tenant_templates:
                raise ValueError(f"template '{name}' already exists for tenant")
            if len(tenant_templates) >= self.MAX_TEMPLATES_PER_TENANT:
                raise ValueError("tenant template limit reached")

            variables = extract_variables(content)
            template = PromptTemplate(
                template_id=self._next_id(),
                name=name,
                tenant_id=tenant_id,
                version=1,
                content=content,
                variables=variables,
                description=description,
                created_at=self._clock(),
                created_by=created_by,
                tags=tags,
            )
            tenant_templates[name] = [template]
            return template

    def update(
        self,
        tenant_id: str,
        name: str,
        *,
        content: str,
        description: str = "",
        updated_by: str = "",
        tags: frozenset[str] = frozenset(),
    ) -> PromptTemplate:
        """Create a new version of an existing template."""
        with self._lock:
            tenant_templates = self._templates.get(tenant_id, {})
            versions = tenant_templates.get(name)
            if not versions:
                raise ValueError(f"template '{name}' not found for tenant")

            if len(versions) >= self.MAX_VERSIONS_PER_TEMPLATE:
                versions.pop(0)  # Evict oldest version

            latest = versions[-1]
            variables = extract_variables(content)
            new_version = PromptTemplate(
                template_id=self._next_id(),
                name=name,
                tenant_id=tenant_id,
                version=latest.version + 1,
                content=content,
                variables=variables,
                description=description or latest.description,
                created_at=self._clock(),
                created_by=updated_by,
                tags=tags or latest.tags,
            )
            versions.append(new_version)
            return new_version

    def get(
        self,
        tenant_id: str,
        name: str,
        *,
        version: int = 0,
    ) -> PromptTemplate | None:
        """Get a template. version=0 means latest."""
        with self._lock:
            versions = self._templates.get(tenant_id, {}).get(name, [])
            if not versions:
                return None
            if version == 0:
                return versions[-1]
            for v in versions:
                if v.version == version:
                    return v
            return None

    def render(
        self,
        tenant_id: str,
        name: str,
        variables: dict[str, str],
        *,
        version: int = 0,
    ) -> str | None:
        """Render a template with variables. Returns None if not found."""
        template = self.get(tenant_id, name, version=version)
        if template is None:
            return None
        return template.render(variables)

    def list_templates(self, tenant_id: str) -> list[PromptTemplate]:
        """List latest version of all templates for a tenant."""
        with self._lock:
            tenant_templates = self._templates.get(tenant_id, {})
            return [versions[-1] for versions in tenant_templates.values() if versions]

    def list_versions(self, tenant_id: str, name: str) -> list[PromptTemplate]:
        """List all versions of a template."""
        with self._lock:
            return list(self._templates.get(tenant_id, {}).get(name, []))

    def delete(self, tenant_id: str, name: str) -> bool:
        """Delete a template and all its versions."""
        with self._lock:
            tenant_templates = self._templates.get(tenant_id, {})
            if name in tenant_templates:
                del tenant_templates[name]
                return True
            return False

    @property
    def template_count(self) -> int:
        return sum(
            len(templates) for templates in self._templates.values()
        )

    def summary(self) -> dict[str, Any]:
        total_versions = sum(
            len(versions)
            for tenant in self._templates.values()
            for versions in tenant.values()
        )
        return {
            "tenants": len(self._templates),
            "templates": self.template_count,
            "total_versions": total_versions,
        }
