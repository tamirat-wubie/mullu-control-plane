"""Purpose: rank proof-route coverage gaps into deterministic closure batches.

Governance scope: reads the canonical proof coverage matrix and declared route
sources, then emits a bounded triage witness for unclassified declared routes.
Dependencies: scripts.proof_coverage_matrix, repository source tree, JSON.
Invariants: no route is reclassified; ranking is deterministic; every closure
candidate is derived from an existing unclassified route family.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.proof_coverage_matrix import (  # noqa: E402
    CANONICAL_OUTPUT,
    ROUTER_PREFIX_PATTERN,
)

DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "proof_route_gap_triage.json"
ROUTE_DECORATOR_PATTERN = re.compile(
    r"@(?:router|app)\.(?P<method>get|post|put|delete|patch)\(\s*[\"'](?P<route>[^\"']+)[\"']"
)
MUTATING_METHODS = frozenset({"DELETE", "PATCH", "POST", "PUT"})
MUTATION_TOKENS = frozenset(
    {
        "action",
        "approve",
        "bootstrap",
        "cancel",
        "certify",
        "disable",
        "enable",
        "execute",
        "invoke",
        "register",
        "restore",
        "rollback",
        "run",
        "trigger",
        "update",
    }
)
READ_MODEL_TOKENS = frozenset(
    {
        "dashboard",
        "health",
        "history",
        "list",
        "read-model",
        "stats",
        "status",
        "summary",
    }
)
RISK_ORDER = {"effect_bearing": 0, "mixed": 1, "read_model": 2}


@dataclass(frozen=True)
class RouteDeclaration:
    """Declared route source metadata used for gap triage."""

    route: str
    method: str
    source_file: str

    def as_dict(self) -> dict[str, str]:
        return {
            "route": self.route,
            "method": self.method,
            "source_file": self.source_file,
        }


def discover_route_declarations(repo_root: Path = REPO_ROOT) -> list[RouteDeclaration]:
    """Return declared route metadata with source file and HTTP method."""
    route_roots = [repo_root / "mcoi" / "mcoi_runtime" / "app" / "routers", repo_root / "gateway"]
    declarations: set[RouteDeclaration] = set()
    for route_root in route_roots:
        if not route_root.exists():
            continue
        for python_file in sorted(route_root.rglob("*.py")):
            if "__pycache__" in python_file.parts:
                continue
            source = python_file.read_text(encoding="utf-8")
            relative_file = python_file.relative_to(repo_root).as_posix()
            prefixes = ROUTER_PREFIX_PATTERN.findall(source)
            for match in ROUTE_DECORATOR_PATTERN.finditer(source):
                method = match.group("method").upper()
                route = match.group("route")
                declarations.add(RouteDeclaration(route=route, method=method, source_file=relative_file))
                for prefix in prefixes:
                    if route.startswith("/"):
                        declarations.add(
                            RouteDeclaration(
                                route=f"{prefix}{route}",
                                method=method,
                                source_file=relative_file,
                            )
                        )
    return sorted(declarations, key=lambda item: (item.route, item.method, item.source_file))


def build_gap_triage_report(
    matrix: dict[str, Any],
    declarations: list[RouteDeclaration] | None = None,
) -> dict[str, Any]:
    """Build a deterministic triage report for unclassified proof routes."""
    route_declarations = declarations if declarations is not None else discover_route_declarations()
    declaration_index = _declaration_index(route_declarations)
    unclassified_routes = _unclassified_routes(matrix)
    families: dict[str, list[str]] = defaultdict(list)
    for route in unclassified_routes:
        families[route_family(route)].append(route)

    ranked_families = [
        _family_record(family, sorted(routes), declaration_index)
        for family, routes in families.items()
    ]
    ranked_families.sort(
        key=lambda family: (
            -family["unclassified_route_count"],
            RISK_ORDER[family["risk_class"]],
            family["route_family"],
        )
    )
    total_unclassified = len(unclassified_routes)
    next_action = "none"
    if ranked_families:
        next_action = f"classify {ranked_families[0]['route_family']} into a named proof surface"
    return {
        "schema_version": 1,
        "generated_by": "scripts/proof_route_gap_triage.py",
        "source_matrix_generated_by": matrix.get("generated_by", "unknown"),
        "declared_route_count": matrix.get("route_coverage", {}).get("route_count", 0),
        "total_unclassified_route_count": total_unclassified,
        "route_family_count": len(ranked_families),
        "ranking_rule": "unclassified_route_count desc, risk_class, route_family",
        "ranked_families": ranked_families,
        "status": "open" if total_unclassified else "closed",
        "open_issue": (
            f"{total_unclassified} proof-relevant declared routes remain unclassified"
            if total_unclassified
            else "none"
        ),
        "next_action": next_action,
    }


def route_family(route: str) -> str:
    """Return the stable closure family for a declared route."""
    parts = [part for part in route.strip("/").split("/") if part]
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
        return f"/api/v1/{parts[2]}"
    if not parts:
        return "/"
    return f"/{parts[0]}"


def write_gap_triage_report(report: dict[str, Any], output_path: Path = DEFAULT_OUTPUT) -> Path:
    """Write a deterministic JSON route-gap triage witness."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _unclassified_routes(matrix: dict[str, Any]) -> list[str]:
    route_records = matrix.get("route_coverage", {}).get("routes", [])
    return sorted(
        record["route"]
        for record in route_records
        if record.get("surface_id") == "unclassified_declared_route"
        and record.get("coverage_state") == "unproven"
    )


def _declaration_index(declarations: list[RouteDeclaration]) -> dict[str, list[RouteDeclaration]]:
    by_route: dict[str, list[RouteDeclaration]] = defaultdict(list)
    for declaration in declarations:
        by_route[declaration.route].append(declaration)
    return {
        route: sorted(items, key=lambda item: (item.method, item.source_file))
        for route, items in by_route.items()
    }


def _family_record(
    family: str,
    routes: list[str],
    declaration_index: dict[str, list[RouteDeclaration]],
) -> dict[str, Any]:
    declarations = [
        declaration
        for route in routes
        for declaration in declaration_index.get(route, [])
    ]
    methods = sorted({declaration.method for declaration in declarations})
    source_files = sorted({declaration.source_file for declaration in declarations})
    risk_class = _risk_class(routes, methods)
    family_token = _family_token(family)
    return {
        "route_family": family,
        "suggested_surface_id": f"{family_token}_proof_surface",
        "closure_candidate_id": f"classify_{family_token}_routes",
        "unclassified_route_count": len(routes),
        "risk_class": risk_class,
        "suggested_proof_level": _suggested_proof_level(risk_class),
        "http_methods": methods,
        "source_files": source_files,
        "sample_routes": routes[:10],
        "closure_reason": _closure_reason(risk_class),
    }


def _risk_class(routes: list[str], methods: list[str]) -> str:
    tokens = {token for route in routes for token in _route_tokens(route)}
    if MUTATING_METHODS & set(methods) or MUTATION_TOKENS & tokens:
        return "effect_bearing"
    if methods == ["GET"] and tokens & READ_MODEL_TOKENS:
        return "read_model"
    return "mixed"


def _suggested_proof_level(risk_class: str) -> str:
    if risk_class == "read_model":
        return "read_model"
    return "action_proof"


def _closure_reason(risk_class: str) -> str:
    if risk_class == "effect_bearing":
        return "mutating method or effect-bearing route token requires request and action proof"
    if risk_class == "read_model":
        return "read-only route family can close as a bounded read model with no mutation path"
    return "ambiguous route family requires explicit read/effect split before closure"


def _route_tokens(route: str) -> list[str]:
    tokens: list[str] = []
    for part in route.strip("/").split("/"):
        tokens.extend(token for token in re.split(r"[^a-zA-Z0-9]+", part.lower()) if token)
    return tokens


def _family_token(family: str) -> str:
    parts = [part for part in family.strip("/").split("/") if part not in {"api", "v1"}]
    token = "_".join(
        re.sub(r"[^a-zA-Z0-9]+", "_", part).strip("_").lower()
        for part in parts
        if part
    )
    if not token:
        return "root"
    return token


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate proof route gap triage witness.")
    parser.add_argument("--matrix", type=Path, default=CANONICAL_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print the report to stdout.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    report = build_gap_triage_report(matrix)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not args.output.exists():
            raise SystemExit(f"{args.output} is missing; run scripts/proof_route_gap_triage.py")
        actual = args.output.read_text(encoding="utf-8")
        if actual != rendered:
            raise SystemExit(f"{args.output} is stale; run scripts/proof_route_gap_triage.py")
    else:
        write_gap_triage_report(report, args.output)
    if args.json:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
