"""Axis traversal engine for InceptaDive-M Concept Boxes.

Purpose: derive structured, projection-only findings across vertical,
horizontal, circular, diagonal, temporal, intensity, and meta axes.
Governance scope: no truth promotion, no execution approval, lineage-preserved
findings, bounded traversal depth, and explicit repair requirements.
Dependencies: dataclasses, runtime invariant helpers, and Concept Box ledger.
Invariants: traversal emits candidates only; every finding records axis,
evidence, confidence, suppression, delta type, and lineage.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Sequence

from mcoi_runtime.core.concept_box_ledger import ConceptBox
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.note_memory_mesh import ProofState, TrustZone


class TraversalAxis(StrEnum):
    """Concept Box traversal axes."""

    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    CIRCULAR = "circular"
    DIAGONAL = "diagonal"
    TEMPORAL = "temporal"
    INTENSITY = "intensity"
    META = "meta"


class DeltaType(StrEnum):
    """Finding delta classes."""

    CONSTRUCTIVE = "constructive"
    FRACTURE = "fracture"


@dataclass(frozen=True)
class SuppressionVector:
    """Seven practical suppressors for traversal findings."""

    evidence_weakness: float = 0.0
    contradiction_pressure: float = 0.0
    staleness: float = 0.0
    scope_mismatch: float = 0.0
    source_authority_weakness: float = 0.0
    privacy_safety_risk: float = 0.0
    execution_risk: float = 0.0

    def __post_init__(self) -> None:
        for name, value in self.to_dict().items():
            if not 0.0 <= float(value) <= 1.0:
                raise RuntimeCoreInvariantError(f"suppression value out of range: {name}")

    def to_dict(self) -> dict[str, float]:
        """Return JSON-compatible suppressor values."""

        return {
            "evidence_weakness": self.evidence_weakness,
            "contradiction_pressure": self.contradiction_pressure,
            "staleness": self.staleness,
            "scope_mismatch": self.scope_mismatch,
            "source_authority_weakness": self.source_authority_weakness,
            "privacy_safety_risk": self.privacy_safety_risk,
            "execution_risk": self.execution_risk,
        }

    @property
    def mean(self) -> float:
        """Return the average suppression factor."""

        values = tuple(self.to_dict().values())
        return sum(values) / len(values)


@dataclass(frozen=True)
class AxisFinding:
    """Structured output from one traversal axis."""

    finding_id: str
    axis: TraversalAxis
    source_box_id: str
    claim: str
    evidence_refs: tuple[str, ...]
    confidence: float
    suppression: SuppressionVector
    delta_type: DeltaType
    repair_requirement: str
    lineage_tag: str

    def __post_init__(self) -> None:
        if not self.finding_id.strip():
            raise RuntimeCoreInvariantError("finding_id must be non-empty")
        if not self.source_box_id.strip():
            raise RuntimeCoreInvariantError("source_box_id must be non-empty")
        if not self.claim.strip():
            raise RuntimeCoreInvariantError("finding claim must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise RuntimeCoreInvariantError("finding confidence must be in [0,1]")
        if self.delta_type == DeltaType.FRACTURE and not self.repair_requirement.strip():
            raise RuntimeCoreInvariantError("fracture finding requires repair_requirement")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible finding."""

        return {
            "finding_id": self.finding_id,
            "axis": self.axis.value,
            "source_box_id": self.source_box_id,
            "claim": self.claim,
            "evidence_refs": list(self.evidence_refs),
            "confidence": self.confidence,
            "suppression": self.suppression.to_dict(),
            "delta_type": self.delta_type.value,
            "repair_requirement": self.repair_requirement,
            "lineage_tag": self.lineage_tag,
        }


@dataclass(frozen=True)
class AxisTraversalPolicy:
    """Bounded traversal policy."""

    max_depth: int = 3
    allowed_trust_zones: tuple[TrustZone, ...] = (TrustZone.LOCAL, TrustZone.WORKSPACE)
    require_evidence: bool = True

    def __post_init__(self) -> None:
        if self.max_depth < 1:
            raise RuntimeCoreInvariantError("axis traversal max_depth must be positive")


@dataclass(frozen=True)
class AxisTraversalResult:
    """Grouped traversal result for a Concept Box."""

    box_id: str
    findings: tuple[AxisFinding, ...]
    proof_state: ProofState

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible traversal result."""

        return {
            "box_id": self.box_id,
            "findings": [finding.to_dict() for finding in self.findings],
            "proof_state": self.proof_state.value,
            "execution_approval": False,
        }


def traverse_concept_box(
    box: ConceptBox,
    *,
    related_boxes: Iterable[ConceptBox] = (),
    policy: AxisTraversalPolicy | None = None,
) -> AxisTraversalResult:
    """Traverse a Concept Box and emit candidate findings only."""

    active_policy = policy or AxisTraversalPolicy()
    if active_policy.max_depth < 1:
        raise RuntimeCoreInvariantError("axis traversal max_depth must be positive")
    related = tuple(related_boxes)
    findings: list[AxisFinding] = []
    findings.extend(_vertical_findings(box, active_policy.max_depth))
    findings.extend(_horizontal_findings(box, related))
    findings.extend(_circular_findings(box))
    findings.extend(_diagonal_findings(box))
    findings.extend(_temporal_findings(box))
    findings.extend(_intensity_findings(box))
    findings.extend(_meta_findings(box, active_policy))
    proof_state = ProofState.PASS if all(finding.delta_type == DeltaType.CONSTRUCTIVE for finding in findings) else ProofState.UNKNOWN
    return AxisTraversalResult(box_id=box.box_id, findings=tuple(findings), proof_state=proof_state)


def _finding(
    *,
    axis: TraversalAxis,
    box: ConceptBox,
    claim: str,
    confidence: float,
    suppression: SuppressionVector,
    delta_type: DeltaType,
    repair_requirement: str = "",
) -> AxisFinding:
    finding_id = stable_identifier(
        "axis-finding",
        {
            "axis": axis.value,
            "source_box_id": box.box_id,
            "claim": claim,
            "delta_type": delta_type.value,
        },
    )
    return AxisFinding(
        finding_id=finding_id,
        axis=axis,
        source_box_id=box.box_id,
        claim=claim,
        evidence_refs=box.evidence_refs,
        confidence=confidence,
        suppression=suppression,
        delta_type=delta_type,
        repair_requirement=repair_requirement,
        lineage_tag="InceptaDive-M:axis-traversal",
    )


def _vertical_findings(box: ConceptBox, max_depth: int) -> tuple[AxisFinding, ...]:
    facet_groups = (
        ("identity", box.identity_facets),
        ("behavior", box.behavior_facets),
        ("intention", box.intention_facets),
        ("cause", box.cause_facets),
        ("effect", box.effect_facets),
        ("risk", box.risk_facets),
    )
    findings: list[AxisFinding] = []
    for facet_name, facets in facet_groups[: max_depth + 3]:
        if facets:
            findings.append(
                _finding(
                    axis=TraversalAxis.VERTICAL,
                    box=box,
                    claim=f"{facet_name} facets are explicit for {box.box_id}",
                    confidence=0.82,
                    suppression=SuppressionVector(evidence_weakness=0.0 if box.evidence_refs else 0.35),
                    delta_type=DeltaType.CONSTRUCTIVE,
                )
            )
    return tuple(findings)


def _horizontal_findings(box: ConceptBox, related_boxes: Sequence[ConceptBox]) -> tuple[AxisFinding, ...]:
    findings: list[AxisFinding] = []
    source_notes = set(box.source_note_ids)
    evidence_refs = set(box.evidence_refs)
    for related in related_boxes:
        if related.box_id == box.box_id:
            continue
        shares_note = bool(source_notes.intersection(related.source_note_ids))
        shares_evidence = bool(evidence_refs.intersection(related.evidence_refs))
        if shares_note or shares_evidence:
            findings.append(
                _finding(
                    axis=TraversalAxis.HORIZONTAL,
                    box=box,
                    claim=f"{box.box_id} relates laterally to {related.box_id}",
                    confidence=0.76,
                    suppression=SuppressionVector(source_authority_weakness=0.1),
                    delta_type=DeltaType.CONSTRUCTIVE,
                )
            )
    return tuple(findings)


def _circular_findings(box: ConceptBox) -> tuple[AxisFinding, ...]:
    if not (box.cause_facets or box.effect_facets or box.behavior_facets):
        return ()
    return (
        _finding(
            axis=TraversalAxis.CIRCULAR,
            box=box,
            claim=f"{box.box_id} has candidate feedback loop material",
            confidence=0.68,
            suppression=SuppressionVector(evidence_weakness=0.0 if box.evidence_refs else 0.3),
            delta_type=DeltaType.CONSTRUCTIVE,
        ),
    )


def _diagonal_findings(box: ConceptBox) -> tuple[AxisFinding, ...]:
    return (
        _finding(
            axis=TraversalAxis.DIAGONAL,
            box=box,
            claim=f"{box.box_type.value} Box can connect note-memory state to workflow governance",
            confidence=0.62,
            suppression=SuppressionVector(source_authority_weakness=0.15),
            delta_type=DeltaType.CONSTRUCTIVE,
        ),
    )


def _temporal_findings(box: ConceptBox) -> tuple[AxisFinding, ...]:
    changed = box.created_at != box.updated_at
    return (
        _finding(
            axis=TraversalAxis.TEMPORAL,
            box=box,
            claim=f"{box.box_id} temporal state is {'evolved' if changed else 'single-snapshot'}",
            confidence=0.7,
            suppression=SuppressionVector(staleness=0.2 if changed else 0.0),
            delta_type=DeltaType.CONSTRUCTIVE,
        ),
    )


def _intensity_findings(box: ConceptBox) -> tuple[AxisFinding, ...]:
    if not box.risk_facets:
        return ()
    return (
        _finding(
            axis=TraversalAxis.INTENSITY,
            box=box,
            claim=f"{box.box_id} has high-intensity risk facets",
            confidence=0.74,
            suppression=SuppressionVector(execution_risk=0.65, privacy_safety_risk=0.15),
            delta_type=DeltaType.FRACTURE,
            repair_requirement="route risk facets to repair queue before action promotion",
        ),
    )


def _meta_findings(box: ConceptBox, policy: AxisTraversalPolicy) -> tuple[AxisFinding, ...]:
    if policy.require_evidence and not box.evidence_refs:
        return (
            _finding(
                axis=TraversalAxis.META,
                box=box,
                claim=f"{box.box_id} lacks evidence references for promotion",
                confidence=0.9,
                suppression=SuppressionVector(evidence_weakness=1.0),
                delta_type=DeltaType.FRACTURE,
                repair_requirement="attach evidence refs or keep finding as unpromoted projection",
            ),
        )
    return ()
