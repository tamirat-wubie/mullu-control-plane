# Mullu Govern Document Geometry Audit v1

## Purpose

`document-geometry-audit.v1` adds the audit, refinement, suggestion, and recommendation layer on top of `document-object-geometry.v1`.

It is read-only. It does not mutate documents, does not dispatch providers, does not add default catalog authority, and does not execute redaction or layout repair. Its job is to inspect a `DocumentObjectGraph` and produce deterministic findings and recommendations.

```text
DocumentObjectGraph
  -> geometry audit policy
  -> page-bound audit
  -> reading-order audit
  -> spatial-edge audit
  -> pixel-witness audit
  -> redaction-proof audit
  -> layout-risk audit
  -> findings
  -> recommendations
  -> confidence score
```

## Audit Contracts

| Contract | Meaning |
| --- | --- |
| `DocumentPageGeometry` | Page bounds used for clipping and coordinate-space checks. |
| `DocumentGeometryAuditPolicy` | Read-only audit requirements for witness coverage, redaction proof, reading order, spatial edges, and confidence floor. |
| `DocumentGeometryAuditFinding` | Typed finding with category, severity, recommendation kind, object IDs, and evidence. |
| `DocumentGeometryRecommendation` | Non-executing recommendation derived from one or more findings. |
| `DocumentGeometryAuditReport` | Deterministic report with status, findings, recommendations, constructive deltas, fracture deltas, and metadata. |

## Status Model

```text
passed
passed_with_recommendations
needs_review
failed
```

Severity maps to terminal status:

```text
no findings -> passed
info -> passed_with_recommendations
warning -> needs_review
error -> needs_review
critical -> failed
```

Critical failures are not averaged away.

## Audit Categories

```text
geometry
pixel_witness
spatial_graph
reading_order
redaction
layout_risk
coverage
```

## Recommendation Kinds

```text
add_page_geometry
add_pixel_witness
add_reading_order
add_spatial_edges
prove_redaction
review_layout_risk
normalize_coordinate_space
raise_geometry_confidence
```

Recommendations are not executable commands. They are bounded, typed refinement instructions derived directly from findings.

## Fail-Closed Redaction Rule

A `redaction_region` is considered unsafe unless it has a passed `redaction_proof` pixel witness.

```text
redaction_region
  + no redaction_proof witness
  -> critical finding
  -> failed audit
  -> prove_redaction recommendation
```

A visual black box is not sufficient evidence. The redaction must be proven by an explicit destructive-redaction witness.

## Refinement Checks

The audit layer checks:

```text
- Missing page geometry.
- Mixed coordinate spaces.
- Missing geometry-aware reading order.
- Partial reading order for text-like objects.
- Missing spatial edges when multiple objects exist.
- Low object geometry confidence.
- Missing pixel witnesses for signatures, stamps, and redaction regions.
- Candidate, review-needed, or failed pixel witnesses.
- Missing or unpassed redaction proof witnesses.
- Existing layout risks in the object graph.
- Object clipping against supplied page bounds.
```

## Confidence Score

`audit_confidence_score(report)` returns a bounded score in `[0.0, 1.0]`.

Penalties:

```text
info      -> 0.02
warning   -> 0.10
error     -> 0.25
critical  -> 0.50
```

The score is a reporting aid only. It does not override the terminal status.

## Constructive Deltas

```text
- Adds read-only geometry audit contracts.
- Adds fail-closed redaction proof audit.
- Adds typed findings and typed recommendations.
- Adds confidence scoring for audit reports.
- Adds tests for clean pass, missing redaction proof, passed redaction proof, missing reading order, missing spatial edges, clipping, redaction overlay, low confidence, and deterministic output.
```

## Fracture Deltas

```text
- None to document execution authority.
- None to provider dispatch.
- None to default skill catalog registration.
- None to document mutation behavior.
```

## Current Implementation

```text
mcoi/mcoi_runtime/contracts/document_geometry_audit.py
mcoi/tests/test_document_geometry_audit.py
```

## Rollback

Revert the additive files:

```text
docs/skills/mullu_govern_document_geometry_audit_v1.md
mcoi/mcoi_runtime/contracts/document_geometry_audit.py
mcoi/tests/test_document_geometry_audit.py
```
