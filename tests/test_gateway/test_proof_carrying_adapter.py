"""Proof-carrying adapter tests.

Tests: capability execution receipt normalization, proof downgrade, and
exception capture for the gateway causal runtime boundary.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.command_spine import (  # noqa: E402
    CommandLedger,
    capability_passport_for,
)
from gateway.proof_carrying_adapter import (  # noqa: E402
    CapabilityExecutionStatus,
    ProofCarryingCapabilityAdapter,
)


def _payment_command() -> tuple[CommandLedger, object, object]:
    ledger = CommandLedger(clock=lambda: "2026-04-24T12:00:00+00:00")
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-proof-adapter",
        intent="financial.send_payment",
        payload={
            "body": "make a payment of $50",
            "skill_intent": {
                "skill": "financial",
                "action": "send_payment",
                "params": {"amount": "50"},
            },
        },
    )
    action = ledger.bind_governed_action(command.command_id)
    return ledger, command, action


def test_proof_adapter_wraps_successful_effect_bearing_result() -> None:
    _, command, action = _payment_command()
    adapter = ProofCarryingCapabilityAdapter(clock=lambda: "2026-04-24T12:00:01+00:00")

    execution = adapter.execute(
        command=command,
        governed_action=action,
        capability_passport=capability_passport_for("financial.send_payment"),
        executor=lambda: {
            "response": "Payment processed.",
            "transaction_id": "tx-1",
            "amount": "50",
            "currency": "USD",
            "recipient_hash": "recipient-proof",
            "ledger_hash": "ledger-proof",
        },
    )

    assert execution.receipt.status is CapabilityExecutionStatus.SUCCEEDED
    assert execution.receipt.command_id == command.command_id
    assert execution.receipt.actual_effects
    assert execution.receipt.evidence_refs
    assert execution.result["proof_carrying_receipt"]["execution_id"] == execution.receipt.execution_id


def test_proof_adapter_downgrades_missing_mutation_proof_to_review() -> None:
    _, command, action = _payment_command()
    adapter = ProofCarryingCapabilityAdapter(clock=lambda: "2026-04-24T12:00:01+00:00")

    execution = adapter.execute(
        command=command,
        governed_action=action,
        capability_passport=capability_passport_for("financial.send_payment"),
        executor=lambda: {"response": "Payment processed."},
    )

    assert execution.receipt.status is CapabilityExecutionStatus.REQUIRES_REVIEW
    assert execution.result["error"] == "missing_required_proof"
    assert "transaction_id" in execution.result["missing_proof_fields"]
    assert execution.receipt.evidence_refs


def test_proof_adapter_converts_exception_to_failed_receipt() -> None:
    _, command, action = _payment_command()
    adapter = ProofCarryingCapabilityAdapter(clock=lambda: "2026-04-24T12:00:01+00:00")

    def fail() -> object:
        raise RuntimeError("provider unavailable")

    execution = adapter.execute(
        command=command,
        governed_action=action,
        capability_passport=capability_passport_for("financial.send_payment"),
        executor=fail,
    )

    assert execution.receipt.status is CapabilityExecutionStatus.FAILED
    assert execution.result["error"] == "RuntimeError"
    assert execution.result["proof_carrying_receipt"]["status"] == "failed"
    assert execution.receipt.evidence_refs
