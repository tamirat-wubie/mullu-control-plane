# MAF Runtime Binding Admission Witness

Purpose: record the Foundation Mode admission gate for future executable MAF runtime binding.
Governance scope: MAF/MCOI runtime-binding admission, UAO evidence, rollback evidence, runtime execution receipts, CI backend evidence, terminal closure denial, and F8 substrate-disconnect continuity.
Dependencies: `MafFailureReceiptPathWitness`, `docs/AUDIT_F8_SCOPING_PLAN.md`, `maf/MAF_BOUNDARY.md`, UAO, and LifeMeaningJudgment.
Invariants: runtime binding admission is evidence-gated; implementation start, executable binding, PyO3, subprocess execution, backend default flip, terminal closure, and success claims remain denied.

## Contract

`MafRuntimeBindingAdmissionWitness` records that the static MAF prerequisites are closed and names the evidence required before executable runtime binding work can begin.

The witness does not implement runtime binding. It keeps `solver_outcome` as `AwaitingEvidence` and preserves an explicit `gap://maf/runtime-binding-implementation-evidence` reference.

## Required Evidence Before Implementation

| Requirement | Evidence ref | Status |
| --- | --- | --- |
| UAO admission | `evidence://maf/runtime-binding/uao-admission` | AwaitingEvidence |
| Implementation design | `evidence://maf/runtime-binding/implementation-design` | AwaitingEvidence |
| Rollback and recovery | `evidence://maf/runtime-binding/rollback-recovery` | AwaitingEvidence |
| Runtime execution receipts | `evidence://maf/runtime-binding/runtime-execution-receipts` | AwaitingEvidence |
| CI Rust backend lane | `evidence://maf/runtime-binding/ci-rust-backend-lane` | AwaitingEvidence |
| Terminal closure review | `evidence://maf/runtime-binding/terminal-closure-review` | AwaitingEvidence |

## Authority Boundary

The witness allows static admission readback only. It denies implementation start, runtime binding, PyO3 binding, subprocess execution, CLI execution, Rust crate execution, Python imports of Rust, CI backend requirement flips, default backend flips, network calls, secret access, filesystem writes, runtime dispatch, canonical state mutation, terminal closure, and success claims.

## Validation

```powershell
python scripts/validate_maf_runtime_binding_admission_witness.py
python -m pytest tests/test_validate_maf_runtime_binding_admission_witness.py -q
```

STATUS:
  Completeness: 100%
  Invariants verified: static prerequisite closure recorded, runtime implementation denied, UAO evidence required, rollback evidence required, runtime receipts required, terminal closure denied
  Open issues: executable runtime binding remains AwaitingEvidence
  Next action: produce the implementation design and rollback evidence before any runtime binding code
