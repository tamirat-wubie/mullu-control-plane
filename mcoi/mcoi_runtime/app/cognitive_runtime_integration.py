"""Mount the cognitive organs into the live HTTP server runtime.

Purpose: instantiate the reasoning/learning engines (world-state, meta-reasoning,
    decision-learning, episodic/working memory) in the SERVED runtime and register
    them on the shared deps container, so live request paths CAN consult them.
    Historically these were instantiated only in the CLI bootstrap (app/bootstrap.py),
    leaving the HTTP server a "brain in a jar" (see
    docs/design/COGNITIVE_LOOP_LIVE_WIRING.md, correction in section 0).
Governance scope: composition/wiring only. This helper instantiates engines and
    registers them; it does NOT consult them, gate any decision, or change any
    response. Mounting is behavior-neutral until a consumer (e.g. the record-only
    shadow observer) reads them.
Dependencies: the in-memory engines in mcoi_runtime.core.* (no IO, no network).
Invariants:
  - Additive: registering these engines changes no existing response (nothing on
    the live path reads them as of this slice).
  - Deterministic construction: engines are in-memory; the only injected
    dependency is the runtime clock.
  - No module-global state: construction returns a handle the caller registers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mcoi_runtime.core.decision_learning import DecisionLearningEngine
from mcoi_runtime.core.memory import EpisodicMemory, WorkingMemory
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
from mcoi_runtime.core.world_state import WorldStateEngine


@dataclass(frozen=True)
class CognitiveRuntime:
    """The bundle of cognitive organs available to the served runtime."""

    world_state: WorldStateEngine
    meta_reasoning: MetaReasoningEngine
    decision_learning: DecisionLearningEngine
    episodic_memory: EpisodicMemory
    working_memory: WorkingMemory


def bootstrap_cognitive_runtime(*, clock: Callable[[], str]) -> CognitiveRuntime:
    """Instantiate the cognitive organs for the served runtime.

    Mirrors the CLI bootstrap (app/bootstrap.py) construction so the HTTP server
    holds the same engines. Pure / in-memory: no IO and no global side effects.
    """
    if clock is None:
        raise ValueError("bootstrap_cognitive_runtime requires a clock")
    return CognitiveRuntime(
        world_state=WorldStateEngine(),
        meta_reasoning=MetaReasoningEngine(clock=clock),
        decision_learning=DecisionLearningEngine(clock=clock),
        episodic_memory=EpisodicMemory(),
        working_memory=WorkingMemory(),
    )


def register_cognitive_runtime(deps: object, cognitive_runtime: CognitiveRuntime) -> None:
    """Register each organ (and the bundle) on the shared deps container.

    Additive: routers that do not look these names up are unaffected.
    """
    deps.set("cognitive_runtime", cognitive_runtime)
    deps.set("world_state", cognitive_runtime.world_state)
    deps.set("meta_reasoning", cognitive_runtime.meta_reasoning)
    deps.set("decision_learning", cognitive_runtime.decision_learning)
    deps.set("episodic_memory", cognitive_runtime.episodic_memory)
    deps.set("working_memory", cognitive_runtime.working_memory)


__all__ = [
    "CognitiveRuntime",
    "bootstrap_cognitive_runtime",
    "register_cognitive_runtime",
]
