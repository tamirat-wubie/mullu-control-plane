"""Multi-Agent Handoff Tests."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.handoff import (  # noqa: E402
    AgentSpec,
    HandoffRouter,
    SpecialistDelegation,
    SpecialistWorkerSpec,
)


class TestAgentRegistration:
    def test_register_agent(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(
            agent_id="fin", name="Financial Agent",
            description="Handles financial queries",
            handles=("balance_check", "spending_insights"),
        ))
        assert router.agent_count == 1

    def test_set_general_agent(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(agent_id="general", name="General", description="", handles=()))
        router.set_general_agent("general")
        summary = router.summary()
        assert summary["general_agent"] == "general"


class TestRouting:
    def test_route_to_specialized_agent(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(
            agent_id="fin", name="Financial", description="",
            handles=("balance",),
            handler=lambda msg, tid, iid: {"response": "Balance: $1000"},
        ))
        result = router.route("check balance", intent="balance", tenant_id="t1", identity_id="u1")
        assert result["agent"] == "fin"
        assert "1000" in result["response"]

    def test_route_to_general_fallback(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(
            agent_id="general", name="General", description="",
            handles=(),
            handler=lambda msg, tid, iid: {"response": "I can help with that"},
        ))
        router.set_general_agent("general")
        result = router.route("hello", intent="unknown", tenant_id="t1", identity_id="u1")
        assert result["agent"] == "general"

    def test_no_agent_available(self):
        router = HandoffRouter()
        result = router.route("test", intent="missing")
        assert "No agent" in result["response"]

    def test_all_results_governed(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(
            agent_id="a", name="A", description="",
            handles=("x",),
            handler=lambda m, t, i: {"response": "ok"},
        ))
        result = router.route("test", intent="x")
        assert result["governed"] is True


class TestHandoff:
    def test_handoff_between_agents(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(
            agent_id="fin", name="Financial", description="",
            handles=("balance",),
            handler=lambda m, t, i: {"response": "Balance result"},
        ))
        router.register_agent(AgentSpec(
            agent_id="general", name="General", description="",
            handles=(),
            handler=lambda m, t, i: {"response": "General result"},
        ))
        router.set_general_agent("general")
        router.handoff(
            "general", "fin",
            message="check my balance", reason="financial intent detected",
            tenant_id="t1", identity_id="u1",
        )
        assert router.handoff_count == 1

    def test_handoff_loop_blocked(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(agent_id="a", name="A", description="", handles=("x",)))
        router.register_agent(AgentSpec(agent_id="b", name="B", description="", handles=("y",)))
        router.set_general_agent("a")
        # A → B
        router.handoff("a", "b", message="test", reason="test")
        # B → A (loop!)
        router.handoff("a", "b", message="test", reason="loop test")
        # Should detect the loop
        assert router.handoff_count >= 1


class TestSpecialistDelegation:
    def test_delegation_issues_bounded_worker_lease(self):
        router = HandoffRouter(clock=lambda: "2026-05-01T12:00:00+00:00")
        router.register_specialist_worker(SpecialistWorkerSpec(
            worker_id="browser-1",
            role="browser_agent",
            allowed_capabilities=("browser.extract_text",),
            max_budget_cents=250,
            max_timeout_seconds=60,
        ))
        receipt = router.delegate_to_specialist(
            delegator_id="planner-1",
            worker_id="browser-1",
            goal_id="goal-1",
            capability_id="browser.extract_text",
            tenant_id="tenant-1",
            identity_id="user-1",
            budget_cents=100,
            timeout_seconds=30,
            payload={"url": "https://docs.mullusi.com"},
        )
        assert receipt.status == "accepted"
        assert receipt.lease_id.startswith("lease-")
        assert receipt.lease_expires_at == "2026-05-01T12:00:30+00:00"

    def test_delegation_rejects_capability_outside_worker_boundary(self):
        router = HandoffRouter(clock=lambda: "2026-05-01T12:00:00+00:00")
        router.register_specialist_worker(SpecialistWorkerSpec(
            worker_id="doc-1",
            role="document_agent",
            allowed_capabilities=("document.pdf.extract_text",),
            max_budget_cents=300,
            max_timeout_seconds=120,
        ))
        receipt = router.delegate_to_specialist(
            delegator_id="planner-1",
            worker_id="doc-1",
            goal_id="goal-1",
            capability_id="document.pdf.generate",
            tenant_id="tenant-1",
            identity_id="user-1",
            budget_cents=100,
            timeout_seconds=30,
        )
        assert receipt.status == "rejected"
        assert receipt.reason == "worker lacks required capability"
        assert receipt.lease_id == "none"

    def test_delegation_rejects_budget_and_timeout_overruns(self):
        router = HandoffRouter(clock=lambda: "2026-05-01T12:00:00+00:00")
        router.register_specialist_worker(SpecialistWorkerSpec(
            worker_id="code-1",
            role="code_agent",
            allowed_capabilities=("computer.test.run",),
            max_budget_cents=200,
            max_timeout_seconds=20,
        ))
        budget_receipt = router.delegate_to_specialist(
            delegator_id="planner-1",
            worker_id="code-1",
            goal_id="goal-1",
            capability_id="computer.test.run",
            tenant_id="tenant-1",
            identity_id="user-1",
            budget_cents=201,
            timeout_seconds=20,
        )
        timeout_receipt = router.delegate_to_specialist(
            delegator_id="planner-1",
            worker_id="code-1",
            goal_id="goal-2",
            capability_id="computer.test.run",
            tenant_id="tenant-1",
            identity_id="user-1",
            budget_cents=200,
            timeout_seconds=21,
        )
        assert budget_receipt.status == "rejected"
        assert budget_receipt.reason == "budget outside worker boundary"
        assert timeout_receipt.reason == "timeout outside worker boundary"

    def test_delegation_handler_completion_releases_lease(self):
        observed: list[SpecialistDelegation] = []

        def handle(delegation: SpecialistDelegation):
            observed.append(delegation)
            return {"artifact_id": "analysis-1", "status": "done"}

        router = HandoffRouter(clock=lambda: "2026-05-01T12:00:00+00:00")
        router.register_specialist_worker(SpecialistWorkerSpec(
            worker_id="research-1",
            role="research_agent",
            allowed_capabilities=("research.summarize",),
            max_budget_cents=500,
            max_timeout_seconds=45,
            handler=handle,
        ))
        receipt = router.delegate_to_specialist(
            delegator_id="planner-1",
            worker_id="research-1",
            goal_id="goal-1",
            capability_id="research.summarize",
            tenant_id="tenant-1",
            identity_id="user-1",
            budget_cents=150,
            timeout_seconds=20,
        )
        second = router.delegate_to_specialist(
            delegator_id="planner-1",
            worker_id="research-1",
            goal_id="goal-2",
            capability_id="research.summarize",
            tenant_id="tenant-1",
            identity_id="user-1",
            budget_cents=150,
            timeout_seconds=20,
        )
        assert receipt.status == "completed"
        assert receipt.output == {"artifact_id": "analysis-1", "status": "done"}
        assert second.status == "completed"
        assert observed[0].tenant_id == "tenant-1"

    def test_active_lease_capacity_and_kill_receipt(self):
        router = HandoffRouter(clock=lambda: "2026-05-01T12:00:00+00:00")
        router.register_specialist_worker(SpecialistWorkerSpec(
            worker_id="review-1",
            role="review_agent",
            allowed_capabilities=("agent.review",),
            max_budget_cents=100,
            max_timeout_seconds=60,
            max_active_leases=1,
        ))
        first = router.delegate_to_specialist(
            delegator_id="planner-1",
            worker_id="review-1",
            goal_id="goal-1",
            capability_id="agent.review",
            tenant_id="tenant-1",
            identity_id="user-1",
            budget_cents=50,
            timeout_seconds=30,
        )
        blocked = router.delegate_to_specialist(
            delegator_id="planner-1",
            worker_id="review-1",
            goal_id="goal-2",
            capability_id="agent.review",
            tenant_id="tenant-1",
            identity_id="user-1",
            budget_cents=50,
            timeout_seconds=30,
        )
        killed = router.kill_specialist_lease(first.lease_id, reason="operator stop")
        assert blocked.status == "rejected"
        assert blocked.reason == "worker lease capacity reached"
        assert killed.status == "cancelled"
        assert killed.reason == "operator stop"

    def test_unsupported_specialist_role_is_rejected_at_registration(self):
        router = HandoffRouter()
        try:
            router.register_specialist_worker(SpecialistWorkerSpec(
                worker_id="swarm-1",
                role="swarm_agent",
                allowed_capabilities=("agent.delegate",),
                max_budget_cents=100,
                max_timeout_seconds=30,
            ))
        except ValueError as exc:
            assert str(exc) == "unsupported specialist role"
        else:
            raise AssertionError("unsupported specialist role was accepted")


class TestSummary:
    def test_summary(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(agent_id="a", name="A", description="", handles=("x", "y")))
        summary = router.summary()
        assert "a" in summary["agents"]
        assert summary["intent_map"]["x"] == "a"
