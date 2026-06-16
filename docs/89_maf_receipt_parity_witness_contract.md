# MAF Receipt Parity Witness Contract

Purpose: define a Foundation Mode witness for Python control-plane receipt parity against local MAF Rust crate surfaces before any runtime Rust binding is considered.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `docs/FOUNDATION_MODE.md`, `docs/82_cross_repo_opportunity_map.md`, `docs/MAF_RECEIPT_COVERAGE.md`, `docs/AUDIT_F8_SCOPING_PLAN.md`, `maf/MAF_BOUNDARY.md`, `schemas/maf_receipt_parity_witness.schema.json`.
Invariants: the witness does not invoke Rust, PyO3, subprocesses, MAF CLI, network calls, filesystem mutation, receipt-emission mutation, production binding, terminal closure, or success claims.

## Boundary

`MafReceiptParityWitness` is a read-only evidence witness, not a runtime bridge.

It may bind:

1. The local MAF Rust workspace member set.
2. Python/Rust receipt and state hash parity constants.
3. Rust crate surfaces and Python/schema surfaces.
4. F8 gap refs from the existing audit plan.
5. Authority denial flags that keep runtime binding out of scope.

It must not bind:

1. PyO3 or FFI authority.
2. Python imports from a Rust runtime module.
3. Rust subprocess execution.
4. MAF CLI execution.
5. Network or connector calls.
6. Filesystem mutation or receipt-emission mutation.
7. A claim that Rust certifies Python runtime requests.
8. Production binding, terminal closure, or success claims.

## Foundation Example

The Foundation Mode example is:

```text
examples/maf_receipt_parity_witness.foundation.json
```

The validator is:

```powershell
python scripts\validate_maf_receipt_parity_witness.py
```

Expected result:

```text
[PASS] maf_receipt_parity_witness
```

## Authority Denials

The Foundation example requires these fields to remain `false`:

| Field | Denial |
| --- | --- |
| `pyo3_binding_present` | no PyO3 authority |
| `python_imports_rust_runtime` | no Python runtime import from Rust |
| `rust_subprocess_invoked` | no subprocess authority |
| `maf_cli_invoked` | no MAF CLI authority |
| `network_call_performed` | no network effect |
| `filesystem_mutation_performed` | no filesystem mutation |
| `receipt_emission_mutated` | no receipt-emission mutation |
| `runtime_certification_claimed` | no runtime certification claim |
| `rust_certifies_python_claimed` | no Rust-certifies-Python claim |
| `production_binding_claimed` | no production binding claim |
| `terminal_closure_allowed` | no terminal closure |
| `success_claim_allowed` | no success claim |

## Verification

Run:

```powershell
python scripts\validate_maf_receipt_parity_witness.py
python -m pytest tests\test_validate_maf_receipt_parity_witness.py -q
python scripts\validate_protocol_manifest.py
python scripts\proof_coverage_matrix.py --check
python scripts\validate_sdlc_artifact.py
python scripts\validate_sdlc_security_review.py --review examples\sdlc\security_review_maf_receipt_parity_witness_20260616.json --strict
```

STATUS:
  Completeness: 100%
  Invariants verified: read-only parity witness, hash constants pinned, MAF crate surfaces mapped, no PyO3, no subprocess, no MAF CLI, no runtime Rust certification claim, no production binding, no terminal closure
  Open issues: F8 runtime binding remains AwaitingEvidence pending operator tooling and ABI decisions
  Next action: use this witness as the evidence boundary before any future MAF FFI or runtime verification plan
