"""Cross-language contract: Python receipt_hash MUST match the Rust receipt_hash
for the same canonical inputs.

The mirror test lives at `maf/rust/crates/maf-kernel/src/lib.rs::receipt_hash_matches_python_sha256`.
If you change the canonical-content recipe on either side, both tests must be
updated in lockstep.

This closes the "Rust ↔ Python protocol drift caught only by code review" gap
documented in `docs/MAF_RECEIPT_COVERAGE.md`.
"""
from __future__ import annotations

import hashlib

from mcoi_runtime.contracts.state_machine import (
    StateMachineSpec,
    TransitionRule,
    TransitionVerdict,
)
from mcoi_runtime.contracts.proof import certify_transition


# SHA-256 of "contract-test-entity:idle:running:start:before-h:after-h:genesis"
EXPECTED_HASH = "27bf13eff30cd9fd5fc334eff381e9b2349037bd0ef9dc88c2ca15d114a77fe5"

CANONICAL_CONTENT = (
    "contract-test-entity:idle:running:start:before-h:after-h:genesis"
)


def _machine() -> StateMachineSpec:
    return StateMachineSpec(
        machine_id="test", name="Test", version="1.0",
        states=("idle", "running", "done"),
        initial_state="idle",
        terminal_states=("done",),
        transitions=(
            TransitionRule(from_state="idle", to_state="running", action="start"),
            TransitionRule(from_state="running", to_state="done", action="finish"),
        ),
    )


def test_canonical_content_hashes_to_expected_constant():
    """Sanity: the constant in this test really is SHA-256 of the canonical content.
    If this fails, the constant or the canonical-content string drifted."""
    assert hashlib.sha256(CANONICAL_CONTENT.encode()).hexdigest() == EXPECTED_HASH


def test_python_receipt_hash_matches_rust():
    """The receipt_hash produced by certify_transition with the canonical
    fixture inputs must equal EXPECTED_HASH. The Rust test
    `receipt_hash_matches_python_sha256` asserts the same constant against
    its independent implementation."""
    capsule = certify_transition(
        _machine(),
        entity_id="contract-test-entity",
        from_state="idle",
        to_state="running",
        action="start",
        before_state_hash="before-h",
        after_state_hash="after-h",
        actor_id="actor",
        reason="contract test",
        causal_parent="genesis",
        timestamp="2026-04-27T00:00:00Z",
    )
    assert capsule.receipt.receipt_hash == EXPECTED_HASH
    assert capsule.receipt.receipt_id == f"rcpt-{EXPECTED_HASH[:16]}"
    assert capsule.audit_record.audit_id == f"audit-{EXPECTED_HASH[:12]}"
    assert capsule.receipt.verdict == TransitionVerdict.ALLOWED
