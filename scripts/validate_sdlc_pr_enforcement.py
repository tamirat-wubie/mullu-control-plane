#!/usr/bin/env python3
"""Validate SDLC pull request enforcement contracts.

Purpose: verify that SDLC evidence is required at PR review, CI, branch
protection, and release/rollback handoff boundaries.
Governance scope: OCE PR evidence completeness, RAG PR-to-artifact linkage,
CDCV merge gate causality, CQTE decidable CI contexts, UWMA CI receipt
anchoring, and PRS closure evidence.
Dependencies: Python standard library, .github/pull_request_template.md,
.github/workflows/ci.yml, docs/SDLC_PR_ENFORCEMENT.md, and SDLC validators.
Invariants:
  - Validation is read-only and deterministic.
  - SDLC governance has a stable CI context.
  - Build Verification depends on the SDLC governance gate.
  - PR evidence includes rollback or incident handoff for effect-bearing work.
  - Validation receipt writes cannot escape the workspace root.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PR_TEMPLATE_PATH = WORKSPACE_ROOT / ".github" / "pull_request_template.md"
CI_WORKFLOW_PATH = WORKSPACE_ROOT / ".github" / "workflows" / "ci.yml"
ENFORCEMENT_DOC_PATH = WORKSPACE_ROOT / "docs" / "SDLC_PR_ENFORCEMENT.md"
RELEASE_POLICY_PATH = WORKSPACE_ROOT / "docs" / "SDLC_RELEASE_POLICY.md"

SDLC_COMMANDS = (
    "python scripts/validate_sdlc_artifact.py",
    "python scripts/validate_sdlc_state_machine.py",
    "python scripts/validate_sdlc_release_readiness.py --strict",
    "python scripts/validate_sdlc_security_review.py --strict",
    "python scripts/validate_sdlc_pr_enforcement.py",
)
SDLC_ARTIFACT_TERMS = (
    "Change request",
    "Requirement",
    "Design decision",
    "Work plan",
    "Implementation receipt",
    "Transition receipt",
    "Verification receipt",
    "Security review",
    "Release or deployment candidate",
    "Recovery handoff receipt",
    "Closure receipt",
)


@dataclass(frozen=True, slots=True)
class EnforcementTexts:
    """Repository text surfaces that define SDLC PR enforcement."""

    pr_template: str
    ci_workflow: str
    enforcement_doc: str
    release_policy: str


def load_text_file(path: Path) -> str:
    """Load one UTF-8 text file."""

    if not path.exists():
        raise FileNotFoundError(f"missing SDLC enforcement file: {_label_path(path)}")
    if not path.is_file():
        raise IsADirectoryError(f"SDLC enforcement path is not a file: {_label_path(path)}")
    return path.read_text(encoding="utf-8")


def load_enforcement_texts() -> EnforcementTexts:
    """Load repository SDLC PR enforcement surfaces."""

    return EnforcementTexts(
        pr_template=load_text_file(PR_TEMPLATE_PATH),
        ci_workflow=load_text_file(CI_WORKFLOW_PATH),
        enforcement_doc=load_text_file(ENFORCEMENT_DOC_PATH),
        release_policy=load_text_file(RELEASE_POLICY_PATH),
    )


def validate_pr_template(template_text: str) -> list[str]:
    """Validate PR template SDLC evidence requirements."""

    errors: list[str] = []
    required_terms = (
        "## SDLC / SDLD evidence",
        "documentation-only or read-only",
        "Gate decision envelope",
        "Closure receipt retains every upstream UAO, causal trace, implementation receipt, transition receipt, recovery handoff receipt, and receipt reference",
        "Rollback or incident handoff path",
    )
    required_terms += SDLC_ARTIFACT_TERMS
    required_terms += SDLC_COMMANDS
    errors.extend(_missing_terms("pull_request_template", template_text, required_terms))
    return errors


def validate_ci_workflow(workflow_text: str) -> list[str]:
    """Validate CI has a stable SDLC enforcement context."""

    errors: list[str] = []
    required_terms = (
        "sdlc-governance-gate:",
        "name: SDLC Governance Gate",
        "ruleset `main-protection` can require it directly",
        "name: sdlc-artifact-validation-receipt",
        "tests/test_validate_sdlc_pr_enforcement.py",
    )
    required_terms += SDLC_COMMANDS
    errors.extend(_missing_terms("ci_workflow", workflow_text, required_terms))
    if "needs: [python-required-status, typescript-sdk, rust-tests, schema-validation, sdlc-governance-gate" not in workflow_text:
        errors.append("ci_workflow missing Build Verification dependency on sdlc-governance-gate")
    if workflow_text.find("sdlc-governance-gate:") > workflow_text.find("build-verification:"):
        errors.append("ci_workflow must define sdlc-governance-gate before build-verification")
    return errors


def validate_enforcement_document(document_text: str) -> list[str]:
    """Validate the SDLC PR enforcement doctrine document."""

    required_terms = (
        "Purpose: bind governed software delivery evidence",
        "SDLC Governance Gate",
        "main-protection",
        "branch protection",
        "merge_ready",
        "gate_decision_envelopes are retained through terminal closure",
        "implementation deltas have `sdlc_implementation_receipt` evidence",
        "state transitions have `sdlc_transition_receipt` evidence",
        "recovery handoff has `sdlc_recovery_handoff_receipt` evidence",
        "rollback_or_incident_handoff",
        "AwaitingEvidence",
        "GovernanceBlocked",
    )
    required_terms += SDLC_COMMANDS
    return _missing_terms("sdlc_pr_enforcement_doc", document_text, required_terms)


def validate_release_policy_links(release_policy_text: str) -> list[str]:
    """Validate release policy binds rollback, incidents, and terminal closure."""

    required_terms = (
        "## Rollback And Incident Linkage",
        "rollback or incident handoff path",
        "incident_recovery_path_if_rollback_fails",
        "sdlc_recovery_handoff_receipt",
        "terminal_closure_certificate_or_sdlc_closure_receipt",
        "terminal closure certificates",
        "SDLC closure receipts",
    )
    return _missing_terms("sdlc_release_policy", release_policy_text, required_terms)


def validate_contract(texts: EnforcementTexts | None = None) -> list[str]:
    """Validate all SDLC PR enforcement surfaces."""

    loaded_texts = load_enforcement_texts() if texts is None else texts
    errors: list[str] = []
    errors.extend(validate_pr_template(loaded_texts.pr_template))
    errors.extend(validate_ci_workflow(loaded_texts.ci_workflow))
    errors.extend(validate_enforcement_document(loaded_texts.enforcement_doc))
    errors.extend(validate_release_policy_links(loaded_texts.release_policy))
    return errors


def build_validation_report() -> dict[str, Any]:
    """Build a machine-readable SDLC PR enforcement validation receipt."""

    try:
        errors = validate_contract()
    except (OSError, ValueError) as exc:
        errors = [f"load-sdlc-pr-enforcement: {_sanitize_error(exc)}"]
    valid = not errors
    checks = (
        "sdlc_pr_template_evidence",
        "sdlc_ci_governance_gate",
        "sdlc_pr_enforcement_document",
        "sdlc_release_rollback_incident_linkage",
    )
    return {
        "receipt_id": "sdlc_pr_enforcement_validation_receipt",
        "terminal_closure_required": True,
        "receipt_is_not_terminal_closure": True,
        "valid": valid,
        "status": "passed" if valid else "failed",
        "document_paths": [
            _label_path(PR_TEMPLATE_PATH),
            _label_path(CI_WORKFLOW_PATH),
            _label_path(ENFORCEMENT_DOC_PATH),
            _label_path(RELEASE_POLICY_PATH),
        ],
        "checks": [{"name": check_name, "passed": valid} for check_name in checks],
        "check_count": len(checks),
        "error_count": len(errors),
        "errors": errors,
    }


def write_validation_report(report: dict[str, Any], receipt_path: Path) -> Path:
    """Persist an SDLC PR enforcement validation receipt."""

    resolved_path = resolve_receipt_path(receipt_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved_path


def resolve_receipt_path(receipt_path: Path) -> Path:
    """Resolve a workspace-local JSON receipt path and reject path escapes."""

    if receipt_path.suffix.lower() != ".json":
        raise ValueError("receipt path must use .json suffix")
    resolved_root = WORKSPACE_ROOT.resolve()
    resolved_path = (WORKSPACE_ROOT / receipt_path).resolve() if not receipt_path.is_absolute() else receipt_path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"receipt path must stay under workspace root: {receipt_path}")
    return resolved_path


def _missing_terms(surface: str, text: str, required_terms: tuple[str, ...]) -> list[str]:
    return [f"{surface} missing required term: {term}" for term in required_terms if term not in text]


def _label_path(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _sanitize_error(exc: BaseException) -> str:
    message = str(exc)
    for path in (PR_TEMPLATE_PATH, CI_WORKFLOW_PATH, ENFORCEMENT_DOC_PATH, RELEASE_POLICY_PATH):
        message = message.replace(str(path), _label_path(path))
        message = message.replace(str(path.resolve(strict=False)), _label_path(path))
    return message


def main(argv: list[str] | None = None) -> int:
    """Validate SDLC PR enforcement."""

    parser = argparse.ArgumentParser(description="Validate SDLC PR enforcement contracts.")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    parser.add_argument("--receipt-path", type=Path, help="optional path to persist the validation receipt")
    args = parser.parse_args(argv)

    report = build_validation_report()
    if args.receipt_path is not None:
        try:
            write_validation_report(report, args.receipt_path)
        except ValueError as exc:
            sys.stderr.write(f"[FAIL] receipt-path: {exc}\nSTATUS: failed\n")
            return 1
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0 if report["valid"] else 1

    if not report["valid"]:
        for error in report["errors"]:
            sys.stderr.write(f"[FAIL] sdlc-pr-enforcement: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] sdlc_pr_template_evidence\n")
    sys.stdout.write("[PASS] sdlc_ci_governance_gate\n")
    sys.stdout.write("[PASS] sdlc_pr_enforcement_document\n")
    sys.stdout.write("[PASS] sdlc_release_rollback_incident_linkage\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
