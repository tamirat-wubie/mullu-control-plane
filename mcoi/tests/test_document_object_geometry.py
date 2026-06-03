"""Tests for document object geometry and pixel witness contracts.

Purpose: pin geometry-aware document object graph contracts.
Governance scope: layout-object identity, spatial edges, layout risks, and
pixel-region witness hashes.
Dependencies: document_object_geometry contract module.
Invariants:
  - Bounding boxes are finite positive-area regions.
  - Region hashes are deterministic over page, geometry, and rendered pixel hash.
  - Object graphs reject dangling edge and witness references.
  - Redaction overlays surface as explicit risks.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.document_object_geometry import (
    DocumentBBox,
    DocumentObject,
    DocumentObjectGraph,
    DocumentObjectType,
    DocumentSpatialEdge,
    LayoutRiskKind,
    PixelWitnessKind,
    SpatialRelation,
    alignment_error,
    build_region_witness,
    build_spatial_edges,
    detect_layout_risks,
    pixel_region_hash,
    visual_density,
)


def _object(
    object_id: str,
    bbox: DocumentBBox,
    object_type: DocumentObjectType,
) -> DocumentObject:
    return DocumentObject(
        object_id=object_id,
        object_type=object_type,
        bbox=bbox,
        source_pixel_hash=f"sha256:{object_id}",
        edit_permissions=("read",),
    )


def test_document_bbox_math_is_positive_and_page_scoped() -> None:
    first = DocumentBBox(page_number=1, x0=10, y0=10, x1=110, y1=60)
    second = DocumentBBox(page_number=1, x0=60, y0=40, x1=140, y1=90)

    assert first.width == 100.0
    assert first.height == 50.0
    assert first.area == 5000.0
    assert first.intersection_area(second) == 1000.0
    assert first.overlap_ratio(second) == 0.25
    assert first.region_key() == "1:10.0:10.0:110.0:60.0:pixel"
    assert alignment_error(first, second) == 30.0
    assert visual_density(2500, first) == 0.5


def test_document_bbox_rejects_invalid_geometry() -> None:
    with pytest.raises(ValueError, match="x1 must be greater than x0"):
        DocumentBBox(page_number=1, x0=10, y0=0, x1=10, y1=1)

    with pytest.raises(ValueError, match="page_number"):
        DocumentBBox(page_number=0, x0=0, y0=0, x1=1, y1=1)


def test_pixel_region_hash_is_deterministic_and_geometry_bound() -> None:
    bbox = DocumentBBox(page_number=2, x0=1, y0=2, x1=3, y1=4)

    first_hash = pixel_region_hash(
        page_number=2,
        bbox=bbox,
        rendered_pixel_hash="sha256:rendered-region",
    )
    second_hash = pixel_region_hash(
        page_number=2,
        bbox=bbox,
        rendered_pixel_hash="sha256:rendered-region",
    )

    assert first_hash == second_hash
    assert first_hash.startswith("sha256:")

    shifted = DocumentBBox(page_number=2, x0=1, y0=2, x1=3, y1=5)
    assert pixel_region_hash(
        page_number=2,
        bbox=shifted,
        rendered_pixel_hash="sha256:rendered-region",
    ) != first_hash


def test_build_region_witness_binds_object_and_page_hash() -> None:
    bbox = DocumentBBox(page_number=1, x0=0, y0=0, x1=25, y1=25)
    witness = build_region_witness(
        witness_id="witness_signature",
        witness_kind=PixelWitnessKind.SIGNATURE_ANCHOR,
        bbox=bbox,
        rendered_pixel_hash="sha256:signature-region",
        rendered_page_hash="sha256:page",
        source_object_id="signature_1",
    )

    assert witness.page_number == 1
    assert witness.source_object_id == "signature_1"
    assert witness.rendered_page_hash == "sha256:page"
    assert witness.region_hash == pixel_region_hash(
        page_number=1,
        bbox=bbox,
        rendered_pixel_hash="sha256:signature-region",
    )


def test_spatial_edges_are_deterministic_from_geometry() -> None:
    heading = _object(
        "heading_1",
        DocumentBBox(page_number=1, x0=20, y0=20, x1=180, y1=50),
        DocumentObjectType.HEADING,
    )
    paragraph = _object(
        "paragraph_1",
        DocumentBBox(page_number=1, x0=20, y0=70, x1=180, y1=140),
        DocumentObjectType.PARAGRAPH,
    )

    edges = build_spatial_edges((heading, paragraph), alignment_tolerance=0.1)
    relations = {edge.relation for edge in edges}

    assert SpatialRelation.ABOVE in relations
    assert SpatialRelation.ALIGNED_WITH in relations
    assert all(edge.source_object_id == "heading_1" for edge in edges)


def test_layout_risk_detector_surfaces_clipping_overlap_and_redaction_overlay() -> None:
    body = _object(
        "body",
        DocumentBBox(page_number=1, x0=0, y0=0, x1=100, y1=100),
        DocumentObjectType.PARAGRAPH,
    )
    redaction = _object(
        "redaction",
        DocumentBBox(page_number=1, x0=10, y0=10, x1=80, y1=80),
        DocumentObjectType.REDACTION_REGION,
    )
    clipped = _object(
        "clipped",
        DocumentBBox(page_number=1, x0=90, y0=90, x1=130, y1=130),
        DocumentObjectType.IMAGE,
    )

    risks = detect_layout_risks(
        (body, redaction, clipped),
        page_width=120,
        page_height=120,
        overlap_threshold=0.01,
    )
    risk_kinds = {risk.risk_kind for risk in risks}

    assert LayoutRiskKind.CLIPPING in risk_kinds
    assert LayoutRiskKind.REDACTION_OVERLAY_RISK in risk_kinds
    assert any("overlap_ratio=" in evidence for risk in risks for evidence in risk.evidence)


def test_object_graph_rejects_dangling_references() -> None:
    obj = _object(
        "paragraph_1",
        DocumentBBox(page_number=1, x0=0, y0=0, x1=100, y1=20),
        DocumentObjectType.PARAGRAPH,
    )
    edge = DocumentSpatialEdge(
        edge_id="bad_edge",
        source_object_id="paragraph_1",
        target_object_id="missing",
        relation=SpatialRelation.ABOVE,
    )

    with pytest.raises(ValueError, match="target object is unknown"):
        DocumentObjectGraph(
            doc_id="doc_1",
            source_hash="sha256:doc",
            objects=(obj,),
            spatial_edges=(edge,),
        )


def test_object_graph_serializes_pixel_witnesses_deterministically() -> None:
    signature = _object(
        "signature_1",
        DocumentBBox(page_number=1, x0=30, y0=200, x1=180, y1=260),
        DocumentObjectType.SIGNATURE,
    )
    witness = build_region_witness(
        witness_id="witness_signature_1",
        witness_kind=PixelWitnessKind.SIGNATURE_ANCHOR,
        bbox=signature.bbox,
        rendered_pixel_hash="sha256:signature-region",
        rendered_page_hash="sha256:page",
        source_object_id=signature.object_id,
    )
    graph = DocumentObjectGraph(
        doc_id="doc_1",
        source_hash="sha256:doc",
        objects=(signature,),
        pixel_witnesses=(witness,),
        reading_order=("signature_1",),
    )

    assert graph.object_by_id("signature_1") == signature
    assert graph.objects_in_reading_order() == (signature,)
    assert graph.to_json() == graph.to_json()
    assert "signature_anchor" in graph.to_json()
