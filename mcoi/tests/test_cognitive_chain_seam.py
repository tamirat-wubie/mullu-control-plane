"""Tests for the agent-chain cognitive seam helpers (PR 3).

The chain endpoint reuses the same gate/shadow/learn entrypoints as the workflow
seam (already covered in test_cognitive_live_integration.py); these tests cover the
chain-specific bits: the coarse capability-key derivation and the shared block detail.
"""

from __future__ import annotations

from mcoi_runtime.app.cognitive_live_integration import (
    chain_capability_key,
    cognitive_block_detail,
)


def test_chain_key_uses_first_nonempty_step_name():
    assert chain_capability_key(("plan", "act")) == "agent_chain:plan"


def test_chain_key_skips_blank_step_names():
    assert chain_capability_key(("  ", "act")) == "agent_chain:act"


def test_chain_key_empty_chain_is_generic():
    assert chain_capability_key(()) == "agent_chain"
    assert chain_capability_key(("", "   ")) == "agent_chain"


def test_chain_key_is_deterministic():
    assert chain_capability_key(("plan", "act")) == chain_capability_key(("plan", "act"))


def test_cognitive_block_detail_shape():
    detail = cognitive_block_detail("defer_to_review")
    assert detail["error_code"] == "cognitive_gate_withheld"
    assert detail["verdict"] == "defer_to_review"
    assert detail["governed"] is True
    assert isinstance(detail["error"], str) and detail["error"]
