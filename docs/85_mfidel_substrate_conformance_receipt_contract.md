# Mfidel Substrate Conformance Receipt Contract

Purpose: define the Foundation Mode receipt that proves Mfidel substrate bounds, exact fidel preservation, and cross-runtime parity evidence state before SDK or kernel parity claims.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `docs/27_mfidel_semantic_layer.md`, `docs/82_cross_repo_opportunity_map.md`, `schemas/mfidel_substrate_conformance_receipt.schema.json`, `examples/mfidel_substrate_conformance_receipt.foundation.json`, `scripts/validate_mfidel_substrate_conformance_receipt.py`.
Invariants: each fidel is atomic; exact sequence preservation is required; sound overlays are metadata only; Unicode normalization and decomposition are denied; forbidden internal-letter modeling is denied; runtime parity remains `AwaitingEvidence` until Python, TypeScript, and Rust fixtures are bound.

## Boundary

`MfidelSubstrateConformanceReceipt` is a read-only governance contract. It does not implement an SDK, tokenizer, OCR engine, transliterator, search index, audio renderer, or runtime kernel binding.

It records:

1. Source family refs for `msic-sdk`, `tatoken-kernel`, and `tarc-core`.
2. Substrate digest metadata for the local contract slice.
3. Grid bounds: rows `1..34`, columns `1..8`, and vibratory overlay row `17`.
4. Exact fidel sequence fixtures with `f[row][col]` references.
5. No-normalization and no-decomposition guard state.
6. Python, TypeScript, and Rust fixture refs with runtime parity still blocked.

## Denied Authority

The receipt explicitly denies:

- live source repository reads;
- Unicode normalization, decomposition, or recomposition;
- shape or sound decomposition;
- forbidden internal-letter modeling;
- lossy transliteration as canonical storage;
- tokenization that splits a fidel into internal parts;
- runtime parity success claims;
- terminal closure.

## Verification

Run:

```powershell
python scripts/validate_mfidel_substrate_conformance_receipt.py
python -m pytest tests/test_validate_mfidel_substrate_conformance_receipt.py -q
python scripts/validate_protocol_manifest.py
python scripts/validate_schemas.py --schema schemas/mfidel_substrate_conformance_receipt.schema.json
python scripts/proof_coverage_matrix.py --check
python scripts/validate_sdlc_security_review.py --review examples/sdlc/security_review_mfidel_substrate_conformance_receipt_20260616.json --strict
```

## Rollback

Remove the schema, example, validator, tests, docs, manifest entry, proof coverage surface, SDLC artifacts, and CI registration. Then rerun the validators above plus workspace governance preflight before claiming rollback closure.

STATUS:
  Completeness: 100%
  Invariants verified: exact fidel preservation, grid bounds, no normalization, no decomposition, no forbidden internal-letter model, no runtime parity claim, no terminal closure
  Open issues: runtime parity remains AwaitingEvidence until Python, TypeScript, and Rust fixtures are bound
  Next action: bind concrete cross-runtime fixtures in a later proof thread
