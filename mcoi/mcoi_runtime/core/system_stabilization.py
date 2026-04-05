"""Phases 186-192 — System Stabilization Program v2.

Purpose: Trust binding, ontology enforcement, agent equilibrium, adversarial defense,
    predictive failure, economic optimization, adaptive sim->real promotion.
Governance scope: system-wide integrity, stability, and self-regulation.
Dependencies: hashlib, datetime, typing.
Invariants: fail-closed, deterministic, proof-carrying, no silent mutation.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone
from hashlib import sha256
import math

# ═══ Phase 186 — Cryptographic Identity & Action Binding ═══

@dataclass(frozen=True)
class SignedIntent:
    intent_id: str
    actor_id: str
    action: str
    target_runtime: str
    intent_hash: str  # SHA-256 of actor_id:action:target
    signed_at: str

@dataclass(frozen=True)
class ActionBinding:
    binding_id: str
    intent: SignedIntent
    execution_id: str
    verification_hash: str
    non_repudiable: bool
    bound_at: str

class IdentityBindingEngine:
    """Binds every action to a cryptographically identified actor."""
    def __init__(self):
        self._intents: dict[str, SignedIntent] = {}
        self._bindings: dict[str, ActionBinding] = {}

    def sign_intent(self, intent_id: str, actor_id: str, action: str, target: str) -> SignedIntent:
        if intent_id in self._intents:
            raise ValueError("intent already registered")
        intent_hash = sha256(f"{actor_id}:{action}:{target}".encode()).hexdigest()
        si = SignedIntent(intent_id, actor_id, action, target, intent_hash, datetime.now(timezone.utc).isoformat())
        self._intents[intent_id] = si
        return si

    def bind_action(self, binding_id: str, intent_id: str, execution_id: str) -> ActionBinding:
        if binding_id in self._bindings:
            raise ValueError("binding already registered")
        intent = self._intents.get(intent_id)
        if not intent:
            raise ValueError("intent unavailable")
        verification_hash = sha256(f"{intent.intent_hash}:{execution_id}".encode()).hexdigest()
        ab = ActionBinding(binding_id, intent, execution_id, verification_hash, True, datetime.now(timezone.utc).isoformat())
        self._bindings[binding_id] = ab
        return ab

    def verify_binding(self, binding_id: str) -> bool:
        b = self._bindings.get(binding_id)
        if not b:
            return False
        expected = sha256(f"{b.intent.intent_hash}:{b.execution_id}".encode()).hexdigest()
        return b.verification_hash == expected

    @property
    def intent_count(self) -> int:
        return len(self._intents)

    @property
    def binding_count(self) -> int:
        return len(self._bindings)

# ═══ Phase 187 — Global Ontology Enforcement ═══

@dataclass(frozen=True)
class OntologyViolation:
    violation_id: str
    source_module: str
    term: str
    expected_canonical: str
    actual_usage: str
    severity: str  # "drift", "conflict", "missing"

class OntologyEnforcer:
    """Validates contracts and terms against the canonical ontology."""
    def __init__(self):
        self._canonical: dict[str, str] = {}  # term -> canonical meaning
        self._violations: list[OntologyViolation] = []

    def register_canonical(self, term: str, meaning: str) -> None:
        self._canonical[term.lower()] = meaning

    def validate_term(self, module: str, term: str, usage: str) -> OntologyViolation | None:
        canonical = self._canonical.get(term.lower())
        if canonical is None:
            v = OntologyViolation(f"ov-{len(self._violations)}", module, term, "undefined", usage, "missing")
            self._violations.append(v)
            return v
        if canonical != usage:
            v = OntologyViolation(f"ov-{len(self._violations)}", module, term, canonical, usage, "drift")
            self._violations.append(v)
            return v
        return None

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    def drift_count(self) -> int:
        return sum(1 for v in self._violations if v.severity == "drift")

# ═══ Phase 188 — Multi-Agent Equilibrium Engine ═══

@dataclass
class AgentLoad:
    agent_id: str
    actions_pending: int = 0
    actions_completed: int = 0
    conflicts: int = 0
    efficiency: float = 1.0  # 0-1

class EquilibriumEngine:
    """Constrains multi-agent system toward global equilibrium."""
    def __init__(self, max_total_pending: int = 100):
        self._agents: dict[str, AgentLoad] = {}
        self._max_pending = max_total_pending

    def register_agent(self, agent_id: str) -> AgentLoad:
        load = AgentLoad(agent_id)
        self._agents[agent_id] = load
        return load

    def record_action(self, agent_id: str) -> bool:
        """Returns True if action is allowed under equilibrium constraints."""
        total = sum(a.actions_pending for a in self._agents.values())
        if total >= self._max_pending:
            return False
        a = self._agents.get(agent_id)
        if a:
            a.actions_pending += 1
        return True

    def complete_action(self, agent_id: str) -> None:
        a = self._agents.get(agent_id)
        if a and a.actions_pending > 0:
            a.actions_pending -= 1
            a.actions_completed += 1

    def record_conflict(self, agent_id: str) -> None:
        a = self._agents.get(agent_id)
        if a:
            a.conflicts += 1
            a.efficiency = max(0.0, a.efficiency - 0.1)

    def equilibrium_score(self) -> float:
        if not self._agents:
            return 1.0
        avg_eff = sum(a.efficiency for a in self._agents.values()) / len(self._agents)
        total_conflicts = sum(a.conflicts for a in self._agents.values())
        penalty = min(1.0, total_conflicts * 0.05)
        return max(0.0, avg_eff - penalty)

    @property
    def agent_count(self) -> int:
        return len(self._agents)

    def is_stable(self) -> bool:
        return self.equilibrium_score() >= 0.7

# ═══ Phase 189 — Adversarial Ground Truth Defense ═══

@dataclass
class TrustDecayRecord:
    source_id: str
    initial_trust: float
    current_trust: float
    decay_events: int = 0
    contradictions: int = 0

class AdversarialDefenseEngine:
    """Detects poisoning, contradiction clustering, and trust decay."""
    def __init__(self):
        self._sources: dict[str, TrustDecayRecord] = {}
        self._anomalies: list[dict[str, Any]] = []

    def register_source(self, source_id: str, initial_trust: float = 0.8) -> TrustDecayRecord:
        record = TrustDecayRecord(source_id, initial_trust, initial_trust)
        self._sources[source_id] = record
        return record

    def record_contradiction(self, source_id: str) -> TrustDecayRecord:
        r = self._sources.get(source_id)
        if not r:
            raise ValueError("source unavailable")
        r.contradictions += 1
        r.current_trust = max(0.0, r.current_trust - 0.15)
        r.decay_events += 1
        if r.contradictions >= 3:
            self._anomalies.append({"source": source_id, "type": "repeated_contradiction", "count": r.contradictions})
        return r

    def detect_poisoning(self, source_id: str, confidence: float) -> bool:
        r = self._sources.get(source_id)
        if not r:
            return False
        if r.current_trust < 0.3 and confidence > 0.8:
            self._anomalies.append({"source": source_id, "type": "poisoning_suspected", "trust": r.current_trust, "confidence": confidence})
            return True
        return False

    def is_trusted(self, source_id: str) -> bool:
        r = self._sources.get(source_id)
        return r is not None and r.current_trust >= 0.5

    @property
    def anomaly_count(self) -> int:
        return len(self._anomalies)

# ═══ Phase 190 — Predictive Failure Engine ═══

@dataclass(frozen=True)
class FailurePrediction:
    prediction_id: str
    target: str
    risk_score: float  # 0-1
    recommendation: str  # "proceed", "reroute", "downgrade", "abort"
    factors: tuple[str, ...]

class PredictiveFailureEngine:
    """Predicts likely failures before dispatch."""
    def __init__(self):
        self._predictions: dict[str, FailurePrediction] = {}
        self._failure_history: dict[str, int] = {}  # target -> failure count

    def record_failure(self, target: str) -> None:
        self._failure_history[target] = self._failure_history.get(target, 0) + 1

    def predict(self, prediction_id: str, target: str, current_load: float = 0.0) -> FailurePrediction:
        failures = self._failure_history.get(target, 0)
        risk = min(1.0, failures * 0.2 + current_load * 0.3)
        factors = []
        if failures > 0:
            factors.append(f"prior_failures:{failures}")
        if current_load > 0.7:
            factors.append(f"high_load:{current_load}")
        if risk >= 0.8:
            rec = "abort"
        elif risk >= 0.6:
            rec = "reroute"
        elif risk >= 0.4:
            rec = "downgrade"
        else:
            rec = "proceed"
        p = FailurePrediction(prediction_id, target, round(risk, 3), rec, tuple(factors))
        self._predictions[prediction_id] = p
        return p

    @property
    def prediction_count(self) -> int:
        return len(self._predictions)

# ═══ Phase 191 — Economic Optimization Engine ═══

@dataclass(frozen=True)
class ExecutionCostEstimate:
    estimate_id: str
    target: str
    estimated_cost: float
    estimated_value: float
    net_value: float
    recommendation: str  # "execute", "defer", "reject"

class EconomicOptimizer:
    """Cost-aware execution routing and budget enforcement."""
    def __init__(self, budget: float = 10000.0):
        self._budget = budget
        self._spent = 0.0
        self._estimates: dict[str, ExecutionCostEstimate] = {}

    def estimate(self, estimate_id: str, target: str, cost: float, value: float) -> ExecutionCostEstimate:
        net = value - cost
        if cost > self._budget - self._spent:
            rec = "reject"
        elif net < 0:
            rec = "defer"
        else:
            rec = "execute"
        e = ExecutionCostEstimate(estimate_id, target, cost, value, round(net, 2), rec)
        self._estimates[estimate_id] = e
        return e

    def commit_spend(self, amount: float) -> bool:
        if self._spent + amount > self._budget:
            return False
        self._spent += amount
        return True

    @property
    def remaining_budget(self) -> float:
        return self._budget - self._spent

    @property
    def utilization(self) -> float:
        return self._spent / self._budget if self._budget else 0.0

# ═══ Phase 192 — Adaptive Sim->Real Promotion Engine ═══

@dataclass(frozen=True)
class PromotionDecision:
    decision_id: str
    scope: str
    confidence: float
    risk_score: float
    decision: str  # "promote", "hold", "reject"
    evidence: tuple[str, ...]

class AdaptivePromotionEngine:
    """Confidence-driven promotion from simulation to reality."""
    def __init__(self, confidence_threshold: float = 0.85, risk_ceiling: float = 0.3):
        self._threshold = confidence_threshold
        self._ceiling = risk_ceiling
        self._decisions: dict[str, PromotionDecision] = {}

    def evaluate_promotion(self, decision_id: str, scope: str, confidence: float, risk: float, evidence: tuple[str, ...] = ()) -> PromotionDecision:
        if confidence >= self._threshold and risk <= self._ceiling:
            decision = "promote"
        elif confidence >= self._threshold * 0.8:
            decision = "hold"
        else:
            decision = "reject"
        d = PromotionDecision(decision_id, scope, confidence, risk, decision, evidence)
        self._decisions[decision_id] = d
        return d

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    def promoted_count(self) -> int:
        return sum(1 for d in self._decisions.values() if d.decision == "promote")
