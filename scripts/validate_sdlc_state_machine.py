#!/usr/bin/env python3
"""Validate the governed SDLC state machine.

Purpose: verify lifecycle states, canonical transitions, blocked states, and
terminal closure evidence for software delivery governance.
Governance scope: OCE state completeness, RAG transition connectivity, CDCV
transition cause evidence, CQTE bounded blocker states, UWMA receipt linkage,
and PRS terminal state closure.
Dependencies: Python standard library and scripts/validate_sdlc_artifact.py.
Invariants:
  - Terminal states have no outgoing transitions.
  - Canonical progression remains ordered and explicit.
  - Closure examples must use a terminal state and receipt evidence.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_sdlc_artifact import (  # noqa: E402
    ARTIFACT_SPEC_BY_KIND,
    load_document_text,
    load_json_object,
    validate_artifact_record,
)


ACTIVE_STATES = (
    "proposed",
    "triaged",
    "requirements_defined",
    "design_ready",
    "planned",
    "implementation_active",
    "verification_active",
    "security_review",
    "release_candidate",
    "deployment_candidate",
    "deployed",
    "monitored",
    "closed",
)
BLOCKED_STATES = (
    "blocked_requirements",
    "blocked_design",
    "blocked_verification",
    "blocked_security",
    "blocked_release",
    "blocked_deployment",
    "blocked_runtime",
)
TERMINAL_STATES = (
    "closed_success",
    "closed_rejected",
    "closed_superseded",
    "closed_rolled_back",
    "closed_failed_with_receipt",
)
CANONICAL_TRANSITIONS = tuple(zip(ACTIVE_STATES, ACTIVE_STATES[1:])) + (("closed", "closed_success"),)
DEFAULT_TRANSITIONS = CANONICAL_TRANSITIONS + (
    ("triaged", "blocked_requirements"),
    ("requirements_defined", "blocked_design"),
    ("verification_active", "blocked_verification"),
    ("security_review", "blocked_security"),
    ("release_candidate", "blocked_release"),
    ("deployment_candidate", "blocked_deployment"),
    ("deployed", "blocked_runtime"),
    ("blocked_requirements", "closed_failed_with_receipt"),
    ("blocked_design", "closed_failed_with_receipt"),
    ("blocked_verification", "closed_failed_with_receipt"),
    ("blocked_security", "closed_failed_with_receipt"),
    ("blocked_release", "closed_failed_with_receipt"),
    ("blocked_deployment", "closed_failed_with_receipt"),
    ("blocked_runtime", "closed_failed_with_receipt"),
)
ALL_STATES = set(ACTIVE_STATES) | set(BLOCKED_STATES) | set(TERMINAL_STATES)
STATE_MACHINE_DOC = WORKSPACE_ROOT / "docs" / "SDLC_STATE_MACHINE.md"


def validate_state_machine_document(document_path: Path = STATE_MACHINE_DOC) -> list[str]:
    """Validate that the state machine document declares the canonical states."""

    document_text = load_document_text(document_path)
    normalized_document_text = " ".join(document_text.split())
    errors: list[str] = []
    for state_name in ACTIVE_STATES + BLOCKED_STATES + TERMINAL_STATES:
        if state_name not in document_text:
            errors.append(f"state machine document missing state: {state_name}")
    for source_state, target_state in CANONICAL_TRANSITIONS:
        transition_text = f"{source_state} -> {target_state}"
        if transition_text not in normalized_document_text and source_state != "closed":
            errors.append(f"state machine document missing transition: {transition_text}")
    if "transition_allowed(s1 -> s2)" not in document_text:
        errors.append("state machine document missing transition rule")
    return errors


def validate_state_machine_graph(
    transitions: tuple[tuple[str, str], ...] = DEFAULT_TRANSITIONS,
) -> list[str]:
    """Validate transition topology."""

    errors: list[str] = []
    observed_transition_set = set(transitions)
    for source_state, target_state in transitions:
        if source_state not in ALL_STATES:
            errors.append(f"unknown transition source state: {source_state}")
        if target_state not in ALL_STATES:
            errors.append(f"unknown transition target state: {target_state}")
        if source_state in TERMINAL_STATES:
            errors.append(f"terminal state has outgoing transition: {source_state}")
    for transition in CANONICAL_TRANSITIONS:
        if transition not in observed_transition_set:
            errors.append(f"missing canonical transition: {transition[0]} -> {transition[1]}")
    if len(observed_transition_set) != len(transitions):
        errors.append("state machine transitions must not contain duplicates")
    return errors


def validate_closure_state(closure_path: Path | None = None) -> list[str]:
    """Validate closure example state and receipt evidence."""

    spec = ARTIFACT_SPEC_BY_KIND["closure_receipt"]
    resolved_path = spec.example_path if closure_path is None else closure_path
    closure = load_json_object(resolved_path, "SDLC closure receipt")
    errors = validate_artifact_record("closure_receipt", closure)
    terminal_state = closure.get("terminal_state")
    if terminal_state not in TERMINAL_STATES:
        errors.append("closure terminal_state is not terminal")
    if not closure.get("receipts"):
        errors.append("closure must carry receipt evidence")
    if terminal_state == "closed_success" and closure.get("known_remaining_blockers"):
        errors.append("closed_success cannot carry remaining blockers")
    return errors


def validate_contract() -> list[str]:
    """Validate the SDLC state machine contract."""

    errors = validate_state_machine_document()
    errors.extend(validate_state_machine_graph())
    errors.extend(validate_closure_state())
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate SDLC state machine."""

    parser = argparse.ArgumentParser(description="Validate SDLC state machine.")
    parser.add_argument("--closure", type=Path, help="optional closure receipt path")
    args = parser.parse_args(argv)

    try:
        errors = validate_state_machine_document()
        errors.extend(validate_state_machine_graph())
        errors.extend(validate_closure_state(args.closure))
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"[FAIL] sdlc-state-machine-load: {exc}\nSTATUS: failed\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[FAIL] sdlc-state-machine: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] sdlc_state_machine_document\n")
    sys.stdout.write("[PASS] sdlc_state_machine_topology\n")
    sys.stdout.write("[PASS] sdlc_state_machine_closure\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
