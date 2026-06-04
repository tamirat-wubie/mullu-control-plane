"""Purpose: audit and recommendation layer for document object geometry graphs.

Governance scope: deterministic inspection of geometry graphs, pixel witnesses,
layout risks, redaction proof state, and refinement recommendations.
Dependencies: document_object_geometry contracts and shared base helpers.
Invariants:
  - Audits are read-only and grant no execution authority.
  - Findings are explicit, typed, severity-bounded, and serializable.
  - Redaction uncertainty fails closed as a critical finding.
  - Recommendations are derived from findings, not free-form mutation commands.
  - Audit output is deterministic for the same graph and audit policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Sequence, TypeVar, cast

from ._base import (
    ContractRecord,
    freeze_value,
    require_finite_float,
    require_non_empty_text,
    require_non_negative_float,
    require_positive_int,
    require_unit_float,
)
from .document_object_geometry import (
    DocumentBBox,
    DocumentObject,
    DocumentObjectGraph,
    DocumentObjectType,
    LayoutRisk,
    LayoutRiskKind,
    PixelRegionWitness,
    PixelWitnessKind,
    PixelWitnessStatus,
)

TContract = TypeVar("TContract", bound=ContractRecord)
DOCUMENT_GEOMETRY_AUDIT_CONTRACT_VERSION = "document-geometry-audit.v1"
DEFAULT_REQUIRED_WITNESS_OBJECT_TYPES = (
    DocumentObjectType.SIGNATURE,
    DocumentObjectType.STAMP,
    DocumentObjectType.REDACTION_REGION,
)


class DocumentGeometryAuditStatus(StrEnum):
    """Terminal audit status for a geometry graph."""

    PASSED = "passed"
    PASSED_WITH_RECOMMENDATIONS = "passed_with_recommendations"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class AuditSeverity(StrEnum):
    """Bounded finding severity."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditCategory(StrEnum):
    """Governed audit area."""

    GEOMETRY = "geometry"
    PIXEL_WITNESS = "pixel_witness"
    SPATIAL_GRAPH = "spatial_graph"
    READING_ORDER = "reading_order"
    REDACTION = "redaction"
    LAYOUT_RISK = "layout_risk"
    COVERAGE = "coverage"


class RecommendationKind(StrEnum):
    """Machine-readable refinement recommendation kind."""

    ADD_PAGE_GEOMETRY = "add_page_geometry"
    ADD_PIXEL_WITNESS = "add_pixel_witness"
    ADD_READING_ORDER = "add_reading_order"
    ADD_SPATIAL_EDGES = "add_spatial_edges"
    PROVE_REDACTION = "prove_redaction"
    REVIEW_LAYOUT_RISK = "review_layout_risk"
    NORMALIZE_COORDINATE_SPACE = "normalize_coordinate_space"
    RAISE_GEOMETRY_CONFIDENCE = "raise_geometry_confidence"


_SEVERITY_RANK = {
    AuditSeverity.INFO: 0,
    AuditSeverity.WARNING: 1,
    AuditSeverity.ERROR: 2,
    AuditSeverity.CRITICAL: 3,
}


def _freeze_contract_tuple(
    values: tuple[TContract, ...] | list[TContract],
    field_name: str,
    record_type: type[TContract],
) -> tuple[TContract, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = cast(tuple[TContract, ...], freeze_value(list(values)))
    for idx, item in enumerate(frozen):
        if not isinstance(item, record_type):
            raise ValueError(f"{field_name}[{idx}] must be a {record_type.__name__}")
    return frozen


def _freeze_text_tuple(
    values: tuple[str, ...] | list[str],
    field_name: str,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = cast(tuple[str, ...], freeze_value(list(values)))
    for idx, value in enumerate(frozen):
        require_non_empty_text(value, f"{field_name}[{idx}]")
    return frozen


def _freeze_required_types(
    values: Sequence[DocumentObjectType],
) -> tuple[DocumentObjectType, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError("required_witness_object_types must be an array")
    frozen = cast(tuple[DocumentObjectType, ...], freeze_value(list(values)))
    for idx, value in enumerate(frozen):
        if not isinstance(value, DocumentObjectType):
            raise ValueError(
                f"required_witness_object_types[{idx}] must be a DocumentObjectType"
            )
    return frozen


def _max_severity(findings: Sequence["DocumentGeometryAuditFinding"]) -> AuditSeverity:
    severity = AuditSeverity.INFO
    for finding in findings:
        if _SEVERITY_RANK[finding.severity] > _SEVERITY_RANK[severity]:
            severity = finding.severity
    return severity


def _status_from_findings(
    findings: Sequence["DocumentGeometryAuditFinding"],
) -> DocumentGeometryAuditStatus:
    if not findings:
        return DocumentGeometryAuditStatus.PASSED
    severity = _max_severity(findings)
    if severity is AuditSeverity.CRITICAL:
        return DocumentGeometryAuditStatus.FAILED
    if severity is AuditSeverity.ERROR:
        return DocumentGeometryAuditStatus.NEEDS_REVIEW
    if severity is AuditSeverity.WARNING:
        return DocumentGeometryAuditStatus.NEEDS_REVIEW
    return DocumentGeometryAuditStatus.PASSED_WITH_RECOMMENDATIONS


@dataclass(frozen=True, slots=True)
class DocumentPageGeometry(ContractRecord):
    """Page bounds used to audit clipping and coordinate-space consistency."""

    page_number: int
    width: float
    height: float
    coordinate_space: str = "pixel"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "page_number",
            require_positive_int(self.page_number, "page_number"),
        )
        width = require_finite_float(self.width, "width")
        height = require_finite_float(self.height, "height")
        if width <= 0.0:
            raise ValueError("width must be positive")
        if height <= 0.0:
            raise ValueError("height must be positive")
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)
        object.__setattr__(
            self,
            "coordinate_space",
            require_non_empty_text(self.coordinate_space, "coordinate_space"),
        )

    def contains(self, bbox: DocumentBBox) -> bool:
        return (
            bbox.page_number == self.page_number
            and bbox.coordinate_space == self.coordinate_space
            and bbox.x0 >= 0.0
            and bbox.y0 >= 0.0
            and bbox.x1 <= self.width
            and bbox.y1 <= self.height
        )


@dataclass(frozen=True, slots=True)
class DocumentGeometryAuditPolicy(ContractRecord):
    """Read-only rules used by the geometry audit."""

    confidence_floor: float = 0.75
    require_reading_order: bool = True
    require_spatial_edges: bool = True
    require_redaction_proof: bool = True
    required_witness_object_types: tuple[DocumentObjectType, ...] = (
        DEFAULT_REQUIRED_WITNESS_OBJECT_TYPES
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "confidence_floor",
            require_unit_float(self.confidence_floor, "confidence_floor"),
        )
        if not isinstance(self.require_reading_order, bool):
            raise ValueError("require_reading_order must be a boolean")
        if not isinstance(self.require_spatial_edges, bool):
            raise ValueError("require_spatial_edges must be a boolean")
        if not isinstance(self.require_redaction_proof, bool):
            raise ValueError("require_redaction_proof must be a boolean")
        object.__setattr__(
            self,
            "required_witness_object_types",
            _freeze_required_types(self.required_witness_object_types),
        )


@dataclass(frozen=True, slots=True)
class DocumentGeometryAuditFinding(ContractRecord):
    """Typed finding emitted by the document geometry audit."""

    finding_id: str
    category: AuditCategory
    severity: AuditSeverity
    message: str
    recommendation_kind: RecommendationKind
    object_ids: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "finding_id",
            require_non_empty_text(self.finding_id, "finding_id"),
        )
        if not isinstance(self.category, AuditCategory):
            raise ValueError("category must be an AuditCategory value")
        if not isinstance(self.severity, AuditSeverity):
            raise ValueError("severity must be an AuditSeverity value")
        object.__setattr__(
            self,
            "message",
            require_non_empty_text(self.message, "message"),
        )
        if not isinstance(self.recommendation_kind, RecommendationKind):
            raise ValueError("recommendation_kind must be a RecommendationKind value")
        object.__setattr__(
            self,
            "object_ids",
            _freeze_text_tuple(self.object_ids, "object_ids"),
        )
        object.__setattr__(self, "evidence", _freeze_text_tuple(self.evidence, "evidence"))


@dataclass(frozen=True, slots=True)
class DocumentGeometryRecommendation(ContractRecord):
    """Actionable but non-executing recommendation derived from a finding."""

    recommendation_id: str
    kind: RecommendationKind
    priority: float
    message: str
    finding_ids: tuple[str, ...]
    object_ids: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "recommendation_id",
            require_non_empty_text(self.recommendation_id, "recommendation_id"),
        )
        if not isinstance(self.kind, RecommendationKind):
            raise ValueError("kind must be a RecommendationKind value")
        object.__setattr__(self, "priority", require_unit_float(self.priority, "priority"))
        object.__setattr__(
            self,
            "message",
            require_non_empty_text(self.message, "message"),
        )
        object.__setattr__(
            self,
            "finding_ids",
            _freeze_text_tuple(self.finding_ids, "finding_ids"),
        )
        if not self.finding_ids:
            raise ValueError("finding_ids must contain at least one item")
        object.__setattr__(
            self,
            "object_ids",
            _freeze_text_tuple(self.object_ids, "object_ids"),
        )
        object.__setattr__(self, "evidence", _freeze_text_tuple(self.evidence, "evidence"))


@dataclass(frozen=True, slots=True)
class DocumentGeometryAuditReport(ContractRecord):
    """Deterministic audit result for a document object graph."""

    doc_id: str
    source_hash: str
    status: DocumentGeometryAuditStatus
    findings: tuple[DocumentGeometryAuditFinding, ...]
    recommendations: tuple[DocumentGeometryRecommendation, ...]
    constructive_deltas: tuple[str, ...]
    fracture_deltas: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "doc_id", require_non_empty_text(self.doc_id, "doc_id"))
        object.__setattr__(
            self,
            "source_hash",
            require_non_empty_text(self.source_hash, "source_hash"),
        )
        if not isinstance(self.status, DocumentGeometryAuditStatus):
            raise ValueError("status must be a DocumentGeometryAuditStatus value")
        object.__setattr__(
            self,
            "findings",
            _freeze_contract_tuple(
                self.findings,
                "findings",
                DocumentGeometryAuditFinding,
            ),
        )
        object.__setattr__(
            self,
            "recommendations",
            _freeze_contract_tuple(
                self.recommendations,
                "recommendations",
                DocumentGeometryRecommendation,
            ),
        )
        object.__setattr__(
            self,
            "constructive_deltas",
            _freeze_text_tuple(self.constructive_deltas, "constructive_deltas"),
        )
        object.__setattr__(
            self,
            "fracture_deltas",
            _freeze_text_tuple(self.fracture_deltas, "fracture_deltas"),
        )
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        self._validate_references()

    def _validate_references(self) -> None:
        finding_ids = tuple(finding.finding_id for finding in self.findings)
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("findings must declare unique finding_id values")
        recommendation_ids = tuple(
            recommendation.recommendation_id for recommendation in self.recommendations
        )
        if len(recommendation_ids) != len(set(recommendation_ids)):
            raise ValueError("recommendations must declare unique recommendation_id values")
        finding_id_set = set(finding_ids)
        for recommendation in self.recommendations:
            if not set(recommendation.finding_ids) <= finding_id_set:
                raise ValueError("recommendation references an unknown finding")


@dataclass(frozen=True, slots=True)
class GeometryAuditAccumulator:
    """Internal deterministic accumulator for audit findings."""

    findings: tuple[DocumentGeometryAuditFinding, ...] = ()

    def add(self, finding: DocumentGeometryAuditFinding) -> "GeometryAuditAccumulator":
        return GeometryAuditAccumulator(findings=(*self.findings, finding))


def audit_document_object_graph(
    graph: DocumentObjectGraph,
    *,
    page_geometries: Sequence[DocumentPageGeometry] = (),
    policy: DocumentGeometryAuditPolicy | None = None,
) -> DocumentGeometryAuditReport:
    """Audit a document object graph without mutating it."""

    if not isinstance(graph, DocumentObjectGraph):
        raise ValueError("graph must be a DocumentObjectGraph")
    audit_policy = policy or DocumentGeometryAuditPolicy()
    page_geometry_tuple = _freeze_contract_tuple(
        tuple(page_geometries),
        "page_geometries",
        DocumentPageGeometry,
    )
    accumulator = GeometryAuditAccumulator()
    accumulator = _audit_coordinate_spaces(graph, page_geometry_tuple, accumulator)
    accumulator = _audit_reading_order(graph, audit_policy, accumulator)
    accumulator = _audit_spatial_edges(graph, audit_policy, accumulator)
    accumulator = _audit_confidence(graph, audit_policy, accumulator)
    accumulator = _audit_pixel_witnesses(graph, audit_policy, accumulator)
    accumulator = _audit_layout_risks(graph, accumulator)
    accumulator = _audit_page_bounds(graph, page_geometry_tuple, accumulator)

    findings = _dedupe_findings(accumulator.findings)
    recommendations = _recommendations_from_findings(findings)
    status = _status_from_findings(findings)
    return DocumentGeometryAuditReport(
        doc_id=graph.doc_id,
        source_hash=graph.source_hash,
        status=status,
        findings=findings,
        recommendations=recommendations,
        constructive_deltas=(
            "geometry_graph_audited",
            "pixel_witness_coverage_checked",
            "layout_risks_reviewed",
            "recommendations_derived_from_findings",
        ),
        fracture_deltas=_fracture_deltas(findings),
        metadata={
            "contract_version": DOCUMENT_GEOMETRY_AUDIT_CONTRACT_VERSION,
            "object_count": len(graph.objects),
            "finding_count": len(findings),
            "recommendation_count": len(recommendations),
        },
    )


def _audit_coordinate_spaces(
    graph: DocumentObjectGraph,
    page_geometries: tuple[DocumentPageGeometry, ...],
    accumulator: GeometryAuditAccumulator,
) -> GeometryAuditAccumulator:
    spaces = {obj.bbox.coordinate_space for obj in graph.objects}
    spaces.update(witness.bbox.coordinate_space for witness in graph.pixel_witnesses)
    spaces.update(page.coordinate_space for page in page_geometries)
    if len(spaces) > 1:
        return accumulator.add(
            DocumentGeometryAuditFinding(
                finding_id="finding_mixed_coordinate_spaces",
                category=AuditCategory.GEOMETRY,
                severity=AuditSeverity.WARNING,
                message="document graph uses multiple coordinate spaces",
                recommendation_kind=RecommendationKind.NORMALIZE_COORDINATE_SPACE,
                evidence=tuple(sorted(spaces)),
            )
        )
    if not page_geometries:
        return accumulator.add(
            DocumentGeometryAuditFinding(
                finding_id="finding_missing_page_geometry",
                category=AuditCategory.GEOMETRY,
                severity=AuditSeverity.INFO,
                message="page geometry was not supplied, so clipping audit is bounded",
                recommendation_kind=RecommendationKind.ADD_PAGE_GEOMETRY,
            )
        )
    return accumulator


def _audit_reading_order(
    graph: DocumentObjectGraph,
    policy: DocumentGeometryAuditPolicy,
    accumulator: GeometryAuditAccumulator,
) -> GeometryAuditAccumulator:
    if not policy.require_reading_order:
        return accumulator
    text_like = tuple(
        obj.object_id
        for obj in graph.objects
        if obj.object_type
        in {
            DocumentObjectType.HEADING,
            DocumentObjectType.PARAGRAPH,
            DocumentObjectType.TABLE_CELL,
            DocumentObjectType.FOOTNOTE,
            DocumentObjectType.FORM_FIELD,
        }
    )
    if not text_like:
        return accumulator
    if not graph.reading_order:
        return accumulator.add(
            DocumentGeometryAuditFinding(
                finding_id="finding_missing_reading_order",
                category=AuditCategory.READING_ORDER,
                severity=AuditSeverity.WARNING,
                message="text-like objects exist without an explicit reading order",
                recommendation_kind=RecommendationKind.ADD_READING_ORDER,
                object_ids=text_like,
            )
        )
    missing = tuple(object_id for object_id in text_like if object_id not in graph.reading_order)
    if missing:
        return accumulator.add(
            DocumentGeometryAuditFinding(
                finding_id="finding_partial_reading_order",
                category=AuditCategory.READING_ORDER,
                severity=AuditSeverity.WARNING,
                message="reading order omits one or more text-like objects",
                recommendation_kind=RecommendationKind.ADD_READING_ORDER,
                object_ids=missing,
            )
        )
    return accumulator


def _audit_spatial_edges(
    graph: DocumentObjectGraph,
    policy: DocumentGeometryAuditPolicy,
    accumulator: GeometryAuditAccumulator,
) -> GeometryAuditAccumulator:
    if policy.require_spatial_edges and len(graph.objects) > 1 and not graph.spatial_edges:
        return accumulator.add(
            DocumentGeometryAuditFinding(
                finding_id="finding_missing_spatial_edges",
                category=AuditCategory.SPATIAL_GRAPH,
                severity=AuditSeverity.WARNING,
                message="multiple objects exist without spatial relation edges",
                recommendation_kind=RecommendationKind.ADD_SPATIAL_EDGES,
                object_ids=tuple(obj.object_id for obj in graph.objects),
            )
        )
    return accumulator


def _audit_confidence(
    graph: DocumentObjectGraph,
    policy: DocumentGeometryAuditPolicy,
    accumulator: GeometryAuditAccumulator,
) -> GeometryAuditAccumulator:
    current = accumulator
    for obj in graph.objects:
        if obj.confidence < policy.confidence_floor:
            current = current.add(
                DocumentGeometryAuditFinding(
                    finding_id=f"finding_low_confidence_{obj.object_id}",
                    category=AuditCategory.GEOMETRY,
                    severity=AuditSeverity.WARNING,
                    message="object geometry confidence is below the audit floor",
                    recommendation_kind=RecommendationKind.RAISE_GEOMETRY_CONFIDENCE,
                    object_ids=(obj.object_id,),
                    evidence=(
                        f"confidence={obj.confidence:.6f}",
                        f"floor={policy.confidence_floor:.6f}",
                    ),
                )
            )
    return current


def _audit_pixel_witnesses(
    graph: DocumentObjectGraph,
    policy: DocumentGeometryAuditPolicy,
    accumulator: GeometryAuditAccumulator,
) -> GeometryAuditAccumulator:
    current = accumulator
    for obj in graph.objects:
        object_witnesses = _witnesses_for_object(graph.pixel_witnesses, obj.object_id)
        if obj.object_type in policy.required_witness_object_types and not object_witnesses:
            severity = AuditSeverity.ERROR
            recommendation = RecommendationKind.ADD_PIXEL_WITNESS
            if obj.object_type == DocumentObjectType.REDACTION_REGION:
                severity = AuditSeverity.CRITICAL
                recommendation = RecommendationKind.PROVE_REDACTION
            current = current.add(
                DocumentGeometryAuditFinding(
                    finding_id=f"finding_missing_pixel_witness_{obj.object_id}",
                    category=AuditCategory.PIXEL_WITNESS,
                    severity=severity,
                    message="required high-trust document object lacks a pixel witness",
                    recommendation_kind=recommendation,
                    object_ids=(obj.object_id,),
                    evidence=(f"object_type={obj.object_type.value}",),
                )
            )
        if policy.require_redaction_proof and obj.object_type == DocumentObjectType.REDACTION_REGION:
            current = _audit_redaction_proof(obj, object_witnesses, current)
        current = _audit_witness_statuses(obj, object_witnesses, current)
    return current


def _audit_redaction_proof(
    obj: DocumentObject,
    witnesses: tuple[PixelRegionWitness, ...],
    accumulator: GeometryAuditAccumulator,
) -> GeometryAuditAccumulator:
    proof_witnesses = tuple(
        witness
        for witness in witnesses
        if witness.witness_kind == PixelWitnessKind.REDACTION_PROOF
    )
    if not proof_witnesses:
        return accumulator.add(
            DocumentGeometryAuditFinding(
                finding_id=f"finding_missing_redaction_proof_{obj.object_id}",
                category=AuditCategory.REDACTION,
                severity=AuditSeverity.CRITICAL,
                message="redaction region has no destructive redaction proof witness",
                recommendation_kind=RecommendationKind.PROVE_REDACTION,
                object_ids=(obj.object_id,),
            )
        )
    if not any(witness.status == PixelWitnessStatus.PASSED for witness in proof_witnesses):
        return accumulator.add(
            DocumentGeometryAuditFinding(
                finding_id=f"finding_unpassed_redaction_proof_{obj.object_id}",
                category=AuditCategory.REDACTION,
                severity=AuditSeverity.CRITICAL,
                message="redaction proof exists but no proof witness has passed status",
                recommendation_kind=RecommendationKind.PROVE_REDACTION,
                object_ids=(obj.object_id,),
                evidence=tuple(witness.status.value for witness in proof_witnesses),
            )
        )
    return accumulator


def _audit_witness_statuses(
    obj: DocumentObject,
    witnesses: tuple[PixelRegionWitness, ...],
    accumulator: GeometryAuditAccumulator,
) -> GeometryAuditAccumulator:
    current = accumulator
    for witness in witnesses:
        if witness.status in {PixelWitnessStatus.CANDIDATE, PixelWitnessStatus.NEEDS_REVIEW}:
            current = current.add(
                DocumentGeometryAuditFinding(
                    finding_id=f"finding_unverified_witness_{witness.witness_id}",
                    category=AuditCategory.PIXEL_WITNESS,
                    severity=AuditSeverity.WARNING,
                    message="pixel witness is not yet terminally verified",
                    recommendation_kind=RecommendationKind.ADD_PIXEL_WITNESS,
                    object_ids=(obj.object_id,),
                    evidence=(f"status={witness.status.value}",),
                )
            )
        if witness.status == PixelWitnessStatus.FAILED:
            current = current.add(
                DocumentGeometryAuditFinding(
                    finding_id=f"finding_failed_witness_{witness.witness_id}",
                    category=AuditCategory.PIXEL_WITNESS,
                    severity=AuditSeverity.ERROR,
                    message="pixel witness is explicitly failed",
                    recommendation_kind=RecommendationKind.ADD_PIXEL_WITNESS,
                    object_ids=(obj.object_id,),
                )
            )
    return current


def _audit_layout_risks(
    graph: DocumentObjectGraph,
    accumulator: GeometryAuditAccumulator,
) -> GeometryAuditAccumulator:
    current = accumulator
    for risk in graph.layout_risks:
        current = current.add(_finding_from_layout_risk(risk))
    return current


def _finding_from_layout_risk(risk: LayoutRisk) -> DocumentGeometryAuditFinding:
    severity = AuditSeverity.INFO
    if risk.severity >= 0.33:
        severity = AuditSeverity.WARNING
    if risk.severity >= 0.66:
        severity = AuditSeverity.ERROR
    if risk.risk_kind == LayoutRiskKind.REDACTION_OVERLAY_RISK:
        severity = AuditSeverity.CRITICAL
    return DocumentGeometryAuditFinding(
        finding_id=f"finding_layout_risk_{risk.risk_id}",
        category=AuditCategory.LAYOUT_RISK,
        severity=severity,
        message="layout risk is present in the document object graph",
        recommendation_kind=RecommendationKind.REVIEW_LAYOUT_RISK,
        object_ids=risk.object_ids,
        evidence=(risk.risk_kind.value, f"severity={risk.severity:.6f}", *risk.evidence),
    )


def _audit_page_bounds(
    graph: DocumentObjectGraph,
    page_geometries: tuple[DocumentPageGeometry, ...],
    accumulator: GeometryAuditAccumulator,
) -> GeometryAuditAccumulator:
    if not page_geometries:
        return accumulator
    page_by_key = {
        (page.page_number, page.coordinate_space): page for page in page_geometries
    }
    current = accumulator
    for obj in graph.objects:
        page = page_by_key.get((obj.bbox.page_number, obj.bbox.coordinate_space))
        if page is None:
            current = current.add(
                DocumentGeometryAuditFinding(
                    finding_id=f"finding_missing_bounds_{obj.object_id}",
                    category=AuditCategory.GEOMETRY,
                    severity=AuditSeverity.INFO,
                    message="object page or coordinate space has no page geometry bounds",
                    recommendation_kind=RecommendationKind.ADD_PAGE_GEOMETRY,
                    object_ids=(obj.object_id,),
                    evidence=(
                        f"page={obj.bbox.page_number}",
                        f"space={obj.bbox.coordinate_space}",
                    ),
                )
            )
        elif not page.contains(obj.bbox):
            current = current.add(
                DocumentGeometryAuditFinding(
                    finding_id=f"finding_clipped_object_{obj.object_id}",
                    category=AuditCategory.GEOMETRY,
                    severity=AuditSeverity.ERROR,
                    message="object geometry extends outside supplied page bounds",
                    recommendation_kind=RecommendationKind.REVIEW_LAYOUT_RISK,
                    object_ids=(obj.object_id,),
                    evidence=(
                        f"page_width={page.width:.6f}",
                        f"page_height={page.height:.6f}",
                        f"bbox={obj.bbox.region_key()}",
                    ),
                )
            )
    return current


def _witnesses_for_object(
    witnesses: Sequence[PixelRegionWitness],
    object_id: str,
) -> tuple[PixelRegionWitness, ...]:
    return tuple(witness for witness in witnesses if witness.source_object_id == object_id)


def _recommendations_from_findings(
    findings: tuple[DocumentGeometryAuditFinding, ...],
) -> tuple[DocumentGeometryRecommendation, ...]:
    grouped: dict[RecommendationKind, list[DocumentGeometryAuditFinding]] = {}
    for finding in findings:
        grouped.setdefault(finding.recommendation_kind, []).append(finding)

    recommendations: list[DocumentGeometryRecommendation] = []
    for idx, kind in enumerate(sorted(grouped, key=lambda item: item.value), start=1):
        finding_group = tuple(grouped[kind])
        severity = _max_severity(finding_group)
        priority = _priority_from_severity(severity)
        object_ids = tuple(
            sorted({object_id for finding in finding_group for object_id in finding.object_ids})
        )
        recommendations.append(
            DocumentGeometryRecommendation(
                recommendation_id=f"recommendation_{idx:03d}_{kind.value}",
                kind=kind,
                priority=priority,
                message=_recommendation_message(kind),
                finding_ids=tuple(finding.finding_id for finding in finding_group),
                object_ids=object_ids,
                evidence=tuple(f"finding_count={len(finding_group)}" for _ in (0,)),
            )
        )
    return tuple(recommendations)


def _priority_from_severity(severity: AuditSeverity) -> float:
    if severity is AuditSeverity.CRITICAL:
        return 1.0
    if severity is AuditSeverity.ERROR:
        return 0.8
    if severity is AuditSeverity.WARNING:
        return 0.5
    return 0.2


def _recommendation_message(kind: RecommendationKind) -> str:
    messages = {
        RecommendationKind.ADD_PAGE_GEOMETRY: "provide page bounds for full clipping audit",
        RecommendationKind.ADD_PIXEL_WITNESS: "add or verify pixel witnesses for high-trust objects",
        RecommendationKind.ADD_READING_ORDER: "derive and attach geometry-aware reading order",
        RecommendationKind.ADD_SPATIAL_EDGES: "derive and attach spatial relation edges",
        RecommendationKind.PROVE_REDACTION: "produce passed destructive redaction proof witnesses",
        RecommendationKind.REVIEW_LAYOUT_RISK: "review and remediate layout risk findings",
        RecommendationKind.NORMALIZE_COORDINATE_SPACE: "normalize object geometry to one coordinate space",
        RecommendationKind.RAISE_GEOMETRY_CONFIDENCE: "rerun extraction or route low-confidence objects to review",
    }
    return messages[kind]


def _fracture_deltas(
    findings: tuple[DocumentGeometryAuditFinding, ...],
) -> tuple[str, ...]:
    return tuple(
        finding.finding_id
        for finding in findings
        if finding.severity in {AuditSeverity.ERROR, AuditSeverity.CRITICAL}
    )


def _dedupe_findings(
    findings: tuple[DocumentGeometryAuditFinding, ...],
) -> tuple[DocumentGeometryAuditFinding, ...]:
    deduped: dict[str, DocumentGeometryAuditFinding] = {}
    for finding in findings:
        deduped.setdefault(finding.finding_id, finding)
    return tuple(deduped.values())


def audit_confidence_score(report: DocumentGeometryAuditReport) -> float:
    """Return a bounded confidence score for the audit report."""

    if not isinstance(report, DocumentGeometryAuditReport):
        raise ValueError("report must be a DocumentGeometryAuditReport")
    if not report.findings:
        return 1.0
    penalty = 0.0
    for finding in report.findings:
        penalty += {
            AuditSeverity.INFO: 0.02,
            AuditSeverity.WARNING: 0.10,
            AuditSeverity.ERROR: 0.25,
            AuditSeverity.CRITICAL: 0.50,
        }[finding.severity]
    return max(0.0, 1.0 - require_non_negative_float(penalty, "penalty"))
