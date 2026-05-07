#!/usr/bin/env python3
"""Validate the formal logic governance application doctrine.

Purpose: fail closed when the logic governance doctrine loses required laws,
surface rules, Mfidel atomicity constraints, halt conditions, or PRS anchors.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: docs/60_logic_governance_application.md.
Invariants: the doctrine remains complete enough to govern code, schema,
proof, Phi traversal, and Mfidel substrate changes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
LOGIC_GOVERNANCE_DOC = REPO_ROOT / "docs" / "60_logic_governance_application.md"

REQUIRED_SECTIONS: tuple[str, ...] = (
    "# Logic Governance Application",
    "## 1. Decision",
    "## 2. Repository Logic Object",
    "## 3. Phi Traversal Applied To Code Change",
    "## 4. Core Predicates",
    "## 5. Governance Law Mapping",
    "## 6. Surface-Specific Logic Rules",
    "### 6.1 Governance package",
    "### 6.2 Proof coverage matrix",
    "### 6.3 Phi operator and UCJA pipeline",
    "### 6.4 Mfidel substrate and overlay",
    "### 6.5 Schemas and public protocol",
    "### 6.6 Runtime closure and promotion",
    "## 7. Test Logic Contract",
    "## 8. Change Execution Checklist",
    "## 9. Halt Conditions",
    "## 10. Proof-of-Resolution Stamp Template",
    "## 11. Operator Summary",
)

REQUIRED_LAWS: tuple[str, ...] = ("OCE", "RAG", "CDCV", "CQTE", "UWMA", "SRCA", "PRS")

REQUIRED_PREDICATES: tuple[str, ...] = (
    "`defined(symbol)`",
    "`governed(surface)`",
    "`atomic(fidel)`",
    "`caused(transition)`",
    "`bounded(error)`",
    "`deterministic(operation)`",
    "`terminates(operation)`",
    "`fail_closed(gate)`",
    "`append_only(record)`",
    "`pool_safe(write)`",
)

REQUIRED_HALT_LITERALS: tuple[str, ...] = (
    "A symbol, status, field, route, or proof term is undefined.",
    "A hard constraint conflicts with another hard constraint.",
    "A state transition lacks a cause or witness.",
    "A failure path can silently succeed.",
    "A public schema change lacks validator/test alignment.",
    "A governance write is not atomic and affects shared runtime state.",
    "A user-visible error leaks unbounded caller-controlled input.",
    "A Phi traversal can recurse or loop without termination evidence.",
    "Mfidel processing decomposes a fidel unit.",
    "A completed task cannot produce a proof-of-resolution trace.",
)

REQUIRED_MFIDEL_LITERALS: tuple[str, ...] = (
    "atomic(fidel)",
    "No Unicode normalization, decomposition, recomposition, root-letter logic",
    "Semantic overlay may group artifacts by meaning, but it cannot redefine",
    "if implementation decomposes Ethiopic codepoint:",
    "reject change",
)

REQUIRED_PRS_FIELDS: tuple[str, ...] = (
    "change_id:",
    "affected_surfaces:",
    "symbols_defined:",
    "constraints_enforced:",
    "invariants_preserved:",
    "tests_or_validators:",
    "witness_artifacts:",
    "rollback_or_halt_path:",
    "open_issues:",
)

FORBIDDEN_LITERALS: tuple[str, ...] = (
    " ".join(("artificial", "intelligence")),
)


def validate_logic_governance_text(content: str) -> list[str]:
    """Validate required doctrine anchors with bounded error messages."""
    errors: list[str] = []

    for section in REQUIRED_SECTIONS:
        if section not in content:
            errors.append(f"missing section: {section}")

    for law in REQUIRED_LAWS:
        if law not in content:
            errors.append(f"missing governance law: {law}")

    for predicate in REQUIRED_PREDICATES:
        if predicate not in content:
            errors.append(f"missing predicate: {predicate}")

    for literal in REQUIRED_HALT_LITERALS:
        if literal not in content:
            errors.append(f"missing halt condition: {literal}")

    for literal in REQUIRED_MFIDEL_LITERALS:
        if literal not in content:
            errors.append(f"missing Mfidel invariant: {literal}")

    for field in REQUIRED_PRS_FIELDS:
        if field not in content:
            errors.append(f"missing PRS field: {field}")

    for forbidden_literal in FORBIDDEN_LITERALS:
        if forbidden_literal in content.lower():
            errors.append(f"forbidden literal present: {forbidden_literal}")

    if "STATUS:\n  Completeness: 100%" not in content:
        errors.append("missing complete status block")
    if "Open issues: none" not in content:
        errors.append("status block must name open issues")

    return errors


def validate_logic_governance_document(path: Path = LOGIC_GOVERNANCE_DOC) -> list[str]:
    """Validate the canonical logic governance document exists and is complete."""
    if not path.exists():
        return [f"missing document: {path.relative_to(REPO_ROOT).as_posix()}"]
    return validate_logic_governance_text(path.read_text(encoding="utf-8"))


def validation_report(path: Path = LOGIC_GOVERNANCE_DOC) -> dict[str, Any]:
    """Return a deterministic validation report for operator witnesses."""
    errors = validate_logic_governance_document(path)
    return {
        "document": path.relative_to(REPO_ROOT).as_posix(),
        "passed": not errors,
        "errors": errors,
        "required_sections": list(REQUIRED_SECTIONS),
        "required_laws": list(REQUIRED_LAWS),
        "required_predicates": list(REQUIRED_PREDICATES),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print a JSON validation report.")
    args = parser.parse_args()

    report = validation_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["passed"]:
        print(f"logic governance application ok: {report['document']}")
    else:
        for error in report["errors"]:
            print(error)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
