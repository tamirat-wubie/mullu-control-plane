"""Contract-level tests for contact_identity contracts."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.communication_surface import ChannelType
from mcoi_runtime.contracts.contact_identity import (
    AvailabilityState,
    AvailabilityWindow,
    ChannelHandle,
    ChannelPreferenceLevel,
    ContactPreferenceRecord,
    EscalationChainRecord,
    EscalationMode,
    IdentityLink,
    IdentityRecord,
    IdentityResolutionRecord,
    IdentityRoutingDecision,
    IdentityType,
)

NOW = "2026-03-20T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestEnumCoverage:
    def test_identity_type_count(self):
        assert len(IdentityType) == 8

    def test_channel_preference_level_count(self):
        assert len(ChannelPreferenceLevel) == 4

    def test_availability_state_count(self):
        assert len(AvailabilityState) == 4

    def test_escalation_mode_count(self):
        assert len(EscalationMode) == 3


# ---------------------------------------------------------------------------
# IdentityRecord
# ---------------------------------------------------------------------------


class TestIdentityRecord:
    def _make(self, **kw):
        defaults = dict(
            identity_id="id-1", identity_type=IdentityType.PERSON,
            display_name="Alice", created_at=NOW, updated_at=NOW,
        )
        defaults.update(kw)
        return IdentityRecord(**defaults)

    def test_valid(self):
        r = self._make()
        assert r.identity_id == "id-1"
        assert r.identity_type == IdentityType.PERSON

    def test_empty_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(identity_id="")

    def test_empty_display_name_rejected(self):
        with pytest.raises(ValueError):
            self._make(display_name="")

    def test_invalid_type(self):
        with pytest.raises(ValueError):
            self._make(identity_type="alien")

    def test_all_identity_types(self):
        for it in IdentityType:
            r = self._make(identity_type=it)
            assert r.identity_type == it

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        with pytest.raises(TypeError):
            r.metadata["new"] = "val"

    def test_role_ids_frozen(self):
        r = self._make(role_ids=("admin", "viewer"))
        assert isinstance(r.role_ids, tuple)

    def test_tags_frozen(self):
        r = self._make(tags=("tag1",))
        assert isinstance(r.tags, tuple)

    def test_frozen(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.identity_id = "new"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["identity_type"] == "person"


# ---------------------------------------------------------------------------
# ChannelHandle
# ---------------------------------------------------------------------------


class TestChannelHandle:
    def _make(self, **kw):
        defaults = dict(
            handle_id="hd-1", identity_id="id-1",
            channel_type=ChannelType.EMAIL,
            address="alice@example.com", created_at=NOW,
        )
        defaults.update(kw)
        return ChannelHandle(**defaults)

    def test_valid(self):
        h = self._make()
        assert h.channel_type == ChannelType.EMAIL
        assert h.verified is False
        assert h.preference_level == ChannelPreferenceLevel.SECONDARY

    def test_empty_handle_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(handle_id="")

    def test_empty_address_rejected(self):
        with pytest.raises(ValueError):
            self._make(address="")

    def test_invalid_channel_type(self):
        with pytest.raises(ValueError):
            self._make(channel_type="pigeon")

    def test_verified_must_be_bool(self):
        with pytest.raises(ValueError):
            self._make(verified="yes")

    def test_invalid_preference_level(self):
        with pytest.raises(ValueError):
            self._make(preference_level="urgent")

    def test_all_preference_levels(self):
        for pl in ChannelPreferenceLevel:
            h = self._make(preference_level=pl)
            assert h.preference_level == pl


# ---------------------------------------------------------------------------
# IdentityLink
# ---------------------------------------------------------------------------


class TestIdentityLink:
    def test_valid(self):
        lk = IdentityLink(
            link_id="lk-1", from_identity_id="id-1",
            to_identity_id="id-2", relation="member_of",
            created_at=NOW,
        )
        assert lk.relation == "member_of"

    def test_self_referential_rejected(self):
        with pytest.raises(ValueError, match="self-referential"):
            IdentityLink(
                link_id="lk-bad", from_identity_id="id-1",
                to_identity_id="id-1", relation="knows",
                created_at=NOW,
            )

    def test_empty_relation_rejected(self):
        with pytest.raises(ValueError):
            IdentityLink(
                link_id="lk-2", from_identity_id="id-1",
                to_identity_id="id-2", relation="",
                created_at=NOW,
            )

    def test_metadata_frozen(self):
        lk = IdentityLink(
            link_id="lk-3", from_identity_id="id-1",
            to_identity_id="id-2", relation="reports_to",
            created_at=NOW, metadata={"k": "v"},
        )
        with pytest.raises(TypeError):
            lk.metadata["new"] = "val"


# ---------------------------------------------------------------------------
# ContactPreferenceRecord
# ---------------------------------------------------------------------------


class TestContactPreferenceRecord:
    def test_valid(self):
        p = ContactPreferenceRecord(
            preference_id="pref-1", identity_id="id-1",
            preferred_channels=(ChannelType.SMS, ChannelType.EMAIL),
            created_at=NOW,
        )
        assert len(p.preferred_channels) == 2

    def test_invalid_channel_in_preferred(self):
        with pytest.raises(ValueError):
            ContactPreferenceRecord(
                preference_id="pref-bad", identity_id="id-1",
                preferred_channels=("telegraph",),
                created_at=NOW,
            )

    def test_invalid_channel_in_blocked(self):
        with pytest.raises(ValueError):
            ContactPreferenceRecord(
                preference_id="pref-bad2", identity_id="id-1",
                blocked_channels=("telegraph",),
                created_at=NOW,
            )


# ---------------------------------------------------------------------------
# AvailabilityWindow
# ---------------------------------------------------------------------------


class TestAvailabilityWindow:
    def test_valid(self):
        w = AvailabilityWindow(
            window_id="aw-1", identity_id="id-1",
            state=AvailabilityState.AVAILABLE, created_at=NOW,
        )
        assert w.state == AvailabilityState.AVAILABLE

    def test_all_states(self):
        for s in AvailabilityState:
            w = AvailabilityWindow(
                window_id=f"aw-{s.value}", identity_id="id-1",
                state=s, created_at=NOW,
            )
            assert w.state == s

    def test_invalid_state(self):
        with pytest.raises(ValueError):
            AvailabilityWindow(
                window_id="aw-bad", identity_id="id-1",
                state="sleeping", created_at=NOW,
            )


# ---------------------------------------------------------------------------
# EscalationChainRecord
# ---------------------------------------------------------------------------


class TestEscalationChainRecord:
    def test_valid(self):
        c = EscalationChainRecord(
            chain_id="esc-1", name="On-call",
            mode=EscalationMode.SEQUENTIAL,
            target_identity_ids=("id-1", "id-2"),
            timeout_minutes=15, created_at=NOW,
        )
        assert len(c.target_identity_ids) == 2

    def test_empty_targets_rejected(self):
        with pytest.raises(ValueError, match="at least one"):
            EscalationChainRecord(
                chain_id="esc-bad", name="Empty",
                mode=EscalationMode.SEQUENTIAL,
                target_identity_ids=(),
                created_at=NOW,
            )

    def test_zero_timeout_rejected(self):
        with pytest.raises(ValueError):
            EscalationChainRecord(
                chain_id="esc-bad2", name="Bad",
                mode=EscalationMode.SEQUENTIAL,
                target_identity_ids=("id-1",),
                timeout_minutes=0, created_at=NOW,
            )

    def test_invalid_mode(self):
        with pytest.raises(ValueError):
            EscalationChainRecord(
                chain_id="esc-bad3", name="Bad",
                mode="random",
                target_identity_ids=("id-1",),
                created_at=NOW,
            )

    def test_all_modes(self):
        for m in EscalationMode:
            c = EscalationChainRecord(
                chain_id=f"esc-{m.value}", name=f"Chain {m.value}",
                mode=m, target_identity_ids=("id-1",),
                created_at=NOW,
            )
            assert c.mode == m

    def test_empty_string_target_rejected(self):
        with pytest.raises(ValueError):
            EscalationChainRecord(
                chain_id="esc-bad4", name="Bad",
                mode=EscalationMode.SEQUENTIAL,
                target_identity_ids=("",),
                created_at=NOW,
            )


# ---------------------------------------------------------------------------
# IdentityResolutionRecord
# ---------------------------------------------------------------------------


class TestIdentityResolutionRecord:
    def test_valid(self):
        r = IdentityResolutionRecord(
            resolution_id="res-1", resolved_identity_id="id-1",
            source_ref="alice@example.com", source_type="email",
            confidence=0.95, resolved_at=NOW,
        )
        assert r.confidence == 0.95

    def test_confidence_out_of_range(self):
        with pytest.raises(ValueError):
            IdentityResolutionRecord(
                resolution_id="res-bad", resolved_identity_id="id-1",
                source_ref="x", source_type="email",
                confidence=1.5, resolved_at=NOW,
            )

    def test_empty_source_ref_rejected(self):
        with pytest.raises(ValueError):
            IdentityResolutionRecord(
                resolution_id="res-bad2", resolved_identity_id="id-1",
                source_ref="", source_type="email",
                resolved_at=NOW,
            )


# ---------------------------------------------------------------------------
# IdentityRoutingDecision
# ---------------------------------------------------------------------------


class TestIdentityRoutingDecision:
    def test_valid(self):
        d = IdentityRoutingDecision(
            decision_id="rd-1", target_identity_id="id-1",
            selected_handle_id="hd-1", reason="Primary email",
            fallback_handle_ids=("hd-2",), created_at=NOW,
        )
        assert d.selected_handle_id == "hd-1"
        assert len(d.fallback_handle_ids) == 1

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError):
            IdentityRoutingDecision(
                decision_id="rd-bad", target_identity_id="id-1",
                selected_handle_id="hd-1", reason="",
                created_at=NOW,
            )

    def test_frozen(self):
        d = IdentityRoutingDecision(
            decision_id="rd-2", target_identity_id="id-1",
            selected_handle_id="hd-1", reason="Best",
            created_at=NOW,
        )
        with pytest.raises(AttributeError):
            d.selected_handle_id = "new"
