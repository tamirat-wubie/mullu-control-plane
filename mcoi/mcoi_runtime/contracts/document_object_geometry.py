"""Purpose: document object geometry and pixel witness contracts.

Governance scope: document geometry typing, spatial graph evidence, layout-risk
classification, and pixel-region witness anchoring only.
Dependencies: shared contract base helpers and Python standard library.
Invariants:
  - Geometry is finite, page-scoped, and positive-area.
  - Pixel witnesses bind rendered regions to page, geometry, and pixel digest.
  - Spatial edges reference admitted document objects only.
  - Layout risks remain explicit typed records, not silent warnings.
  - Contract helpers are deterministic and grant no execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
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

TContract = TypeVar("TContract", bound=ContractRecord)
DOCUMENT_OBJECT_GEOMETRY_CONTRACT_VERSION = "document-object-geometry.v1"


class DocumentObjectType(StrEnum):
    """Visible or inferred page object categories."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    TABLE_CELL = "table_cell"
    FIGURE = "figure"
    IMAGE = "image"
    CHART = "chart"
    SIGNATURE = "signature"
    STAMP = "stamp"
    CHECKBOX = "checkbox"
    FORM_FIELD = "form_field"
    WATERMARK = "watermark"
    FOOTER = "footer"
    HEADER = "header"
    FOOTNOTE = "footnote"
    CITATION_MARKER = "citation_marker"
    REDACTION_REGION = "redaction_region"
    UNKNOWN = "unknown"


class SpatialRelation(StrEnum):
    """Directed geometric relation between two document objects."""

    ABOVE = "above"
    BELOW = "below"
    LEFT_OF = "left_of"
    RIGHT_OF = "right_of"
    CONTAINS = "contains"
    OVERLAPS = "overlaps"
    ALIGNED_WITH = "aligned_with"
    NEAR = "near"
    CAPTION_OF = "caption_of"
    HEADER_OF = "header_of"
    CELL_OF = "cell_of"


class LayoutRiskKind(StrEnum):
    """Typed layout fracture classes emitted by geometry validation."""

    OVERLAP = "overlap"
    CLIPPING = "clipping"
    MARGIN_VIOLATION = "margin_violation"
    READING_ORDER_ANOMALY = "reading_order_anomaly"
    REDACTION_OVERLAY_RISK = "redaction_overlay_risk"
    LOW_CONFIDENCE_GEOMETRY = "low_confidence_geometry"


class PixelWitnessKind(StrEnum):
    """Pixel-region witness purposes."""

    REGION_HASH = "region_hash"
    PAGE_RENDER_HASH = "page_render_hash"
    BEFORE_AFTER_DIFF = "before_after_diff"
    REDACTION_PROOF = "redaction_proof"
    SIGNATURE_ANCHOR = "signature_anchor"


class PixelWitnessStatus(StrEnum):
    """Lifecycle status for a pixel witness."""

    CANDIDATE = "candidate"
    PASSED = "passed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


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


def _freeze_optional_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return require_non_empty_text(value, field_name)


def _positive_finite(value: float, field_name: str) -> float:
    checked = require_finite_float(value, field_name)
    if checked <= 0.0:
        raise ValueError(f"{field_name} must be positive")
    return checked


def _object_ids(objects: Sequence["DocumentObject"]) -> tuple[str, ...]:
    return tuple(obj.object_id for obj in objects)


@dataclass(frozen=True, slots=True)
class CoordinatePoint(ContractRecord):
    """One point in a document coordinate system."""

    x: float
    y: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", require_finite_float(self.x, "x"))
        object.__setattr__(self, "y", require_finite_float(self.y, "y"))


@dataclass(frozen=True, slots=True)
class DocumentBBox(ContractRecord):
    """Positive-area page-scoped bounding box."""

    page_number: int
    x0: float
    y0: float
    x1: float
    y1: float
    coordinate_space: str = "pixel"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "page_number",
            require_positive_int(self.page_number, "page_number"),
        )
        object.__setattr__(self, "x0", require_finite_float(self.x0, "x0"))
        object.__setattr__(self, "y0", require_finite_float(self.y0, "y0"))
        object.__setattr__(self, "x1", require_finite_float(self.x1, "x1"))
        object.__setattr__(self, "y1", require_finite_float(self.y1, "y1"))
        object.__setattr__(
            self,
            "coordinate_space",
            require_non_empty_text(self.coordinate_space, "coordinate_space"),
        )
        if self.x1 <= self.x0:
            raise ValueError("x1 must be greater than x0")
        if self.y1 <= self.y0:
            raise ValueError("y1 must be greater than y0")

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center_x(self) -> float:
        return self.x0 + (self.width / 2.0)

    @property
    def center_y(self) -> float:
        return self.y0 + (self.height / 2.0)

    def same_page(self, other: "DocumentBBox") -> bool:
        return self.page_number == other.page_number

    def intersection_area(self, other: "DocumentBBox") -> float:
        if not self.same_page(other):
            return 0.0
        x_overlap = max(0.0, min(self.x1, other.x1) - max(self.x0, other.x0))
        y_overlap = max(0.0, min(self.y1, other.y1) - max(self.y0, other.y0))
        return x_overlap * y_overlap

    def overlap_ratio(self, other: "DocumentBBox") -> float:
        intersection = self.intersection_area(other)
        if intersection == 0.0:
            return 0.0
        return intersection / min(self.area, other.area)

    def contains(self, other: "DocumentBBox") -> bool:
        if not self.same_page(other):
            return False
        return (
            self.x0 <= other.x0
            and self.y0 <= other.y0
            and self.x1 >= other.x1
            and self.y1 >= other.y1
        )

    def region_key(self) -> str:
        values = (
            self.page_number,
            round(self.x0, 6),
            round(self.y0, 6),
            round(self.x1, 6),
            round(self.y1, 6),
            self.coordinate_space,
        )
        return ":".join(str(value) for value in values)


@dataclass(frozen=True, slots=True)
class DocumentObject(ContractRecord):
    """A governed visible or inferred document object."""

    object_id: str
    object_type: DocumentObjectType
    bbox: DocumentBBox
    polygon: tuple[CoordinatePoint, ...] = ()
    z_index: int = 0
    text_ref: str | None = None
    style_ref: str | None = None
    semantic_role: str | None = None
    confidence: float = 1.0
    source_pixel_hash: str | None = None
    edit_permissions: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "object_id",
            require_non_empty_text(self.object_id, "object_id"),
        )
        if not isinstance(self.object_type, DocumentObjectType):
            raise ValueError("object_type must be a DocumentObjectType value")
        if not isinstance(self.bbox, DocumentBBox):
            raise ValueError("bbox must be a DocumentBBox")
        object.__setattr__(
            self,
            "polygon",
            _freeze_contract_tuple(self.polygon, "polygon", CoordinatePoint),
        )
        if not isinstance(self.z_index, int) or isinstance(self.z_index, bool):
            raise ValueError("z_index must be an integer")
        object.__setattr__(self, "text_ref", _freeze_optional_text(self.text_ref, "text_ref"))
        object.__setattr__(self, "style_ref", _freeze_optional_text(self.style_ref, "style_ref"))
        object.__setattr__(
            self,
            "semantic_role",
            _freeze_optional_text(self.semantic_role, "semantic_role"),
        )
        object.__setattr__(
            self,
            "confidence",
            require_unit_float(self.confidence, "confidence"),
        )
        object.__setattr__(
            self,
            "source_pixel_hash",
            _freeze_optional_text(self.source_pixel_hash, "source_pixel_hash"),
        )
        object.__setattr__(
            self,
            "edit_permissions",
            _freeze_text_tuple(self.edit_permissions, "edit_permissions"),
        )
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class DocumentSpatialEdge(ContractRecord):
    """Directed geometry relation between two document objects."""

    edge_id: str
    source_object_id: str
    target_object_id: str
    relation: SpatialRelation
    confidence: float = 1.0
    evidence: tuple[str, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", require_non_empty_text(self.edge_id, "edge_id"))
        object.__setattr__(
            self,
            "source_object_id",
            require_non_empty_text(self.source_object_id, "source_object_id"),
        )
        object.__setattr__(
            self,
            "target_object_id",
            require_non_empty_text(self.target_object_id, "target_object_id"),
        )
        if self.source_object_id == self.target_object_id:
            raise ValueError("spatial edge must connect two distinct objects")
        if not isinstance(self.relation, SpatialRelation):
            raise ValueError("relation must be a SpatialRelation value")
        object.__setattr__(
            self,
            "confidence",
            require_unit_float(self.confidence, "confidence"),
        )
        object.__setattr__(self, "evidence", _freeze_text_tuple(self.evidence, "evidence"))
        object.__setattr__(self, "metrics", freeze_value(self.metrics))


@dataclass(frozen=True, slots=True)
class LayoutRisk(ContractRecord):
    """Explicit layout fracture or review-needed signal."""

    risk_id: str
    risk_kind: LayoutRiskKind
    object_ids: tuple[str, ...]
    severity: float
    description: str
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "risk_id", require_non_empty_text(self.risk_id, "risk_id"))
        if not isinstance(self.risk_kind, LayoutRiskKind):
            raise ValueError("risk_kind must be a LayoutRiskKind value")
        object.__setattr__(
            self,
            "object_ids",
            _freeze_text_tuple(self.object_ids, "object_ids"),
        )
        if not self.object_ids:
            raise ValueError("object_ids must contain at least one item")
        object.__setattr__(
            self,
            "severity",
            require_unit_float(self.severity, "severity"),
        )
        object.__setattr__(
            self,
            "description",
            require_non_empty_text(self.description, "description"),
        )
        object.__setattr__(self, "evidence", _freeze_text_tuple(self.evidence, "evidence"))


@dataclass(frozen=True, slots=True)
class PixelRegionWitness(ContractRecord):
    """Evidence that a rendered pixel region was bound to a document object."""

    witness_id: str
    witness_kind: PixelWitnessKind
    page_number: int
    bbox: DocumentBBox
    region_hash: str
    rendered_page_hash: str
    status: PixelWitnessStatus = PixelWitnessStatus.CANDIDATE
    source_object_id: str | None = None
    confidence: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "witness_id",
            require_non_empty_text(self.witness_id, "witness_id"),
        )
        if not isinstance(self.witness_kind, PixelWitnessKind):
            raise ValueError("witness_kind must be a PixelWitnessKind value")
        object.__setattr__(
            self,
            "page_number",
            require_positive_int(self.page_number, "page_number"),
        )
        if not isinstance(self.bbox, DocumentBBox):
            raise ValueError("bbox must be a DocumentBBox")
        if self.bbox.page_number != self.page_number:
            raise ValueError("bbox page_number must match witness page_number")
        object.__setattr__(
            self,
            "region_hash",
            require_non_empty_text(self.region_hash, "region_hash"),
        )
        object.__setattr__(
            self,
            "rendered_page_hash",
            require_non_empty_text(self.rendered_page_hash, "rendered_page_hash"),
        )
        if not isinstance(self.status, PixelWitnessStatus):
            raise ValueError("status must be a PixelWitnessStatus value")
        object.__setattr__(
            self,
            "source_object_id",
            _freeze_optional_text(self.source_object_id, "source_object_id"),
        )
        object.__setattr__(
            self,
            "confidence",
            require_unit_float(self.confidence, "confidence"),
        )
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class DocumentObjectGraph(ContractRecord):
    """Geometry-aware document graph with pixel witnesses and layout risks."""

    doc_id: str
    source_hash: str
    objects: tuple[DocumentObject, ...]
    spatial_edges: tuple[DocumentSpatialEdge, ...] = ()
    pixel_witnesses: tuple[PixelRegionWitness, ...] = ()
    layout_risks: tuple[LayoutRisk, ...] = ()
    reading_order: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "doc_id", require_non_empty_text(self.doc_id, "doc_id"))
        object.__setattr__(
            self,
            "source_hash",
            require_non_empty_text(self.source_hash, "source_hash"),
        )
        object.__setattr__(
            self,
            "objects",
            _freeze_contract_tuple(self.objects, "objects", DocumentObject),
        )
        if not self.objects:
            raise ValueError("objects must contain at least one item")
        object.__setattr__(
            self,
            "spatial_edges",
            _freeze_contract_tuple(
                self.spatial_edges,
                "spatial_edges",
                DocumentSpatialEdge,
            ),
        )
        object.__setattr__(
            self,
            "pixel_witnesses",
            _freeze_contract_tuple(
                self.pixel_witnesses,
                "pixel_witnesses",
                PixelRegionWitness,
            ),
        )
        object.__setattr__(
            self,
            "layout_risks",
            _freeze_contract_tuple(self.layout_risks, "layout_risks", LayoutRisk),
        )
        object.__setattr__(
            self,
            "reading_order",
            _freeze_text_tuple(self.reading_order, "reading_order"),
        )
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        self._validate_references()

    def _validate_references(self) -> None:
        object_ids = _object_ids(self.objects)
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("objects must declare unique object_id values")

        edge_ids = tuple(edge.edge_id for edge in self.spatial_edges)
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("spatial_edges must declare unique edge_id values")

        witness_ids = tuple(witness.witness_id for witness in self.pixel_witnesses)
        if len(witness_ids) != len(set(witness_ids)):
            raise ValueError("pixel_witnesses must declare unique witness_id values")

        risk_ids = tuple(risk.risk_id for risk in self.layout_risks)
        if len(risk_ids) != len(set(risk_ids)):
            raise ValueError("layout_risks must declare unique risk_id values")

        object_id_set = set(object_ids)
        for edge in self.spatial_edges:
            if edge.source_object_id not in object_id_set:
                raise ValueError("spatial edge source object is unknown")
            if edge.target_object_id not in object_id_set:
                raise ValueError("spatial edge target object is unknown")

        for witness in self.pixel_witnesses:
            if witness.source_object_id is not None and witness.source_object_id not in object_id_set:
                raise ValueError("pixel witness source object is unknown")

        for risk in self.layout_risks:
            if not set(risk.object_ids) <= object_id_set:
                raise ValueError("layout risk references an unknown object")

        if len(self.reading_order) != len(set(self.reading_order)):
            raise ValueError("reading_order must not contain duplicates")
        if not set(self.reading_order) <= object_id_set:
            raise ValueError("reading_order references an unknown object")

    def object_by_id(self, object_id: str) -> DocumentObject:
        target = require_non_empty_text(object_id, "object_id")
        for obj in self.objects:
            if obj.object_id == target:
                return obj
        raise KeyError(target)

    def objects_in_reading_order(self) -> tuple[DocumentObject, ...]:
        if not self.reading_order:
            return self.objects
        by_id = {obj.object_id: obj for obj in self.objects}
        ordered = [by_id[object_id] for object_id in self.reading_order]
        remainder = [obj for obj in self.objects if obj.object_id not in self.reading_order]
        return tuple(ordered + remainder)


def alignment_error(first: DocumentBBox, second: DocumentBBox) -> float:
    """Smallest left/center/right alignment distance between two boxes."""

    if not first.same_page(second):
        return float("inf")
    return min(
        abs(first.x0 - second.x0),
        abs(first.center_x - second.center_x),
        abs(first.x1 - second.x1),
    )


def visual_density(occupied_pixel_area: float, region: DocumentBBox) -> float:
    """Return occupied-area ratio for a positive page region."""

    occupied = require_non_negative_float(occupied_pixel_area, "occupied_pixel_area")
    if occupied > region.area:
        raise ValueError("occupied_pixel_area must not exceed region area")
    return occupied / region.area


def pixel_region_hash(
    *,
    page_number: int,
    bbox: DocumentBBox,
    rendered_pixel_hash: str,
    algorithm: str = "sha256",
) -> str:
    """Hash a rendered page-region witness binding."""

    if algorithm != "sha256":
        raise ValueError("algorithm must be sha256")
    checked_page = require_positive_int(page_number, "page_number")
    if bbox.page_number != checked_page:
        raise ValueError("bbox page_number must match page_number")
    pixel_hash = require_non_empty_text(rendered_pixel_hash, "rendered_pixel_hash")
    payload = {
        "algorithm": algorithm,
        "bbox": bbox.to_json_dict(),
        "contract_version": DOCUMENT_OBJECT_GEOMETRY_CONTRACT_VERSION,
        "page_number": checked_page,
        "rendered_pixel_hash": pixel_hash,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_region_witness(
    *,
    witness_id: str,
    witness_kind: PixelWitnessKind,
    bbox: DocumentBBox,
    rendered_pixel_hash: str,
    rendered_page_hash: str,
    source_object_id: str | None = None,
    status: PixelWitnessStatus = PixelWitnessStatus.CANDIDATE,
    confidence: float = 1.0,
) -> PixelRegionWitness:
    """Construct a pixel witness with a deterministic region hash."""

    return PixelRegionWitness(
        witness_id=witness_id,
        witness_kind=witness_kind,
        page_number=bbox.page_number,
        bbox=bbox,
        region_hash=pixel_region_hash(
            page_number=bbox.page_number,
            bbox=bbox,
            rendered_pixel_hash=rendered_pixel_hash,
        ),
        rendered_page_hash=rendered_page_hash,
        status=status,
        source_object_id=source_object_id,
        confidence=confidence,
    )


def _axis_gap(first: DocumentBBox, second: DocumentBBox) -> tuple[float, float]:
    if not first.same_page(second):
        return (float("inf"), float("inf"))
    x_gap = max(0.0, max(first.x0, second.x0) - min(first.x1, second.x1))
    y_gap = max(0.0, max(first.y0, second.y0) - min(first.y1, second.y1))
    return x_gap, y_gap


def build_spatial_edges(
    objects: Sequence[DocumentObject],
    *,
    overlap_threshold: float = 0.0,
    alignment_tolerance: float = 2.0,
    near_distance: float = 24.0,
) -> tuple[DocumentSpatialEdge, ...]:
    """Derive deterministic spatial edges from object bounding boxes."""

    frozen_objects = tuple(objects)
    overlap_limit = require_unit_float(overlap_threshold, "overlap_threshold")
    align_limit = require_non_negative_float(alignment_tolerance, "alignment_tolerance")
    near_limit = require_non_negative_float(near_distance, "near_distance")
    edges: list[DocumentSpatialEdge] = []

    for idx, first in enumerate(frozen_objects):
        if not isinstance(first, DocumentObject):
            raise ValueError("objects must contain DocumentObject records")
        for second in frozen_objects[idx + 1 :]:
            if not isinstance(second, DocumentObject):
                raise ValueError("objects must contain DocumentObject records")
            if not first.bbox.same_page(second.bbox):
                continue

            overlap = first.bbox.overlap_ratio(second.bbox)
            metrics = {
                "alignment_error": alignment_error(first.bbox, second.bbox),
                "overlap_ratio": overlap,
            }

            if first.bbox.contains(second.bbox):
                edges.append(
                    DocumentSpatialEdge(
                        edge_id=f"edge_{first.object_id}_contains_{second.object_id}",
                        source_object_id=first.object_id,
                        target_object_id=second.object_id,
                        relation=SpatialRelation.CONTAINS,
                        metrics=metrics,
                    )
                )
            elif second.bbox.contains(first.bbox):
                edges.append(
                    DocumentSpatialEdge(
                        edge_id=f"edge_{second.object_id}_contains_{first.object_id}",
                        source_object_id=second.object_id,
                        target_object_id=first.object_id,
                        relation=SpatialRelation.CONTAINS,
                        metrics=metrics,
                    )
                )
            elif overlap > overlap_limit:
                edges.append(
                    DocumentSpatialEdge(
                        edge_id=f"edge_{first.object_id}_overlaps_{second.object_id}",
                        source_object_id=first.object_id,
                        target_object_id=second.object_id,
                        relation=SpatialRelation.OVERLAPS,
                        confidence=min(1.0, overlap),
                        metrics=metrics,
                    )
                )

            if first.bbox.y1 <= second.bbox.y0:
                relation = SpatialRelation.ABOVE
            elif first.bbox.y0 >= second.bbox.y1:
                relation = SpatialRelation.BELOW
            elif first.bbox.x1 <= second.bbox.x0:
                relation = SpatialRelation.LEFT_OF
            elif first.bbox.x0 >= second.bbox.x1:
                relation = SpatialRelation.RIGHT_OF
            else:
                relation = None

            if relation is not None:
                edges.append(
                    DocumentSpatialEdge(
                        edge_id=f"edge_{first.object_id}_{relation.value}_{second.object_id}",
                        source_object_id=first.object_id,
                        target_object_id=second.object_id,
                        relation=relation,
                        metrics=metrics,
                    )
                )

            x_gap, y_gap = _axis_gap(first.bbox, second.bbox)
            if min(x_gap, y_gap) <= near_limit:
                edges.append(
                    DocumentSpatialEdge(
                        edge_id=f"edge_{first.object_id}_near_{second.object_id}",
                        source_object_id=first.object_id,
                        target_object_id=second.object_id,
                        relation=SpatialRelation.NEAR,
                        metrics={**metrics, "x_gap": x_gap, "y_gap": y_gap},
                    )
                )

            if metrics["alignment_error"] <= align_limit:
                edges.append(
                    DocumentSpatialEdge(
                        edge_id=f"edge_{first.object_id}_aligned_with_{second.object_id}",
                        source_object_id=first.object_id,
                        target_object_id=second.object_id,
                        relation=SpatialRelation.ALIGNED_WITH,
                        metrics=metrics,
                    )
                )

    deduped: dict[str, DocumentSpatialEdge] = {}
    for edge in edges:
        deduped.setdefault(edge.edge_id, edge)
    return tuple(deduped.values())


def detect_layout_risks(
    objects: Sequence[DocumentObject],
    *,
    page_width: float,
    page_height: float,
    overlap_threshold: float = 0.01,
    confidence_floor: float = 0.5,
) -> tuple[LayoutRisk, ...]:
    """Detect bounded geometry risks from object locations."""

    frozen_objects = tuple(objects)
    checked_width = _positive_finite(page_width, "page_width")
    checked_height = _positive_finite(page_height, "page_height")
    overlap_limit = require_unit_float(overlap_threshold, "overlap_threshold")
    min_confidence = require_unit_float(confidence_floor, "confidence_floor")
    risks: list[LayoutRisk] = []

    for obj in frozen_objects:
        if not isinstance(obj, DocumentObject):
            raise ValueError("objects must contain DocumentObject records")
        bbox = obj.bbox
        if bbox.x0 < 0.0 or bbox.y0 < 0.0 or bbox.x1 > checked_width or bbox.y1 > checked_height:
            risks.append(
                LayoutRisk(
                    risk_id=f"risk_clipping_{obj.object_id}",
                    risk_kind=LayoutRiskKind.CLIPPING,
                    object_ids=(obj.object_id,),
                    severity=1.0,
                    description="object geometry extends outside the rendered page bounds",
                )
            )
        if obj.confidence < min_confidence:
            risks.append(
                LayoutRisk(
                    risk_id=f"risk_low_confidence_{obj.object_id}",
                    risk_kind=LayoutRiskKind.LOW_CONFIDENCE_GEOMETRY,
                    object_ids=(obj.object_id,),
                    severity=1.0 - obj.confidence,
                    description="object geometry confidence is below the required floor",
                )
            )

    for idx, first in enumerate(frozen_objects):
        for second in frozen_objects[idx + 1 :]:
            if not first.bbox.same_page(second.bbox):
                continue
            overlap = first.bbox.overlap_ratio(second.bbox)
            if overlap <= overlap_limit:
                continue
            risk_kind = LayoutRiskKind.OVERLAP
            if (
                first.object_type is DocumentObjectType.REDACTION_REGION
                or second.object_type is DocumentObjectType.REDACTION_REGION
            ):
                risk_kind = LayoutRiskKind.REDACTION_OVERLAY_RISK
            risks.append(
                LayoutRisk(
                    risk_id=f"risk_{risk_kind.value}_{first.object_id}_{second.object_id}",
                    risk_kind=risk_kind,
                    object_ids=(first.object_id, second.object_id),
                    severity=min(1.0, overlap),
                    description="object geometries overlap beyond the permitted threshold",
                    evidence=(f"overlap_ratio={overlap:.6f}",),
                )
            )

    return tuple(risks)
