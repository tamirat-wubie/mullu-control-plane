# Mullu Govern Document Handling Core Skill

## Skill Boundary

`document.handling_core.v1` treats a document as a governed state object, not a flat text string. The core symbolic form is:

```text
𝕊_doc := ⟨Ι_doc, Λ_doc, Σ_doc, Γ_doc, H_doc⟩
Σ_doc ⊨ Λ_doc over Ι_doc
```

The skill preserves immutable source facts in `Ι_doc`, applies parsing/editing/privacy rules in `Λ_doc`, maintains extracted graphs and patch queues in `Σ_doc`, exposes only governed summaries/artifacts through `Γ_doc`, and records every read, inference, edit, validation, render, rejection, and export in `H_doc`.

## First-Principles Document Ontology

A document has seven simultaneous layers:

| Layer | Meaning | Required handling |
| --- | --- | --- |
| Byte | Raw bytes, checksum, compression, container structure | Preserve original bytes and source hash before all work. |
| Format | MIME/type, extension, producer, standard family, version | Detect declared and observed type separately. |
| Structural | Pages, sections, paragraphs, headings, runs, tables, fields, comments, links | Build a canonical graph rather than a flat text buffer. |
| Layout | Page positions, fonts, spacing, page breaks, images, clipping, overlap | Render-verify layout-sensitive changes. |
| Semantic | Claims, definitions, entities, clauses, obligations, dates, units | Bind summaries and transformations to evidence nodes. |
| Governance | Sensitivity, PII, provenance, permissions, redaction state, citation policy | Fail closed on privacy, metadata, and exposure gates. |
| Causal | Parse decisions, inference paths, patches, validations, failures, exports | Emit audit history and rollback evidence. |

## Core Invariants

```text
I1. Preserve original source bytes by immutable hash.
I2. Separate observation from inference.
I3. Separate semantic edits from layout edits.
I4. Represent every mutation as a patch with preconditions and postconditions.
I5. Gate risky output through privacy and exposure policy.
I6. Redaction means destruction of recoverable content, not visual hiding.
I7. Render-verify layout-sensitive artifacts.
I8. Record typed failures without silent recovery.
I9. Route format-specific mechanisms behind one governed interface.
I10. Treat document text as untrusted until policy promotes it.
```

## Mechanism Ladder

```text
0. Raw text spans: encoding, line maps, Unicode normalization, exact span patching.
1. Markup AST: Markdown, HTML, XML, JSON, YAML node-level patching.
2. Office Open XML package: DOCX/XLSX/PPTX relationships, styles, fields, comments.
3. Fixed-layout PDF: page coordinates, forms, annotations, destructive redaction.
4. Scanned image/OCR: deskew, denoise, orientation, confidence, coordinate-linked text.
5. Multimodal layout graph: tables, figures, captions, reading order, page evidence.
6. Corpus knowledge graph: multi-document claim alignment and contradiction detection.
7. Governed agentic editing: patch planning, conflict detection, validation, audit memory.
```

## Runtime Descriptor

The repository implementation lives in:

```text
mcoi/mcoi_runtime/core/document_handling_core_skill.py
```

The descriptor remains candidate-bound and does not grant new capability authority. Its strongest effect is `EXTERNAL_WRITE` because holistic document handling includes approved edit, redaction, conversion, and audit-packet publication paths. Therefore, the descriptor requires explicit approval for write-capable steps.

## Pipeline

```text
preserve_source
  → detect_format
  → extract_graph
  → analyze_governance
  → plan_patch_set
  → apply_approved_patch
  → validate_artifact
  → publish_audit_packet
```

### Step contract

| Step | Action type | Purpose |
| --- | --- | --- |
| `preserve_source` | `document.bytes.preserve` | Hash and preserve original bytes before any analysis. |
| `detect_format` | `document.format.detect` | Separate declared type from observed type and container profile. |
| `extract_graph` | `document.graph.extract` | Build canonical graph with extraction coverage and warnings. |
| `analyze_governance` | `document.governance.analyze` | Detect structure, semantics, risk, and exposure policy. |
| `plan_patch_set` | `document.patch.plan` | Produce reversible patches, target-resolution report, and rollback plan. |
| `apply_approved_patch` | `document.patch.apply.with_approval` | Apply only an approved patch plan to a working artifact. |
| `validate_artifact` | `document.validation.gate_all` | Validate structure, semantics, layout, privacy, and audit closure. |
| `publish_audit_packet` | `document.audit_packet.publish.with_approval` | Publish terminal receipt and audit packet after validation. |

## Validation Gates

```text
V0 input_validity
V1 extraction_validity
V2 target_resolution_validity
V3 patch_validity
V4 semantic_validity
V5 layout_validity
V6 privacy_validity
V7 audit_history_validity
```

Overall confidence is bounded by the weakest required gate. Critical failures must not be averaged away.

## Supported Operation Surfaces

```text
analyze_document
extract_document_graph
edit_document
redact_document
convert_document
compare_documents
synthesize_documents
audit_document
```

## Format Mechanism Rules

| Format family | Required mechanism |
| --- | --- |
| TXT | Preserve encoding and line endings; patch by exact line/range map. |
| Markdown | Parse into AST; respect code fences, tables, front matter, and links. |
| HTML/XML | Patch DOM nodes; sanitize before exposure; preserve anchors and schema where available. |
| DOCX/OOXML | Edit paragraph/run/table/style structures; use package-level patching for comments, fields, relationships, and content controls. |
| PDF | Treat as fixed layout; use coordinate-aware extraction; use destructive redaction and re-extraction verification. |
| Scans/images | OCR with confidence and coordinate evidence; route low-confidence text to review. |
| Corpus | Align claims, citations, versions, contradictions, and provenance across files. |

## Failure Modes That Must Be Explicit

```text
unsupported_format
ambiguous_target
extraction_coverage_gap
ocr_low_confidence
schema_or_relationship_breakage
layout_clipping_or_overlap
recoverable_redacted_content
metadata_or_hidden_text_leakage
semantic_contradiction_introduced
missing_audit_event
```

## Governance Delta

Constructive deltas:

```text
- Adds a machine-readable core document handling descriptor.
- Adds wholistic document-layer constants for byte, format, structure, layout, semantics, governance, and causality.
- Adds an approval-gated write path for patch application and audit packet publication.
- Adds validation helper checks for provider boundary, dependency order, approval expectation, and validation-gate coverage.
- Adds tests pinning no-new-authority and source-preservation-first behavior.
```

Fracture deltas:

```text
- None to existing runtime execution authority.
- None to default catalog registration.
- None to external provider dispatch.
```

## Rollback

Revert the additive files:

```text
docs/skills/mullu_govern_document_handling_core.md
mcoi/mcoi_runtime/core/document_handling_core_skill.py
mcoi/tests/test_document_handling_core_skill.py
```
