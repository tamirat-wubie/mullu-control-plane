# Mfidel Substrate Conformance Receipt Contract

Purpose: define the Foundation Mode receipt for Mfidel substrate conformance across local Python runtime surfaces and future TypeScript/Rust SDK or kernel bindings.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS, and Mfidel atomicity.
Dependencies: `schemas/mfidel_substrate_conformance_receipt.schema.json`, `examples/mfidel_substrate_conformance_receipt.foundation.json`, `scripts/validate_mfidel_substrate_conformance_receipt.py`, `mcoi/mcoi_runtime/substrate/mfidel/grid.py`, `mcoi/mcoi_runtime/core/mfidel_matrix.py`, `mcoi/mcoi_runtime/contracts/mfidel.py`, and `mcoi/tests/test_mfidel_atomicity.py`.
Invariants: each fidel is atomic; no Unicode normalization, decomposition, or recomposition is admitted; overlays are sound metadata only; cross-runtime closure is not claimed while SDK/kernel evidence is missing.

## Boundary

`MfidelSubstrateConformanceReceipt` is an audit receipt, not a runtime adapter. It records:

1. Canonical grid bounds: 34 rows, 8 columns, row 17 overlay row, 272 vector dimension, 269 non-empty fidels, and three known empty slots.
2. Local runtime digest evidence for the Python substrate grid, legacy matrix view, and Mfidel contracts.
3. Exact-preservation witnesses that map each input fidel sequence to `f[row][col]` positions without normalization.
4. Denied operations: Unicode normalization, Unicode decomposition, Unicode recomposition, root-letter modeling, consonant/vowel splitting, lossy transliteration as identity, phoneme identity substitution, structural overlay decomposition, raw secret retention, live runtime import authority, and terminal closure.
5. Awaiting-evidence bindings for TypeScript and Rust SDK/kernel surfaces.

## Non-Authority

The receipt does not:

- import external SDK/kernel code;
- call live runtimes;
- normalize or canonicalize fidel codepoints;
- split a fidel into internal written parts;
- treat Latin sound impressions as Amharic spelling;
- claim cross-runtime closure;
- grant deployment, connector, filesystem, or terminal closure authority.

## Verification

The validator recomputes local grid counts, checks canonical empty slots and overlay exceptions, hashes local implementation files, inspects implementation source for normalization APIs, verifies exact sequence witnesses through `MfidelMatrix`, and recomputes summary counts.

The Foundation example remains `AwaitingEvidence` until external TypeScript and Rust evidence provides digests, no-normalization proof refs, and exact-preservation fixture refs.

## Rollback

Revert the schema, example, validator, tests, documentation, manifest entry, proof coverage entry, CI hook, and SDLC artifacts. Then rerun schema validation, proof coverage validation, SDLC validation, and workspace governance preflight.
