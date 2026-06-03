# Mullu Govern Document Object Geometry v1

## Purpose

`document-object-geometry.v1` upgrades document handling from text-first extraction to visual-symbolic document state.

The contract treats rendered document content as page-scoped objects with geometry, spatial relations, pixel-region witnesses, and explicit layout risks.

```text
Document pixels
  -> page objects
  -> geometric relations
  -> pixel witnesses
  -> layout risks
  -> governed document object graph
```

This is a pure contract slice. It adds no execution authority, no provider dispatch, no default-catalog admission, and no document mutation path.

## Core Objects

| Contract | Meaning |
| --- | --- |
| `DocumentBBox` | Positive-area page-scoped bounding box. |
| `DocumentObject` | Visible or inferred document object such as heading, paragraph, table, signature, stamp, image, checkbox, or redaction region. |
| `DocumentSpatialEdge` | Directed spatial relation between two document objects. |
| `PixelRegionWitness` | Deterministic hash witness for a rendered page region. |
| `LayoutRisk` | Explicit layout or redaction-overlay fracture signal. |
| `DocumentObjectGraph` | Object graph binding document objects, spatial edges, pixel witnesses, reading order, and layout risks. |

## Geometry Layer

A page is treated as a bounded 2D coordinate plane.

```text
bbox := (page_number, x0, y0, x1, y1, coordinate_space)
area := (x1 - x0) * (y1 - y0)
overlap_ratio(A, B) := area(intersection(A, B)) / min(area(A), area(B))
alignment_error(A, B) := min(|A.left-B.left|, |A.center-B.center|, |A.right-B.right|)
visual_density(region) := occupied_pixel_area / region_area
```

The contract rejects invalid geometry:

```text
- page_number < 1
- non-finite coordinates
- x1 <= x0
- y1 <= y0
- negative occupied pixel area
- occupied pixel area larger than region area
```

## Spatial Relations

Supported relation types:

```text
above
below
left_of
right_of
contains
overlaps
aligned_with
near
caption_of
header_of
cell_of
```

Edges must reference known object IDs. Dangling source or target references fail closed.

## Pixel Witness Layer

A pixel witness binds:

```text
page_number
bbox
rendered_pixel_hash
rendered_page_hash
source_object_id
witness_kind
```

The deterministic region hash is:

```text
region_hash := sha256(contract_version, page_number, bbox, rendered_pixel_hash)
```

Witness kinds:

```text
region_hash
page_render_hash
before_after_diff
redaction_proof
signature_anchor
```

This creates a future path for:

```text
- signature/stamp anchoring
- visual tamper detection
- redaction-region proof
- before/after layout diffing
- geometry-bound audit evidence
```

## Layout Risks

The first risk detector covers:

```text
overlap
clipping
margin_violation
reading_order_anomaly
redaction_overlay_risk
low_confidence_geometry
```

The most important fracture is `redaction_overlay_risk`: if a `redaction_region` overlaps another object, the system records an explicit review signal instead of assuming the redaction is safe.

## Engineering Value

This enables document handling to reason about what is physically visible, not only what text extraction returns.

Immediate benefits:

```text
- Detect clipped or overlapping layout objects.
- Detect suspicious visual redaction overlays.
- Anchor signatures, stamps, and high-trust regions by pixel hash.
- Preserve reading order through geometry rather than extracted string order only.
- Prepare for layout-safe patch simulation and visual diff verification.
```

## Current Implementation

```text
mcoi/mcoi_runtime/contracts/document_object_geometry.py
mcoi/tests/test_document_object_geometry.py
```

## Governance Delta

Constructive deltas:

```text
- Adds geometry-aware document object contracts.
- Adds deterministic region hashing for rendered pixel witnesses.
- Adds object graph reference validation.
- Adds geometry-derived spatial edge helpers.
- Adds layout-risk detection helpers for clipping, overlap, redaction-overlay risk, and low-confidence geometry.
- Adds focused tests for deterministic hashing, dangling-reference rejection, reading order, and redaction overlay risk.
```

Fracture deltas:

```text
- None to document execution authority.
- None to default skill catalog registration.
- None to provider dispatch.
- None to existing document mutation behavior.
```

## Rollback

Revert the additive files:

```text
docs/skills/mullu_govern_document_object_geometry_v1.md
mcoi/mcoi_runtime/contracts/document_object_geometry.py
mcoi/tests/test_document_object_geometry.py
```
