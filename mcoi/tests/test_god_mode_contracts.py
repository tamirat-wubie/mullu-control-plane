"""Contract-level tests for the god-mode subsystem.

Verifies frozen-dataclass invariants on each public type — every god capability
is inert until upgraded by an explicit agreement, and the agreement/ticket/
receipt records reject malformed inputs at construction time.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.contracts.god_mode import (
    ActivationAgreement,
    GodCapability,
    GodCapabilityBlastRadius,
    GodCapabilityState,
    GodModeReceipt,
    GodModeTicket,
    GodReceiptOutcome,
    GodTicketState,
    RegistrationAgreement,
)


_LONG_JUST = "x" * 60  # comfortably above the 50-char min

ISO_NOW = "2026-05-09T12:00:00Z"
ISO_LATER = "2026-05-09T12:05:00Z"


# ---------------------------------------------------------------------------
# GodCapability
# ---------------------------------------------------------------------------


def _make_capability(**overrides):
    base = dict(
        module="data",
        name="purge_tenant_now",
        description="Delete all data for a tenant immediately.",
        blast_radius=GodCapabilityBlastRadius.CATASTROPHIC,
        bypasses=("retention_window",),
        default_ttl_seconds=60,
    )
    base.update(overrides)
    return GodCapability(**base)


def test_capability_basic_construction_succeeds():
    cap = _make_capability()
    assert cap.module == "data"
    assert cap.name == "purge_tenant_now"
    assert cap.fqn == "data.purge_tenant_now"
    assert cap.key == ("data", "purge_tenant_now")


def test_capability_is_frozen():
    cap = _make_capability()
    with pytest.raises(AttributeError):
        cap.module = "rbac"  # type: ignore[misc]


def test_capability_rejects_empty_module():
    with pytest.raises(ValueError):
        _make_capability(module="")


def test_capability_rejects_empty_bypasses():
    with pytest.raises(ValueError):
        _make_capability(bypasses=())


def test_capability_rejects_non_enum_blast_radius():
    with pytest.raises(ValueError):
        _make_capability(blast_radius="catastrophic")  # type: ignore[arg-type]


def test_capability_rejects_ttl_too_low():
    with pytest.raises(ValueError):
        _make_capability(default_ttl_seconds=1)


def test_capability_rejects_ttl_too_high():
    with pytest.raises(ValueError):
        _make_capability(default_ttl_seconds=99999)


def test_capability_rejects_min_justification_below_floor():
    with pytest.raises(ValueError):
        _make_capability(min_justification_chars=10)


def test_capability_freeze_bypasses():
    cap = _make_capability(bypasses=["a", "b", "c"])
    assert isinstance(cap.bypasses, tuple)
    assert cap.bypasses == ("a", "b", "c")


def test_capability_to_json_dict_round_trip():
    cap = _make_capability()
    payload = cap.to_json_dict()
    assert payload["module"] == "data"
    assert payload["blast_radius"] == "catastrophic"
    assert payload["bypasses"] == ["retention_window"]


# ---------------------------------------------------------------------------
# RegistrationAgreement
# ---------------------------------------------------------------------------


def _make_registration(**overrides):
    base = dict(
        agreement_id="god-reg-abc",
        capability_module="data",
        capability_name="purge_tenant_now",
        actor_id="alice",
        justification=_LONG_JUST,
        recorded_at=ISO_NOW,
    )
    base.update(overrides)
    return RegistrationAgreement(**base)


def test_registration_active_by_default():
    agreement = _make_registration()
    assert agreement.is_active is True


def test_registration_rejects_short_justification():
    with pytest.raises(ValueError):
        _make_registration(justification="too short")


def test_registration_rejects_bad_iso_datetime():
    with pytest.raises(ValueError):
        _make_registration(recorded_at="yesterday")


def test_registration_withdrawn_requires_reason():
    with pytest.raises(ValueError):
        _make_registration(withdrawn_at=ISO_LATER, withdrawn_reason="")


def test_registration_withdrawn_active_false():
    agreement = _make_registration(
        withdrawn_at=ISO_LATER, withdrawn_reason="rotated"
    )
    assert agreement.is_active is False


# ---------------------------------------------------------------------------
# ActivationAgreement
# ---------------------------------------------------------------------------


def _make_activation(**overrides):
    base = dict(
        agreement_id="god-act-abc",
        capability_module="data",
        capability_name="purge_tenant_now",
        actor_id="alice",
        justification=_LONG_JUST,
        target=(("tenant_id", "acme-7"),),
        requested_ttl_seconds=60,
        recorded_at=ISO_NOW,
    )
    base.update(overrides)
    return ActivationAgreement(**base)


def test_activation_basic():
    a = _make_activation()
    assert a.target == (("tenant_id", "acme-7"),)


def test_activation_rejects_bad_target_pair():
    with pytest.raises(ValueError):
        _make_activation(target=(("only_one_field",),))


def test_activation_rejects_ttl_zero():
    with pytest.raises(ValueError):
        _make_activation(requested_ttl_seconds=0)


# ---------------------------------------------------------------------------
# GodModeTicket
# ---------------------------------------------------------------------------


def _make_ticket(**overrides):
    base = dict(
        ticket_id="god-tkt-1",
        agreement_id="god-act-abc",
        capability_module="data",
        capability_name="purge_tenant_now",
        actor_id="alice",
        issued_at=ISO_NOW,
        expires_at=ISO_LATER,
        state=GodTicketState.ISSUED,
    )
    base.update(overrides)
    return GodModeTicket(**base)


def test_ticket_issued_state():
    ticket = _make_ticket()
    assert ticket.state == GodTicketState.ISSUED


def test_ticket_revoked_requires_reason():
    with pytest.raises(ValueError):
        _make_ticket(state=GodTicketState.REVOKED, revoked_at=ISO_LATER, revoked_reason="")


def test_ticket_state_must_be_enum():
    with pytest.raises(ValueError):
        _make_ticket(state="issued")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GodModeReceipt
# ---------------------------------------------------------------------------


def _make_receipt(**overrides):
    base = dict(
        receipt_id="god-rcpt-1",
        ticket_id="god-tkt-1",
        agreement_id="god-act-abc",
        capability_module="data",
        capability_name="purge_tenant_now",
        actor_id="alice",
        outcome=GodReceiptOutcome.SUCCESS,
        consumed_at=ISO_LATER,
        pre_state_hash="sha256:" + "0" * 64,
        post_state_hash="sha256:" + "1" * 64,
    )
    base.update(overrides)
    return GodModeReceipt(**base)


def test_receipt_success_basic():
    r = _make_receipt()
    assert r.outcome == GodReceiptOutcome.SUCCESS


def test_receipt_failure_requires_reason():
    with pytest.raises(ValueError):
        _make_receipt(outcome=GodReceiptOutcome.FAILURE, failure_reason="")


def test_receipt_failure_with_reason_ok():
    r = _make_receipt(outcome=GodReceiptOutcome.FAILURE, failure_reason="boom")
    assert r.outcome == GodReceiptOutcome.FAILURE
    assert r.failure_reason == "boom"


def test_receipt_aborted_requires_reason():
    with pytest.raises(ValueError):
        _make_receipt(outcome=GodReceiptOutcome.ABORTED, failure_reason="")


def test_capability_state_enum_complete():
    """Lifecycle states must cover dormant→armed→suspended/withdrawn."""
    members = {member.value for member in GodCapabilityState}
    assert {"dormant", "armed", "suspended", "withdrawn"} <= members


def test_ticket_state_enum_complete():
    members = {member.value for member in GodTicketState}
    assert {"issued", "consumed", "expired", "revoked"} <= members
