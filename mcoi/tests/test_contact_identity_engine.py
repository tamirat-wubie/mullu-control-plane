"""Engine-level tests for ContactIdentityEngine."""

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
from mcoi_runtime.core.contact_identity import ContactIdentityEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

NOW = "2026-03-20T12:00:00+00:00"


def _identity(iid="id-1", name="Alice", itype=IdentityType.PERSON, **kw):
    defaults = dict(
        identity_id=iid, identity_type=itype,
        display_name=name, created_at=NOW, updated_at=NOW,
    )
    defaults.update(kw)
    return IdentityRecord(**defaults)


def _handle(hid="hd-1", iid="id-1", ctype=ChannelType.EMAIL, addr="alice@example.com", **kw):
    defaults = dict(
        handle_id=hid, identity_id=iid,
        channel_type=ctype, address=addr, created_at=NOW,
    )
    defaults.update(kw)
    return ChannelHandle(**defaults)


# ---------------------------------------------------------------------------
# Identity CRUD
# ---------------------------------------------------------------------------


class TestIdentityCRUD:
    def test_add_and_get(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        assert engine.get_identity("id-1") is not None

    def test_duplicate_rejected(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate") as exc_info:
            engine.add_identity(_identity())
        assert "id-1" not in str(exc_info.value)

    def test_get_missing(self):
        engine = ContactIdentityEngine()
        assert engine.get_identity("nope") is None

    def test_list_all(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity("id-1", "Alice"))
        engine.add_identity(_identity("id-2", "Bob"))
        assert len(engine.list_identities()) == 2

    def test_list_by_type(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity("id-p", "Person", IdentityType.PERSON))
        engine.add_identity(_identity("id-t", "Team", IdentityType.TEAM))
        assert len(engine.list_identities(identity_type=IdentityType.PERSON)) == 1

    def test_list_by_org(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity("id-1", "A", organization_id="org-1"))
        engine.add_identity(_identity("id-2", "B", organization_id="org-2"))
        assert len(engine.list_identities(organization_id="org-1")) == 1

    def test_list_by_team(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity("id-1", "A", team_id="t-1"))
        engine.add_identity(_identity("id-2", "B", team_id="t-2"))
        assert len(engine.list_identities(team_id="t-1")) == 1

    def test_identity_count(self):
        engine = ContactIdentityEngine()
        assert engine.identity_count == 0
        engine.add_identity(_identity())
        assert engine.identity_count == 1

    def test_bad_type_rejected(self):
        engine = ContactIdentityEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="IdentityRecord"):
            engine.add_identity("not a record")


# ---------------------------------------------------------------------------
# Channel handles
# ---------------------------------------------------------------------------


class TestChannelHandles:
    def test_add_and_get(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle())
        assert engine.get_handle("hd-1") is not None

    def test_duplicate_rejected(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle())
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate") as exc_info:
            engine.add_channel_handle(_handle())
        assert "hd-1" not in str(exc_info.value)

    def test_missing_identity_rejected(self):
        engine = ContactIdentityEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="identity not found") as exc_info:
            engine.add_channel_handle(_handle(iid="missing"))
        assert "missing" not in str(exc_info.value)

    def test_list_for_identity(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle("hd-1", addr="a@x.com"))
        engine.add_channel_handle(_handle("hd-2", addr="b@x.com"))
        assert len(engine.list_handles_for_identity("id-1")) == 2

    def test_list_filtered_by_channel_type(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle("hd-e", ctype=ChannelType.EMAIL, addr="a@x.com"))
        engine.add_channel_handle(_handle("hd-s", ctype=ChannelType.SMS, addr="+1234"))
        assert len(engine.list_handles_for_identity("id-1", channel_type=ChannelType.EMAIL)) == 1

    def test_exclude_disabled(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle("hd-a", addr="a@x.com", preference_level=ChannelPreferenceLevel.PRIMARY))
        engine.add_channel_handle(_handle("hd-d", addr="d@x.com", preference_level=ChannelPreferenceLevel.DISABLED))
        handles = engine.list_handles_for_identity("id-1", exclude_disabled=True)
        assert len(handles) == 1
        assert handles[0].handle_id == "hd-a"

    def test_sorted_by_preference(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle("hd-sec", addr="sec@x.com", preference_level=ChannelPreferenceLevel.SECONDARY))
        engine.add_channel_handle(_handle("hd-pri", addr="pri@x.com", preference_level=ChannelPreferenceLevel.PRIMARY))
        handles = engine.list_handles_for_identity("id-1")
        assert handles[0].preference_level == ChannelPreferenceLevel.PRIMARY

    def test_handle_count(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        assert engine.handle_count == 0
        engine.add_channel_handle(_handle())
        assert engine.handle_count == 1


# ---------------------------------------------------------------------------
# Identity linking
# ---------------------------------------------------------------------------


class TestIdentityLinking:
    def test_link(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity("id-1", "Alice"))
        engine.add_identity(_identity("id-2", "Bob"))
        link = IdentityLink(
            link_id="lk-1", from_identity_id="id-1",
            to_identity_id="id-2", relation="reports_to", created_at=NOW,
        )
        engine.link_identities(link)
        assert engine.link_count == 1

    def test_duplicate_link_rejected(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity("id-1", "Alice"))
        engine.add_identity(_identity("id-2", "Bob"))
        link = IdentityLink(
            link_id="lk-1", from_identity_id="id-1",
            to_identity_id="id-2", relation="knows", created_at=NOW,
        )
        engine.link_identities(link)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate") as exc_info:
            engine.link_identities(link)
        assert "lk-1" not in str(exc_info.value)

    def test_missing_from_rejected(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity("id-2", "Bob"))
        link = IdentityLink(
            link_id="lk-bad", from_identity_id="missing",
            to_identity_id="id-2", relation="knows", created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="from_identity") as exc_info:
            engine.link_identities(link)
        assert "missing" not in str(exc_info.value)

    def test_missing_to_rejected(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity("id-1", "Alice"))
        link = IdentityLink(
            link_id="lk-bad", from_identity_id="id-1",
            to_identity_id="missing", relation="knows", created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="to_identity") as exc_info:
            engine.link_identities(link)
        assert "missing" not in str(exc_info.value)

    def test_get_links_for(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity("id-1", "A"))
        engine.add_identity(_identity("id-2", "B"))
        engine.add_identity(_identity("id-3", "C"))
        engine.link_identities(IdentityLink(
            link_id="lk-1", from_identity_id="id-1",
            to_identity_id="id-2", relation="knows", created_at=NOW,
        ))
        engine.link_identities(IdentityLink(
            link_id="lk-2", from_identity_id="id-3",
            to_identity_id="id-1", relation="manages", created_at=NOW,
        ))
        links = engine.get_links_for("id-1")
        assert len(links) == 2


# ---------------------------------------------------------------------------
# Contact preferences
# ---------------------------------------------------------------------------


class TestContactPreferences:
    def test_set_and_get(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        pref = ContactPreferenceRecord(
            preference_id="pref-1", identity_id="id-1",
            preferred_channels=(ChannelType.SMS,), created_at=NOW,
        )
        engine.set_contact_preference(pref)
        assert engine.get_contact_preference("id-1") is not None

    def test_missing_identity_rejected(self):
        engine = ContactIdentityEngine()
        pref = ContactPreferenceRecord(
            preference_id="pref-1", identity_id="missing",
            created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="identity not found") as exc_info:
            engine.set_contact_preference(pref)
        assert "missing" not in str(exc_info.value)

    def test_replaces_existing(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        pref1 = ContactPreferenceRecord(
            preference_id="pref-1", identity_id="id-1",
            preferred_channels=(ChannelType.SMS,), created_at=NOW,
        )
        engine.set_contact_preference(pref1)
        pref2 = ContactPreferenceRecord(
            preference_id="pref-2", identity_id="id-1",
            preferred_channels=(ChannelType.EMAIL,), created_at=NOW,
        )
        engine.set_contact_preference(pref2)
        assert engine.get_contact_preference("id-1").preference_id == "pref-2"


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


class TestAvailability:
    def test_set_and_get(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        w = AvailabilityWindow(
            window_id="aw-1", identity_id="id-1",
            state=AvailabilityState.AVAILABLE, created_at=NOW,
        )
        engine.set_availability(w)
        assert engine.get_availability("id-1").state == AvailabilityState.AVAILABLE

    def test_missing_identity_rejected(self):
        engine = ContactIdentityEngine()
        w = AvailabilityWindow(
            window_id="aw-1", identity_id="missing",
            state=AvailabilityState.AVAILABLE, created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="identity not found") as exc_info:
            engine.set_availability(w)
        assert "missing" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# Escalation chains
# ---------------------------------------------------------------------------


class TestEscalationChains:
    def test_add_and_get(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity("id-1", "A"))
        engine.add_identity(_identity("id-2", "B"))
        chain = EscalationChainRecord(
            chain_id="esc-1", name="On-call",
            mode=EscalationMode.SEQUENTIAL,
            target_identity_ids=("id-1", "id-2"),
            created_at=NOW,
        )
        engine.add_escalation_chain(chain)
        assert engine.get_escalation_chain("esc-1") is not None

    def test_duplicate_rejected(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        chain = EscalationChainRecord(
            chain_id="esc-1", name="Chain",
            mode=EscalationMode.SEQUENTIAL,
            target_identity_ids=("id-1",), created_at=NOW,
        )
        engine.add_escalation_chain(chain)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate") as exc_info:
            engine.add_escalation_chain(chain)
        assert "esc-1" not in str(exc_info.value)

    def test_missing_target_rejected(self):
        engine = ContactIdentityEngine()
        chain = EscalationChainRecord(
            chain_id="esc-bad", name="Bad",
            mode=EscalationMode.SEQUENTIAL,
            target_identity_ids=("missing",), created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="target not found") as exc_info:
            engine.add_escalation_chain(chain)
        assert "missing" not in str(exc_info.value)

    def test_list_chains(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_escalation_chain(EscalationChainRecord(
            chain_id="esc-1", name="C1", mode=EscalationMode.SEQUENTIAL,
            target_identity_ids=("id-1",), created_at=NOW,
        ))
        engine.add_escalation_chain(EscalationChainRecord(
            chain_id="esc-2", name="C2", mode=EscalationMode.PARALLEL,
            target_identity_ids=("id-1",), created_at=NOW,
        ))
        assert len(engine.list_escalation_chains()) == 2

    def test_chain_count(self):
        engine = ContactIdentityEngine()
        assert engine.chain_count == 0


# ---------------------------------------------------------------------------
# Identity resolution
# ---------------------------------------------------------------------------


class TestIdentityResolution:
    def test_resolve_by_address(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle(addr="alice@example.com", verified=True))
        res = engine.resolve_identity("alice@example.com", "email")
        assert res is not None
        assert res.resolved_identity_id == "id-1"
        assert res.confidence == 1.0

    def test_resolve_unverified(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle(addr="alice@x.com", verified=False))
        res = engine.resolve_identity("alice@x.com", "email")
        assert res is not None
        assert res.confidence == 0.7

    def test_resolve_not_found(self):
        engine = ContactIdentityEngine()
        assert engine.resolve_identity("unknown@x.com", "email") is None

    def test_resolution_stored(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle(addr="a@x.com"))
        res = engine.resolve_identity("a@x.com", "email")
        assert engine.resolution_count == 1
        assert engine.get_resolution(res.resolution_id) is not None


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


class TestRouting:
    def test_route_contact_basic(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle(preference_level=ChannelPreferenceLevel.PRIMARY))
        decision = engine.route_contact("id-1")
        assert decision is not None
        assert decision.selected_handle_id == "hd-1"

    def test_route_missing_identity(self):
        engine = ContactIdentityEngine()
        assert engine.route_contact("missing") is None

    def test_route_no_handles(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        assert engine.route_contact("id-1") is None

    def test_route_skips_blocked(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle("hd-e", addr="a@x.com", ctype=ChannelType.EMAIL,
                                          preference_level=ChannelPreferenceLevel.PRIMARY))
        engine.add_channel_handle(_handle("hd-s", addr="+123", ctype=ChannelType.SMS,
                                          preference_level=ChannelPreferenceLevel.SECONDARY))
        engine.set_contact_preference(ContactPreferenceRecord(
            preference_id="pref-1", identity_id="id-1",
            blocked_channels=(ChannelType.EMAIL,), created_at=NOW,
        ))
        decision = engine.route_contact("id-1")
        assert decision is not None
        assert decision.selected_handle_id == "hd-s"

    def test_route_unavailable_returns_none(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle(preference_level=ChannelPreferenceLevel.PRIMARY))
        engine.set_availability(AvailabilityWindow(
            window_id="aw-1", identity_id="id-1",
            state=AvailabilityState.UNAVAILABLE, created_at=NOW,
        ))
        assert engine.route_contact("id-1") is None

    def test_route_emergency_ignores_unavailable(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle(preference_level=ChannelPreferenceLevel.PRIMARY))
        engine.set_availability(AvailabilityWindow(
            window_id="aw-1", identity_id="id-1",
            state=AvailabilityState.UNAVAILABLE, created_at=NOW,
        ))
        decision = engine.route_contact("id-1", urgency="emergency")
        assert decision is not None
        assert decision.reason == "contact route selected"
        assert "emergency" not in decision.reason

    def test_route_with_fallbacks(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle("hd-1", addr="a@x.com",
                                          preference_level=ChannelPreferenceLevel.PRIMARY))
        engine.add_channel_handle(_handle("hd-2", addr="+123", ctype=ChannelType.SMS,
                                          preference_level=ChannelPreferenceLevel.SECONDARY))
        decision = engine.route_contact("id-1")
        assert len(decision.fallback_handle_ids) == 1
        assert decision.fallback_handle_ids[0] == "hd-2"

    def test_routing_history_tracked(self):
        engine = ContactIdentityEngine()
        engine.add_identity(_identity())
        engine.add_channel_handle(_handle(preference_level=ChannelPreferenceLevel.PRIMARY))
        engine.route_contact("id-1")
        assert engine.routing_decision_count == 1


# ---------------------------------------------------------------------------
# Escalation routing
# ---------------------------------------------------------------------------


class TestEscalationRouting:
    def _setup_chain(self, engine, mode=EscalationMode.SEQUENTIAL):
        engine.add_identity(_identity("id-1", "Alice"))
        engine.add_identity(_identity("id-2", "Bob"))
        engine.add_identity(_identity("id-3", "Carol"))
        engine.add_channel_handle(_handle("hd-1", "id-1", addr="a@x.com",
                                          preference_level=ChannelPreferenceLevel.PRIMARY))
        engine.add_channel_handle(_handle("hd-2", "id-2", addr="b@x.com",
                                          preference_level=ChannelPreferenceLevel.PRIMARY))
        engine.add_channel_handle(_handle("hd-3", "id-3", addr="c@x.com",
                                          preference_level=ChannelPreferenceLevel.PRIMARY))
        chain = EscalationChainRecord(
            chain_id="esc-1", name="On-call", mode=mode,
            target_identity_ids=("id-1", "id-2", "id-3"),
            created_at=NOW,
        )
        engine.add_escalation_chain(chain)

    def test_sequential_routes_to_first(self):
        engine = ContactIdentityEngine()
        self._setup_chain(engine, EscalationMode.SEQUENTIAL)
        decisions = engine.route_escalation("esc-1")
        assert len(decisions) == 1
        assert decisions[0].target_identity_id == "id-1"
        assert decisions[0].reason == "escalation route selected"
        assert "On-call" not in decisions[0].reason
        assert EscalationMode.SEQUENTIAL.value not in decisions[0].reason

    def test_sequential_skips_unavailable(self):
        engine = ContactIdentityEngine()
        self._setup_chain(engine, EscalationMode.SEQUENTIAL)
        engine.set_availability(AvailabilityWindow(
            window_id="aw-1", identity_id="id-1",
            state=AvailabilityState.UNAVAILABLE, created_at=NOW,
        ))
        decisions = engine.route_escalation("esc-1")
        assert len(decisions) == 1
        assert decisions[0].target_identity_id == "id-2"

    def test_parallel_routes_to_all(self):
        engine = ContactIdentityEngine()
        self._setup_chain(engine, EscalationMode.PARALLEL)
        decisions = engine.route_escalation("esc-1")
        assert len(decisions) == 3

    def test_emergency_broadcast_routes_to_all(self):
        engine = ContactIdentityEngine()
        self._setup_chain(engine, EscalationMode.EMERGENCY_BROADCAST)
        decisions = engine.route_escalation("esc-1")
        assert len(decisions) == 3

    def test_missing_chain(self):
        engine = ContactIdentityEngine()
        assert engine.route_escalation("missing") == ()


# ---------------------------------------------------------------------------
# State hash
# ---------------------------------------------------------------------------


class TestStateHash:
    def test_deterministic(self):
        e1 = ContactIdentityEngine()
        e2 = ContactIdentityEngine()
        e1.add_identity(_identity())
        e2.add_identity(_identity())
        assert e1.state_hash() == e2.state_hash()

    def test_changes_on_add(self):
        engine = ContactIdentityEngine()
        h1 = engine.state_hash()
        engine.add_identity(_identity())
        h2 = engine.state_hash()
        assert h1 != h2

    def test_length(self):
        engine = ContactIdentityEngine()
        assert len(engine.state_hash()) == 64
