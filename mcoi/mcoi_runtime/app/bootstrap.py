"""Purpose: wire the local MCOI operator entry path without side effects.
Governance scope: operator-loop bootstrap only.
Dependencies: execution-slice adapters, runtime-core boundaries, and local app configuration.
Invariants: bootstrap constructs deterministic wiring only and never executes commands or observes the live machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping

from mcoi_runtime.adapters.executor_base import ExecutorAdapter, utc_now_text
from mcoi_runtime.adapters.filesystem_observer import FilesystemObserver
from mcoi_runtime.adapters.observer_base import ObserverAdapter
from mcoi_runtime.adapters.process_observer import ProcessObserver
from mcoi_runtime.adapters.shell_executor import ShellExecutor
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.template import TemplateReference
from mcoi_runtime.core.dispatcher import Dispatcher
from mcoi_runtime.core.evidence_merger import EvidenceMerger
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
from mcoi_runtime.core.planning_boundary import PlanningBoundary
from mcoi_runtime.core.policy_engine import PolicyEngine
from mcoi_runtime.core.registry_index import RegistryIndex
from mcoi_runtime.core.registry_store import RegistryStore
from mcoi_runtime.core.replay_engine import ReplayEngine
from mcoi_runtime.core.runtime_kernel import RuntimeKernel
from mcoi_runtime.core.template_validator import TemplateValidator
from mcoi_runtime.core.provider_registry import ProviderRegistry
from mcoi_runtime.core.verification_engine import VerificationEngine
from mcoi_runtime.core.world_state import WorldStateEngine

from .config import AppConfig


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
    executors: Mapping[str, ExecutorAdapter]
    observers: Mapping[str, ObserverAdapter[object]]


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
) -> BootstrappedRuntime:
    app_config = config or AppConfig()
    runtime_clock = clock or utc_now_text

    registry_store: RegistryStore[TemplateReference] = RegistryStore()
    registry_index: RegistryIndex[TemplateReference] = RegistryIndex()
    evidence_merger = EvidenceMerger()
    planning_boundary = PlanningBoundary()
    policy_engine: PolicyEngine[PolicyDecision] = PolicyEngine()
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
        executor_map["shell_command"] = ShellExecutor(clock=runtime_clock)

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

    dispatcher = Dispatcher(
        template_validator=template_validator,
        executors=frozen_executors,
        clock=runtime_clock,
    )

    world_state = WorldStateEngine()
    meta_reasoning = MetaReasoningEngine(clock=runtime_clock)
    provider_registry = ProviderRegistry(clock=runtime_clock)

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
        executors=frozen_executors,
        observers=frozen_observers,
    )
