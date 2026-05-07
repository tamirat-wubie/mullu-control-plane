"""Financial Compliance Export Tests.

Tests: Audit package generation, tenant reports, integrity hashes,
    lifecycle coverage, no-secret leakage.
"""

import sys
from pathlib import Path
from decimal import Decimal

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from skills.financial.core.transaction_ledger import TransactionLedger  # noqa: E402
from skills.financial.core.transaction_state import TxState  # noqa: E402
from skills.financial.core.compliance_export import ComplianceExporter, AuditPackage, ComplianceReport  # noqa: E402


def _ledger_with_tx() -> TransactionLedger:
    """Create a ledger with a settled transaction."""
    ledger = TransactionLedger()
    ledger.create(
        tx_id="tx1", idempotency_key="idem1", tenant_id="t1",
        debit_account="tenant:t1", credit_account="vendor:v1",
        amount=Decimal("500"), currency="USD", provider="stripe",
        created_at="2026-04-01T00:00:00Z",
    )
    ledger.advance("tx1", TxState.PENDING_APPROVAL, reason="high risk", actor_id="requester", timestamp="2026-04-01T00:00:01Z")
    ledger.advance("tx1", TxState.AUTHORIZED, reason="approved", actor_id="manager", timestamp="2026-04-01T00:01:00Z")
    ledger.advance("tx1", TxState.CAPTURED, provider_tx_id="pl_123", timestamp="2026-04-01T00:01:01Z")
    ledger.advance("tx1", TxState.SETTLED, reason="confirmed", timestamp="2026-04-01T00:02:00Z")
    return ledger


# ═══ Audit Package ═══


class TestAuditPackage:
    def test_export_settled_tx(self):
        ledger = _ledger_with_tx()
        exporter = ComplianceExporter(ledger)
        pkg = exporter.export_transaction("tx1")
        assert pkg is not None
        assert isinstance(pkg, AuditPackage)
        assert pkg.tx_id == "tx1"
        assert pkg.tenant_id == "t1"
        assert pkg.amount == "500"
        assert pkg.currency == "USD"
        assert pkg.state == "settled"
        assert pkg.provider == "stripe"

    def test_transitions_included(self):
        ledger = _ledger_with_tx()
        pkg = ComplianceExporter(ledger).export_transaction("tx1")
        assert len(pkg.transitions) == 4
        states = [t["to"] for t in pkg.transitions]
        assert "pending_approval" in states
        assert "authorized" in states
        assert "captured" in states
        assert "settled" in states

    def test_proof_hash_present(self):
        ledger = _ledger_with_tx()
        pkg = ComplianceExporter(ledger).export_transaction("tx1")
        assert pkg.proof_hash != ""
        assert len(pkg.proof_hash) == 64  # SHA-256

    def test_package_hash_present(self):
        ledger = _ledger_with_tx()
        pkg = ComplianceExporter(ledger).export_transaction("tx1")
        assert pkg.package_hash != ""
        assert len(pkg.package_hash) == 64

    def test_package_hash_deterministic(self):
        ledger = _ledger_with_tx()
        exporter = ComplianceExporter(ledger)
        pkg1 = exporter.export_transaction("tx1")
        pkg2 = exporter.export_transaction("tx1")
        assert pkg1.package_hash == pkg2.package_hash

    def test_settled_at_captured(self):
        ledger = _ledger_with_tx()
        pkg = ComplianceExporter(ledger).export_transaction("tx1")
        assert pkg.settled_at == "2026-04-01T00:02:00Z"

    def test_nonexistent_tx_returns_none(self):
        ledger = TransactionLedger()
        assert ComplianceExporter(ledger).export_transaction("nope") is None

    def test_no_secrets_in_package(self):
        ledger = _ledger_with_tx()
        pkg = ComplianceExporter(ledger).export_transaction("tx1")
        # Verify no credential-like data
        import json
        serialized = json.dumps({
            "tx_id": pkg.tx_id, "tenant_id": pkg.tenant_id,
            "amount": pkg.amount, "state": pkg.state,
            "provider_tx_id": pkg.provider_tx_id,
            "transitions": [dict(t) for t in pkg.transitions],
        })
        assert "api_key" not in serialized.lower()
        assert "secret" not in serialized.lower()
        assert "password" not in serialized.lower()


# ═══ Compliance Report ═══


class TestComplianceReport:
    def test_single_tenant_report(self):
        ledger = _ledger_with_tx()
        exporter = ComplianceExporter(ledger)
        report = exporter.export_tenant_report("t1", generated_at="2026-04-01T12:00:00Z")
        assert isinstance(report, ComplianceReport)
        assert report.tenant_id == "t1"
        assert report.total_transactions == 1
        assert report.total_settled == 1
        assert report.total_amount_settled == "500"

    def test_report_with_refund(self):
        ledger = _ledger_with_tx()
        ledger.advance("tx1", TxState.REFUND_PENDING, reason="customer", timestamp="2026-04-01T03:00:00Z")
        ledger.advance("tx1", TxState.REFUNDED, timestamp="2026-04-01T03:01:00Z")
        report = ComplianceExporter(ledger).export_tenant_report("t1")
        assert report.total_refunded == 1
        assert report.total_amount_refunded == "500"

    def test_report_includes_packages(self):
        ledger = _ledger_with_tx()
        report = ComplianceExporter(ledger).export_tenant_report("t1")
        assert len(report.packages) == 1
        assert report.packages[0].tx_id == "tx1"

    def test_report_hash_present(self):
        ledger = _ledger_with_tx()
        report = ComplianceExporter(ledger).export_tenant_report("t1")
        assert report.report_hash != ""
        assert len(report.report_hash) == 64

    def test_empty_tenant_report(self):
        ledger = TransactionLedger()
        report = ComplianceExporter(ledger).export_tenant_report("empty")
        assert report.total_transactions == 0
        assert len(report.packages) == 0

    def test_multi_tx_report(self):
        ledger = _ledger_with_tx()
        # Add a second transaction
        ledger.create(
            tx_id="tx2", idempotency_key="idem2", tenant_id="t1",
            debit_account="tenant:t1", credit_account="vendor:v2",
            amount=Decimal("200"), currency="USD", provider="stripe",
            created_at="2026-04-01T04:00:00Z",
        )
        ledger.advance("tx2", TxState.REJECTED, reason="denied", timestamp="2026-04-01T04:01:00Z")
        report = ComplianceExporter(ledger).export_tenant_report("t1")
        assert report.total_transactions == 2
        assert report.total_settled == 1
        assert report.total_failed == 1
        assert len(report.packages) == 2
