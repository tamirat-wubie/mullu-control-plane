"""Tests for document geometry audit contracts.

Purpose: pin read-only audit, refinement, and recommendation behavior for
DocumentObjectGraph records.
Governance scope: findings, recommendations, status derivation, and confidence
scoring only.
Dependencies: document_object_geometry and document_geometry_audit contracts.
Invariants:
  - Audit does not mutate the graph.
  - Missing destructive redaction proof fails closed.
  - Recommendations are derived from typed findings.
  - Clean high-trust geometry passes deterministically.
"""

from __future__ import annotations

from mcoi_runtime.contracts.document_geometry_audit import (
    AuditSeverity,
    DocumentGeometryAuditPolicy,
    DocumentGeometryAuditStatus,
    DocumentPageGeometry,
    RecommendationKind,
    audit_confidence_score,
    audit_document_object_graph,
)
from mcoi_runtime.contracts.document_object_geometry import (
    DocumentBBox,
    DocumentObject,
    DocumentObjectGraph,
    DocumentObjectType,
    LayoutRisk,
    LayoutRiskKind,
    PixelRegionWitness,
    PixelWitnessKind,
    PixelWitnessStatus,
    build_region_witness,
    build_spatial_edges,
)


def _object(
    object_id: str,
    object_type: DocumentObjectType,
    bbox: DocumentBBox,
    *,
    confidence: float = 1.0,
) -> DocumentObject:
    return DocumentObject(
        object_id=object_id,
        object_type=object_type,
        bbox=bbox,
        confidence=confidence,
        source_pixel_hash=f"sha256:{object_id}",
    )


def _witness(
    witness_id: str,
    object_id: str,
    bbox: DocumentBBox,
    *,
    witness_kind: PixelWitnessKind = PixelWitnessKind.SIGNATURE_ANCHOR,
    status: PixelWitnessStatus = PixelWitnessStatus.PASSED,
) -> PixelRegionWitness:
    return build_region_witness(
        witness_id=witness_id,
        witness_kind=witness_kind,
        bbox=bbox,
        rendered_pixel_hash=f"sha256:region:{witness_id}",
        rendered_page_hash="sha256:page",
        source_object_id=object_id,
        status=status,
    )


def test_geometry_audit_passes_clean_signature_graph() -> None:
    signature = _object(
        "signature_1",
        DocumentObjectType.SIGNATURE,
        DocumentBBox(page_number=1, x0=20, y0=100, x1=180, y1=150),
    )
    graph = DocumentObjectGraph(
        doc_id="doc_1",
        source_hash="sha256:doc",
        objects=(signature,),
        pixel_witnesses=(
            _witness("witness_signature_1", signature.object_id, signature.bbox),
        ),
        reading_order=(signature.object_id,),
    )

    report = audit_document_object_graph(
        graph,
        page_geometries=(DocumentPageGeometry(page_number=1, width=612, height=792),),
    )

    assert report.status is DocumentGeometryAuditStatus.PASSED
    assert report.findings == ()
    assert report.recommendations == ()
    assert audit_confidence_score(report) == 1.0
    assert graph.object_by_id("signature_1") == signature


def test_geometry_audit_fails_closed_for_missing_redaction_proof() -> None:
    redaction = _object(
        "redaction_1",
        DocumentObjectType.REDACTION_REGION,
        DocumentBBox(page_number=1, x0=10, y0=10, x1=100, y1=50),
    )
    graph = DocumentObjectGraph(
        doc_id="doc_1",
        source_hash="sha256:doc",
        objects=(redaction,),
        pixel_witnesses=(
            _witness(
                "witness_redaction_region",
                redaction.object_id,
                redaction.bbox,
                witness_kind=PixelWitnessKind.REGION_HASH,
            ),
        ),
    )

    report = audit_document_object_graph(
        graph,
        page_geometries=(DocumentPageGeometry(page_number=1, width=612, height=792),),
    )

    assert report.status is DocumentGeometryAuditStatus.FAILED
    assert any(finding.severity is AuditSeverity.CRITICAL for finding in report.findings)
    assert any(
        recommendation.kind is RecommendationKind.PROVE_REDACTION
        for recommendation in report.recommendations
    )
    assert "finding_missing_redaction_proof_redaction_1" in report.fracture_deltas


def test_geometry_audit_accepts_passed_destructive_redaction_proof() -> None:
    redaction = _object(
        "redaction_1",
        DocumentObjectType.REDACTION_REGION,
        DocumentBBox(page_number=1, x0=10, y0=10, x1=100, y1=50),
    )
    graph = DocumentObjectGraph(
        doc_id="doc_1",
        source_hash="sha256:doc",
        objects=(redaction,),
        pixel_witnesses=(
            _witness(
                "witness_redaction_proof",
                redaction.object_id,
                redaction.bbox,
                witness_kind=PixelWitnessKind.REDACTION_PROOF,
                status=PixelWitnessStatus.PASSED,
            ),
        ),
    )

    report = audit_document_object_graph(
        graph,
        page_geometries=(DocumentPageGeometry(page_number=1, width=612, height=792),),
    )

    assert report.status is DocumentGeometryAuditStatus.PASSED
    assert report.findings == ()


def test_geometry_audit_recommends_reading_order_and_spatial_edges() -> None:
    heading = _object(
        "heading_1",
        DocumentObjectType.HEADING,
        DocumentBBox(page_number=1, x0=20, y0=20, x1=200, y1=50),
    )
    paragraph = _object(
        "paragraph_1",
        DocumentObjectType.PARAGRAPH,
        DocumentBBox(page_number=1, x0=20, y0=70, x1=200, y1=130),
    )
    graph = DocumentObjectGraph(
        doc_id="doc_1",
        source_hash="sha256:doc",
        objects=(heading, paragraph),
    )

    report = audit_document_object_graph(
        graph,
        page_geometries=(DocumentPageGeometry(page_number=1, width=612, height=792),),
    )
    kinds = {recommendation.kind for recommendation in report.recommendations}

    assert report.status is DocumentGeometryAuditStatus.NEEDS_REVIEW
    assert RecommendationKind.ADD_READING_ORDER in kinds
    assert RecommendationKind.ADD_SPATIAL_EDGES in kinds
    assert audit_confidence_score(report) < 1.0


def test_geometry_audit_detects_clipped_object_against_page_bounds() -> None:
    image = _object(
        "image_1",
        DocumentObjectType.IMAGE,
        DocumentBBox(page_number=1, x0=500, y0=700, x1=700, y1=900),
    )
    graph = DocumentObjectGraph(
        doc_id="doc_1",
        source_hash="sha256:doc",
        objects=(image,),
    )

    report = audit_document_object_graph(
        graph,
        page_geometries=(DocumentPageGeometry(page_number=1, width=612, height=792),),
    )

    assert report.status is DocumentGeometryAuditStatus.NEEDS_REVIEW
    assert any(finding.finding_id == "finding_clipped_object_image_1" for finding in report.findings)
    assert any(
        recommendation.kind is RecommendationKind.REVIEW_LAYOUT_RISK
        for recommendation in report.recommendations
    )


def test_geometry_audit_surfaces_layout_risk_and_low_confidence_geometry() -> None:
    body = _object(
        "body",
        DocumentObjectType.PARAGRAPH,
        DocumentBBox(page_number=1, x0=0, y0=0, x1=100, y1=100),
        confidence=0.4,
    )
    redaction = _object(
        "redaction",
        DocumentObjectType.REDACTION_REGION,
        DocumentBBox(page_number=1, x0=10, y0=10, x1=80, y1=80),
    )
    graph = DocumentObjectGraph(
        doc_id="doc_1",
        source_hash="sha256:doc",
        objects=(body, redaction),
        spatial_edges=build_spatial_edges((body, redaction)),
        pixel_witnesses=(
            _witness(
                "witness_redaction_proof",
                redaction.object_id,
                redaction.bbox,
                witness_kind=PixelWitnessKind.REDACTION_PROOF,
                status=PixelWitnessStatus.PASSED,
            ),
        ),
        layout_risks=(
            LayoutRisk(
                risk_id="redaction_overlay",
                risk_kind=LayoutRiskKind.REDACTION_OVERLAY_RISK,
                object_ids=(body.object_id, redaction.object_id),
                severity=0.9,
                description="redaction visually overlaps body text",
            ),
        ),
        reading_order=(body.object_id,),
    )

    report = audit_document_object_graph(
        graph,
        page_geometries=(DocumentPageGeometry(page_number=1, width=612, height=792),),
        policy=DocumentGeometryAuditPolicy(confidence_floor=0.75),
    )

    assert report.status is DocumentGeometryAuditStatus.FAILED
    assert "finding_layout_risk_redaction_overlay" in report.fracture_deltas
    assert any(
        recommendation.kind is RecommendationKind.RAISE_GEOMETRY_CONFIDENCE
        for recommendation in report.recommendations
    )
    assert any(
        recommendation.kind is RecommendationKind.REVIEW_LAYOUT_RISK
        for recommendation in report.recommendations
    )


def test_geometry_audit_report_is_deterministic() -> None:
    heading = _object(
        "heading_1",
        DocumentObjectType.HEADING,
        DocumentBBox(page_number=1, x0=20, y0=20, x1=200, y1=50),
    )
    graph = DocumentObjectGraph(
        doc_id="doc_1",
        source_hash="sha256:doc",
        objects=(heading,),
    )

    first = audit_document_object_graph(graph)
    second = audit_document_object_graph(graph)

    assert first.to_json() == second.to_json()
    assert first.metadata["contract_version"] == "document-geometry-audit.v1"
