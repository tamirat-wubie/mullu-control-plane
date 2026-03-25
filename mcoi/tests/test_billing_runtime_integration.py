"""Tests for BillingRuntimeIntegration bridge.

Covers constructor validation, all 5 billing creation methods, memory mesh
attachment, graph attachment, event emission, and a full lifecycle golden path.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.billing_runtime import BillingRuntimeEngine
from mcoi_runtime.core.billing_runtime_integration import BillingRuntimeIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.contracts.billing_runtime import ChargeKind
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def event_spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def billing_engine(event_spine: EventSpineEngine) -> BillingRuntimeEngine:
    return BillingRuntimeEngine(event_spine)


@pytest.fixture()
def memory_engine() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def integration(
    billing_engine: BillingRuntimeEngine,
    event_spine: EventSpineEngine,
    memory_engine: MemoryMeshEngine,
) -> BillingRuntimeIntegration:
    return BillingRuntimeIntegration(billing_engine, event_spine, memory_engine)


def _create_account(integration: BillingRuntimeIntegration) -> dict:
    """Helper: register a billing account so downstream methods work."""
    return integration.billing_from_contract("acct-1", "t-1", "contract-1")


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_rejects_wrong_billing_engine_type(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="billing_engine"):
            BillingRuntimeIntegration("not-an-engine", event_spine, memory_engine)

    def test_rejects_wrong_event_spine_type(
        self, billing_engine: BillingRuntimeEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            BillingRuntimeIntegration(billing_engine, "not-a-spine", memory_engine)

    def test_rejects_wrong_memory_engine_type(
        self, billing_engine: BillingRuntimeEngine, event_spine: EventSpineEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            BillingRuntimeIntegration(billing_engine, event_spine, 42)

    def test_accepts_valid_arguments(
        self,
        billing_engine: BillingRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        bri = BillingRuntimeIntegration(billing_engine, event_spine, memory_engine)
        assert bri is not None


# ---------------------------------------------------------------------------
# billing_from_contract
# ---------------------------------------------------------------------------


class TestBillingFromContract:
    def test_returns_expected_keys(self, integration: BillingRuntimeIntegration) -> None:
        result = integration.billing_from_contract("acct-1", "t-1", "c-1")
        assert set(result.keys()) == {
            "account_id", "tenant_id", "counterparty", "status", "currency",
            "source_type",
        }

    def test_source_type_is_contract(self, integration: BillingRuntimeIntegration) -> None:
        result = integration.billing_from_contract("acct-1", "t-1", "c-1")
        assert result["source_type"] == "contract"

    def test_status_is_active(self, integration: BillingRuntimeIntegration) -> None:
        result = integration.billing_from_contract("acct-1", "t-1", "c-1")
        assert result["status"] == "active"

    def test_counterparty_matches_contract_id(
        self, integration: BillingRuntimeIntegration
    ) -> None:
        result = integration.billing_from_contract("acct-1", "t-1", "c-42")
        assert result["counterparty"] == "c-42"

    def test_default_currency_is_usd(self, integration: BillingRuntimeIntegration) -> None:
        result = integration.billing_from_contract("acct-1", "t-1", "c-1")
        assert result["currency"] == "USD"

    def test_custom_currency(self, integration: BillingRuntimeIntegration) -> None:
        result = integration.billing_from_contract(
            "acct-1", "t-1", "c-1", currency="EUR"
        )
        assert result["currency"] == "EUR"

    def test_account_id_matches(self, integration: BillingRuntimeIntegration) -> None:
        result = integration.billing_from_contract("acct-99", "t-1", "c-1")
        assert result["account_id"] == "acct-99"

    def test_tenant_id_matches(self, integration: BillingRuntimeIntegration) -> None:
        result = integration.billing_from_contract("acct-1", "t-77", "c-1")
        assert result["tenant_id"] == "t-77"


# ---------------------------------------------------------------------------
# billing_from_sla_breach
# ---------------------------------------------------------------------------


class TestBillingFromSlaBreach:
    def test_returns_expected_keys(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_sla_breach("pen-1", "acct-1", "br-1", 500.0)
        assert set(result.keys()) == {
            "penalty_id", "account_id", "breach_id", "amount", "source_type",
        }

    def test_source_type_is_sla_breach(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_sla_breach("pen-1", "acct-1", "br-1", 500.0)
        assert result["source_type"] == "sla_breach"

    def test_penalty_id_matches(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_sla_breach("pen-42", "acct-1", "br-1", 100.0)
        assert result["penalty_id"] == "pen-42"

    def test_amount_matches(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_sla_breach("pen-1", "acct-1", "br-1", 999.99)
        assert result["amount"] == 999.99

    def test_breach_id_matches(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_sla_breach("pen-1", "acct-1", "br-7", 100.0)
        assert result["breach_id"] == "br-7"


# ---------------------------------------------------------------------------
# billing_from_remedy
# ---------------------------------------------------------------------------


class TestBillingFromRemedy:
    def test_returns_expected_keys(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_remedy("cred-1", "acct-1", "br-1", 200.0)
        assert set(result.keys()) == {
            "credit_id", "account_id", "breach_id", "amount", "disposition",
            "source_type",
        }

    def test_source_type_is_remedy(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_remedy("cred-1", "acct-1", "br-1", 200.0)
        assert result["source_type"] == "remedy"

    def test_disposition_is_applied(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_remedy("cred-1", "acct-1", "br-1", 200.0)
        assert result["disposition"] == "applied"

    def test_credit_id_matches(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_remedy("cred-77", "acct-1", "br-1", 50.0)
        assert result["credit_id"] == "cred-77"

    def test_amount_matches(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_remedy("cred-1", "acct-1", "br-1", 123.45)
        assert result["amount"] == 123.45


# ---------------------------------------------------------------------------
# billing_from_campaign_completion
# ---------------------------------------------------------------------------


class TestBillingFromCampaignCompletion:
    def test_returns_expected_keys(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_campaign_completion(
            "inv-1", "acct-1", "camp-1", 1000.0
        )
        assert set(result.keys()) == {
            "invoice_id", "account_id", "charge_id", "campaign_id", "amount",
            "status", "source_type",
        }

    def test_source_type_is_campaign_completion(
        self, integration: BillingRuntimeIntegration
    ) -> None:
        _create_account(integration)
        result = integration.billing_from_campaign_completion(
            "inv-1", "acct-1", "camp-1", 1000.0
        )
        assert result["source_type"] == "campaign_completion"

    def test_status_is_draft(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_campaign_completion(
            "inv-1", "acct-1", "camp-1", 1000.0
        )
        assert result["status"] == "draft"

    def test_campaign_id_matches(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_campaign_completion(
            "inv-1", "acct-1", "camp-55", 500.0
        )
        assert result["campaign_id"] == "camp-55"

    def test_amount_matches(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_campaign_completion(
            "inv-1", "acct-1", "camp-1", 7777.77
        )
        assert result["amount"] == 7777.77

    def test_charge_id_is_string(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_campaign_completion(
            "inv-1", "acct-1", "camp-1", 100.0
        )
        assert isinstance(result["charge_id"], str)
        assert len(result["charge_id"]) > 0


# ---------------------------------------------------------------------------
# billing_from_reporting_requirement
# ---------------------------------------------------------------------------


class TestBillingFromReportingRequirement:
    def test_returns_expected_keys(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_reporting_requirement(
            "inv-2", "acct-1", "req-1", 2000.0
        )
        assert set(result.keys()) == {
            "invoice_id", "account_id", "charge_id", "requirement_id", "amount",
            "status", "source_type",
        }

    def test_source_type_is_reporting_requirement(
        self, integration: BillingRuntimeIntegration
    ) -> None:
        _create_account(integration)
        result = integration.billing_from_reporting_requirement(
            "inv-2", "acct-1", "req-1", 2000.0
        )
        assert result["source_type"] == "reporting_requirement"

    def test_status_is_draft(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_reporting_requirement(
            "inv-2", "acct-1", "req-1", 2000.0
        )
        assert result["status"] == "draft"

    def test_requirement_id_matches(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_reporting_requirement(
            "inv-2", "acct-1", "req-88", 300.0
        )
        assert result["requirement_id"] == "req-88"

    def test_amount_matches(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_reporting_requirement(
            "inv-2", "acct-1", "req-1", 4321.00
        )
        assert result["amount"] == 4321.00

    def test_charge_id_is_string(self, integration: BillingRuntimeIntegration) -> None:
        _create_account(integration)
        result = integration.billing_from_reporting_requirement(
            "inv-2", "acct-1", "req-1", 100.0
        )
        assert isinstance(result["charge_id"], str)
        assert len(result["charge_id"]) > 0


# ---------------------------------------------------------------------------
# Memory mesh attachment
# ---------------------------------------------------------------------------


class TestAttachBillingToMemoryMesh:
    def test_returns_memory_record(
        self, integration: BillingRuntimeIntegration
    ) -> None:
        mem = integration.attach_billing_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_tags_contain_expected_values(
        self, integration: BillingRuntimeIntegration
    ) -> None:
        mem = integration.attach_billing_to_memory_mesh("scope-1")
        assert "billing" in mem.tags
        assert "revenue" in mem.tags
        assert "credit" in mem.tags

    def test_tags_are_tuple(self, integration: BillingRuntimeIntegration) -> None:
        mem = integration.attach_billing_to_memory_mesh("scope-1")
        assert isinstance(mem.tags, tuple)
        assert mem.tags == ("billing", "revenue", "credit")

    def test_title_contains_scope_ref_id(
        self, integration: BillingRuntimeIntegration
    ) -> None:
        mem = integration.attach_billing_to_memory_mesh("my-scope")
        assert "my-scope" in mem.title

    def test_memory_id_is_string(self, integration: BillingRuntimeIntegration) -> None:
        mem = integration.attach_billing_to_memory_mesh("scope-1")
        assert isinstance(mem.memory_id, str)
        assert len(mem.memory_id) > 0

    def test_memory_added_to_engine(
        self,
        integration: BillingRuntimeIntegration,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        mem = integration.attach_billing_to_memory_mesh("scope-1")
        retrieved = memory_engine.get_memory(mem.memory_id)
        assert retrieved is not None
        assert retrieved.memory_id == mem.memory_id


# ---------------------------------------------------------------------------
# Graph attachment
# ---------------------------------------------------------------------------


class TestAttachBillingToGraph:
    def test_returns_expected_keys(
        self, integration: BillingRuntimeIntegration
    ) -> None:
        result = integration.attach_billing_to_graph("scope-1")
        expected_keys = {
            "scope_ref_id",
            "total_accounts",
            "total_invoices",
            "total_charges",
            "total_credits",
            "total_penalties",
            "total_disputes",
            "total_violations",
            "recognized_revenue",
            "pending_revenue",
        }
        assert set(result.keys()) == expected_keys

    def test_values_match_engine_state_empty(
        self, integration: BillingRuntimeIntegration
    ) -> None:
        result = integration.attach_billing_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"
        assert result["total_accounts"] == 0
        assert result["total_invoices"] == 0
        assert result["total_charges"] == 0
        assert result["total_credits"] == 0
        assert result["total_penalties"] == 0

    def test_values_reflect_registered_account(
        self, integration: BillingRuntimeIntegration
    ) -> None:
        integration.billing_from_contract("acct-1", "t-1", "c-1")
        result = integration.attach_billing_to_graph("scope-1")
        assert result["total_accounts"] == 1


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


class TestEventEmission:
    def test_contract_billing_emits_events(
        self,
        integration: BillingRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.billing_from_contract("acct-1", "t-1", "c-1")
        after = event_spine.event_count
        assert after > before

    def test_sla_breach_billing_emits_events(
        self,
        integration: BillingRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        _create_account(integration)
        before = event_spine.event_count
        integration.billing_from_sla_breach("pen-1", "acct-1", "br-1", 500.0)
        after = event_spine.event_count
        assert after > before

    def test_remedy_billing_emits_events(
        self,
        integration: BillingRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        _create_account(integration)
        before = event_spine.event_count
        integration.billing_from_remedy("cred-1", "acct-1", "br-1", 200.0)
        after = event_spine.event_count
        assert after > before

    def test_campaign_billing_emits_events(
        self,
        integration: BillingRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        _create_account(integration)
        before = event_spine.event_count
        integration.billing_from_campaign_completion("inv-1", "acct-1", "camp-1", 1000.0)
        after = event_spine.event_count
        assert after > before

    def test_reporting_billing_emits_events(
        self,
        integration: BillingRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        _create_account(integration)
        before = event_spine.event_count
        integration.billing_from_reporting_requirement("inv-2", "acct-1", "req-1", 2000.0)
        after = event_spine.event_count
        assert after > before

    def test_memory_mesh_attachment_emits_event(
        self,
        integration: BillingRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.attach_billing_to_memory_mesh("scope-1")
        after = event_spine.event_count
        assert after > before


# ---------------------------------------------------------------------------
# Golden path: full lifecycle
# ---------------------------------------------------------------------------


class TestGoldenPathFullLifecycle:
    def test_full_lifecycle(
        self,
        integration: BillingRuntimeIntegration,
        billing_engine: BillingRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        # 1. Create billing account from contract
        acct = integration.billing_from_contract("acct-1", "t-1", "contract-1")
        assert acct["source_type"] == "contract"
        assert acct["status"] == "active"
        assert acct["counterparty"] == "contract-1"
        assert acct["currency"] == "USD"

        # 2. Add penalty from SLA breach
        pen = integration.billing_from_sla_breach("pen-1", "acct-1", "br-1", 500.0)
        assert pen["source_type"] == "sla_breach"
        assert pen["penalty_id"] == "pen-1"
        assert pen["amount"] == 500.0

        # 3. Add credit from remedy
        cred = integration.billing_from_remedy("cred-1", "acct-1", "br-1", 200.0)
        assert cred["source_type"] == "remedy"
        assert cred["disposition"] == "applied"
        assert cred["amount"] == 200.0

        # 4. Create invoice from campaign completion
        inv_camp = integration.billing_from_campaign_completion(
            "inv-1", "acct-1", "camp-1", 5000.0
        )
        assert inv_camp["source_type"] == "campaign_completion"
        assert inv_camp["status"] == "draft"
        assert inv_camp["campaign_id"] == "camp-1"
        assert inv_camp["amount"] == 5000.0

        # 5. Create invoice from reporting requirement
        inv_rep = integration.billing_from_reporting_requirement(
            "inv-2", "acct-1", "req-1", 3000.0
        )
        assert inv_rep["source_type"] == "reporting_requirement"
        assert inv_rep["status"] == "draft"
        assert inv_rep["requirement_id"] == "req-1"

        # 6. Attach billing state to memory mesh
        mem = integration.attach_billing_to_memory_mesh("lifecycle-scope")
        assert isinstance(mem, MemoryRecord)
        assert "billing" in mem.tags
        assert "revenue" in mem.tags
        assert "credit" in mem.tags
        assert memory_engine.get_memory(mem.memory_id) is not None

        # 7. Attach billing state to graph
        graph = integration.attach_billing_to_graph("lifecycle-scope")
        assert graph["scope_ref_id"] == "lifecycle-scope"
        assert graph["total_accounts"] == 1
        assert graph["total_invoices"] == 2
        assert graph["total_charges"] == 2
        assert graph["total_credits"] == 1
        assert graph["total_penalties"] == 1

        # 8. Verify events were emitted throughout
        # Each billing method emits at least 1 event, plus engine-level events
        assert event_spine.event_count >= 6
