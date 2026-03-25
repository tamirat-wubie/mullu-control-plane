"""Golden scenario tests for contact/identity graph subsystem.

7 scenarios covering end-to-end identity management flows.
"""

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
    IdentityRecord,
    IdentityType,
)
from mcoi_runtime.contracts.event import EventType
from mcoi_runtime.core.contact_identity import ContactIdentityEngine
from mcoi_runtime.core.contact_identity_integration import ContactIdentityIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine

NOW = "2026-03-20T12:00:00+00:00"


def _build():
    ie = ContactIdentityEngine()
    es = EventSpineEngine()
    me = MemoryMeshEngine()
    integ = ContactIdentityIntegration(
        identity_engine=ie, event_spine=es, memory_engine=me,
    )
    return ie, es, me, integ


# ---------------------------------------------------------------------------
# Scenario 1: Same person resolved across email + SMS + chat handles
# ---------------------------------------------------------------------------


class TestGolden1CrossChannelResolution:
    def test_same_person_multiple_channels(self):
        ie, es, me, integ = _build()

        # Register person with email
        result = integ.register_from_org_directory("p-alice", "Alice", "alice@example.com")
        iid = result["identity"].identity_id

        # Add SMS and chat handles
        ie.add_channel_handle(ChannelHandle(
            handle_id="hd-sms", identity_id=iid,
            channel_type=ChannelType.SMS, address="+15551234567",
            verified=True, preference_level=ChannelPreferenceLevel.SECONDARY,
            created_at=NOW,
        ))
        ie.add_channel_handle(ChannelHandle(
            handle_id="hd-chat", identity_id=iid,
            channel_type=ChannelType.CHAT, address="@alice",
            verified=True, preference_level=ChannelPreferenceLevel.SECONDARY,
            created_at=NOW,
        ))

        # Resolve from each channel
        res_email = ie.resolve_identity("alice@example.com", "email")
        res_sms = ie.resolve_identity("+15551234567", "sms")
        res_chat = ie.resolve_identity("@alice", "chat")

        # All resolve to same identity
        assert res_email.resolved_identity_id == iid
        assert res_sms.resolved_identity_id == iid
        assert res_chat.resolved_identity_id == iid

        # All handles listed for identity
        handles = ie.list_handles_for_identity(iid)
        assert len(handles) == 3
        channel_types = {h.channel_type for h in handles}
        assert channel_types == {ChannelType.EMAIL, ChannelType.SMS, ChannelType.CHAT}


# ---------------------------------------------------------------------------
# Scenario 2: Escalation chain routes to next identity when first unavailable
# ---------------------------------------------------------------------------


class TestGolden2EscalationSkipsUnavailable:
    def test_escalation_skips_unavailable(self):
        ie, es, me, integ = _build()

        # Register three people
        r1 = integ.register_from_org_directory("p-1", "Alice", "a@x.com")
        r2 = integ.register_from_org_directory("p-2", "Bob", "b@x.com")
        r3 = integ.register_from_org_directory("p-3", "Carol", "c@x.com")
        id1, id2, id3 = r1["identity"].identity_id, r2["identity"].identity_id, r3["identity"].identity_id

        # Mark Alice as unavailable
        ie.set_availability(AvailabilityWindow(
            window_id="aw-1", identity_id=id1,
            state=AvailabilityState.UNAVAILABLE, created_at=NOW,
        ))

        # Create sequential escalation chain
        ie.add_escalation_chain(EscalationChainRecord(
            chain_id="esc-oncall", name="On-call rotation",
            mode=EscalationMode.SEQUENTIAL,
            target_identity_ids=(id1, id2, id3),
            created_at=NOW,
        ))

        # Escalate — should skip Alice, route to Bob
        result = integ.route_escalation_for_obligation("esc-oncall", "obl-urgent")
        decisions = result["decisions"]
        assert len(decisions) == 1
        assert decisions[0].target_identity_id == id2

        # Event emitted
        assert result["event"].event_type == EventType.OBLIGATION_ESCALATED


# ---------------------------------------------------------------------------
# Scenario 3: Contact preference picks SMS over email for urgent obligation
# ---------------------------------------------------------------------------


class TestGolden3PreferencePicksSMS:
    def test_sms_preferred_for_urgent(self):
        ie, es, me, integ = _build()

        # Register with email (PRIMARY) and SMS (SECONDARY)
        result = integ.register_from_org_directory("p-1", "Alice", "alice@x.com")
        iid = result["identity"].identity_id
        ie.add_channel_handle(ChannelHandle(
            handle_id="hd-sms", identity_id=iid,
            channel_type=ChannelType.SMS, address="+1555",
            verified=True, preference_level=ChannelPreferenceLevel.PRIMARY,
            created_at=NOW,
        ))

        # Block email for this identity
        ie.set_contact_preference(ContactPreferenceRecord(
            preference_id="pref-1", identity_id=iid,
            preferred_channels=(ChannelType.SMS,),
            blocked_channels=(ChannelType.EMAIL,),
            created_at=NOW,
        ))

        # Route — should pick SMS since email is blocked
        route_result = integ.route_message_for_identity(iid, urgency="urgent")
        decision = route_result["decision"]
        assert decision is not None
        handle = ie.get_handle(decision.selected_handle_id)
        assert handle.channel_type == ChannelType.SMS


# ---------------------------------------------------------------------------
# Scenario 4: Identity routing decision remembered into memory mesh
# ---------------------------------------------------------------------------


class TestGolden4RoutingRemembered:
    def test_routing_decision_in_memory(self):
        ie, es, me, integ = _build()

        result = integ.register_from_org_directory("p-1", "Alice", "a@x.com")
        iid = result["identity"].identity_id

        # Route and remember
        route_result = integ.route_message_for_identity(iid)
        mem = integ.remember_identity_decision(route_result["decision"])

        # Memory should contain routing details
        assert mem.content["target_identity_id"] == iid
        assert mem.content["selected_handle_id"] == route_result["decision"].selected_handle_id
        assert "routing" in mem.tags
        assert "identity" in mem.tags

        # Also attach identity to memory mesh
        identity_mem = integ.attach_identity_to_memory_mesh(result["identity"])
        assert identity_mem.content["display_name"] == "Alice"
        assert "registration" in identity_mem.tags

        # Memory engine has both records
        assert me.memory_count >= 2


# ---------------------------------------------------------------------------
# Scenario 5: Org/team registration produces consistent identity graph
# ---------------------------------------------------------------------------


class TestGolden5OrgTeamRegistration:
    def test_consistent_graph(self):
        ie, es, me, integ = _build()

        # Register org members
        r_alice = integ.register_from_org_directory("p-alice", "Alice", "alice@acme.com", "acme")
        r_bob = integ.register_from_org_directory("p-bob", "Bob", "bob@acme.com", "acme")
        r_carol = integ.register_from_org_directory("p-carol", "Carol", "carol@acme.com", "acme")

        alice_id = r_alice["identity"].identity_id
        bob_id = r_bob["identity"].identity_id
        carol_id = r_carol["identity"].identity_id

        # Register team with members
        team_result = integ.register_from_team_runtime(
            "team-eng", "Engineering",
            member_ids=(alice_id, bob_id, carol_id),
            organization_id="acme",
        )

        # Verify team identity
        assert team_result["identity"].identity_type == IdentityType.TEAM
        assert team_result["identity"].organization_id == "acme"

        # Verify links
        assert len(team_result["links"]) == 3
        for link in team_result["links"]:
            assert link.relation == "member_of"
            assert link.to_identity_id == team_result["identity"].identity_id

        # Count: 3 persons + 1 team = 4 identities
        assert ie.identity_count == 4
        assert ie.link_count == 3

        # All org members findable
        acme_ids = ie.list_identities(organization_id="acme")
        assert len(acme_ids) == 4  # 3 persons + 1 team


# ---------------------------------------------------------------------------
# Scenario 6: Failed channel falls back to next preferred handle
# ---------------------------------------------------------------------------


class TestGolden6ChannelFallback:
    def test_fallback_handles_available(self):
        ie, es, me, integ = _build()

        result = integ.register_from_org_directory("p-1", "Alice", "alice@x.com")
        iid = result["identity"].identity_id

        # Add secondary SMS and emergency voice
        ie.add_channel_handle(ChannelHandle(
            handle_id="hd-sms", identity_id=iid,
            channel_type=ChannelType.SMS, address="+1555",
            verified=True, preference_level=ChannelPreferenceLevel.SECONDARY,
            created_at=NOW,
        ))
        ie.add_channel_handle(ChannelHandle(
            handle_id="hd-voice", identity_id=iid,
            channel_type=ChannelType.VOICE, address="+1555-voice",
            verified=True, preference_level=ChannelPreferenceLevel.EMERGENCY_ONLY,
            created_at=NOW,
        ))

        # Route normally — should pick email (primary), with SMS as fallback
        decision = ie.route_contact(iid)
        assert decision is not None

        # Primary handle selected
        primary = ie.get_handle(decision.selected_handle_id)
        assert primary.preference_level == ChannelPreferenceLevel.PRIMARY

        # Fallbacks available (SMS but not emergency-only for normal urgency)
        assert len(decision.fallback_handle_ids) >= 1
        fallback_handle = ie.get_handle(decision.fallback_handle_ids[0])
        assert fallback_handle.channel_type == ChannelType.SMS


# ---------------------------------------------------------------------------
# Scenario 7: Emergency broadcast escalation fans out deterministically
# ---------------------------------------------------------------------------


class TestGolden7EmergencyBroadcast:
    def test_emergency_broadcast_fans_out(self):
        ie, es, me, integ = _build()

        # Register 5 people
        ids = []
        for i in range(5):
            r = integ.register_from_org_directory(f"p-{i}", f"Person {i}", f"p{i}@x.com")
            ids.append(r["identity"].identity_id)

        # Create emergency broadcast chain
        ie.add_escalation_chain(EscalationChainRecord(
            chain_id="esc-emergency", name="Emergency Broadcast",
            mode=EscalationMode.EMERGENCY_BROADCAST,
            target_identity_ids=tuple(ids),
            created_at=NOW,
        ))

        # Route — all 5 should receive
        result = integ.route_escalation_for_obligation("esc-emergency", "obl-critical")
        decisions = result["decisions"]
        assert len(decisions) == 5

        # Each decision targets a different identity
        targeted = {d.target_identity_id for d in decisions}
        assert targeted == set(ids)

        # Event records the fan-out
        assert result["event"].payload["target_count"] == 5

        # Deterministic — run again with same engine state should be consistent
        # (can't re-run because routing history changes ts, but verify first run is complete)
        assert ie.routing_decision_count == 5

        # Run second broadcast (different chain to avoid routing dedup)
        ie.add_escalation_chain(EscalationChainRecord(
            chain_id="esc-emergency-2", name="Emergency Broadcast 2",
            mode=EscalationMode.EMERGENCY_BROADCAST,
            target_identity_ids=tuple(ids),
            created_at=NOW,
        ))
        result2 = integ.route_escalation_for_obligation("esc-emergency-2", "obl-critical-2")
        assert len(result2["decisions"]) == 5
        targeted2 = {d.target_identity_id for d in result2["decisions"]}
        assert targeted2 == set(ids)
