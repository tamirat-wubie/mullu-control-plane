"""Purpose: wire the local MCOI operator entry path without side effects.
Governance scope: operator-loop bootstrap only.
Dependencies: execution-slice adapters, runtime-core boundaries, and local app configuration.
Invariants:
  - bootstrap constructs deterministic wiring only.
  - bootstrap never executes commands or observes the live machine.
  - persisted memory restore is explicit and read-only during bootstrap.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping

from mcoi_runtime.adapters.executor_base import ExecutorAdapter, utc_now_text
from mcoi_runtime.adapters.filesystem_observer import FilesystemObserver
from mcoi_runtime.adapters.observer_base import ObserverAdapter
from mcoi_runtime.adapters.process_observer import ProcessObserver
from mcoi_runtime.adapters.shell_executor import ShellExecutor, ShellSandboxPolicy
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.template import TemplateReference
from mcoi_runtime.core.dispatcher import Dispatcher
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
from mcoi_runtime.core.case_runtime import CaseRuntimeEngine
from mcoi_runtime.core.evidence_merger import EvidenceMerger
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
from mcoi_runtime.core.memory import EpisodicMemory, WorkingMemory
from mcoi_runtime.core.operational_graph import OperationalGraph
from mcoi_runtime.core.planning_boundary import PlanningBoundary
from mcoi_runtime.governance.policy.engine import PolicyEngine
from mcoi_runtime.core.registry_index import RegistryIndex
from mcoi_runtime.core.registry_store import RegistryStore
from mcoi_runtime.core.replay_engine import ReplayEngine
from mcoi_runtime.core.runtime_kernel import RuntimeKernel
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.autonomy import AutonomyMode
from mcoi_runtime.core.autonomy import AutonomyEngine
from mcoi_runtime.core.goal_reasoning import GoalReasoningEngine
from mcoi_runtime.core.skills import SkillExecutor, SkillRegistry, SkillSelector
from mcoi_runtime.core.template_validator import TemplateValidator
from mcoi_runtime.core.provider_registry import ProviderRegistry
from mcoi_runtime.core.provider_attribution import ProviderAttributionLedger
from mcoi_runtime.core.verification_engine import VerificationEngine
from mcoi_runtime.core.workflow import WorkflowEngine
from mcoi_runtime.core.world_state import WorldStateEngine
from mcoi_runtime.persistence.goal_store import GoalStore
from mcoi_runtime.persistence.memory_store import MemoryStore
from mcoi_runtime.persistence.mil_audit_store import MILAuditStore
from mcoi_runtime.persistence.trace_store import TraceStore
from mcoi_runtime.persistence.workflow_store import WorkflowStore

from .config import AppConfig
from .policy_packs import PolicyPackRegistry


@dataclass(frozen=True, slots=True)
class BootstrappedRuntime:
    config: AppConfig
    clock: Callable[[], str]
    registry_store: RegistryStore[TemplateReference]
    registry_index: RegistryIndex[TemplateReference]
    evidence_merger: EvidenceMerger
    planning_boundary: PlanningBoundary
    policy_engine: PolicyEngine[PolicyDecision]
    replay_engine: ReplayEngine
    verification_engine: VerificationEngine
    runtime_kernel: RuntimeKernel[TemplateReference, PolicyDecision]
    template_validator: TemplateValidator
    dispatcher: Dispatcher
    world_state: WorldStateEngine
    meta_reasoning: MetaReasoningEngine
    provider_registry: ProviderRegistry
    provider_attribution_ledger: ProviderAttributionLedger
    skill_registry: SkillRegistry
    skill_selector: SkillSelector
    skill_executor: SkillExecutor
    autonomy: AutonomyEngine
    goal_reasoning_engine: GoalReasoningEngine
    workflow_engine: WorkflowEngine
    goal_store: GoalStore | None
    workflow_store: WorkflowStore | None
    mil_audit_store: MILAuditStore | None
    trace_store: TraceStore | None
    working_memory: WorkingMemory
    episodic_memory: EpisodicMemory
    memory_store: MemoryStore | None
    executors: Mapping[str, ExecutorAdapter]
    observers: Mapping[str, ObserverAdapter[object]]
    effect_assurance: EffectAssuranceGate | None = None
    operational_graph: OperationalGraph | None = None
    event_spine: EventSpineEngine | None = None
    case_runtime: CaseRuntimeEngine | None = None
    governed_dispatcher: object | None = None


def build_policy_decision(
    *,
    decision_id: str,
    subject_id: str,
    goal_id: str,
    status: str,
    reasons: tuple[object, ...],
    issued_at: str,
) -> PolicyDecision:
    return PolicyDecision(
        decision_id=decision_id,
        subject_id=subject_id,
        goal_id=goal_id,
        status=PolicyDecisionStatus(status),
        reasons=tuple(
            DecisionReason(
                message=getattr(reason, "message"),
                code=getattr(reason, "code"),
            )
            for reason in reasons
        ),
        issued_at=issued_at,
    )


def bootstrap_runtime(
    *,
    config: AppConfig | None = None,
    clock: Callable[[], str] | None = None,
    executors: Mapping[str, ExecutorAdapter] | None = None,
    observers: Mapping[str, ObserverAdapter[object]] | None = None,
    goal_store: GoalStore | None = None,
    workflow_store: WorkflowStore | None = None,
    mil_audit_store: MILAuditStore | None = None,
    trace_store: TraceStore | None = None,
    memory_store: MemoryStore | None = None,
    restore_memory: bool = False,
) -> BootstrappedRuntime:
    app_config = config or AppConfig()
    runtime_clock = clock or utc_now_text

    if restore_memory and memory_store is None:
        raise RuntimeCoreInvariantError("restore_memory requires a memory_store")

    registry_store: RegistryStore[TemplateReference] = RegistryStore()
    registry_index: RegistryIndex[TemplateReference] = RegistryIndex()
    evidence_merger = EvidenceMerger()
    planning_boundary = PlanningBoundary()
    policy_pack_registry = PolicyPackRegistry()
    policy_engine: PolicyEngine[PolicyDecision] = PolicyEngine(
        pack_resolver=policy_pack_registry
    )
    replay_engine = ReplayEngine()
    verification_engine = VerificationEngine()
    runtime_kernel: RuntimeKernel[TemplateReference, PolicyDecision] = RuntimeKernel(
        registry_store=registry_store,
        registry_index=registry_index,
        evidence_merger=evidence_merger,
        planning_boundary=planning_boundary,
        policy_engine=policy_engine,
        replay_engine=replay_engine,
    )
    template_validator = TemplateValidator()

    executor_map: dict[str, ExecutorAdapter] = {}
    if executors is not None:
        executor_map.update(executors)
    elif "shell_command" in app_config.enabled_executor_routes:
        shell_sandbox_policy = (
            ShellSandboxPolicy(
                sandbox_id=app_config.shell_sandbox_id,
                allowed_cwd_roots=app_config.shell_allowed_cwd_roots,
                allowed_environment_keys=app_config.shell_allowed_environment_keys,
                allow_inherited_environment=app_config.shell_allow_inherited_environment,
                require_cwd=app_config.shell_require_cwd,
            )
            if app_config.shell_sandbox_enabled
            else None
        )
        executor_map["shell_command"] = ShellExecutor(
            clock=runtime_clock,
            sandbox_policy=shell_sandbox_policy,
        )

    observer_map: dict[str, ObserverAdapter[object]] = {}
    if observers is not None:
        observer_map.update(observers)
    else:
        if "filesystem" in app_config.enabled_observer_routes:
            observer_map["filesystem"] = FilesystemObserver()
        if "process" in app_config.enabled_observer_routes:
            observer_map["process"] = ProcessObserver()

    frozen_executors: Mapping[str, ExecutorAdapter] = MappingProxyType(dict(executor_map))
    frozen_observers: Mapping[str, ObserverAdapter[object]] = MappingProxyType(dict(observer_map))

    world_state = WorldStateEngine()
    meta_reasoning = MetaReasoningEngine(clock=runtime_clock)
    provider_registry = ProviderRegistry(clock=runtime_clock)
    provider_attribution_ledger = ProviderAttributionLedger(clock=runtime_clock)
    skill_registry = SkillRegistry()
    skill_selector = SkillSelector()
    skill_executor = SkillExecutor(clock=runtime_clock)
    autonomy = AutonomyEngine(mode=AutonomyMode(app_config.autonomy_mode))
    goal_reasoning_engine = GoalReasoningEngine(clock=runtime_clock)
    workflow_engine_inst = WorkflowEngine(clock=runtime_clock)
    operational_graph = (
        OperationalGraph(clock=runtime_clock)
        if app_config.effect_assurance_required
        else None
    )
    event_spine = (
        EventSpineEngine(clock=runtime_clock)
        if app_config.effect_assurance_required
        else None
    )
    case_runtime = (
        CaseRuntimeEngine(event_spine)
        if event_spine is not None
        else None
    )
    effect_assurance = (
        EffectAssuranceGate(clock=runtime_clock, graph=operational_graph)
        if operational_graph is not None
        else None
    )

    dispatcher = Dispatcher(
        template_validator=template_validator,
        executors=frozen_executors,
        clock=runtime_clock,
    )

    # Phase 195C: create governed dispatcher wrapping the raw one.
    from mcoi_runtime.core.governed_dispatcher import GovernedDispatcher
    governed = GovernedDispatcher(
        dispatcher,
        effect_assurance=effect_assurance,
        case_runtime=case_runtime,
        clock=runtime_clock,
    )

    if restore_memory and memory_store is not None:
        working_memory, episodic_memory = memory_store.load_all(allow_missing=True)
    else:
        working_memory = WorkingMemory()
        episodic_memory = EpisodicMemory()

    return BootstrappedRuntime(
        config=app_config,
        clock=runtime_clock,
        registry_store=registry_store,
        registry_index=registry_index,
        evidence_merger=evidence_merger,
        planning_boundary=planning_boundary,
        policy_engine=policy_engine,
        replay_engine=replay_engine,
        verification_engine=verification_engine,
        runtime_kernel=runtime_kernel,
        template_validator=template_validator,
        dispatcher=dispatcher,
        world_state=world_state,
        meta_reasoning=meta_reasoning,
        provider_registry=provider_registry,
        provider_attribution_ledger=provider_attribution_ledger,
        skill_registry=skill_registry,
        skill_selector=skill_selector,
        skill_executor=skill_executor,
        autonomy=autonomy,
        goal_reasoning_engine=goal_reasoning_engine,
        workflow_engine=workflow_engine_inst,
        goal_store=goal_store,
        workflow_store=workflow_store,
        mil_audit_store=mil_audit_store,
        trace_store=trace_store,
        working_memory=working_memory,
        episodic_memory=episodic_memory,
        memory_store=memory_store,
        executors=frozen_executors,
        observers=frozen_observers,
        effect_assurance=effect_assurance,
        operational_graph=operational_graph,
        event_spine=event_spine,
        case_runtime=case_runtime,
        governed_dispatcher=governed,
    )
