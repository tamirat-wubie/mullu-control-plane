"""Purpose: verify causal runtime ledger append, cause, and hash-chain rules.
Governance scope: append-only event lineage and deterministic verification.
Dependencies: mcoi_runtime.core.causal_runtime_ledger.
Invariants: unknown causes fail closed; event hashes bind previous hashes.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.causal_runtime_ledger import CausalRuntimeLedger, hash_runtime_payload
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


def _clock() -> str:
    return "2026-05-13T12:00:00+00:00"


def test_ledger_appends_hash_chained_events_with_causes() -> None:
    ledger = CausalRuntimeLedger(clock=_clock)
    first = ledger.append(
        tenant_id="tenant-1",
        actor_id="agent-1",
        surface="runtime",
        action="plan.created",
        outcome="accepted",
        correlation_id="corr-1",
        input_hash=hash_runtime_payload({"goal": "inspect"}),
    )
    second = ledger.append(
        tenant_id="tenant-1",
        actor_id="agent-1",
        surface="runtime",
        action="tool.ready",
        outcome="accepted",
        correlation_id="corr-1",
        cause_event_ids=(first.event_id,),
        constraint_refs=("constraint:tool-ready",),
        proof_refs=("proof://tool-ready",),
    )

    assert ledger.event_count == 2
    assert second.cause_event_ids == (first.event_id,)
    assert second.previous_event_hash == first.event_hash
    assert ledger.verify_chain().verified is True


def test_ledger_rejects_unknown_cause_before_append() -> None:
    ledger = CausalRuntimeLedger(clock=_clock)

    with pytest.raises(RuntimeCoreInvariantError, match="cause event not found"):
        ledger.append(
            tenant_id="tenant-1",
            actor_id="agent-1",
            surface="runtime",
            action="tool.ready",
            outcome="accepted",
            correlation_id="corr-1",
            cause_event_ids=("missing-event",),
        )

    assert ledger.event_count == 0
    assert ledger.last_event_hash == "0" * 64
    assert ledger.verify_chain().event_count == 0


def test_ledger_filters_events_by_surface_and_correlation() -> None:
    ledger = CausalRuntimeLedger(clock=_clock)
    ledger.append(
        tenant_id="tenant-1",
        actor_id="agent-1",
        surface="tool_gateway",
        action="tool.invoke",
        outcome="succeeded",
        correlation_id="corr-1",
    )
    ledger.append(
        tenant_id="tenant-1",
        actor_id="agent-1",
        surface="runtime",
        action="plan.closed",
        outcome="accepted",
        correlation_id="corr-2",
    )

    tool_events = ledger.list_events(surface="tool_gateway")
    corr_events = ledger.list_events(correlation_id="corr-2")

    assert len(tool_events) == 1
    assert tool_events[0].surface == "tool_gateway"
    assert len(corr_events) == 1
    assert corr_events[0].correlation_id == "corr-2"
