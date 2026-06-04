#!/usr/bin/env python3
"""Validate SDLC pull request enforcement contracts.

Purpose: verify that SDLC evidence is required at PR review, CI, branch
protection, and release/rollback handoff boundaries.
Governance scope: OCE PR evidence completeness, RAG PR-to-artifact linkage,
CDCV merge gate causality, CQTE decidable CI contexts, UWMA CI receipt
anchoring, and PRS closure evidence.
Dependencies: Python standard library, .github/pull_request_template.md,
.github/workflows/ci.yml, docs/SDLC_PR_ENFORCEMENT.md, branch ruleset
witness, and SDLC validators.
Invariants:
  - Validation is read-only and deterministic.
  - SDLC governance has a stable CI context.
  - Build Verification depends on the SDLC governance gate.
  - Branch protection witness retains required status contexts.
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
RULESET_WITNESS_PATH = WORKSPACE_ROOT / "docs" / "main-protection-ruleset-witness.json"

SDLC_COMMANDS = (
    "python scripts/validate_sdlc_artifact.py",
    "python scripts/validate_sdlc_route.py",
    "python scripts/validate_sdlc_state_machine.py",
    "python scripts/validate_sdlc_release_readiness.py --strict",
    "python scripts/validate_sdlc_security_review.py --strict",
    "python scripts/validate_sdlc_pr_enforcement.py",
    "python scripts/run_workspace_governance_checks.py --json --receipt-path .tmp/workspace-governance-preflight-receipt.json",
)
REQUIRED_RULESET_STATUS_CONTEXTS = (
    "Rust Tests",
    "Schema Validation",
    "Python Tests (ubuntu-latest, Python 3.13)",
    "SDLC Governance Gate",
)
REQUIRED_RULESET_TYPES = ("deletion", "non_fast_forward", "pull_request", "required_status_checks")
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
    ruleset_witness: dict[str, Any]


def load_text_file(path: Path) -> str:
    """Load one UTF-8 text file."""

    if not path.exists():
        raise FileNotFoundError(f"missing SDLC enforcement file: {_label_path(path)}")
    if not path.is_file():
        raise IsADirectoryError(f"SDLC enforcement path is not a file: {_label_path(path)}")
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object file."""

    if not path.exists():
        raise FileNotFoundError(f"missing SDLC enforcement file: {_label_path(path)}")
    if not path.is_file():
        raise IsADirectoryError(f"SDLC enforcement path is not a file: {_label_path(path)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"SDLC enforcement JSON must be an object: {_label_path(path)}")
    return payload


def load_enforcement_texts() -> EnforcementTexts:
    """Load repository SDLC PR enforcement surfaces."""

    return EnforcementTexts(
        pr_template=load_text_file(PR_TEMPLATE_PATH),
        ci_workflow=load_text_file(CI_WORKFLOW_PATH),
        enforcement_doc=load_text_file(ENFORCEMENT_DOC_PATH),
        release_policy=load_text_file(RELEASE_POLICY_PATH),
        ruleset_witness=load_json_object(RULESET_WITNESS_PATH),
    )


def validate_pr_template(template_text: str) -> list[str]:
    """Validate PR template SDLC evidence requirements."""

    errors: list[str] = []
    required_terms = (
        "## SDLC / SDLD evidence",
        "documentation-only or read-only",
        "SDLC route used",
        "python scripts/route_sdlc.py",
        "python scripts/validate_sdlc_route.py",
        "Gate decision envelope",
        "Inventory closure",
        "Workspace preflight receipt",
        "Branch protection witness",
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
    required_terms += REQUIRED_RULESET_STATUS_CONTEXTS
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
        "SDLC route used",
        "python scripts/route_sdlc.py",
        "python scripts/validate_sdlc_route.py",
        "main-protection",
        "branch protection",
        "merge_ready",
        "sdlc_branch_ruleset_witness proves `main-protection` requires SDLC-critical status contexts",
        "gate_decision_envelopes are retained through terminal closure",
        "sdlc_inventory_closure proves canonical schema and example coverage",
        "sdlc_workspace_preflight_closure proves workspace preflight command, receipt artifact, validator output, and closure retention",
        "implementation deltas have `sdlc_implementation_receipt` evidence",
        "state transitions have `sdlc_transition_receipt` evidence",
        "recovery handoff has `sdlc_recovery_handoff_receipt` evidence",
        "rollback_or_incident_handoff",
        "AwaitingEvidence",
        "GovernanceBlocked",
    )
    required_terms += SDLC_COMMANDS
    required_terms += REQUIRED_RULESET_STATUS_CONTEXTS
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


def validate_ruleset_witness(witness: dict[str, Any]) -> list[str]:
    """Validate the local main-protection branch ruleset witness."""

    errors: list[str] = []
    if witness.get("ruleset_name") != "main-protection":
        errors.append("sdlc_ruleset_witness: ruleset_name must be main-protection")
    if witness.get("target") != "branch":
        errors.append("sdlc_ruleset_witness: target must be branch")
    if witness.get("enforcement") != "active":
        errors.append("sdlc_ruleset_witness: enforcement must be active")
    if "~DEFAULT_BRANCH" not in witness.get("ref_includes", []):
        errors.append("sdlc_ruleset_witness: ref_includes must include ~DEFAULT_BRANCH")
    if witness.get("bypass_actors") != []:
        errors.append("sdlc_ruleset_witness: bypass_actors must be empty")
    if witness.get("current_user_can_bypass") != "never":
        errors.append("sdlc_ruleset_witness: current_user_can_bypass must be never")

    rules = witness.get("rules", [])
    if not isinstance(rules, list):
        return errors + ["sdlc_ruleset_witness: rules must be a list"]
    rules_by_type = {rule.get("type"): rule for rule in rules if isinstance(rule, dict)}
    missing_rule_types = set(REQUIRED_RULESET_TYPES) - set(rules_by_type)
    if missing_rule_types:
        errors.append(f"sdlc_ruleset_witness: missing required rule types: {sorted(missing_rule_types)}")

    pull_request_rule = rules_by_type.get("pull_request", {})
    if pull_request_rule.get("required_review_thread_resolution") is not True:
        errors.append("sdlc_ruleset_witness: pull_request rule must require review thread resolution")

    status_rule = rules_by_type.get("required_status_checks", {})
    status_checks = status_rule.get("required_status_checks", [])
    if not isinstance(status_checks, list):
        errors.append("sdlc_ruleset_witness: required_status_checks must be a list")
    else:
        observed_contexts = tuple(
            check.get("context") for check in status_checks if isinstance(check, dict) and isinstance(check.get("context"), str)
        )
        missing_contexts = set(REQUIRED_RULESET_STATUS_CONTEXTS) - set(observed_contexts)
        unexpected_contexts = set(observed_contexts) - set(REQUIRED_RULESET_STATUS_CONTEXTS)
        if missing_contexts:
            errors.append(f"sdlc_ruleset_witness: missing required status contexts: {sorted(missing_contexts)}")
        if unexpected_contexts:
            errors.append(f"sdlc_ruleset_witness: unexpected required status contexts: {sorted(unexpected_contexts)}")
        if len(observed_contexts) != len(set(observed_contexts)):
            errors.append("sdlc_ruleset_witness: required status contexts must be unique")
    return errors


def validate_contract(texts: EnforcementTexts | None = None) -> list[str]:
    """Validate all SDLC PR enforcement surfaces."""

    loaded_texts = load_enforcement_texts() if texts is None else texts
    errors: list[str] = []
    errors.extend(validate_pr_template(loaded_texts.pr_template))
    errors.extend(validate_ci_workflow(loaded_texts.ci_workflow))
    errors.extend(validate_enforcement_document(loaded_texts.enforcement_doc))
    errors.extend(validate_release_policy_links(loaded_texts.release_policy))
    errors.extend(validate_ruleset_witness(loaded_texts.ruleset_witness))
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
        "sdlc_branch_ruleset_witness",
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
            _label_path(RULESET_WITNESS_PATH),
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
    for path in (PR_TEMPLATE_PATH, CI_WORKFLOW_PATH, ENFORCEMENT_DOC_PATH, RELEASE_POLICY_PATH, RULESET_WITNESS_PATH):
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

    for check in report["checks"]:
        sys.stdout.write(f"[PASS] {check['name']}\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
