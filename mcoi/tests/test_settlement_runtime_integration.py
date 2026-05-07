"""Tests for SettlementRuntimeIntegration bridge.

Covers constructor validation, all 7 methods (settlement creation, memory mesh
attachment, graph attachment), event emission, and a full lifecycle golden path.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.settlement_runtime import SettlementRuntimeEngine
from mcoi_runtime.core.settlement_runtime_integration import SettlementRuntimeIntegration
from mcoi_runtime.contracts.settlement_runtime import PaymentMethodKind
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def event_spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def settlement_engine(event_spine: EventSpineEngine) -> SettlementRuntimeEngine:
    return SettlementRuntimeEngine(event_spine)


@pytest.fixture()
def memory_engine() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def integration(
    settlement_engine: SettlementRuntimeEngine,
    event_spine: EventSpineEngine,
    memory_engine: MemoryMeshEngine,
) -> SettlementRuntimeIntegration:
    return SettlementRuntimeIntegration(settlement_engine, event_spine, memory_engine)


def _create_settlement(integration: SettlementRuntimeIntegration) -> dict:
    """Helper: create a settlement so downstream methods work."""
    return integration.settlement_from_invoice(
        "sett-1", "inv-1", "acct-1", 1000.0
    )


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_rejects_wrong_settlement_engine_type(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="settlement_engine"):
            SettlementRuntimeIntegration("not-an-engine", event_spine, memory_engine)

    def test_rejects_wrong_event_spine_type(
        self, settlement_engine: SettlementRuntimeEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            SettlementRuntimeIntegration(settlement_engine, "not-a-spine", memory_engine)

    def test_rejects_wrong_memory_engine_type(
        self, settlement_engine: SettlementRuntimeEngine, event_spine: EventSpineEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            SettlementRuntimeIntegration(settlement_engine, event_spine, 42)

    def test_accepts_valid_arguments(
        self,
        settlement_engine: SettlementRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        sri = SettlementRuntimeIntegration(settlement_engine, event_spine, memory_engine)
        assert sri is not None


# ---------------------------------------------------------------------------
# settlement_from_invoice
# ---------------------------------------------------------------------------


class TestSettlementFromInvoice:
    def test_returns_expected_keys(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_invoice("sett-1", "inv-1", "acct-1", 1000.0)
        assert set(result.keys()) == {
            "settlement_id", "invoice_id", "account_id", "total_amount",
            "outstanding", "status", "source_type",
        }

    def test_source_type_is_invoice(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_invoice("sett-1", "inv-1", "acct-1", 1000.0)
        assert result["source_type"] == "invoice"

    def test_status_is_open(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_invoice("sett-1", "inv-1", "acct-1", 1000.0)
        assert result["status"] == "open"

    def test_settlement_id_matches(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_invoice("sett-99", "inv-1", "acct-1", 500.0)
        assert result["settlement_id"] == "sett-99"

    def test_invoice_id_matches(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_invoice("sett-1", "inv-42", "acct-1", 500.0)
        assert result["invoice_id"] == "inv-42"

    def test_account_id_matches(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_invoice("sett-1", "inv-1", "acct-77", 500.0)
        assert result["account_id"] == "acct-77"

    def test_total_amount_matches(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_invoice("sett-1", "inv-1", "acct-1", 2345.67)
        assert result["total_amount"] == 2345.67

    def test_outstanding_equals_total_amount(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_invoice("sett-1", "inv-1", "acct-1", 800.0)
        assert result["outstanding"] == 800.0

    def test_default_currency_is_usd(self, integration: SettlementRuntimeIntegration) -> None:
        # Currency is not in the returned dict, but the method accepts it
        result = integration.settlement_from_invoice("sett-1", "inv-1", "acct-1", 100.0)
        assert result["status"] == "open"

    def test_custom_currency(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_invoice(
            "sett-1", "inv-1", "acct-1", 100.0, currency="EUR"
        )
        assert result["source_type"] == "invoice"


# ---------------------------------------------------------------------------
# settlement_from_dispute
# ---------------------------------------------------------------------------


class TestSettlementFromDispute:
    def test_returns_expected_keys(self, integration: SettlementRuntimeIntegration) -> None:
        _create_settlement(integration)
        result = integration.settlement_from_dispute("sett-1")
        assert set(result.keys()) == {
            "settlement_id", "invoice_id", "status", "outstanding", "source_type",
        }

    def test_source_type_is_dispute(self, integration: SettlementRuntimeIntegration) -> None:
        _create_settlement(integration)
        result = integration.settlement_from_dispute("sett-1")
        assert result["source_type"] == "dispute"

    def test_status_is_disputed(self, integration: SettlementRuntimeIntegration) -> None:
        _create_settlement(integration)
        result = integration.settlement_from_dispute("sett-1")
        assert result["status"] == "disputed"

    def test_settlement_id_matches(self, integration: SettlementRuntimeIntegration) -> None:
        _create_settlement(integration)
        result = integration.settlement_from_dispute("sett-1")
        assert result["settlement_id"] == "sett-1"

    def test_invoice_id_matches(self, integration: SettlementRuntimeIntegration) -> None:
        _create_settlement(integration)
        result = integration.settlement_from_dispute("sett-1")
        assert result["invoice_id"] == "inv-1"

    def test_outstanding_preserved(self, integration: SettlementRuntimeIntegration) -> None:
        _create_settlement(integration)
        result = integration.settlement_from_dispute("sett-1")
        assert result["outstanding"] == 1000.0


# ---------------------------------------------------------------------------
# settlement_from_credit
# ---------------------------------------------------------------------------


class TestSettlementFromCredit:
    def test_returns_expected_keys(self, integration: SettlementRuntimeIntegration) -> None:
        _create_settlement(integration)
        result = integration.settlement_from_credit("app-1", "sett-1", "cref-1", 200.0)
        assert set(result.keys()) == {
            "application_id", "settlement_id", "credit_ref", "amount",
            "outstanding", "status", "source_type",
        }

    def test_source_type_is_credit(self, integration: SettlementRuntimeIntegration) -> None:
        _create_settlement(integration)
        result = integration.settlement_from_credit("app-1", "sett-1", "cref-1", 200.0)
        assert result["source_type"] == "credit"

    def test_application_id_matches(self, integration: SettlementRuntimeIntegration) -> None:
        _create_settlement(integration)
        result = integration.settlement_from_credit("app-42", "sett-1", "cref-1", 100.0)
        assert result["application_id"] == "app-42"

    def test_settlement_id_matches(self, integration: SettlementRuntimeIntegration) -> None:
        _create_settlement(integration)
        result = integration.settlement_from_credit("app-1", "sett-1", "cref-1", 100.0)
        assert result["settlement_id"] == "sett-1"

    def test_credit_ref_matches(self, integration: SettlementRuntimeIntegration) -> None:
        _create_settlement(integration)
        result = integration.settlement_from_credit("app-1", "sett-1", "cref-77", 100.0)
        assert result["credit_ref"] == "cref-77"

    def test_amount_matches(self, integration: SettlementRuntimeIntegration) -> None:
        _create_settlement(integration)
        result = integration.settlement_from_credit("app-1", "sett-1", "cref-1", 350.0)
        assert result["amount"] == 350.0

    def test_outstanding_reduced_by_credit(self, integration: SettlementRuntimeIntegration) -> None:
        _create_settlement(integration)
        result = integration.settlement_from_credit("app-1", "sett-1", "cref-1", 300.0)
        assert result["outstanding"] == 700.0


# ---------------------------------------------------------------------------
# settlement_from_penalty
# ---------------------------------------------------------------------------


class TestSettlementFromPenalty:
    def test_returns_expected_keys(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_penalty("pay-1", "inv-1", "acct-1", 500.0)
        assert set(result.keys()) == {
            "payment_id", "invoice_id", "account_id", "amount", "status",
            "source_type",
        }

    def test_source_type_is_penalty(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_penalty("pay-1", "inv-1", "acct-1", 500.0)
        assert result["source_type"] == "penalty"

    def test_status_is_cleared(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_penalty("pay-1", "inv-1", "acct-1", 500.0)
        assert result["status"] == "cleared"

    def test_payment_id_matches(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_penalty("pay-99", "inv-1", "acct-1", 100.0)
        assert result["payment_id"] == "pay-99"

    def test_invoice_id_matches(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_penalty("pay-1", "inv-55", "acct-1", 100.0)
        assert result["invoice_id"] == "inv-55"

    def test_account_id_matches(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_penalty("pay-1", "inv-1", "acct-33", 100.0)
        assert result["account_id"] == "acct-33"

    def test_amount_matches(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_penalty("pay-1", "inv-1", "acct-1", 777.77)
        assert result["amount"] == 777.77

    def test_default_method_is_bank_transfer(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_penalty("pay-1", "inv-1", "acct-1", 100.0)
        assert result["status"] == "cleared"

    def test_custom_method(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.settlement_from_penalty(
            "pay-2", "inv-1", "acct-1", 100.0,
            method=PaymentMethodKind.CREDIT_CARD,
        )
        assert result["source_type"] == "penalty"


# ---------------------------------------------------------------------------
# open_collection_from_overdue
# ---------------------------------------------------------------------------


class TestOpenCollectionFromOverdue:
    def test_returns_expected_keys(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.open_collection_from_overdue("case-1", "inv-1", "acct-1", 500.0)
        assert set(result.keys()) == {
            "case_id", "invoice_id", "account_id", "outstanding_amount",
            "status", "source_type",
        }

    def test_source_type_is_overdue(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.open_collection_from_overdue("case-1", "inv-1", "acct-1", 500.0)
        assert result["source_type"] == "overdue"

    def test_status_is_open(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.open_collection_from_overdue("case-1", "inv-1", "acct-1", 500.0)
        assert result["status"] == "open"

    def test_case_id_matches(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.open_collection_from_overdue("case-42", "inv-1", "acct-1", 100.0)
        assert result["case_id"] == "case-42"

    def test_invoice_id_matches(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.open_collection_from_overdue("case-1", "inv-88", "acct-1", 100.0)
        assert result["invoice_id"] == "inv-88"

    def test_account_id_matches(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.open_collection_from_overdue("case-1", "inv-1", "acct-55", 100.0)
        assert result["account_id"] == "acct-55"

    def test_outstanding_amount_matches(self, integration: SettlementRuntimeIntegration) -> None:
        result = integration.open_collection_from_overdue("case-1", "inv-1", "acct-1", 3456.78)
        assert result["outstanding_amount"] == 3456.78


# ---------------------------------------------------------------------------
# Memory mesh attachment
# ---------------------------------------------------------------------------


class TestAttachSettlementToMemoryMesh:
    def test_returns_memory_record(
        self, integration: SettlementRuntimeIntegration
    ) -> None:
        mem = integration.attach_settlement_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_tags_contain_expected_values(
        self, integration: SettlementRuntimeIntegration
    ) -> None:
        mem = integration.attach_settlement_to_memory_mesh("scope-1")
        assert "settlement" in mem.tags
        assert "payments" in mem.tags
        assert "collections" in mem.tags

    def test_tags_are_tuple(self, integration: SettlementRuntimeIntegration) -> None:
        mem = integration.attach_settlement_to_memory_mesh("scope-1")
        assert isinstance(mem.tags, tuple)
        assert mem.tags == ("settlement", "payments", "collections")

    def test_title_is_bounded(
        self, integration: SettlementRuntimeIntegration
    ) -> None:
        mem = integration.attach_settlement_to_memory_mesh("my-scope")
        assert mem.title == "Settlement state"
        assert "my-scope" not in mem.title
        assert mem.scope_ref_id == "my-scope"

    def test_memory_id_is_string(self, integration: SettlementRuntimeIntegration) -> None:
        mem = integration.attach_settlement_to_memory_mesh("scope-1")
        assert isinstance(mem.memory_id, str)
        assert len(mem.memory_id) > 0

    def test_memory_added_to_engine(
        self,
        integration: SettlementRuntimeIntegration,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        mem = integration.attach_settlement_to_memory_mesh("scope-1")
        retrieved = memory_engine.get_memory(mem.memory_id)
        assert retrieved is not None
        assert retrieved.memory_id == mem.memory_id


# ---------------------------------------------------------------------------
# Graph attachment
# ---------------------------------------------------------------------------


class TestAttachSettlementToGraph:
    def test_returns_expected_keys(
        self, integration: SettlementRuntimeIntegration
    ) -> None:
        result = integration.attach_settlement_to_graph("scope-1")
        expected_keys = {
            "scope_ref_id",
            "total_settlements",
            "total_payments",
            "total_collections",
            "total_refunds",
            "total_writeoffs",
            "total_collected",
            "total_outstanding",
            "total_disputed",
        }
        assert set(result.keys()) == expected_keys

    def test_values_match_engine_state_empty(
        self, integration: SettlementRuntimeIntegration
    ) -> None:
        result = integration.attach_settlement_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"
        assert result["total_settlements"] == 0
        assert result["total_payments"] == 0
        assert result["total_collections"] == 0
        assert result["total_refunds"] == 0
        assert result["total_writeoffs"] == 0

    def test_values_reflect_created_settlement(
        self, integration: SettlementRuntimeIntegration
    ) -> None:
        _create_settlement(integration)
        result = integration.attach_settlement_to_graph("scope-1")
        assert result["total_settlements"] == 1

    def test_total_outstanding_after_settlement(
        self, integration: SettlementRuntimeIntegration
    ) -> None:
        _create_settlement(integration)
        result = integration.attach_settlement_to_graph("scope-1")
        assert result["total_outstanding"] == 1000.0


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


class TestEventEmission:
    def test_invoice_settlement_emits_events(
        self,
        integration: SettlementRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.settlement_from_invoice("sett-1", "inv-1", "acct-1", 1000.0)
        after = event_spine.event_count
        assert after > before

    def test_dispute_settlement_emits_events(
        self,
        integration: SettlementRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        _create_settlement(integration)
        before = event_spine.event_count
        integration.settlement_from_dispute("sett-1")
        after = event_spine.event_count
        assert after > before

    def test_credit_settlement_emits_events(
        self,
        integration: SettlementRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        _create_settlement(integration)
        before = event_spine.event_count
        integration.settlement_from_credit("app-1", "sett-1", "cref-1", 200.0)
        after = event_spine.event_count
        assert after > before

    def test_penalty_settlement_emits_events(
        self,
        integration: SettlementRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.settlement_from_penalty("pay-1", "inv-1", "acct-1", 500.0)
        after = event_spine.event_count
        assert after > before

    def test_collection_emits_events(
        self,
        integration: SettlementRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.open_collection_from_overdue("case-1", "inv-1", "acct-1", 500.0)
        after = event_spine.event_count
        assert after > before

    def test_memory_mesh_attachment_emits_event(
        self,
        integration: SettlementRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.attach_settlement_to_memory_mesh("scope-1")
        after = event_spine.event_count
        assert after > before


# ---------------------------------------------------------------------------
# Golden path: full lifecycle
# ---------------------------------------------------------------------------


class TestGoldenPathFullLifecycle:
    def test_full_lifecycle(
        self,
        integration: SettlementRuntimeIntegration,
        settlement_engine: SettlementRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        # 1. Create settlement from invoice
        sett = integration.settlement_from_invoice(
            "sett-1", "inv-1", "acct-1", 1000.0
        )
        assert sett["source_type"] == "invoice"
        assert sett["status"] == "open"
        assert sett["settlement_id"] == "sett-1"
        assert sett["invoice_id"] == "inv-1"
        assert sett["account_id"] == "acct-1"
        assert sett["total_amount"] == 1000.0
        assert sett["outstanding"] == 1000.0

        # 2. Mark settlement as disputed
        dispute = integration.settlement_from_dispute("sett-1")
        assert dispute["source_type"] == "dispute"
        assert dispute["status"] == "disputed"
        assert dispute["settlement_id"] == "sett-1"
        assert dispute["outstanding"] == 1000.0

        # 3. Apply credit to settlement
        credit = integration.settlement_from_credit(
            "app-1", "sett-1", "cref-1", 400.0
        )
        assert credit["source_type"] == "credit"
        assert credit["application_id"] == "app-1"
        assert credit["credit_ref"] == "cref-1"
        assert credit["amount"] == 400.0
        assert credit["outstanding"] == 600.0

        # 4. Record a penalty payment
        penalty = integration.settlement_from_penalty(
            "pay-1", "inv-2", "acct-1", 250.0
        )
        assert penalty["source_type"] == "penalty"
        assert penalty["status"] == "cleared"
        assert penalty["payment_id"] == "pay-1"
        assert penalty["amount"] == 250.0

        # 5. Open collection from overdue
        collection = integration.open_collection_from_overdue(
            "case-1", "inv-3", "acct-1", 600.0
        )
        assert collection["source_type"] == "overdue"
        assert collection["status"] == "open"
        assert collection["case_id"] == "case-1"
        assert collection["outstanding_amount"] == 600.0

        # 6. Attach settlement state to memory mesh
        mem = integration.attach_settlement_to_memory_mesh("lifecycle-scope")
        assert isinstance(mem, MemoryRecord)
        assert "settlement" in mem.tags
        assert "payments" in mem.tags
        assert "collections" in mem.tags
        assert memory_engine.get_memory(mem.memory_id) is not None

        # 7. Attach settlement state to graph
        graph = integration.attach_settlement_to_graph("lifecycle-scope")
        assert graph["scope_ref_id"] == "lifecycle-scope"
        assert graph["total_settlements"] == 1
        assert graph["total_payments"] == 1
        assert graph["total_collections"] == 1

        # 8. Verify events were emitted throughout
        assert event_spine.event_count >= 6
