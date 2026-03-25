"""Tests for the LedgerRuntimeEngine.

Covers account, wallet, transaction, proof, anchor, assessment, snapshot,
violation detection, state_hash, and engine-level golden scenarios.
"""

import pytest

from mcoi_runtime.contracts.ledger_runtime import (
    AnchorDisposition,
    AnchorRecord,
    LedgerAccount,
    LedgerAssessment,
    LedgerClosureReport,
    LedgerDecision,
    LedgerNetworkKind,
    LedgerSnapshot,
    LedgerStatus,
    LedgerTransaction,
    LedgerViolation,
    LedgerViolationKind,
    SettlementProof,
    SettlementProofStatus,
    WalletRecord,
    WalletStatus,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.ledger_runtime import LedgerRuntimeEngine


# ======================================================================
# Fixtures
# ======================================================================

FIXED_TIME = "2026-01-01T00:00:00+00:00"


def _make_engine(clock=None):
    es = EventSpineEngine()
    clk = clock or FixedClock(FIXED_TIME)
    eng = LedgerRuntimeEngine(es, clock=clk)
    return eng, es


def _engine_with_account(account_id="acct-1", tenant_id="t-1"):
    eng, es = _make_engine()
    eng.register_account(account_id, tenant_id, "Test Account")
    return eng, es


def _engine_with_tx(account_id="acct-1", tx_id="tx-1", tenant_id="t-1"):
    eng, es = _engine_with_account(account_id, tenant_id)
    eng.create_transaction(tx_id, tenant_id, account_id, "acct-dst", 100.0, "ref-001")
    return eng, es


# ======================================================================
# Constructor
# ======================================================================


class TestConstructor:
    def test_valid_construction(self):
        eng, es = _make_engine()
        assert eng.account_count == 0
        assert eng.transaction_count == 0
        assert eng.proof_count == 0
        assert eng.anchor_count == 0
        assert eng.wallet_count == 0
        assert eng.violation_count == 0

    def test_invalid_event_spine_rejected(self):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            LedgerRuntimeEngine("not-an-engine")

    def test_none_event_spine_rejected(self):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            LedgerRuntimeEngine(None)

    def test_clock_kwarg_accepted(self):
        es = EventSpineEngine()
        clk = FixedClock("2026-03-01T00:00:00+00:00")
        eng = LedgerRuntimeEngine(es, clock=clk)
        acct = eng.register_account("a1", "t1", "name")
        assert acct.created_at == "2026-03-01T00:00:00+00:00"

    def test_no_clock_uses_wall_clock(self):
        es = EventSpineEngine()
        eng = LedgerRuntimeEngine(es)
        acct = eng.register_account("a1", "t1", "name")
        assert len(acct.created_at) > 0  # just ensure it has a timestamp


# ======================================================================
# Accounts
# ======================================================================


class TestRegisterAccount:
    def test_register_returns_account(self):
        eng, es = _make_engine()
        a = eng.register_account("acct-1", "t-1", "Main")
        assert isinstance(a, LedgerAccount)
        assert a.account_id == "acct-1"
        assert a.tenant_id == "t-1"
        assert a.status is LedgerStatus.ACTIVE
        assert a.network is LedgerNetworkKind.PRIVATE
        assert a.balance == 0.0

    def test_register_with_network(self):
        eng, _ = _make_engine()
        a = eng.register_account("a1", "t1", "Name", network=LedgerNetworkKind.PUBLIC)
        assert a.network is LedgerNetworkKind.PUBLIC

    def test_register_with_balance(self):
        eng, _ = _make_engine()
        a = eng.register_account("a1", "t1", "Name", balance=500.0)
        assert a.balance == 500.0

    def test_register_increments_count(self):
        eng, _ = _make_engine()
        eng.register_account("a1", "t1", "Name")
        eng.register_account("a2", "t1", "Name2")
        assert eng.account_count == 2

    def test_register_emits_event(self):
        eng, es = _make_engine()
        eng.register_account("a1", "t1", "Name")
        assert es.event_count >= 1

    def test_duplicate_account_id_rejected(self):
        eng, _ = _make_engine()
        eng.register_account("a1", "t1", "Name")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate account_id"):
            eng.register_account("a1", "t2", "Name2")

    def test_register_uses_clock_timestamp(self):
        eng, _ = _make_engine()
        a = eng.register_account("a1", "t1", "Name")
        assert a.created_at == FIXED_TIME


class TestGetAccount:
    def test_get_existing(self):
        eng, _ = _engine_with_account()
        a = eng.get_account("acct-1")
        assert a.account_id == "acct-1"

    def test_get_unknown_raises(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown account_id"):
            eng.get_account("nope")


class TestAccountsForTenant:
    def test_empty_tenant(self):
        eng, _ = _make_engine()
        assert eng.accounts_for_tenant("t-1") == ()

    def test_filters_by_tenant(self):
        eng, _ = _make_engine()
        eng.register_account("a1", "t-1", "A1")
        eng.register_account("a2", "t-2", "A2")
        eng.register_account("a3", "t-1", "A3")
        result = eng.accounts_for_tenant("t-1")
        assert len(result) == 2
        assert all(a.tenant_id == "t-1" for a in result)

    def test_returns_tuple(self):
        eng, _ = _engine_with_account()
        result = eng.accounts_for_tenant("t-1")
        assert isinstance(result, tuple)


# ======================================================================
# Wallets
# ======================================================================


class TestRegisterWallet:
    def test_register_returns_wallet(self):
        eng, _ = _make_engine()
        w = eng.register_wallet("w1", "t1", "id-ref", "pk-ref")
        assert isinstance(w, WalletRecord)
        assert w.wallet_id == "w1"
        assert w.status is WalletStatus.ACTIVE

    def test_register_increments_count(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        eng.register_wallet("w2", "t1", "id2", "pk2")
        assert eng.wallet_count == 2

    def test_register_emits_event(self):
        eng, es = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        assert es.event_count >= 1

    def test_duplicate_wallet_id_rejected(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate wallet_id"):
            eng.register_wallet("w1", "t1", "id2", "pk2")


class TestGetWallet:
    def test_get_existing(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        w = eng.get_wallet("w1")
        assert w.wallet_id == "w1"

    def test_get_unknown_raises(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown wallet_id"):
            eng.get_wallet("nope")


class TestFreezeWallet:
    def test_freeze_active_wallet(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        w = eng.freeze_wallet("w1")
        assert w.status is WalletStatus.FROZEN

    def test_freeze_emits_event(self):
        eng, es = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        count_before = es.event_count
        eng.freeze_wallet("w1")
        assert es.event_count > count_before

    def test_freeze_closed_wallet_rejected(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        eng.close_wallet("w1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            eng.freeze_wallet("w1")

    def test_freeze_compromised_wallet_rejected(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        eng.mark_compromised("w1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            eng.freeze_wallet("w1")


class TestCloseWallet:
    def test_close_active_wallet(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        w = eng.close_wallet("w1")
        assert w.status is WalletStatus.CLOSED

    def test_close_frozen_wallet(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        eng.freeze_wallet("w1")
        w = eng.close_wallet("w1")
        assert w.status is WalletStatus.CLOSED

    def test_close_emits_event(self):
        eng, es = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        before = es.event_count
        eng.close_wallet("w1")
        assert es.event_count > before

    def test_close_already_closed_rejected(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        eng.close_wallet("w1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            eng.close_wallet("w1")

    def test_close_compromised_rejected(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        eng.mark_compromised("w1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            eng.close_wallet("w1")


class TestMarkCompromised:
    def test_mark_active(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        w = eng.mark_compromised("w1")
        assert w.status is WalletStatus.COMPROMISED

    def test_mark_frozen(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        eng.freeze_wallet("w1")
        w = eng.mark_compromised("w1")
        assert w.status is WalletStatus.COMPROMISED

    def test_mark_emits_event(self):
        eng, es = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        before = es.event_count
        eng.mark_compromised("w1")
        assert es.event_count > before

    def test_mark_closed_rejected(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        eng.close_wallet("w1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            eng.mark_compromised("w1")

    def test_mark_already_compromised_rejected(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        eng.mark_compromised("w1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            eng.mark_compromised("w1")


class TestWalletsForTenant:
    def test_empty(self):
        eng, _ = _make_engine()
        assert eng.wallets_for_tenant("t-1") == ()

    def test_filters_by_tenant(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t-1", "id1", "pk1")
        eng.register_wallet("w2", "t-2", "id2", "pk2")
        eng.register_wallet("w3", "t-1", "id3", "pk3")
        assert len(eng.wallets_for_tenant("t-1")) == 2

    def test_returns_tuple(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t-1", "id1", "pk1")
        assert isinstance(eng.wallets_for_tenant("t-1"), tuple)


# ======================================================================
# Transactions
# ======================================================================


class TestCreateTransaction:
    def test_creates_transaction(self):
        eng, _ = _engine_with_account()
        tx = eng.create_transaction("tx-1", "t-1", "acct-1", "acct-dst", 100.0, "ref-001")
        assert isinstance(tx, LedgerTransaction)
        assert tx.transaction_id == "tx-1"
        assert tx.amount == 100.0

    def test_increments_count(self):
        eng, _ = _engine_with_account()
        eng.create_transaction("tx-1", "t-1", "acct-1", "acct-dst", 50.0, "ref-001")
        eng.create_transaction("tx-2", "t-1", "acct-1", "acct-dst", 25.0, "ref-002")
        assert eng.transaction_count == 2

    def test_emits_event(self):
        eng, es = _engine_with_account()
        before = es.event_count
        eng.create_transaction("tx-1", "t-1", "acct-1", "dst", 10.0, "ref")
        assert es.event_count > before

    def test_duplicate_transaction_id_rejected(self):
        eng, _ = _engine_with_account()
        eng.create_transaction("tx-1", "t-1", "acct-1", "dst", 10.0, "ref")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate transaction_id"):
            eng.create_transaction("tx-1", "t-1", "acct-1", "dst", 20.0, "ref2")

    def test_unknown_from_account_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown from_account"):
            eng.create_transaction("tx-1", "t-1", "no-such-acct", "dst", 10.0, "ref")

    def test_zero_amount(self):
        eng, _ = _engine_with_account()
        tx = eng.create_transaction("tx-1", "t-1", "acct-1", "dst", 0.0, "ref")
        assert tx.amount == 0.0

    def test_uses_clock_timestamp(self):
        eng, _ = _engine_with_account()
        tx = eng.create_transaction("tx-1", "t-1", "acct-1", "dst", 10.0, "ref")
        assert tx.created_at == FIXED_TIME


class TestGetTransaction:
    def test_get_existing(self):
        eng, _ = _engine_with_tx()
        tx = eng.get_transaction("tx-1")
        assert tx.transaction_id == "tx-1"

    def test_get_unknown_raises(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown transaction_id"):
            eng.get_transaction("nope")


class TestTransactionsForTenant:
    def test_empty(self):
        eng, _ = _make_engine()
        assert eng.transactions_for_tenant("t-1") == ()

    def test_filters_by_tenant(self):
        eng, _ = _make_engine()
        eng.register_account("a1", "t-1", "A1")
        eng.register_account("a2", "t-2", "A2")
        eng.create_transaction("tx-1", "t-1", "a1", "dst", 10.0, "ref")
        eng.create_transaction("tx-2", "t-2", "a2", "dst", 20.0, "ref")
        assert len(eng.transactions_for_tenant("t-1")) == 1

    def test_returns_tuple(self):
        eng, _ = _engine_with_tx()
        assert isinstance(eng.transactions_for_tenant("t-1"), tuple)


# ======================================================================
# Settlement Proofs
# ======================================================================


class TestCreateSettlementProof:
    def test_creates_proof(self):
        eng, _ = _make_engine()
        p = eng.create_settlement_proof("prf-1", "t-1", "tx-ref", "hash123")
        assert isinstance(p, SettlementProof)
        assert p.proof_id == "prf-1"
        assert p.status is SettlementProofStatus.PENDING
        assert p.proof_hash == "hash123"
        assert p.verified_at == ""

    def test_increments_count(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.create_settlement_proof("p2", "t1", "tx", "h2")
        assert eng.proof_count == 2

    def test_emits_event(self):
        eng, es = _make_engine()
        before = es.event_count
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        assert es.event_count > before

    def test_duplicate_proof_id_rejected(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate proof_id"):
            eng.create_settlement_proof("p1", "t1", "tx", "h2")


class TestConfirmProof:
    def test_confirm_pending(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        p = eng.confirm_proof("p1")
        assert p.status is SettlementProofStatus.CONFIRMED
        assert p.verified_at == FIXED_TIME

    def test_confirm_disputed(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.dispute_proof("p1")
        p = eng.confirm_proof("p1")
        assert p.status is SettlementProofStatus.CONFIRMED

    def test_confirm_emits_event(self):
        eng, es = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        before = es.event_count
        eng.confirm_proof("p1")
        assert es.event_count > before

    def test_confirm_unknown_raises(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown proof_id"):
            eng.confirm_proof("nope")

    def test_confirm_already_confirmed_rejected(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.confirm_proof("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            eng.confirm_proof("p1")

    def test_confirm_failed_rejected(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.fail_proof("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            eng.confirm_proof("p1")


class TestFailProof:
    def test_fail_pending(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        p = eng.fail_proof("p1")
        assert p.status is SettlementProofStatus.FAILED

    def test_fail_disputed(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.dispute_proof("p1")
        p = eng.fail_proof("p1")
        assert p.status is SettlementProofStatus.FAILED

    def test_fail_emits_event(self):
        eng, es = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        before = es.event_count
        eng.fail_proof("p1")
        assert es.event_count > before

    def test_fail_unknown_raises(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown proof_id"):
            eng.fail_proof("nope")

    def test_fail_already_failed_rejected(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.fail_proof("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            eng.fail_proof("p1")

    def test_fail_confirmed_rejected(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.confirm_proof("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            eng.fail_proof("p1")


class TestDisputeProof:
    def test_dispute_pending(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        p = eng.dispute_proof("p1")
        assert p.status is SettlementProofStatus.DISPUTED

    def test_dispute_emits_event(self):
        eng, es = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        before = es.event_count
        eng.dispute_proof("p1")
        assert es.event_count > before

    def test_dispute_unknown_raises(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown proof_id"):
            eng.dispute_proof("nope")

    def test_dispute_confirmed_rejected(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.confirm_proof("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            eng.dispute_proof("p1")

    def test_dispute_failed_rejected(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.fail_proof("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            eng.dispute_proof("p1")


# ======================================================================
# Anchors
# ======================================================================


class TestCreateAnchor:
    def test_creates_anchor(self):
        eng, _ = _make_engine()
        a = eng.create_anchor("anc-1", "t-1", "src-001", "hash123", "ref-chain")
        assert isinstance(a, AnchorRecord)
        assert a.anchor_id == "anc-1"
        assert a.disposition is AnchorDisposition.PENDING
        assert a.content_hash == "hash123"

    def test_increments_count(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        eng.create_anchor("a2", "t1", "src", "h2", "ref")
        assert eng.anchor_count == 2

    def test_emits_event(self):
        eng, es = _make_engine()
        before = es.event_count
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        assert es.event_count > before

    def test_duplicate_anchor_id_rejected(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate anchor_id"):
            eng.create_anchor("a1", "t1", "src", "h2", "ref")


class TestConfirmAnchor:
    def test_confirm_pending(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        a = eng.confirm_anchor("a1")
        assert a.disposition is AnchorDisposition.ANCHORED

    def test_confirm_emits_event(self):
        eng, es = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        before = es.event_count
        eng.confirm_anchor("a1")
        assert es.event_count > before

    def test_confirm_unknown_raises(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown anchor_id"):
            eng.confirm_anchor("nope")

    def test_confirm_already_anchored_rejected(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        eng.confirm_anchor("a1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal disposition"):
            eng.confirm_anchor("a1")

    def test_confirm_failed_rejected(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        eng.fail_anchor("a1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal disposition"):
            eng.confirm_anchor("a1")

    def test_confirm_revoked_rejected(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        eng.revoke_anchor("a1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal disposition"):
            eng.confirm_anchor("a1")


class TestFailAnchor:
    def test_fail_pending(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        a = eng.fail_anchor("a1")
        assert a.disposition is AnchorDisposition.FAILED

    def test_fail_emits_event(self):
        eng, es = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        before = es.event_count
        eng.fail_anchor("a1")
        assert es.event_count > before

    def test_fail_unknown_raises(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown anchor_id"):
            eng.fail_anchor("nope")

    def test_fail_anchored_rejected(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        eng.confirm_anchor("a1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal disposition"):
            eng.fail_anchor("a1")

    def test_fail_already_failed_rejected(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        eng.fail_anchor("a1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal disposition"):
            eng.fail_anchor("a1")

    def test_fail_revoked_rejected(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        eng.revoke_anchor("a1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal disposition"):
            eng.fail_anchor("a1")


class TestRevokeAnchor:
    def test_revoke_pending(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        a = eng.revoke_anchor("a1")
        assert a.disposition is AnchorDisposition.REVOKED

    def test_revoke_emits_event(self):
        eng, es = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        before = es.event_count
        eng.revoke_anchor("a1")
        assert es.event_count > before

    def test_revoke_unknown_raises(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown anchor_id"):
            eng.revoke_anchor("nope")

    def test_revoke_anchored_rejected(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        eng.confirm_anchor("a1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal disposition"):
            eng.revoke_anchor("a1")

    def test_revoke_failed_rejected(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        eng.fail_anchor("a1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal disposition"):
            eng.revoke_anchor("a1")

    def test_revoke_already_revoked_rejected(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        eng.revoke_anchor("a1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal disposition"):
            eng.revoke_anchor("a1")


# ======================================================================
# Proof verification
# ======================================================================


class TestVerifyProof:
    def test_verified_confirmed_matching_hash(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.confirm_proof("p1")
        assert eng.verify_proof("p1", "h1") is True

    def test_wrong_hash_returns_false(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.confirm_proof("p1")
        assert eng.verify_proof("p1", "wrong") is False

    def test_pending_returns_false(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        assert eng.verify_proof("p1", "h1") is False

    def test_failed_returns_false(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.fail_proof("p1")
        assert eng.verify_proof("p1", "h1") is False

    def test_unknown_proof_returns_false(self):
        eng, _ = _make_engine()
        assert eng.verify_proof("nope", "h1") is False

    def test_disputed_returns_false(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.dispute_proof("p1")
        assert eng.verify_proof("p1", "h1") is False


# ======================================================================
# Assessment
# ======================================================================


class TestLedgerAssessment:
    def test_assessment_no_proofs(self):
        eng, _ = _make_engine()
        a = eng.ledger_assessment("assess-1", "t-1")
        assert isinstance(a, LedgerAssessment)
        assert a.total_confirmed == 0
        assert a.total_failed == 0
        assert a.total_disputed == 0
        assert a.integrity_score == 1.0  # no proofs → perfect

    def test_assessment_all_confirmed(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t-1", "tx", "h1")
        eng.confirm_proof("p1")
        eng.create_settlement_proof("p2", "t-1", "tx", "h2")
        eng.confirm_proof("p2")
        a = eng.ledger_assessment("assess-1", "t-1")
        assert a.total_confirmed == 2
        assert a.integrity_score == 1.0

    def test_assessment_mixed(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t-1", "tx", "h1")
        eng.confirm_proof("p1")
        eng.create_settlement_proof("p2", "t-1", "tx", "h2")
        eng.fail_proof("p2")
        a = eng.ledger_assessment("assess-1", "t-1")
        assert a.total_confirmed == 1
        assert a.total_failed == 1
        assert a.integrity_score == pytest.approx(0.5)

    def test_assessment_tenant_scoped(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t-1", "tx", "h1")
        eng.confirm_proof("p1")
        eng.create_settlement_proof("p2", "t-2", "tx", "h2")
        eng.fail_proof("p2")
        a = eng.ledger_assessment("assess-1", "t-1")
        assert a.total_confirmed == 1
        assert a.total_failed == 0

    def test_assessment_emits_event(self):
        eng, es = _make_engine()
        before = es.event_count
        eng.ledger_assessment("assess-1", "t-1")
        assert es.event_count > before

    def test_assessment_with_disputed(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t-1", "tx", "h1")
        eng.dispute_proof("p1")
        a = eng.ledger_assessment("assess-1", "t-1")
        assert a.total_disputed == 1
        assert a.integrity_score == 0.0

    def test_assessment_pending_not_counted(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t-1", "tx", "h1")
        a = eng.ledger_assessment("assess-1", "t-1")
        # pending proofs not in confirmed/failed/disputed
        assert a.total_confirmed == 0
        assert a.total_failed == 0
        assert a.total_disputed == 0
        assert a.integrity_score == 1.0


# ======================================================================
# Snapshot
# ======================================================================


class TestLedgerSnapshotEngine:
    def test_snapshot_empty(self):
        eng, _ = _make_engine()
        s = eng.ledger_snapshot("snap-1", "t-1")
        assert isinstance(s, LedgerSnapshot)
        assert s.total_accounts == 0
        assert s.total_transactions == 0
        assert s.total_proofs == 0
        assert s.total_anchors == 0
        assert s.total_wallets == 0
        assert s.total_violations == 0

    def test_snapshot_reflects_state(self):
        eng, _ = _make_engine()
        eng.register_account("a1", "t-1", "A1")
        eng.register_account("a2", "t-1", "A2")
        eng.register_wallet("w1", "t-1", "id1", "pk1")
        eng.create_anchor("anc-1", "t-1", "src", "h1", "ref")
        s = eng.ledger_snapshot("snap-1", "t-1")
        assert s.total_accounts == 2
        assert s.total_wallets == 1
        assert s.total_anchors == 1

    def test_snapshot_tenant_scoped(self):
        eng, _ = _make_engine()
        eng.register_account("a1", "t-1", "A1")
        eng.register_account("a2", "t-2", "A2")
        s = eng.ledger_snapshot("snap-1", "t-1")
        assert s.total_accounts == 1

    def test_snapshot_emits_event(self):
        eng, es = _make_engine()
        before = es.event_count
        eng.ledger_snapshot("snap-1", "t-1")
        assert es.event_count > before


# ======================================================================
# Violation detection
# ======================================================================


class TestDetectLedgerViolations:
    def test_no_violations(self):
        eng, _ = _make_engine()
        result = eng.detect_ledger_violations("t-1")
        assert result == ()

    def test_failed_proof_creates_violation(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t-1", "tx", "h1")
        eng.fail_proof("p1")
        viols = eng.detect_ledger_violations("t-1")
        assert len(viols) == 1
        assert viols[0].kind is LedgerViolationKind.PROOF_FAILED

    def test_failed_anchor_creates_violation(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t-1", "src", "h1", "ref")
        eng.fail_anchor("a1")
        viols = eng.detect_ledger_violations("t-1")
        assert len(viols) == 1
        assert viols[0].kind is LedgerViolationKind.ANCHOR_EXPIRED

    def test_compromised_wallet_creates_violation(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t-1", "id1", "pk1")
        eng.mark_compromised("w1")
        viols = eng.detect_ledger_violations("t-1")
        assert len(viols) == 1
        assert viols[0].kind is LedgerViolationKind.WALLET_COMPROMISED

    def test_idempotent_second_call_returns_empty(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t-1", "tx", "h1")
        eng.fail_proof("p1")
        viols1 = eng.detect_ledger_violations("t-1")
        assert len(viols1) == 1
        viols2 = eng.detect_ledger_violations("t-1")
        assert len(viols2) == 0

    def test_idempotent_preserves_violation_count(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t-1", "tx", "h1")
        eng.fail_proof("p1")
        eng.detect_ledger_violations("t-1")
        eng.detect_ledger_violations("t-1")
        assert eng.violation_count == 1

    def test_tenant_scoped(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t-1", "tx", "h1")
        eng.fail_proof("p1")
        eng.create_settlement_proof("p2", "t-2", "tx", "h2")
        eng.fail_proof("p2")
        viols = eng.detect_ledger_violations("t-1")
        assert len(viols) == 1
        assert viols[0].tenant_id == "t-1"

    def test_multiple_violation_types(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t-1", "tx", "h1")
        eng.fail_proof("p1")
        eng.create_anchor("a1", "t-1", "src", "h1", "ref")
        eng.fail_anchor("a1")
        eng.register_wallet("w1", "t-1", "id1", "pk1")
        eng.mark_compromised("w1")
        viols = eng.detect_ledger_violations("t-1")
        assert len(viols) == 3
        kinds = {v.kind for v in viols}
        assert LedgerViolationKind.PROOF_FAILED in kinds
        assert LedgerViolationKind.ANCHOR_EXPIRED in kinds
        assert LedgerViolationKind.WALLET_COMPROMISED in kinds

    def test_detect_emits_event_when_violations_found(self):
        eng, es = _make_engine()
        eng.create_settlement_proof("p1", "t-1", "tx", "h1")
        eng.fail_proof("p1")
        before = es.event_count
        eng.detect_ledger_violations("t-1")
        assert es.event_count > before

    def test_detect_no_event_when_empty(self):
        eng, es = _make_engine()
        before = es.event_count
        eng.detect_ledger_violations("t-1")
        assert es.event_count == before


# ======================================================================
# State hash & snapshot (engine level)
# ======================================================================


class TestStateHash:
    def test_empty_engine_hash(self):
        eng, _ = _make_engine()
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256

    def test_hash_changes_after_mutation(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.register_account("a1", "t1", "Name")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_hash_deterministic(self):
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        eng1.register_account("a1", "t1", "Name")
        eng2.register_account("a1", "t1", "Name")
        assert eng1.state_hash() == eng2.state_hash()

    def test_hash_changes_on_status_transition(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        h1 = eng.state_hash()
        eng.confirm_proof("p1")
        h2 = eng.state_hash()
        assert h1 != h2


class TestEngineSnapshot:
    def test_snapshot_returns_dict(self):
        eng, _ = _make_engine()
        s = eng.snapshot()
        assert isinstance(s, dict)
        assert "_state_hash" in s

    def test_snapshot_contains_all_collections(self):
        eng, _ = _make_engine()
        s = eng.snapshot()
        for key in ("accounts", "transactions", "proofs", "anchors", "wallets", "decisions", "violations"):
            assert key in s

    def test_snapshot_captures_data(self):
        eng, _ = _make_engine()
        eng.register_account("a1", "t1", "Name")
        s = eng.snapshot()
        assert "a1" in s["accounts"]

    def test_snapshot_hash_matches_state_hash(self):
        eng, _ = _make_engine()
        eng.register_account("a1", "t1", "Name")
        s = eng.snapshot()
        assert s["_state_hash"] == eng.state_hash()


# ======================================================================
# Golden scenarios
# ======================================================================


class TestGoldenScenarioBillingSettlement:
    """Golden scenario 1: billing settlement produces ledger proof."""

    def test_create_tx_then_proof_then_confirm(self):
        eng, es = _make_engine()
        # Setup: create account
        eng.register_account("billing-acct", "t-1", "Billing Account")
        # Step 1: create transaction
        tx = eng.create_transaction("tx-bill", "t-1", "billing-acct", "revenue-acct", 250.0, "inv-001")
        assert tx.transaction_id == "tx-bill"
        # Step 2: create proof
        p = eng.create_settlement_proof("prf-bill", "t-1", "tx-bill", "sha256-hash-001")
        assert p.status is SettlementProofStatus.PENDING
        # Step 3: confirm
        confirmed = eng.confirm_proof("prf-bill")
        assert confirmed.status is SettlementProofStatus.CONFIRMED
        assert confirmed.verified_at == FIXED_TIME
        # Verify proof
        assert eng.verify_proof("prf-bill", "sha256-hash-001") is True
        # Events emitted
        assert es.event_count >= 4


class TestGoldenScenarioPartnerRevenueShare:
    """Golden scenario 2: partner revenue share produces settlement record."""

    def test_partner_revenue_share_flow(self):
        eng, es = _make_engine()
        eng.register_account("partner-acct", "t-1", "Partner Account")
        tx = eng.create_transaction("tx-partner", "t-1", "partner-acct", "share-acct", 100.0, "contract-001")
        p = eng.create_settlement_proof("prf-partner", "t-1", "tx-partner", "hash-partner")
        eng.confirm_proof("prf-partner")
        # Assessment
        a = eng.ledger_assessment("assess-partner", "t-1")
        assert a.total_confirmed == 1
        assert a.integrity_score == 1.0
        assert es.event_count >= 5


class TestGoldenScenarioAssuranceAnchor:
    """Golden scenario 3: assurance artifact anchored to ledger."""

    def test_anchor_create_and_confirm(self):
        eng, es = _make_engine()
        anchor = eng.create_anchor("anc-assurance", "t-1", "assurance-001", "content-hash-abc", "chain-ref-001")
        assert anchor.disposition is AnchorDisposition.PENDING
        confirmed = eng.confirm_anchor("anc-assurance")
        assert confirmed.disposition is AnchorDisposition.ANCHORED
        assert es.event_count >= 2


class TestGoldenScenarioRegulatoryAnchor:
    """Golden scenario 4: regulatory package anchored and verified."""

    def test_regulatory_anchor_and_verify(self):
        eng, es = _make_engine()
        # Anchor
        eng.create_anchor("anc-reg", "t-1", "reg-submission-001", "reg-hash", "chain-reg-ref")
        eng.confirm_anchor("anc-reg")
        # Create related proof
        eng.create_settlement_proof("prf-reg", "t-1", "reg-tx", "proof-hash-reg")
        eng.confirm_proof("prf-reg")
        assert eng.verify_proof("prf-reg", "proof-hash-reg") is True
        # Snapshot
        snap = eng.ledger_snapshot("snap-reg", "t-1")
        assert snap.total_anchors == 1
        assert snap.total_proofs == 1


class TestGoldenScenarioFailedVerification:
    """Golden scenario 5: failed proof verification creates violation."""

    def test_failed_proof_creates_violation(self):
        eng, es = _make_engine()
        eng.create_settlement_proof("prf-fail", "t-1", "tx-bad", "bad-hash")
        eng.fail_proof("prf-fail")
        # Verify returns false
        assert eng.verify_proof("prf-fail", "bad-hash") is False
        # Detect violation
        viols = eng.detect_ledger_violations("t-1")
        assert len(viols) == 1
        assert viols[0].kind is LedgerViolationKind.PROOF_FAILED
        # Assessment shows failure
        a = eng.ledger_assessment("assess-fail", "t-1")
        assert a.total_failed == 1
        assert a.integrity_score == 0.0


class TestGoldenScenarioReplayRestore:
    """Golden scenario 6: replay/restore preserves ledger state and proofs."""

    def test_same_ops_produce_same_state_hash(self):
        def _run():
            eng, _ = _make_engine()
            eng.register_account("a1", "t-1", "Account One")
            eng.register_wallet("w1", "t-1", "id1", "pk1")
            eng.create_transaction("tx-1", "t-1", "a1", "dst", 100.0, "ref")
            eng.create_settlement_proof("p1", "t-1", "tx-1", "hash1")
            eng.confirm_proof("p1")
            eng.create_anchor("anc-1", "t-1", "src", "chash", "ref")
            eng.confirm_anchor("anc-1")
            return eng.state_hash()

        h1 = _run()
        h2 = _run()
        assert h1 == h2

    def test_snapshot_captures_full_state(self):
        eng, _ = _make_engine()
        eng.register_account("a1", "t-1", "Account One")
        eng.create_settlement_proof("p1", "t-1", "tx", "hash1")
        eng.confirm_proof("p1")
        snap = eng.snapshot()
        assert "a1" in snap["accounts"]
        assert "p1" in snap["proofs"]
        assert snap["proofs"]["p1"]["status"] is SettlementProofStatus.CONFIRMED


# ======================================================================
# Terminal state blocking (comprehensive)
# ======================================================================


class TestTerminalStateBlocking:
    """Comprehensive terminal state tests across all entity types."""

    # -- Proof terminal states --

    @pytest.mark.parametrize("terminal_action", ["confirm_proof", "fail_proof"])
    @pytest.mark.parametrize("subsequent_action", ["confirm_proof", "fail_proof", "dispute_proof"])
    def test_proof_terminal_blocks_all_mutations(self, terminal_action, subsequent_action):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        getattr(eng, terminal_action)("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            getattr(eng, subsequent_action)("p1")

    # -- Anchor terminal states --

    @pytest.mark.parametrize("terminal_action", ["confirm_anchor", "fail_anchor", "revoke_anchor"])
    @pytest.mark.parametrize("subsequent_action", ["confirm_anchor", "fail_anchor", "revoke_anchor"])
    def test_anchor_terminal_blocks_all_mutations(self, terminal_action, subsequent_action):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        getattr(eng, terminal_action)("a1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal disposition"):
            getattr(eng, subsequent_action)("a1")

    # -- Wallet terminal states --

    @pytest.mark.parametrize("terminal_action", ["close_wallet", "mark_compromised"])
    @pytest.mark.parametrize("subsequent_action", ["freeze_wallet", "close_wallet", "mark_compromised"])
    def test_wallet_terminal_blocks_all_mutations(self, terminal_action, subsequent_action):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        getattr(eng, terminal_action)("w1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            getattr(eng, subsequent_action)("w1")


# ======================================================================
# Event emission (comprehensive)
# ======================================================================


class TestEventEmission:
    """Ensure every mutation emits at least one event."""

    def test_register_account_emits(self):
        eng, es = _make_engine()
        eng.register_account("a1", "t1", "Name")
        assert es.event_count >= 1

    def test_register_wallet_emits(self):
        eng, es = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        assert es.event_count >= 1

    def test_freeze_wallet_emits(self):
        eng, es = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        before = es.event_count
        eng.freeze_wallet("w1")
        assert es.event_count > before

    def test_close_wallet_emits(self):
        eng, es = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        before = es.event_count
        eng.close_wallet("w1")
        assert es.event_count > before

    def test_mark_compromised_emits(self):
        eng, es = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        before = es.event_count
        eng.mark_compromised("w1")
        assert es.event_count > before

    def test_create_transaction_emits(self):
        eng, es = _engine_with_account()
        before = es.event_count
        eng.create_transaction("tx-1", "t-1", "acct-1", "dst", 10.0, "ref")
        assert es.event_count > before

    def test_create_proof_emits(self):
        eng, es = _make_engine()
        before = es.event_count
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        assert es.event_count > before

    def test_confirm_proof_emits(self):
        eng, es = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        before = es.event_count
        eng.confirm_proof("p1")
        assert es.event_count > before

    def test_fail_proof_emits(self):
        eng, es = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        before = es.event_count
        eng.fail_proof("p1")
        assert es.event_count > before

    def test_dispute_proof_emits(self):
        eng, es = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        before = es.event_count
        eng.dispute_proof("p1")
        assert es.event_count > before

    def test_create_anchor_emits(self):
        eng, es = _make_engine()
        before = es.event_count
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        assert es.event_count > before

    def test_confirm_anchor_emits(self):
        eng, es = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        before = es.event_count
        eng.confirm_anchor("a1")
        assert es.event_count > before

    def test_fail_anchor_emits(self):
        eng, es = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        before = es.event_count
        eng.fail_anchor("a1")
        assert es.event_count > before

    def test_revoke_anchor_emits(self):
        eng, es = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        before = es.event_count
        eng.revoke_anchor("a1")
        assert es.event_count > before

    def test_assessment_emits(self):
        eng, es = _make_engine()
        before = es.event_count
        eng.ledger_assessment("assess-1", "t1")
        assert es.event_count > before

    def test_snapshot_emits(self):
        eng, es = _make_engine()
        before = es.event_count
        eng.ledger_snapshot("snap-1", "t1")
        assert es.event_count > before


# ======================================================================
# Edge cases and boundary tests
# ======================================================================


class TestBoundaryConditions:
    def test_many_accounts_same_tenant(self):
        eng, _ = _make_engine()
        for i in range(50):
            eng.register_account(f"a-{i}", "t-1", f"Account {i}")
        assert eng.account_count == 50
        assert len(eng.accounts_for_tenant("t-1")) == 50

    def test_many_wallets_same_tenant(self):
        eng, _ = _make_engine()
        for i in range(50):
            eng.register_wallet(f"w-{i}", "t-1", f"id-{i}", f"pk-{i}")
        assert eng.wallet_count == 50

    def test_many_proofs_assessment(self):
        eng, _ = _make_engine()
        for i in range(20):
            eng.create_settlement_proof(f"p-{i}", "t-1", "tx", f"h-{i}")
            if i % 2 == 0:
                eng.confirm_proof(f"p-{i}")
            else:
                eng.fail_proof(f"p-{i}")
        a = eng.ledger_assessment("assess-many", "t-1")
        assert a.total_confirmed == 10
        assert a.total_failed == 10
        assert a.integrity_score == pytest.approx(0.5)

    def test_snapshot_after_violations(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t-1", "tx", "h1")
        eng.fail_proof("p1")
        eng.detect_ledger_violations("t-1")
        snap = eng.ledger_snapshot("snap-v", "t-1")
        assert snap.total_violations == 1
        assert snap.total_proofs == 1

    def test_engine_properties_consistent(self):
        eng, _ = _make_engine()
        eng.register_account("a1", "t-1", "A1")
        eng.register_wallet("w1", "t-1", "id1", "pk1")
        eng.create_anchor("anc-1", "t-1", "src", "h1", "ref")
        eng.create_settlement_proof("p1", "t-1", "tx", "h1")
        eng.create_transaction("tx-1", "t-1", "a1", "dst", 10.0, "ref")
        assert eng.account_count == 1
        assert eng.wallet_count == 1
        assert eng.anchor_count == 1
        assert eng.proof_count == 1
        assert eng.transaction_count == 1
        assert eng.violation_count == 0


# ======================================================================
# Wallet lifecycle transitions
# ======================================================================


class TestWalletLifecycle:
    def test_active_to_frozen_to_closed(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        w = eng.freeze_wallet("w1")
        assert w.status is WalletStatus.FROZEN
        w = eng.close_wallet("w1")
        assert w.status is WalletStatus.CLOSED

    def test_active_to_frozen_to_compromised(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        eng.freeze_wallet("w1")
        w = eng.mark_compromised("w1")
        assert w.status is WalletStatus.COMPROMISED

    def test_active_directly_to_closed(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        w = eng.close_wallet("w1")
        assert w.status is WalletStatus.CLOSED

    def test_active_directly_to_compromised(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        w = eng.mark_compromised("w1")
        assert w.status is WalletStatus.COMPROMISED

    def test_wallet_preserves_metadata_after_freeze(self):
        eng, _ = _make_engine()
        eng.register_wallet("w1", "t1", "id1", "pk1")
        w = eng.freeze_wallet("w1")
        assert w.tenant_id == "t1"
        assert w.identity_ref == "id1"
        assert w.public_key_ref == "pk1"


# ======================================================================
# Proof lifecycle transitions
# ======================================================================


class TestProofLifecycle:
    def test_pending_to_confirmed(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        p = eng.confirm_proof("p1")
        assert p.status is SettlementProofStatus.CONFIRMED

    def test_pending_to_failed(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        p = eng.fail_proof("p1")
        assert p.status is SettlementProofStatus.FAILED

    def test_pending_to_disputed(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        p = eng.dispute_proof("p1")
        assert p.status is SettlementProofStatus.DISPUTED

    def test_disputed_to_confirmed(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.dispute_proof("p1")
        p = eng.confirm_proof("p1")
        assert p.status is SettlementProofStatus.CONFIRMED

    def test_disputed_to_failed(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "h1")
        eng.dispute_proof("p1")
        p = eng.fail_proof("p1")
        assert p.status is SettlementProofStatus.FAILED

    def test_proof_preserves_hash_after_confirm(self):
        eng, _ = _make_engine()
        eng.create_settlement_proof("p1", "t1", "tx", "hash-original")
        p = eng.confirm_proof("p1")
        assert p.proof_hash == "hash-original"


# ======================================================================
# Anchor lifecycle transitions
# ======================================================================


class TestAnchorLifecycle:
    def test_pending_to_anchored(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        a = eng.confirm_anchor("a1")
        assert a.disposition is AnchorDisposition.ANCHORED

    def test_pending_to_failed(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        a = eng.fail_anchor("a1")
        assert a.disposition is AnchorDisposition.FAILED

    def test_pending_to_revoked(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "h1", "ref")
        a = eng.revoke_anchor("a1")
        assert a.disposition is AnchorDisposition.REVOKED

    def test_anchor_preserves_content_hash(self):
        eng, _ = _make_engine()
        eng.create_anchor("a1", "t1", "src", "original-hash", "ref")
        a = eng.confirm_anchor("a1")
        assert a.content_hash == "original-hash"


# ======================================================================
# Collections internal method
# ======================================================================


class TestCollections:
    def test_collections_returns_dict(self):
        eng, _ = _make_engine()
        c = eng._collections()
        assert isinstance(c, dict)
        assert "accounts" in c
        assert "transactions" in c
        assert "proofs" in c
        assert "anchors" in c
        assert "wallets" in c
        assert "decisions" in c
        assert "violations" in c
