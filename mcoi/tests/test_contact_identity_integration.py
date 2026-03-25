"""Integration tests for ContactIdentityIntegration bridge."""

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
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
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
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_valid(self):
        _, _, _, integ = _build()
        assert integ is not None

    def test_bad_identity_engine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="identity_engine"):
            ContactIdentityIntegration(
                identity_engine="bad",
                event_spine=EventSpineEngine(),
                memory_engine=MemoryMeshEngine(),
            )

    def test_bad_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            ContactIdentityIntegration(
                identity_engine=ContactIdentityEngine(),
                event_spine="bad",
                memory_engine=MemoryMeshEngine(),
            )

    def test_bad_memory_engine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            ContactIdentityIntegration(
                identity_engine=ContactIdentityEngine(),
                event_spine=EventSpineEngine(),
                memory_engine="bad",
            )


# ---------------------------------------------------------------------------
# register_from_org_directory
# ---------------------------------------------------------------------------


class TestRegisterFromOrgDirectory:
    def test_creates_identity_and_handle(self):
        ie, es, me, integ = _build()
        result = integ.register_from_org_directory(
            "person-1", "Alice", "alice@example.com", "org-1",
        )
        assert result["identity"].identity_type == IdentityType.PERSON
        assert len(result["handles"]) == 1
        assert result["handles"][0].channel_type == ChannelType.EMAIL
        assert ie.identity_count == 1
        assert ie.handle_count == 1

    def test_tags_include_org_directory(self):
        _, _, _, integ = _build()
        result = integ.register_from_org_directory("p-1", "A", "a@x.com")
        assert "org_directory" in result["identity"].tags

    def test_custom_tags(self):
        _, _, _, integ = _build()
        result = integ.register_from_org_directory(
            "p-1", "A", "a@x.com", tags=("vip",),
        )
        assert "vip" in result["identity"].tags


# ---------------------------------------------------------------------------
# register_from_team_runtime
# ---------------------------------------------------------------------------


class TestRegisterFromTeamRuntime:
    def test_creates_team_identity(self):
        ie, es, me, integ = _build()
        result = integ.register_from_team_runtime("team-1", "Engineering")
        assert result["identity"].identity_type == IdentityType.TEAM
        assert ie.identity_count == 1

    def test_links_existing_members(self):
        ie, es, me, integ = _build()
        # Register member first
        integ.register_from_org_directory("p-1", "Alice", "a@x.com")
        member_id = ie.list_identities(identity_type=IdentityType.PERSON)[0].identity_id

        result = integ.register_from_team_runtime(
            "team-1", "Engineering", member_ids=(member_id,),
        )
        assert len(result["links"]) == 1

    def test_skips_missing_members(self):
        ie, es, me, integ = _build()
        result = integ.register_from_team_runtime(
            "team-1", "Engineering", member_ids=("nonexistent",),
        )
        assert len(result["links"]) == 0


# ---------------------------------------------------------------------------
# register_from_operator_identity
# ---------------------------------------------------------------------------


class TestRegisterFromOperatorIdentity:
    def test_creates_operator(self):
        ie, es, me, integ = _build()
        result = integ.register_from_operator_identity("op-1", "Admin", "admin@x.com")
        assert result["identity"].identity_type == IdentityType.OPERATOR
        assert len(result["handles"]) == 1

    def test_with_chat(self):
        ie, es, me, integ = _build()
        result = integ.register_from_operator_identity(
            "op-1", "Admin", "admin@x.com", chat_address="@admin",
        )
        assert len(result["handles"]) == 2


# ---------------------------------------------------------------------------
# route_message_for_identity
# ---------------------------------------------------------------------------


class TestRouteMessageForIdentity:
    def test_routes_and_emits_event(self):
        ie, es, me, integ = _build()
        integ.register_from_org_directory("p-1", "Alice", "a@x.com")
        iid = ie.list_identities()[0].identity_id
        result = integ.route_message_for_identity(iid)
        assert result["decision"] is not None
        assert result["event"] is not None
        assert result["event"].payload["action"] == "message_routed"

    def test_missing_identity_returns_none(self):
        _, _, _, integ = _build()
        result = integ.route_message_for_identity("missing")
        assert result["decision"] is None
        assert result["event"] is None


# ---------------------------------------------------------------------------
# route_escalation_for_obligation
# ---------------------------------------------------------------------------


class TestRouteEscalationForObligation:
    def test_routes_and_emits_event(self):
        ie, es, me, integ = _build()
        integ.register_from_org_directory("p-1", "Alice", "a@x.com")
        iid = ie.list_identities()[0].identity_id
        ie.add_escalation_chain(EscalationChainRecord(
            chain_id="esc-1", name="Chain",
            mode=EscalationMode.PARALLEL,
            target_identity_ids=(iid,), created_at=NOW,
        ))
        result = integ.route_escalation_for_obligation("esc-1", "obl-1")
        assert len(result["decisions"]) == 1
        assert result["event"].event_type == EventType.OBLIGATION_ESCALATED


# ---------------------------------------------------------------------------
# route_notification_for_incident
# ---------------------------------------------------------------------------


class TestRouteNotificationForIncident:
    def test_routes_and_emits_event(self):
        ie, es, me, integ = _build()
        integ.register_from_org_directory("p-1", "Alice", "a@x.com")
        iid = ie.list_identities()[0].identity_id
        ie.add_escalation_chain(EscalationChainRecord(
            chain_id="esc-1", name="Notify",
            mode=EscalationMode.PARALLEL,
            target_identity_ids=(iid,), created_at=NOW,
        ))
        result = integ.route_notification_for_incident("esc-1", "inc-1")
        assert result["event"].payload["action"] == "incident_notification_routed"


# ---------------------------------------------------------------------------
# resolve_handles_from_communication
# ---------------------------------------------------------------------------


class TestResolveFromCommunication:
    def test_resolves(self):
        ie, es, me, integ = _build()
        integ.register_from_org_directory("p-1", "Alice", "alice@x.com")
        res = integ.resolve_handles_from_communication("alice@x.com")
        assert res is not None

    def test_not_found(self):
        _, _, _, integ = _build()
        assert integ.resolve_handles_from_communication("unknown@x.com") is None


# ---------------------------------------------------------------------------
# Memory mesh attachment
# ---------------------------------------------------------------------------


class TestMemoryMeshAttachment:
    def test_remember_routing_decision(self):
        ie, es, me, integ = _build()
        integ.register_from_org_directory("p-1", "Alice", "a@x.com")
        iid = ie.list_identities()[0].identity_id
        result = integ.route_message_for_identity(iid)
        mem = integ.remember_identity_decision(result["decision"])
        assert "routing" in mem.tags
        assert mem.content["target_identity_id"] == iid

    def test_attach_identity(self):
        ie, es, me, integ = _build()
        integ.register_from_org_directory("p-1", "Alice", "a@x.com")
        identity = ie.list_identities()[0]
        mem = integ.attach_identity_to_memory_mesh(identity)
        assert "registration" in mem.tags
        assert mem.content["display_name"] == "Alice"
