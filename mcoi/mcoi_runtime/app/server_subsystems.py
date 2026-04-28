"""Subsystem bootstrap helpers for the governed HTTP server.

Purpose: isolate mid-layer subsystem construction and observability wiring from
the main server module.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: coordination, scheduler, connector, RBAC, sandbox, explanation,
audit anchor, knowledge graph, event bus, and batch pipeline subsystems.
Invariants:
  - Coordination storage path resolution remains deterministic.
  - Late-bound guard and audit fields remain unset at bootstrap time.
  - RBAC seeding remains explicit and observable.
  - Event bus health registration remains stable.
  - Batch pipeline keeps the same llm completion bridge contract.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from mcoi_runtime.governance.guards.access import AccessRuntimeEngine
from mcoi_runtime.governance.audit.anchor import AuditAnchorStore
from mcoi_runtime.core.batch_pipeline import BatchPipeline
from mcoi_runtime.core.connector_framework import GovernedConnectorFramework
from mcoi_runtime.core.coordination import CoordinationEngine
from mcoi_runtime.core.data_governance import DataGovernanceEngine
from mcoi_runtime.core.event_bus import EventBus
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.explanation_engine import ExplanationEngine
from mcoi_runtime.core.knowledge_graph import KnowledgeGraph
from mcoi_runtime.governance.policy.sandbox import PolicySandbox
from mcoi_runtime.core.rbac_defaults import seed_default_permissions
from mcoi_runtime.core.runbook_learning import RunbookLearningEngine
from mcoi_runtime.core.scheduler import GovernedScheduler
from mcoi_runtime.persistence import CoordinationStore


@dataclass(frozen=True)
class SubsystemBootstrap:
    """Mid-layer subsystem bootstrap result."""

    coordination_store: Any
    coordination_engine: Any
    scheduler: Any
    connector_framework: Any
    access_runtime: Any
    rbac_rules_seeded: int
    policy_sandbox: Any
    runbook_learning: Any
    explanation_engine: Any
    audit_anchor: Any
    knowledge_graph: Any
    data_governance: Any
    event_bus: Any
    batch_pipeline: Any


def bootstrap_subsystems(
    *,
    clock: Callable[[], str],
    runtime_env: Mapping[str, str],
    llm_bridge: Any,
    audit_trail: Any,
    observability: Any,
    deep_health: Any,
    coordination_store_cls: type[Any] = CoordinationStore,
    coordination_engine_cls: type[Any] = CoordinationEngine,
    governed_scheduler_cls: type[Any] = GovernedScheduler,
    connector_framework_cls: type[Any] = GovernedConnectorFramework,
    event_spine_engine_cls: type[Any] = EventSpineEngine,
    access_runtime_engine_cls: type[Any] = AccessRuntimeEngine,
    seed_default_permissions_fn: Callable[[Any], int] = seed_default_permissions,
    policy_sandbox_cls: type[Any] = PolicySandbox,
    runbook_learning_engine_cls: type[Any] = RunbookLearningEngine,
    explanation_engine_cls: type[Any] = ExplanationEngine,
    audit_anchor_store_cls: type[Any] = AuditAnchorStore,
    knowledge_graph_cls: type[Any] = KnowledgeGraph,
    data_governance_engine_cls: type[Any] = DataGovernanceEngine,
    event_bus_cls: type[Any] = EventBus,
    batch_pipeline_cls: type[Any] = BatchPipeline,
    tempdir_getter: Callable[[], str] = tempfile.gettempdir,
) -> SubsystemBootstrap:
    """Create coordination, policy, and eventing subsystems."""
    coordination_base = Path(
        runtime_env.get(
            "MULLU_COORDINATION_DIR",
            os.path.join(
                runtime_env.get("MULLU_DATA_DIR", tempdir_getter()),
                "mullu-coordination",
            ),
        )
    )
    coordination_store = coordination_store_cls(coordination_base)
    coordination_engine = coordination_engine_cls(
        clock=clock,
        coordination_store=coordination_store,
        policy_pack_id="default",
    )
    observability.register_source("coordination", lambda: coordination_engine.summary())

    scheduler = governed_scheduler_cls(
        clock=clock,
        guard_chain=None,
        audit_trail=None,
    )
    observability.register_source("scheduler", lambda: scheduler.summary())

    connector_framework = connector_framework_cls(
        clock=clock,
        guard_chain=None,
        audit_trail=None,
    )
    observability.register_source("connectors", lambda: connector_framework.summary())

    access_runtime = access_runtime_engine_cls(event_spine_engine_cls(clock=clock))
    rbac_rules_seeded = seed_default_permissions_fn(access_runtime)
    observability.register_source(
        "rbac",
        lambda: {
            "identities": access_runtime.identity_count,
            "roles": access_runtime.role_count,
            "bindings": access_runtime.binding_count,
            "rules_seeded": rbac_rules_seeded,
        },
    )

    policy_sandbox = policy_sandbox_cls(
        clock=clock,
        guard_chain=None,
    )
    observability.register_source("simulation", lambda: policy_sandbox.summary())

    runbook_learning = runbook_learning_engine_cls(clock=clock)
    observability.register_source("runbooks", lambda: runbook_learning.summary())

    explanation_engine = explanation_engine_cls(
        clock=clock,
        audit_trail=None,
        guard_chain=None,
    )
    observability.register_source("explanations", lambda: explanation_engine.summary())

    audit_anchor = audit_anchor_store_cls(clock=clock)
    observability.register_source("audit_anchors", lambda: audit_anchor.summary())

    knowledge_graph = knowledge_graph_cls(clock=clock)
    observability.register_source("knowledge", lambda: knowledge_graph.summary())

    data_governance = data_governance_engine_cls(EventSpineEngine(clock=clock))
    observability.register_source(
        "data_governance",
        lambda: {
            "records": data_governance.record_count,
            "policies": data_governance.policy_count,
            "residency_constraints": data_governance.residency_constraint_count,
            "privacy_rules": data_governance.privacy_rule_count,
            "redaction_rules": data_governance.redaction_rule_count,
            "retention_rules": data_governance.retention_rule_count,
            "decisions": data_governance.decision_count,
            "violations": data_governance.violation_count,
            "state_hash": data_governance.state_hash(),
        },
    )

    event_bus = event_bus_cls(clock=clock)
    observability.register_source("event_bus", lambda: event_bus.summary())
    deep_health.register(
        "event_bus",
        lambda: {
            "status": "healthy",
            "events": event_bus.event_count,
            "errors": event_bus.error_count,
        },
    )

    batch_pipeline = batch_pipeline_cls(
        clock=clock,
        llm_complete_fn=lambda prompt, **kwargs: llm_bridge.complete(prompt, **kwargs),
    )
    observability.register_source("pipelines", lambda: batch_pipeline.summary())

    return SubsystemBootstrap(
        coordination_store=coordination_store,
        coordination_engine=coordination_engine,
        scheduler=scheduler,
        connector_framework=connector_framework,
        access_runtime=access_runtime,
        rbac_rules_seeded=rbac_rules_seeded,
        policy_sandbox=policy_sandbox,
        runbook_learning=runbook_learning,
        explanation_engine=explanation_engine,
        audit_anchor=audit_anchor,
        knowledge_graph=knowledge_graph,
        data_governance=data_governance,
        event_bus=event_bus,
        batch_pipeline=batch_pipeline,
    )
