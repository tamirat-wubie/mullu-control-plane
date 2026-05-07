"""Purpose: derive deterministic app architecture specs from product specs.
Governance scope: architecture boundaries, modules, routes, surfaces,
    integration points, quality profile, and security controls.
Dependencies: regular expressions and app-builder contract records.
Invariants:
  - Architecture planning is declarative and side-effect free.
  - Runtime stack, data entities, routes, UI surfaces, and modules are explicit.
  - Baseline security controls are retained with product security requirements.
  - Direct deployment is marked unavailable in architecture metadata.
"""

from __future__ import annotations

import re

from mcoi_runtime.contracts.app_builder import ArchitectureSpec, ProductSpec


_BASELINE_SECURITY_CONTROLS = ("tenant_boundary_preserved", "input_validation_required", "rbac_review_required", "pii_redaction_reviewed")
_STANDARD_MODULES = ("backend_data_model", "backend_api", "frontend_ui", "validation_security", "automated_tests", "integration_wiring", "preview_review")
_STOPWORDS = frozenset({"add", "admin", "app", "build", "create", "dashboard", "for", "manager", "management", "portal", "small", "system", "the", "tool", "track", "tracker", "view", "with"})


def draft_architecture_spec(product_spec: ProductSpec, *, runtime_stack: str = "fastapi_typescript") -> ArchitectureSpec:
    """Create a deterministic architecture spec from a bounded product spec."""
    if not isinstance(product_spec, ProductSpec):
        raise ValueError("product_spec must be a ProductSpec")
    entity_name = _primary_entity_name(product_spec)
    entity_slug = _slug(entity_name)
    plural_slug = _plural_slug(entity_slug)
    return ArchitectureSpec(
        app_name=product_spec.app_name,
        runtime_stack=runtime_stack,
        data_entities=(entity_name,),
        api_routes=(f"/api/{plural_slug}", f"/api/{plural_slug}/{{id}}"),
        ui_surfaces=(f"/{plural_slug}", f"/{plural_slug}/new"),
        modules=_STANDARD_MODULES,
        integration_points=("backend_api_to_frontend_client", "operator_review_packet"),
        security_controls=tuple(dict.fromkeys((*_BASELINE_SECURITY_CONTROLS, *product_spec.security_requirements))),
        quality_gate_profile="standard_app",
        metadata={"generated_from": "product_spec", "primary_entity": entity_name, "primary_entity_slug": entity_slug, "direct_deployment_allowed": False},
    )


def _primary_entity_name(product_spec: ProductSpec) -> str:
    source_text = " ".join((product_spec.app_name, *product_spec.jobs_to_be_done, *product_spec.core_flows))
    for token in re.findall(r"[A-Za-z][A-Za-z0-9]*", source_text):
        normalized = token.lower()
        if normalized not in _STOPWORDS and len(normalized) > 2:
            return _pascal_case(_singular(normalized))
    return "Record"


def _slug(value: str) -> str:
    return "-".join(re.findall(r"[A-Za-z0-9]+", value.lower())) or "record"


def _plural_slug(slug: str) -> str:
    if slug.endswith("s"):
        return slug
    if slug.endswith("y"):
        return f"{slug[:-1]}ies"
    return f"{slug}s"


def _singular(value: str) -> str:
    if value.endswith("ies") and len(value) > 3:
        return f"{value[:-3]}y"
    if value.endswith("s") and len(value) > 3:
        return value[:-1]
    return value


def _pascal_case(value: str) -> str:
    return "".join(part.capitalize() for part in re.findall(r"[a-z0-9]+", value)) or "Record"
