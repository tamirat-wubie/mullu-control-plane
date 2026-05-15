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
from mcoi_runtime.core.proof_bridge import ProofBridge


# SHA-256 of "contract-test-entity:idle:running:start:before-h:after-h:genesis"
EXPECTED_HASH = "27bf13eff30cd9fd5fc334eff381e9b2349037bd0ef9dc88c2ca15d114a77fe5"

CANONICAL_CONTENT = (
    "contract-test-entity:idle:running:start:before-h:after-h:genesis"
)

EXPECTED_STATE_HASH = "965b4f39a0784ee6858ff1e38a591b741edb48787395f2391e2089dbfadc534d"

CANONICAL_STATE_CONTENT = (
    "evaluating:request:tenant-alpha:/v1/govern:2026-04-28T00:00:00Z"
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


def test_canonical_state_content_hashes_to_expected_constant():
    """Sanity: the state-hash fixture locks docs/STATE_HASH_SPEC.md v1."""
    digest = hashlib.sha256(CANONICAL_STATE_CONTENT.encode()).hexdigest()

    assert digest == EXPECTED_STATE_HASH
    assert len(digest) == 64
    assert digest.islower()


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
    # replay_token is sha256(content + ":" + timestamp)[:16] on both sides.
    # Locking it in addition to receipt_hash catches any drift in the
    # replay-token derivation that the receipt_hash alone wouldn't surface.
    assert capsule.receipt.replay_token == "replay-4c4180b2fd61031d"


def test_python_state_hash_matches_rust():
    """ProofBridge._state_hash must match maf-kernel::state_hash for the
    canonical fixture in the Rust mirror test."""
    bridge = ProofBridge(clock=lambda: "2026-04-28T00:00:00Z")
    digest = bridge._state_hash(
        "evaluating",
        "request:tenant-alpha:/v1/govern",
        "2026-04-28T00:00:00Z",
    )

    assert digest == EXPECTED_STATE_HASH
    assert len(digest) == 64
    assert digest.islower()
