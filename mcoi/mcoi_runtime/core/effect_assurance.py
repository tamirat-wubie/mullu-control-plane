"""Purpose: effect assurance gate for governed reality-changing execution.
Governance scope: pre-dispatch effect planning, simulation request creation,
post-dispatch observation, verification, reconciliation, and graph commit.
Dependencies: effect assurance contracts, execution contracts, verification
contracts, simulation engine, operational graph.
Invariants:
  - No effect-bearing action is committed without reconciliation MATCH.
  - Actual effects are derived from ExecutionResult.actual_effects only.
  - Assumed effects are never promoted into observed effects.
  - Simulation is read-only and never grants execution by itself.
  - Graph commit requires evidence-bearing observed effects.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from mcoi_runtime.contracts.effect_assurance import (
    EffectPlan,
    EffectReconciliation,
    ExpectedEffect,
    ObservedEffect,
    ReconciliationStatus,
)
from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionResult
from mcoi_runtime.contracts.graph import EdgeType, NodeType
from mcoi_runtime.contracts.simulation import (
    RiskLevel,
    SimulationOption,
    SimulationRequest,
    SimulationVerdict,
)
from mcoi_runtime.contracts.verification import (
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)

from .invariants import RuntimeCoreInvariantError, stable_identifier
from .operational_graph import OperationalGraph
from .simulation import SimulationEngine


_RISK_COST: dict[RiskLevel, float] = {
    RiskLevel.MINIMAL: 0.0,
    RiskLevel.LOW: 100.0,
    RiskLevel.MODERATE: 500.0,
    RiskLevel.HIGH: 2500.0,
    RiskLevel.CRITICAL: 10000.0,
}

_RISK_SUCCESS: dict[RiskLevel, float] = {
    RiskLevel.MINIMAL: 0.98,
    RiskLevel.LOW: 0.9,
    RiskLevel.MODERATE: 0.75,
    RiskLevel.HIGH: 0.55,
    RiskLevel.CRITICAL: 0.25,
}


@dataclass(frozen=True, slots=True)
class EffectGraphCommitReceipt:
    """Observed Effect Assurance operational graph commit receipt."""

    receipt_id: str
    mutation_type: str
    effect_name: str
    command_id: str
    effect_plan_id: str
    reconciliation_id: str
    evidence_ref: str
    verification_result_id: str | None
    observed_effect_ids: tuple[str, ...]
    observed_evidence_refs: tuple[str, ...]
    before_node_count: int
    before_edge_count: int
    after_node_count: int
    after_edge_count: int
    recorded_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "mutation_type": self.mutation_type,
            "effect_name": self.effect_name,
            "command_id": self.command_id,
            "effect_plan_id": self.effect_plan_id,
            "reconciliation_id": self.reconciliation_id,
            "evidence_ref": self.evidence_ref,
            "verification_result_id": self.verification_result_id,
            "observed_effect_ids": self.observed_effect_ids,
            "observed_evidence_refs": self.observed_evidence_refs,
            "before_node_count": self.before_node_count,
            "before_edge_count": self.before_edge_count,
            "after_node_count": self.after_node_count,
            "after_edge_count": self.after_edge_count,
            "recorded_at": self.recorded_at,
            "metadata": dict(self.metadata),
        }

    def to_effect_record(self) -> EffectRecord:
        return EffectRecord(
            name=self.effect_name,
            details={
                "effect_id": self.effect_name,
                "receipt_id": self.receipt_id,
                "mutation_type": self.mutation_type,
                "command_id": self.command_id,
                "effect_plan_id": self.effect_plan_id,
                "reconciliation_id": self.reconciliation_id,
                "evidence_ref": self.evidence_ref,
                "verification_result_id": self.verification_result_id,
                "observed_effect_ids": self.observed_effect_ids,
                "observed_evidence_refs": self.observed_evidence_refs,
                "before_node_count": self.before_node_count,
                "before_edge_count": self.before_edge_count,
                "after_node_count": self.after_node_count,
                "after_edge_count": self.after_edge_count,
                "observed_at": self.recorded_at,
                "metadata": dict(self.metadata),
                "source": "effect_assurance_graph_commit",
            },
        )


def _require_graph_commit_receipt(receipt: object) -> EffectGraphCommitReceipt:
    if not isinstance(receipt, EffectGraphCommitReceipt):
        raise ValueError("receipt must be an EffectGraphCommitReceipt instance")
    return receipt


def _require_positive_limit(limit: object) -> int:
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("limit must be an integer")
    if limit < 1:
        raise ValueError("limit must be >= 1")
    return limit


class EffectGraphCommitReceiptStore:
    """Base graph-commit receipt store with degraded no-op semantics."""

    def append(self, receipt: EffectGraphCommitReceipt) -> None:
        """Persist an Effect Assurance graph commit receipt."""
        _require_graph_commit_receipt(receipt)
        return None

    def list(self, *, limit: int = 50) -> tuple[EffectGraphCommitReceipt, ...]:
        """Return recent graph commit receipts in append order."""
        _require_positive_limit(limit)
        return ()

    @property
    def receipt_count(self) -> int:
        """Number of graph commit receipts tracked by this store."""
        return 0


class InMemoryEffectGraphCommitReceiptStore(EffectGraphCommitReceiptStore):
    """Bounded in-memory graph commit receipt store."""

    def __init__(self, *, max_records: int = 10_000) -> None:
        self._max_records = _require_positive_limit(max_records)
        self._receipts: list[EffectGraphCommitReceipt] = []

    def append(self, receipt: EffectGraphCommitReceipt) -> None:
        receipt = _require_graph_commit_receipt(receipt)
        self._receipts.append(receipt)
        if len(self._receipts) > self._max_records:
            del self._receipts[0 : len(self._receipts) - self._max_records]

    def list(self, *, limit: int = 50) -> tuple[EffectGraphCommitReceipt, ...]:
        limit = _require_positive_limit(limit)
        return tuple(self._receipts[-limit:])

    @property
    def receipt_count(self) -> int:
        return len(self._receipts)


class JsonlEffectGraphCommitReceiptStore(InMemoryEffectGraphCommitReceiptStore):
    """Append-only JSONL store for Effect Assurance graph commit receipts."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_records: int = 10_000,
        sync_on_write: bool = False,
    ) -> None:
        if not isinstance(sync_on_write, bool):
            raise ValueError("sync_on_write must be a boolean")
        self._path = Path(path)
        self._sync_on_write = sync_on_write
        super().__init__(max_records=max_records)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists():
            self._replay()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def sync_on_write(self) -> bool:
        return self._sync_on_write

    def append(self, receipt: EffectGraphCommitReceipt) -> None:
        receipt = _require_graph_commit_receipt(receipt)
        super().append(receipt)
        line = json.dumps(
            {
                "type": "effect_graph_commit_receipt",
                "receipt": receipt.to_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        with self._path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            if self._sync_on_write:
                os.fsync(handle.fileno())

    def _replay(self) -> None:
        for line_number, raw_line in enumerate(self._path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"effect graph commit receipt JSONL line {line_number} is malformed") from exc
            if not isinstance(event, dict):
                raise ValueError(f"effect graph commit receipt JSONL line {line_number} must be an object")
            if event.get("type") != "effect_graph_commit_receipt":
                raise ValueError(f"effect graph commit receipt JSONL line {line_number} has unsupported event type")
            receipt_payload = event.get("receipt")
            if not isinstance(receipt_payload, dict):
                raise ValueError(f"effect graph commit receipt JSONL line {line_number} receipt must be an object")
            InMemoryEffectGraphCommitReceiptStore.append(
                self,
                _effect_graph_commit_receipt_from_dict(receipt_payload),
            )


def _effect_graph_commit_receipt_from_dict(payload: Mapping[str, Any]) -> EffectGraphCommitReceipt:
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("effect graph commit receipt metadata must be an object")
    return EffectGraphCommitReceipt(
        receipt_id=_required_receipt_text(payload, "receipt_id"),
        mutation_type=_required_receipt_text(payload, "mutation_type"),
        effect_name=_required_receipt_text(payload, "effect_name"),
        command_id=_required_receipt_text(payload, "command_id"),
        effect_plan_id=_required_receipt_text(payload, "effect_plan_id"),
        reconciliation_id=_required_receipt_text(payload, "reconciliation_id"),
        evidence_ref=_required_receipt_text(payload, "evidence_ref"),
        verification_result_id=_optional_receipt_text(payload, "verification_result_id"),
        observed_effect_ids=_required_receipt_text_tuple(payload, "observed_effect_ids"),
        observed_evidence_refs=_required_receipt_text_tuple(payload, "observed_evidence_refs"),
        before_node_count=_required_receipt_int(payload, "before_node_count"),
        before_edge_count=_required_receipt_int(payload, "before_edge_count"),
        after_node_count=_required_receipt_int(payload, "after_node_count"),
        after_edge_count=_required_receipt_int(payload, "after_edge_count"),
        recorded_at=_required_receipt_text(payload, "recorded_at"),
        metadata=dict(metadata),
    )


def _required_receipt_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"effect graph commit receipt {field_name} must be a string")
    if not value.strip():
        raise ValueError(f"effect graph commit receipt {field_name} is required")
    return value


def _optional_receipt_text(payload: Mapping[str, Any], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"effect graph commit receipt {field_name} must be a string")
    if not value.strip():
        raise ValueError(f"effect graph commit receipt {field_name} is required")
    return value


def _required_receipt_int(payload: Mapping[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"effect graph commit receipt {field_name} must be an integer")
    if value < 0:
        raise ValueError(f"effect graph commit receipt {field_name} must be non-negative")
    return value


def _required_receipt_text_tuple(payload: Mapping[str, Any], field_name: str) -> tuple[str, ...]:
    value = payload.get(field_name)
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"effect graph commit receipt {field_name} must be an array")
    values: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"effect graph commit receipt {field_name} entries must be strings")
        if not item.strip():
            raise ValueError(f"effect graph commit receipt {field_name} entries are required")
        values.append(item)
    return tuple(values)


class EffectAssuranceGate:
    """Mandatory bridge from approved action to evidence-backed commit."""

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        graph: OperationalGraph | None = None,
        simulation_engine: SimulationEngine | None = None,
        graph_commit_receipt_store: EffectGraphCommitReceiptStore | None = None,
    ) -> None:
        self._clock = clock
        self._graph = graph
        self._simulation_engine = simulation_engine
        self._graph_commit_receipt_store = (
            graph_commit_receipt_store
            if graph_commit_receipt_store is not None
            else InMemoryEffectGraphCommitReceiptStore()
        )

    @property
    def graph_commit_available(self) -> bool:
        """Return whether matched effects can be committed to an operational graph."""
        return self._graph is not None

    def graph_commit_receipts(self, limit: int = 50) -> tuple[EffectGraphCommitReceipt, ...]:
        """Return recent Effect Assurance graph commit receipts in append order."""
        return self._graph_commit_receipt_store.list(limit=limit)

    def graph_commit_effect_records(self, limit: int = 50) -> tuple[EffectRecord, ...]:
        """Return recent graph commit receipts as execution actual-effect records."""
        return tuple(receipt.to_effect_record() for receipt in self.graph_commit_receipts(limit=limit))

    def create_plan(
        self,
        *,
        command_id: str,
        tenant_id: str,
        capability_id: str,
        expected_effects: tuple[ExpectedEffect, ...],
        forbidden_effects: tuple[str, ...],
        rollback_plan_id: str | None = None,
        compensation_plan_id: str | None = None,
        graph_node_refs: tuple[str, ...] = (),
        graph_edge_refs: tuple[str, ...] = (),
    ) -> EffectPlan:
        """Create an effect plan before dispatch."""
        now = self._clock()
        effect_plan_id = stable_identifier(
            "effect-plan",
            {
                "command_id": command_id,
                "tenant_id": tenant_id,
                "capability_id": capability_id,
                "created_at": now,
            },
        )
        if not graph_node_refs:
            graph_node_refs = (
                f"command:{command_id}",
                f"capability:{capability_id}",
                f"effect_plan:{effect_plan_id}",
            )
        if not graph_edge_refs:
            graph_edge_refs = (
                "command depends_on capability",
                "command produced effect_plan",
            )
        return EffectPlan(
            effect_plan_id=effect_plan_id,
            command_id=command_id,
            tenant_id=tenant_id,
            capability_id=capability_id,
            expected_effects=expected_effects,
            forbidden_effects=forbidden_effects,
            rollback_plan_id=rollback_plan_id,
            compensation_plan_id=compensation_plan_id,
            graph_node_refs=graph_node_refs,
            graph_edge_refs=graph_edge_refs,
            created_at=now,
        )

    def build_simulation_request(
        self,
        plan: EffectPlan,
        *,
        risk_level: RiskLevel,
        estimated_duration_seconds: float = 60.0,
    ) -> SimulationRequest:
        """Project an effect plan into a read-only simulation request."""
        option = SimulationOption(
            option_id=f"effect-option:{plan.effect_plan_id}",
            label=f"dispatch {plan.capability_id}",
            risk_level=risk_level,
            estimated_cost=_RISK_COST[risk_level],
            estimated_duration_seconds=estimated_duration_seconds,
            success_probability=_RISK_SUCCESS[risk_level],
        )
        return SimulationRequest(
            request_id=f"simreq:{plan.effect_plan_id}",
            context_type="command",
            context_id=plan.command_id,
            description="Effect assurance simulation for governed capability dispatch",
            options=(option,),
        )

    def simulate(
        self,
        plan: EffectPlan,
        *,
        risk_level: RiskLevel,
        estimated_duration_seconds: float = 60.0,
    ) -> SimulationVerdict:
        """Run read-only consequence simulation for a planned effect."""
        engine = self._simulation_engine
        if engine is None:
            if self._graph is None:
                raise RuntimeCoreInvariantError("simulation requires a graph or simulation_engine")
            engine = SimulationEngine(graph=self._graph, clock=self._clock)
        request = self.build_simulation_request(
            plan,
            risk_level=risk_level,
            estimated_duration_seconds=estimated_duration_seconds,
        )
        _, verdict = engine.full_simulation(request)
        return verdict

    def observe(self, execution_result: ExecutionResult) -> tuple[ObservedEffect, ...]:
        """Collect observed effects from execution actual_effects only."""
        if not execution_result.actual_effects:
            raise RuntimeCoreInvariantError("actual_effects required for observation")
        observed_at = self._clock()
        observed: list[ObservedEffect] = []
        for index, effect in enumerate(execution_result.actual_effects):
            if not isinstance(effect, EffectRecord):
                raise RuntimeCoreInvariantError("actual_effects must contain EffectRecord values")
            details = _mapping_or_empty(effect.details)
            evidence_ref = str(details.get("evidence_ref") or f"{execution_result.execution_id}:{effect.name}:{index}")
            effect_id = str(details.get("effect_id") or effect.name)
            source = str(details.get("source") or execution_result.execution_id)
            observed_value = details.get("observed_value", effect.details)
            observed.append(
                ObservedEffect(
                    effect_id=effect_id,
                    name=effect.name,
                    source=source,
                    observed_value=observed_value,
                    evidence_ref=evidence_ref,
                    observed_at=observed_at,
                )
            )
        return tuple(observed)

    def verify(
        self,
        *,
        plan: EffectPlan,
        execution_result: ExecutionResult,
        observed_effects: tuple[ObservedEffect, ...],
    ) -> VerificationResult:
        """Verify required expected effects and forbidden effect absence."""
        observed_ids = {effect.effect_id for effect in observed_effects}
        observed_names = {effect.name for effect in observed_effects}
        checks: list[VerificationCheck] = []
        for expected in plan.expected_effects:
            passed = expected.effect_id in observed_ids or expected.name in observed_names
            status = VerificationStatus.PASS if passed or not expected.required else VerificationStatus.FAIL
            checks.append(
                VerificationCheck(
                    name=f"expected:{expected.effect_id}",
                    status=status,
                    details={
                        "effect_id": expected.effect_id,
                        "required": expected.required,
                        "verification_method": expected.verification_method,
                    },
                )
            )
        for forbidden in plan.forbidden_effects:
            absent = forbidden not in observed_ids and forbidden not in observed_names
            checks.append(
                VerificationCheck(
                    name=f"forbidden:{forbidden}",
                    status=VerificationStatus.PASS if absent else VerificationStatus.FAIL,
                    details={"forbidden_effect": forbidden},
                )
            )
        overall = VerificationStatus.PASS
        if any(check.status is VerificationStatus.FAIL for check in checks):
            overall = VerificationStatus.FAIL
        evidence = tuple(
            EvidenceRecord(
                description="Observed effect evidence",
                uri=effect.evidence_ref,
                details={
                    "effect_id": effect.effect_id,
                    "source": effect.source,
                    "observed_at": effect.observed_at,
                },
            )
            for effect in observed_effects
        )
        if not evidence:
            evidence = (
                EvidenceRecord(
                    description="No observed effects available",
                    uri=f"execution:{execution_result.execution_id}",
                    details={"effect_plan_id": plan.effect_plan_id},
                ),
            )
        return VerificationResult(
            verification_id=stable_identifier(
                "effect-verification",
                {
                    "plan": plan.effect_plan_id,
                    "execution": execution_result.execution_id,
                    "closed_at": self._clock(),
                },
            ),
            execution_id=execution_result.execution_id,
            status=overall,
            checks=tuple(checks),
            evidence=evidence,
            closed_at=self._clock(),
            metadata={
                "command_id": plan.command_id,
                "effect_plan_id": plan.effect_plan_id,
            },
        )

    def reconcile(
        self,
        *,
        plan: EffectPlan,
        observed_effects: tuple[ObservedEffect, ...],
        verification_result: VerificationResult | None,
        case_id: str | None = None,
    ) -> EffectReconciliation:
        """Compare planned and observed effects into a terminal status."""
        observed_keys = {effect.effect_id for effect in observed_effects} | {effect.name for effect in observed_effects}
        required = tuple(effect for effect in plan.expected_effects if effect.required)
        matched = tuple(
            effect.effect_id
            for effect in plan.expected_effects
            if effect.effect_id in observed_keys or effect.name in observed_keys
        )
        missing = tuple(
            effect.effect_id
            for effect in required
            if effect.effect_id not in observed_keys and effect.name not in observed_keys
        )
        forbidden = set(plan.forbidden_effects)
        unexpected = tuple(
            sorted(
                effect.effect_id
                for effect in observed_effects
                if effect.effect_id in forbidden or effect.name in forbidden
            )
        )
        if not observed_effects:
            status = ReconciliationStatus.UNKNOWN
        elif unexpected:
            status = ReconciliationStatus.MISMATCH
        elif missing:
            status = ReconciliationStatus.PARTIAL_MATCH if matched else ReconciliationStatus.MISMATCH
        elif verification_result is not None and verification_result.status is VerificationStatus.FAIL:
            status = ReconciliationStatus.MISMATCH
        else:
            status = ReconciliationStatus.MATCH
        decided_at = self._clock()
        return EffectReconciliation(
            reconciliation_id=stable_identifier(
                "effect-reconciliation",
                {
                    "plan": plan.effect_plan_id,
                    "status": status.value,
                    "decided_at": decided_at,
                },
            ),
            command_id=plan.command_id,
            effect_plan_id=plan.effect_plan_id,
            status=status,
            matched_effects=matched,
            missing_effects=missing,
            unexpected_effects=unexpected,
            verification_result_id=(
                verification_result.verification_id if verification_result is not None else None
            ),
            case_id=case_id,
            decided_at=decided_at,
        )

    def commit_graph(
        self,
        *,
        plan: EffectPlan,
        observed_effects: tuple[ObservedEffect, ...],
        reconciliation: EffectReconciliation,
    ) -> EffectGraphCommitReceipt:
        """Commit a reconciled action to the operational graph."""
        if self._graph is None:
            raise RuntimeCoreInvariantError("graph commit requires graph")
        if reconciliation.status is not ReconciliationStatus.MATCH:
            raise RuntimeCoreInvariantError("graph commit requires reconciliation MATCH")
        if not observed_effects:
            raise RuntimeCoreInvariantError("graph commit requires observed effects")

        before_snapshot = self._graph.capture_snapshot()
        command_node = self._graph.ensure_node(
            f"command:{plan.command_id}",
            NodeType.JOB,
            f"Command {plan.command_id}",
        )
        capability_node = self._graph.ensure_node(
            f"capability:{plan.capability_id}",
            NodeType.FUNCTION,
            f"Capability {plan.capability_id}",
        )
        verification_node = self._graph.ensure_node(
            f"verification:{reconciliation.verification_result_id}",
            NodeType.VERIFICATION,
            f"Effect verification {reconciliation.verification_result_id}",
        )
        self._graph.add_edge(EdgeType.DEPENDS_ON, command_node.node_id, capability_node.node_id)
        self._graph.add_edge(EdgeType.VERIFIED_BY, command_node.node_id, verification_node.node_id)
        for effect in observed_effects:
            evidence_node = self._graph.ensure_node(
                f"evidence:{effect.evidence_ref}",
                NodeType.DOCUMENT,
                f"Evidence {effect.evidence_ref}",
            )
            provider_node = self._graph.ensure_node(
                f"provider_action:{effect.effect_id}",
                NodeType.PROVIDER_ACTION,
                f"Observed effect {effect.name}",
            )
            self._graph.add_edge(EdgeType.PRODUCED, command_node.node_id, provider_node.node_id)
            self._graph.add_evidence_link(provider_node.node_id, evidence_node.node_id, "observed_effect", 1.0)
            self._graph.add_edge(EdgeType.VERIFIED_BY, provider_node.node_id, verification_node.node_id)
        after_snapshot = self._graph.capture_snapshot()
        return self._record_graph_commit_receipt(
            plan=plan,
            observed_effects=observed_effects,
            reconciliation=reconciliation,
            before_node_count=before_snapshot.node_count,
            before_edge_count=before_snapshot.edge_count,
            after_node_count=after_snapshot.node_count,
            after_edge_count=after_snapshot.edge_count,
            recorded_at=after_snapshot.captured_at,
        )

    def _record_graph_commit_receipt(
        self,
        *,
        plan: EffectPlan,
        observed_effects: tuple[ObservedEffect, ...],
        reconciliation: EffectReconciliation,
        before_node_count: int,
        before_edge_count: int,
        after_node_count: int,
        after_edge_count: int,
        recorded_at: str,
    ) -> EffectGraphCommitReceipt:
        receipt_id = stable_identifier(
            "effect-graph-commit-receipt",
            {
                "command_id": plan.command_id,
                "effect_plan_id": plan.effect_plan_id,
                "reconciliation_id": reconciliation.reconciliation_id,
                "ordinal": self._graph_commit_receipt_store.receipt_count,
                "recorded_at": recorded_at,
            },
        )
        receipt = EffectGraphCommitReceipt(
            receipt_id=receipt_id,
            mutation_type="commit_graph",
            effect_name="effect_graph_committed",
            command_id=plan.command_id,
            effect_plan_id=plan.effect_plan_id,
            reconciliation_id=reconciliation.reconciliation_id,
            evidence_ref=f"effect-graph-commit:{receipt_id}",
            verification_result_id=reconciliation.verification_result_id,
            observed_effect_ids=tuple(effect.effect_id for effect in observed_effects),
            observed_evidence_refs=tuple(effect.evidence_ref for effect in observed_effects),
            before_node_count=before_node_count,
            before_edge_count=before_edge_count,
            after_node_count=after_node_count,
            after_edge_count=after_edge_count,
            recorded_at=recorded_at,
            metadata={
                "node_delta": after_node_count - before_node_count,
                "edge_delta": after_edge_count - before_edge_count,
            },
        )
        self._graph_commit_receipt_store.append(receipt)
        return receipt


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
