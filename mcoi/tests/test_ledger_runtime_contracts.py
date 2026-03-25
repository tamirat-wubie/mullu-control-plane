"""Tests for ledger / blockchain runtime contracts.

Covers all 11 dataclasses and 7 enums in
mcoi_runtime.contracts.ledger_runtime with thorough validation,
frozen-field, metadata, to_dict, and to_json_dict tests.
"""

import math
import pytest
from dataclasses import FrozenInstanceError
from types import MappingProxyType

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

# ======================================================================
# Helpers
# ======================================================================

TS = "2025-06-01T00:00:00+00:00"
TS2 = "2025-07-01T12:00:00+00:00"
DATE_ONLY = "2025-06-01"


def _account(**kw):
    defaults = dict(
        account_id="acct-1",
        tenant_id="t-1",
        display_name="Main Account",
        status=LedgerStatus.ACTIVE,
        network=LedgerNetworkKind.PRIVATE,
        balance=100.0,
        created_at=TS,
    )
    defaults.update(kw)
    return LedgerAccount(**defaults)


def _transaction(**kw):
    defaults = dict(
        transaction_id="tx-1",
        tenant_id="t-1",
        from_account="acct-src",
        to_account="acct-dst",
        amount=50.0,
        reference_ref="ref-001",
        created_at=TS,
    )
    defaults.update(kw)
    return LedgerTransaction(**defaults)


def _proof(**kw):
    defaults = dict(
        proof_id="prf-1",
        tenant_id="t-1",
        transaction_ref="tx-1",
        status=SettlementProofStatus.PENDING,
        proof_hash="abc123hash",
        created_at=TS,
    )
    defaults.update(kw)
    return SettlementProof(**defaults)


def _anchor(**kw):
    defaults = dict(
        anchor_id="anc-1",
        tenant_id="t-1",
        source_ref="src-001",
        content_hash="hash123",
        disposition=AnchorDisposition.PENDING,
        anchor_ref="ref-chain",
        created_at=TS,
    )
    defaults.update(kw)
    return AnchorRecord(**defaults)


def _wallet(**kw):
    defaults = dict(
        wallet_id="w-1",
        tenant_id="t-1",
        identity_ref="id-001",
        status=WalletStatus.ACTIVE,
        public_key_ref="pk-001",
        created_at=TS,
    )
    defaults.update(kw)
    return WalletRecord(**defaults)


def _decision(**kw):
    defaults = dict(
        decision_id="dec-1",
        tenant_id="t-1",
        operation="transfer",
        disposition="approved",
        reason="policy allows",
        decided_at=TS,
    )
    defaults.update(kw)
    return LedgerDecision(**defaults)


def _snapshot(**kw):
    defaults = dict(
        snapshot_id="snap-1",
        tenant_id="t-1",
        total_accounts=1,
        total_transactions=2,
        total_proofs=3,
        total_anchors=4,
        total_wallets=5,
        total_violations=0,
        captured_at=TS,
    )
    defaults.update(kw)
    return LedgerSnapshot(**defaults)


def _violation(**kw):
    defaults = dict(
        violation_id="viol-1",
        tenant_id="t-1",
        kind=LedgerViolationKind.PROOF_FAILED,
        operation="proof:prf-1",
        reason="hash mismatch",
        detected_at=TS,
    )
    defaults.update(kw)
    return LedgerViolation(**defaults)


def _assessment(**kw):
    defaults = dict(
        assessment_id="assess-1",
        tenant_id="t-1",
        total_confirmed=5,
        total_failed=1,
        total_disputed=0,
        integrity_score=0.83,
        assessed_at=TS,
    )
    defaults.update(kw)
    return LedgerAssessment(**defaults)


def _closure(**kw):
    defaults = dict(
        report_id="rpt-1",
        tenant_id="t-1",
        total_accounts=3,
        total_transactions=10,
        total_proofs=5,
        total_anchors=2,
        total_violations=1,
        created_at=TS,
    )
    defaults.update(kw)
    return LedgerClosureReport(**defaults)


# ======================================================================
# Enum membership tests
# ======================================================================


class TestLedgerStatusEnum:
    def test_members(self):
        assert set(LedgerStatus) == {
            LedgerStatus.ACTIVE,
            LedgerStatus.SUSPENDED,
            LedgerStatus.CLOSED,
            LedgerStatus.ARCHIVED,
        }

    @pytest.mark.parametrize("member", list(LedgerStatus))
    def test_value_is_string(self, member):
        assert isinstance(member.value, str)

    def test_from_value(self):
        assert LedgerStatus("active") is LedgerStatus.ACTIVE


class TestLedgerNetworkKindEnum:
    def test_members(self):
        assert set(LedgerNetworkKind) == {
            LedgerNetworkKind.PRIVATE,
            LedgerNetworkKind.CONSORTIUM,
            LedgerNetworkKind.PUBLIC,
            LedgerNetworkKind.HYBRID,
        }

    @pytest.mark.parametrize("member", list(LedgerNetworkKind))
    def test_value_is_string(self, member):
        assert isinstance(member.value, str)


class TestSettlementProofStatusEnum:
    def test_members(self):
        assert set(SettlementProofStatus) == {
            SettlementProofStatus.PENDING,
            SettlementProofStatus.CONFIRMED,
            SettlementProofStatus.FAILED,
            SettlementProofStatus.DISPUTED,
        }

    @pytest.mark.parametrize("member", list(SettlementProofStatus))
    def test_value_is_string(self, member):
        assert isinstance(member.value, str)


class TestAnchorDispositionEnum:
    def test_members(self):
        assert set(AnchorDisposition) == {
            AnchorDisposition.ANCHORED,
            AnchorDisposition.PENDING,
            AnchorDisposition.FAILED,
            AnchorDisposition.REVOKED,
        }

    @pytest.mark.parametrize("member", list(AnchorDisposition))
    def test_value_is_string(self, member):
        assert isinstance(member.value, str)


class TestWalletStatusEnum:
    def test_members(self):
        assert set(WalletStatus) == {
            WalletStatus.ACTIVE,
            WalletStatus.FROZEN,
            WalletStatus.CLOSED,
            WalletStatus.COMPROMISED,
        }

    @pytest.mark.parametrize("member", list(WalletStatus))
    def test_value_is_string(self, member):
        assert isinstance(member.value, str)


class TestLedgerViolationKindEnum:
    def test_members(self):
        assert set(LedgerViolationKind) == {
            LedgerViolationKind.PROOF_FAILED,
            LedgerViolationKind.ANCHOR_EXPIRED,
            LedgerViolationKind.WALLET_COMPROMISED,
            LedgerViolationKind.SETTLEMENT_DISPUTED,
        }

    @pytest.mark.parametrize("member", list(LedgerViolationKind))
    def test_value_is_string(self, member):
        assert isinstance(member.value, str)


# ======================================================================
# LedgerAccount
# ======================================================================


class TestLedgerAccount:
    def test_valid_construction(self):
        a = _account()
        assert a.account_id == "acct-1"
        assert a.tenant_id == "t-1"
        assert a.display_name == "Main Account"
        assert a.status is LedgerStatus.ACTIVE
        assert a.network is LedgerNetworkKind.PRIVATE
        assert a.balance == 100.0
        assert a.created_at == TS

    def test_all_statuses_accepted(self):
        for s in LedgerStatus:
            a = _account(status=s)
            assert a.status is s

    def test_all_networks_accepted(self):
        for n in LedgerNetworkKind:
            a = _account(network=n)
            assert a.network is n

    def test_zero_balance_accepted(self):
        a = _account(balance=0.0)
        assert a.balance == 0.0

    def test_int_balance_coerced(self):
        a = _account(balance=5)
        assert a.balance == 5.0

    def test_date_only_accepted(self):
        a = _account(created_at=DATE_ONLY)
        assert a.created_at == DATE_ONLY

    # -- empty-string rejections --

    @pytest.mark.parametrize("field", ["account_id", "tenant_id", "display_name"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _account(**{field: ""})

    @pytest.mark.parametrize("field", ["account_id", "tenant_id", "display_name"])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _account(**{field: "   "})

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _account(created_at="")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _account(created_at="not-a-date")

    # -- type rejections --

    def test_invalid_status_type_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _account(status="active")

    def test_invalid_network_type_rejected(self):
        with pytest.raises(ValueError, match="network"):
            _account(network="private")

    # -- balance validation --

    def test_negative_balance_rejected(self):
        with pytest.raises(ValueError, match="balance"):
            _account(balance=-1.0)

    def test_bool_balance_rejected(self):
        with pytest.raises(ValueError, match="balance"):
            _account(balance=True)

    def test_nan_balance_rejected(self):
        with pytest.raises(ValueError, match="balance"):
            _account(balance=float("nan"))

    def test_inf_balance_rejected(self):
        with pytest.raises(ValueError, match="balance"):
            _account(balance=float("inf"))

    # -- frozen --

    def test_frozen_rejects_mutation(self):
        a = _account()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "account_id", "x")

    def test_frozen_rejects_balance_mutation(self):
        a = _account()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "balance", 999.0)

    # -- metadata --

    def test_metadata_defaults_empty(self):
        a = _account()
        assert isinstance(a.metadata, MappingProxyType)
        assert len(a.metadata) == 0

    def test_metadata_frozen_to_mapping_proxy(self):
        a = _account(metadata={"k": "v"})
        assert isinstance(a.metadata, MappingProxyType)
        assert a.metadata["k"] == "v"

    def test_metadata_nested_dict_frozen(self):
        a = _account(metadata={"inner": {"x": 1}})
        assert isinstance(a.metadata["inner"], MappingProxyType)

    def test_metadata_immutable(self):
        a = _account(metadata={"k": "v"})
        with pytest.raises(TypeError):
            a.metadata["k2"] = "v2"

    # -- to_dict --

    def test_to_dict_preserves_enum(self):
        d = _account().to_dict()
        assert d["status"] is LedgerStatus.ACTIVE
        assert d["network"] is LedgerNetworkKind.PRIVATE

    def test_to_dict_metadata_is_plain_dict(self):
        d = _account(metadata={"k": "v"}).to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_dict_roundtrip_fields(self):
        a = _account()
        d = a.to_dict()
        assert d["account_id"] == "acct-1"
        assert d["balance"] == 100.0

    # -- to_json_dict --

    def test_to_json_dict_enums_as_strings(self):
        d = _account().to_json_dict()
        assert d["status"] == "active"
        assert d["network"] == "private"

    def test_to_json_produces_valid_json(self):
        import json
        s = _account().to_json()
        parsed = json.loads(s)
        assert parsed["account_id"] == "acct-1"


# ======================================================================
# LedgerTransaction
# ======================================================================


class TestLedgerTransaction:
    def test_valid_construction(self):
        t = _transaction()
        assert t.transaction_id == "tx-1"
        assert t.tenant_id == "t-1"
        assert t.from_account == "acct-src"
        assert t.to_account == "acct-dst"
        assert t.amount == 50.0
        assert t.reference_ref == "ref-001"

    def test_zero_amount_accepted(self):
        t = _transaction(amount=0.0)
        assert t.amount == 0.0

    def test_int_amount_coerced(self):
        t = _transaction(amount=10)
        assert t.amount == 10.0

    def test_date_only_accepted(self):
        t = _transaction(created_at=DATE_ONLY)
        assert t.created_at == DATE_ONLY

    @pytest.mark.parametrize("field", [
        "transaction_id", "tenant_id", "from_account",
        "to_account", "reference_ref",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _transaction(**{field: ""})

    @pytest.mark.parametrize("field", [
        "transaction_id", "tenant_id", "from_account",
        "to_account", "reference_ref",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _transaction(**{field: "  "})

    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError, match="amount"):
            _transaction(amount=-1.0)

    def test_bool_amount_rejected(self):
        with pytest.raises(ValueError, match="amount"):
            _transaction(amount=False)

    def test_nan_amount_rejected(self):
        with pytest.raises(ValueError, match="amount"):
            _transaction(amount=float("nan"))

    def test_inf_amount_rejected(self):
        with pytest.raises(ValueError, match="amount"):
            _transaction(amount=float("inf"))

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _transaction(created_at="")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _transaction(created_at="nope")

    def test_frozen(self):
        t = _transaction()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(t, "amount", 99.0)

    def test_metadata_frozen(self):
        t = _transaction(metadata={"k": "v"})
        assert isinstance(t.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            t.metadata["k2"] = "v2"

    def test_to_dict_metadata_plain_dict(self):
        d = _transaction(metadata={"k": "v"}).to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_dict_fields(self):
        d = _transaction().to_dict()
        assert d["transaction_id"] == "tx-1"
        assert d["amount"] == 50.0

    def test_to_json_dict(self):
        d = _transaction().to_json_dict()
        assert d["transaction_id"] == "tx-1"

    def test_to_json_string(self):
        import json
        s = _transaction().to_json()
        parsed = json.loads(s)
        assert parsed["from_account"] == "acct-src"


# ======================================================================
# SettlementProof
# ======================================================================


class TestSettlementProof:
    def test_valid_construction(self):
        p = _proof()
        assert p.proof_id == "prf-1"
        assert p.status is SettlementProofStatus.PENDING
        assert p.proof_hash == "abc123hash"
        assert p.verified_at == ""

    def test_all_statuses(self):
        for s in SettlementProofStatus:
            p = _proof(status=s)
            assert p.status is s

    def test_verified_at_optional_empty(self):
        p = _proof(verified_at="")
        assert p.verified_at == ""

    def test_verified_at_valid_datetime(self):
        p = _proof(verified_at=TS2)
        assert p.verified_at == TS2

    def test_verified_at_date_only_accepted(self):
        p = _proof(verified_at=DATE_ONLY)
        assert p.verified_at == DATE_ONLY

    def test_verified_at_invalid_rejected(self):
        with pytest.raises(ValueError, match="verified_at"):
            _proof(verified_at="bad-date")

    def test_date_only_created_at(self):
        p = _proof(created_at=DATE_ONLY)
        assert p.created_at == DATE_ONLY

    @pytest.mark.parametrize("field", [
        "proof_id", "tenant_id", "transaction_ref", "proof_hash",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _proof(**{field: ""})

    @pytest.mark.parametrize("field", [
        "proof_id", "tenant_id", "transaction_ref", "proof_hash",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _proof(**{field: "   "})

    def test_invalid_status_type_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _proof(status="pending")

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _proof(created_at="")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _proof(created_at="xxx")

    def test_frozen(self):
        p = _proof()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(p, "proof_id", "x")

    def test_frozen_status(self):
        p = _proof()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(p, "status", SettlementProofStatus.CONFIRMED)

    def test_metadata_frozen(self):
        p = _proof(metadata={"k": "v"})
        assert isinstance(p.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _proof().to_dict()
        assert d["status"] is SettlementProofStatus.PENDING

    def test_to_dict_metadata_plain(self):
        d = _proof(metadata={"k": "v"}).to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_json_dict_status_string(self):
        d = _proof().to_json_dict()
        assert d["status"] == "pending"

    def test_to_json_string(self):
        import json
        s = _proof().to_json()
        parsed = json.loads(s)
        assert parsed["proof_hash"] == "abc123hash"


# ======================================================================
# AnchorRecord
# ======================================================================


class TestAnchorRecord:
    def test_valid_construction(self):
        a = _anchor()
        assert a.anchor_id == "anc-1"
        assert a.disposition is AnchorDisposition.PENDING
        assert a.content_hash == "hash123"

    def test_all_dispositions(self):
        for d in AnchorDisposition:
            a = _anchor(disposition=d)
            assert a.disposition is d

    def test_date_only_accepted(self):
        a = _anchor(created_at=DATE_ONLY)
        assert a.created_at == DATE_ONLY

    @pytest.mark.parametrize("field", [
        "anchor_id", "tenant_id", "source_ref",
        "content_hash", "anchor_ref",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _anchor(**{field: ""})

    @pytest.mark.parametrize("field", [
        "anchor_id", "tenant_id", "source_ref",
        "content_hash", "anchor_ref",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _anchor(**{field: "   "})

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError, match="disposition"):
            _anchor(disposition="pending")

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _anchor(created_at="")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _anchor(created_at="nope")

    def test_frozen(self):
        a = _anchor()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "anchor_id", "x")

    def test_metadata_frozen(self):
        a = _anchor(metadata={"k": "v"})
        assert isinstance(a.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _anchor().to_dict()
        assert d["disposition"] is AnchorDisposition.PENDING

    def test_to_dict_metadata_plain(self):
        d = _anchor(metadata={"k": "v"}).to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_json_dict_disposition_string(self):
        d = _anchor().to_json_dict()
        assert d["disposition"] == "pending"

    def test_to_json_string(self):
        import json
        s = _anchor().to_json()
        parsed = json.loads(s)
        assert parsed["content_hash"] == "hash123"


# ======================================================================
# WalletRecord
# ======================================================================


class TestWalletRecord:
    def test_valid_construction(self):
        w = _wallet()
        assert w.wallet_id == "w-1"
        assert w.status is WalletStatus.ACTIVE
        assert w.public_key_ref == "pk-001"

    def test_all_statuses(self):
        for s in WalletStatus:
            w = _wallet(status=s)
            assert w.status is s

    def test_date_only_accepted(self):
        w = _wallet(created_at=DATE_ONLY)
        assert w.created_at == DATE_ONLY

    @pytest.mark.parametrize("field", [
        "wallet_id", "tenant_id", "identity_ref", "public_key_ref",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _wallet(**{field: ""})

    @pytest.mark.parametrize("field", [
        "wallet_id", "tenant_id", "identity_ref", "public_key_ref",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _wallet(**{field: "   "})

    def test_invalid_status_type(self):
        with pytest.raises(ValueError, match="status"):
            _wallet(status="active")

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _wallet(created_at="")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _wallet(created_at="oops")

    def test_frozen(self):
        w = _wallet()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(w, "wallet_id", "x")

    def test_metadata_frozen(self):
        w = _wallet(metadata={"k": "v"})
        assert isinstance(w.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _wallet().to_dict()
        assert d["status"] is WalletStatus.ACTIVE

    def test_to_dict_metadata_plain(self):
        d = _wallet(metadata={"k": "v"}).to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_json_dict_status_string(self):
        d = _wallet().to_json_dict()
        assert d["status"] == "active"

    def test_to_json_string(self):
        import json
        s = _wallet().to_json()
        parsed = json.loads(s)
        assert parsed["public_key_ref"] == "pk-001"


# ======================================================================
# LedgerDecision
# ======================================================================


class TestLedgerDecision:
    def test_valid_construction(self):
        d = _decision()
        assert d.decision_id == "dec-1"
        assert d.operation == "transfer"
        assert d.disposition == "approved"
        assert d.reason == "policy allows"

    def test_date_only_accepted(self):
        d = _decision(decided_at=DATE_ONLY)
        assert d.decided_at == DATE_ONLY

    @pytest.mark.parametrize("field", [
        "decision_id", "tenant_id", "operation",
        "disposition", "reason",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _decision(**{field: ""})

    @pytest.mark.parametrize("field", [
        "decision_id", "tenant_id", "operation",
        "disposition", "reason",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _decision(**{field: "   "})

    def test_empty_decided_at_rejected(self):
        with pytest.raises(ValueError, match="decided_at"):
            _decision(decided_at="")

    def test_invalid_decided_at_rejected(self):
        with pytest.raises(ValueError, match="decided_at"):
            _decision(decided_at="abc")

    def test_frozen(self):
        d = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "decision_id", "x")

    def test_metadata_frozen(self):
        d = _decision(metadata={"k": "v"})
        assert isinstance(d.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        d = _decision(metadata={"k": "v"}).to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_dict_fields(self):
        d = _decision().to_dict()
        assert d["operation"] == "transfer"

    def test_to_json_string(self):
        import json
        s = _decision().to_json()
        parsed = json.loads(s)
        assert parsed["disposition"] == "approved"


# ======================================================================
# LedgerSnapshot
# ======================================================================


class TestLedgerSnapshot:
    def test_valid_construction(self):
        s = _snapshot()
        assert s.snapshot_id == "snap-1"
        assert s.total_accounts == 1
        assert s.total_transactions == 2
        assert s.total_proofs == 3
        assert s.total_anchors == 4
        assert s.total_wallets == 5
        assert s.total_violations == 0

    def test_all_zeros_accepted(self):
        s = _snapshot(
            total_accounts=0, total_transactions=0, total_proofs=0,
            total_anchors=0, total_wallets=0, total_violations=0,
        )
        assert s.total_accounts == 0

    def test_date_only_accepted(self):
        s = _snapshot(captured_at=DATE_ONLY)
        assert s.captured_at == DATE_ONLY

    @pytest.mark.parametrize("field", ["snapshot_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _snapshot(**{field: ""})

    @pytest.mark.parametrize("field", [
        "total_accounts", "total_transactions", "total_proofs",
        "total_anchors", "total_wallets", "total_violations",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _snapshot(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_accounts", "total_transactions", "total_proofs",
        "total_anchors", "total_wallets", "total_violations",
    ])
    def test_bool_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _snapshot(**{field: True})

    @pytest.mark.parametrize("field", [
        "total_accounts", "total_transactions", "total_proofs",
        "total_anchors", "total_wallets", "total_violations",
    ])
    def test_float_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _snapshot(**{field: 1.5})

    def test_empty_captured_at_rejected(self):
        with pytest.raises(ValueError, match="captured_at"):
            _snapshot(captured_at="")

    def test_invalid_captured_at_rejected(self):
        with pytest.raises(ValueError, match="captured_at"):
            _snapshot(captured_at="nope")

    def test_frozen(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "total_accounts", 99)

    def test_metadata_frozen(self):
        s = _snapshot(metadata={"k": "v"})
        assert isinstance(s.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        d = _snapshot(metadata={"k": "v"}).to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_dict_fields(self):
        d = _snapshot().to_dict()
        assert d["total_proofs"] == 3

    def test_to_json_string(self):
        import json
        s = _snapshot().to_json()
        parsed = json.loads(s)
        assert parsed["total_wallets"] == 5


# ======================================================================
# LedgerViolation
# ======================================================================


class TestLedgerViolation:
    def test_valid_construction(self):
        v = _violation()
        assert v.violation_id == "viol-1"
        assert v.kind is LedgerViolationKind.PROOF_FAILED
        assert v.operation == "proof:prf-1"
        assert v.reason == "hash mismatch"

    def test_all_kinds(self):
        for k in LedgerViolationKind:
            v = _violation(kind=k)
            assert v.kind is k

    def test_date_only_accepted(self):
        v = _violation(detected_at=DATE_ONLY)
        assert v.detected_at == DATE_ONLY

    @pytest.mark.parametrize("field", [
        "violation_id", "tenant_id", "operation", "reason",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _violation(**{field: ""})

    @pytest.mark.parametrize("field", [
        "violation_id", "tenant_id", "operation", "reason",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _violation(**{field: "   "})

    def test_invalid_kind_type(self):
        with pytest.raises(ValueError, match="kind"):
            _violation(kind="proof_failed")

    def test_empty_detected_at_rejected(self):
        with pytest.raises(ValueError, match="detected_at"):
            _violation(detected_at="")

    def test_invalid_detected_at_rejected(self):
        with pytest.raises(ValueError, match="detected_at"):
            _violation(detected_at="xyz")

    def test_frozen(self):
        v = _violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "violation_id", "x")

    def test_metadata_frozen(self):
        v = _violation(metadata={"k": "v"})
        assert isinstance(v.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _violation().to_dict()
        assert d["kind"] is LedgerViolationKind.PROOF_FAILED

    def test_to_dict_metadata_plain(self):
        d = _violation(metadata={"k": "v"}).to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_json_dict_kind_string(self):
        d = _violation().to_json_dict()
        assert d["kind"] == "proof_failed"

    def test_to_json_string(self):
        import json
        s = _violation().to_json()
        parsed = json.loads(s)
        assert parsed["operation"] == "proof:prf-1"


# ======================================================================
# LedgerAssessment
# ======================================================================


class TestLedgerAssessment:
    def test_valid_construction(self):
        a = _assessment()
        assert a.assessment_id == "assess-1"
        assert a.total_confirmed == 5
        assert a.total_failed == 1
        assert a.total_disputed == 0
        assert a.integrity_score == pytest.approx(0.83)

    def test_zero_integrity_accepted(self):
        a = _assessment(integrity_score=0.0)
        assert a.integrity_score == 0.0

    def test_one_integrity_accepted(self):
        a = _assessment(integrity_score=1.0)
        assert a.integrity_score == 1.0

    def test_int_zero_integrity_accepted(self):
        a = _assessment(integrity_score=0)
        assert a.integrity_score == 0.0

    def test_int_one_integrity_accepted(self):
        a = _assessment(integrity_score=1)
        assert a.integrity_score == 1.0

    def test_date_only_accepted(self):
        a = _assessment(assessed_at=DATE_ONLY)
        assert a.assessed_at == DATE_ONLY

    @pytest.mark.parametrize("field", ["assessment_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _assessment(**{field: ""})

    # -- int field validation --

    @pytest.mark.parametrize("field", [
        "total_confirmed", "total_failed", "total_disputed",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _assessment(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_confirmed", "total_failed", "total_disputed",
    ])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _assessment(**{field: True})

    @pytest.mark.parametrize("field", [
        "total_confirmed", "total_failed", "total_disputed",
    ])
    def test_float_int_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _assessment(**{field: 1.5})

    # -- integrity_score (unit float) --

    def test_negative_integrity_rejected(self):
        with pytest.raises(ValueError, match="integrity_score"):
            _assessment(integrity_score=-0.1)

    def test_over_one_integrity_rejected(self):
        with pytest.raises(ValueError, match="integrity_score"):
            _assessment(integrity_score=1.01)

    def test_nan_integrity_rejected(self):
        with pytest.raises(ValueError, match="integrity_score"):
            _assessment(integrity_score=float("nan"))

    def test_inf_integrity_rejected(self):
        with pytest.raises(ValueError, match="integrity_score"):
            _assessment(integrity_score=float("inf"))

    def test_bool_integrity_rejected(self):
        with pytest.raises(ValueError, match="integrity_score"):
            _assessment(integrity_score=True)

    def test_empty_assessed_at_rejected(self):
        with pytest.raises(ValueError, match="assessed_at"):
            _assessment(assessed_at="")

    def test_invalid_assessed_at_rejected(self):
        with pytest.raises(ValueError, match="assessed_at"):
            _assessment(assessed_at="xyz")

    def test_frozen(self):
        a = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "integrity_score", 0.5)

    def test_metadata_frozen(self):
        a = _assessment(metadata={"k": "v"})
        assert isinstance(a.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        d = _assessment(metadata={"k": "v"}).to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_dict_fields(self):
        d = _assessment().to_dict()
        assert d["total_confirmed"] == 5

    def test_to_json_string(self):
        import json
        s = _assessment().to_json()
        parsed = json.loads(s)
        assert parsed["total_failed"] == 1


# ======================================================================
# LedgerClosureReport
# ======================================================================


class TestLedgerClosureReport:
    def test_valid_construction(self):
        c = _closure()
        assert c.report_id == "rpt-1"
        assert c.total_accounts == 3
        assert c.total_transactions == 10
        assert c.total_proofs == 5
        assert c.total_anchors == 2
        assert c.total_violations == 1

    def test_all_zeros_accepted(self):
        c = _closure(
            total_accounts=0, total_transactions=0, total_proofs=0,
            total_anchors=0, total_violations=0,
        )
        assert c.total_accounts == 0

    def test_date_only_accepted(self):
        c = _closure(created_at=DATE_ONLY)
        assert c.created_at == DATE_ONLY

    @pytest.mark.parametrize("field", ["report_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _closure(**{field: ""})

    @pytest.mark.parametrize("field", [
        "total_accounts", "total_transactions", "total_proofs",
        "total_anchors", "total_violations",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _closure(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_accounts", "total_transactions", "total_proofs",
        "total_anchors", "total_violations",
    ])
    def test_bool_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _closure(**{field: True})

    @pytest.mark.parametrize("field", [
        "total_accounts", "total_transactions", "total_proofs",
        "total_anchors", "total_violations",
    ])
    def test_float_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _closure(**{field: 1.5})

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _closure(created_at="")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _closure(created_at="nope")

    def test_frozen(self):
        c = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, "total_accounts", 99)

    def test_metadata_frozen(self):
        c = _closure(metadata={"k": "v"})
        assert isinstance(c.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        d = _closure(metadata={"k": "v"}).to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_dict_fields(self):
        d = _closure().to_dict()
        assert d["total_proofs"] == 5

    def test_to_json_string(self):
        import json
        s = _closure().to_json()
        parsed = json.loads(s)
        assert parsed["total_violations"] == 1


# ======================================================================
# Cross-cutting: metadata edge cases
# ======================================================================


class TestMetadataEdgeCases:
    """Shared metadata freeze/thaw patterns across all contract types."""

    @pytest.mark.parametrize("factory", [
        _account, _transaction, _proof, _anchor, _wallet,
        _decision, _snapshot, _violation, _assessment, _closure,
    ])
    def test_empty_metadata_is_mapping_proxy(self, factory):
        obj = factory()
        assert isinstance(obj.metadata, MappingProxyType)

    @pytest.mark.parametrize("factory", [
        _account, _transaction, _proof, _anchor, _wallet,
        _decision, _snapshot, _violation, _assessment, _closure,
    ])
    def test_metadata_dict_frozen(self, factory):
        obj = factory(metadata={"key": "val"})
        assert isinstance(obj.metadata, MappingProxyType)
        assert obj.metadata["key"] == "val"

    @pytest.mark.parametrize("factory", [
        _account, _transaction, _proof, _anchor, _wallet,
        _decision, _snapshot, _violation, _assessment, _closure,
    ])
    def test_metadata_immutable(self, factory):
        obj = factory(metadata={"k": "v"})
        with pytest.raises(TypeError):
            obj.metadata["new"] = "fail"

    @pytest.mark.parametrize("factory", [
        _account, _transaction, _proof, _anchor, _wallet,
        _decision, _snapshot, _violation, _assessment, _closure,
    ])
    def test_to_dict_metadata_plain_dict(self, factory):
        d = factory(metadata={"k": "v"}).to_dict()
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("factory", [
        _account, _transaction, _proof, _anchor, _wallet,
        _decision, _snapshot, _violation, _assessment, _closure,
    ])
    def test_nested_metadata_frozen(self, factory):
        obj = factory(metadata={"inner": {"a": 1}})
        assert isinstance(obj.metadata["inner"], MappingProxyType)

    @pytest.mark.parametrize("factory", [
        _account, _transaction, _proof, _anchor, _wallet,
        _decision, _snapshot, _violation, _assessment, _closure,
    ])
    def test_list_in_metadata_becomes_tuple(self, factory):
        obj = factory(metadata={"items": [1, 2, 3]})
        assert isinstance(obj.metadata["items"], tuple)


# ======================================================================
# Cross-cutting: frozen instance tests
# ======================================================================


class TestFrozenInstances:
    @pytest.mark.parametrize("factory,field", [
        (_account, "account_id"),
        (_account, "balance"),
        (_account, "status"),
        (_transaction, "transaction_id"),
        (_transaction, "amount"),
        (_proof, "proof_id"),
        (_proof, "status"),
        (_anchor, "anchor_id"),
        (_anchor, "disposition"),
        (_wallet, "wallet_id"),
        (_wallet, "status"),
        (_decision, "decision_id"),
        (_snapshot, "snapshot_id"),
        (_snapshot, "total_accounts"),
        (_violation, "violation_id"),
        (_violation, "kind"),
        (_assessment, "assessment_id"),
        (_assessment, "integrity_score"),
        (_closure, "report_id"),
        (_closure, "total_accounts"),
    ])
    def test_setattr_rejected(self, factory, field):
        obj = factory()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(obj, field, "x")


# ======================================================================
# Cross-cutting: datetime edge cases
# ======================================================================


class TestDatetimeEdgeCases:
    """Ensure various ISO formats are accepted."""

    @pytest.mark.parametrize("ts", [
        "2025-06-01T00:00:00+00:00",
        "2025-06-01T00:00:00Z",
        "2025-06-01T12:30:00-05:00",
        "2025-06-01",
        "2025-12-31T23:59:59+00:00",
    ])
    def test_account_accepts_various_timestamps(self, ts):
        a = _account(created_at=ts)
        assert a.created_at == ts

    @pytest.mark.parametrize("ts", [
        "2025-06-01T00:00:00+00:00",
        "2025-06-01",
        "2025-06-01T12:30:00Z",
    ])
    def test_transaction_accepts_various_timestamps(self, ts):
        t = _transaction(created_at=ts)
        assert t.created_at == ts

    @pytest.mark.parametrize("ts", [
        "2025-06-01T00:00:00+00:00",
        "2025-06-01",
    ])
    def test_proof_accepts_various_timestamps(self, ts):
        p = _proof(created_at=ts)
        assert p.created_at == ts

    @pytest.mark.parametrize("ts", [
        "2025-06-01T00:00:00+00:00",
        "2025-06-01",
    ])
    def test_anchor_accepts_various_timestamps(self, ts):
        a = _anchor(created_at=ts)
        assert a.created_at == ts

    @pytest.mark.parametrize("ts", [
        "2025-06-01T00:00:00+00:00",
        "2025-06-01",
    ])
    def test_wallet_accepts_various_timestamps(self, ts):
        w = _wallet(created_at=ts)
        assert w.created_at == ts

    @pytest.mark.parametrize("ts", [
        "2025-06-01T00:00:00+00:00",
        "2025-06-01",
    ])
    def test_decision_accepts_various_timestamps(self, ts):
        d = _decision(decided_at=ts)
        assert d.decided_at == ts

    @pytest.mark.parametrize("ts", [
        "2025-06-01T00:00:00+00:00",
        "2025-06-01",
    ])
    def test_snapshot_accepts_various_timestamps(self, ts):
        s = _snapshot(captured_at=ts)
        assert s.captured_at == ts

    @pytest.mark.parametrize("ts", [
        "2025-06-01T00:00:00+00:00",
        "2025-06-01",
    ])
    def test_violation_accepts_various_timestamps(self, ts):
        v = _violation(detected_at=ts)
        assert v.detected_at == ts

    @pytest.mark.parametrize("ts", [
        "2025-06-01T00:00:00+00:00",
        "2025-06-01",
    ])
    def test_assessment_accepts_various_timestamps(self, ts):
        a = _assessment(assessed_at=ts)
        assert a.assessed_at == ts

    @pytest.mark.parametrize("ts", [
        "2025-06-01T00:00:00+00:00",
        "2025-06-01",
    ])
    def test_closure_accepts_various_timestamps(self, ts):
        c = _closure(created_at=ts)
        assert c.created_at == ts
