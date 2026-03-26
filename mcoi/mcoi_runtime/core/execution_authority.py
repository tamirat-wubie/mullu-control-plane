"""Phase 194 — Execution Authority / Bypass Prevention.

Purpose: Ensures all critical execution paths are routed through governed dispatch.
    Provides an authority context that must be present for any state-mutating operation.
Governance scope: universal execution authority enforcement.
Dependencies: governed_dispatcher.
Invariants: no production side-effect without authority context, fail-closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ExecutionAuthority:
    """Proof that an action was authorized through the governed dispatch pipeline.

    Must be present for any state-mutating operation in production.
    """

    authority_id: str
    actor_id: str
    intent_hash: str
    gates_passed: tuple[str, ...]
    issued_at: str

    def verify(self) -> bool:
        """Verify the authority token is structurally valid."""
        return bool(
            self.authority_id
            and self.actor_id
            and self.intent_hash
            and self.gates_passed
        )


class ExecutionAuthorityError(Exception):
    """Raised when an operation is attempted without valid execution authority."""


# ─── Entry Point Registry ───


@dataclass
class EntryPointRecord:
    """A single execution-capable surface and its governance routing status."""

    path: str  # module.class.method
    effect_type: str  # "execution", "mutation", "external", "delegation", "promotion"
    routing: str  # "governed", "legacy", "bypass", "internal_safe"
    governed_required: bool


class EntryPointRegistry:
    """Tracks all execution-capable surfaces and their governance routing status."""

    def __init__(self) -> None:
        self._entries: dict[str, EntryPointRecord] = {}

    def register(
        self,
        path: str,
        effect_type: str,
        routing: str,
        governed_required: bool = True,
    ) -> EntryPointRecord:
        record = EntryPointRecord(path, effect_type, routing, governed_required)
        self._entries[path] = record
        return record

    def get(self, path: str) -> EntryPointRecord | None:
        return self._entries.get(path)

    def ungoverned_production_paths(self) -> list[EntryPointRecord]:
        """Returns all production paths that bypass governed dispatch — these are violations."""
        return [
            e
            for e in self._entries.values()
            if e.governed_required and e.routing in ("legacy", "bypass")
        ]

    def coverage_score(self) -> float:
        """Fraction of required paths that are governed."""
        required = [e for e in self._entries.values() if e.governed_required]
        if not required:
            return 1.0
        governed = [e for e in required if e.routing == "governed"]
        return len(governed) / len(required)

    def coverage_matrix(self) -> dict[str, Any]:
        governed = sum(1 for e in self._entries.values() if e.routing == "governed")
        legacy = sum(1 for e in self._entries.values() if e.routing == "legacy")
        bypass = sum(1 for e in self._entries.values() if e.routing == "bypass")
        internal = sum(
            1 for e in self._entries.values() if e.routing == "internal_safe"
        )
        violations = len(self.ungoverned_production_paths())
        return {
            "total_entries": len(self._entries),
            "governed": governed,
            "legacy": legacy,
            "bypass": bypass,
            "internal_safe": internal,
            "violations": violations,
            "coverage_score": round(self.coverage_score(), 3),
        }


# ─── Known Entry Points (from codebase analysis) ───


def build_known_registry() -> EntryPointRegistry:
    """Registers all known execution-capable surfaces in the MCOI runtime."""
    reg = EntryPointRegistry()

    # Governed paths (Phase 193)
    reg.register(
        "core.governed_dispatcher.GovernedDispatcher.governed_dispatch",
        "execution",
        "governed",
    )

    # Legacy dispatcher (should be wrapped or restricted)
    reg.register("core.dispatcher.Dispatcher.dispatch", "execution", "legacy")

    # Operator loop (the main CLI entry point)
    reg.register("app.operator_loop.OperatorLoop.run_step", "execution", "legacy")
    reg.register("app.operator_requests.run_skill_step", "execution", "legacy")
    reg.register("app.operator_workflows.run_workflow_step", "execution", "legacy")
    reg.register("app.operator_goals.run_goal_step", "execution", "legacy")

    # Adapters (direct execution surfaces)
    reg.register(
        "adapters.shell_executor.ShellExecutor.execute", "external", "legacy"
    )
    reg.register("adapters.http_connector.HttpConnector.fetch", "external", "legacy")
    reg.register(
        "adapters.smtp_communication.SmtpChannel.send", "external", "legacy"
    )
    reg.register("adapters.browser_adapter.BrowserAdapter.run", "external", "legacy")
    reg.register(
        "adapters.stub_model.StubModelAdapter.generate", "external", "legacy"
    )
    reg.register(
        "adapters.process_model.ProcessModelAdapter.generate", "external", "legacy"
    )
    reg.register(
        "adapters.code_adapter.LocalCodeAdapter.run_build", "external", "legacy"
    )

    # External connector execution surfaces
    reg.register(
        "core.external_connectors.ExternalConnectorRegistry.execute",
        "external",
        "legacy",
    )
    reg.register(
        "core.live_channel_bindings.LiveChannelBindings.execute",
        "external",
        "legacy",
    )

    # Persistence mutations (state changes — internal, governed by engine invariants)
    reg.register(
        "persistence.trace_store.TraceStore.append",
        "mutation",
        "internal_safe",
        governed_required=False,
    )
    reg.register(
        "persistence.replay_store.ReplayStore.save",
        "mutation",
        "internal_safe",
        governed_required=False,
    )
    reg.register(
        "persistence.snapshot_store.SnapshotStore.save",
        "mutation",
        "internal_safe",
        governed_required=False,
    )
    reg.register(
        "persistence.memory_store.MemoryStore.save",
        "mutation",
        "internal_safe",
        governed_required=False,
    )
    reg.register(
        "persistence.coordination_store.CoordinationStore.save_state",
        "mutation",
        "internal_safe",
        governed_required=False,
    )

    # Engine state mutations (internal, governed by engine invariants)
    reg.register(
        "core.event_spine.EventSpineEngine.emit",
        "mutation",
        "internal_safe",
        governed_required=False,
    )

    return reg
