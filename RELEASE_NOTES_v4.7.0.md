# Mullu Platform v4.7.0 — MUSIA Runtime (Six Domains)

**Release date:** TBD
**Codename:** Span
**Migration required:** No (additive)

---

## What this release is

Three new domain adapters land together: `manufacturing`, `healthcare`,
and `education`. With the existing `software_dev`, `business_process`,
and `scientific_research` adapters, the framework now reaches **all six
domains** the original MUSIA v3.0 specification listed.

This release also extracts shared cycle-wiring code into a single helper
(`_cycle_helpers.py`), shrinking each new adapter to ~350 lines instead
of ~450. Existing adapters keep their inline wiring for now; consolidation
is deferred to a separate cleanup release.

---

## What is new in v4.7.0

### `manufacturing` domain adapter

[manufacturing.py](mullu-control-plane/mcoi/mcoi_runtime/domain_adapters/manufacturing.py).

8 action kinds: machining, assembly, quality_inspection, rework, scrap,
recall, calibration, batch_release.

Distinctive shape:
- **QE + ISO observers as authority chain**, distinct from individual reviewers
- **Numerical tolerance constraints** (microns) emit at `escalate` level
- **Yield constraint** at `warn` level — review process capability rather than block production
- **Safety-critical flag** adds an explicit `block`-level constraint
- **Reversibility content-dependent**: `REWORK` reversible; `MACHINING/ASSEMBLY/SCRAP/RECALL` irreversible
- **Tight tolerance × low yield combo** flagged as production capability mismatch
- **Batch release without QE** flagged separately from low-yield risk

24 tests covering all 8 action kinds, all 4 blast radii, every constraint type, all 9 risk-flag conditions, end-to-end UCJA→SCCCE.

### `healthcare` domain adapter

[healthcare.py](mullu-control-plane/mcoi/mcoi_runtime/domain_adapters/healthcare.py).

8 action kinds: assessment, diagnosis, prescription, procedure, surgery,
discharge, reassessment, referral.

Distinctive shape:
- **Patient consent as governance dimension**: not authority (only the patient grants it), separately tracked as observer
- **Emergency mode** lifts consent constraint from `block` to `warn` (implied consent permitted)
- **Contraindication flags** emit per-flag `escalate` constraints
- **High-dose flag** only applies to prescriptions (not other actions)
- **Inference kind is `abductive`** — clinical reasoning is best-explanation, distinct from `deductive` (software) or `inductive` (statistical research)
- **Reversibility tilts irreversible**: prescription, procedure, surgery, discharge are all `irreversible`; only reassessment reversible
- Risk flags surface emergency mode, missing consent, contraindications, high-dose alerts, surgery-without-specialist, irreversibility warnings

23 tests covering all 8 action kinds, consent variants, contraindication enumeration, high-dose-only-for-prescription, all 4 blast radii, end-to-end UCJA→SCCCE.

### `education` domain adapter

[education.py](mullu-control-plane/mcoi/mcoi_runtime/domain_adapters/education.py).

8 action kinds: course_offering, enrollment, assessment_design, grading,
grade_appeal, certification, accreditation, withdrawal.

Distinctive shape:
- **Three-tier authority**: instructor + curriculum committee + accreditor (the accreditor only attaches for certification/accreditation actions)
- **Prerequisite chain** as `escalate` constraints (registrar may override)
- **Accessibility (ADA) requirements** as `block` constraints (legal, not optional)
- **Learning objectives constraint** at `warn` level — outcome measurability check
- **Reversibility tilts content-dependent**: certification + accreditation `irreversible`; grading + withdrawal + grade-appeal `reversible`
- **Learner identifiers in observers** (capped at 3) — privacy-respectful audit trail
- Risk flags surface no-prerequisites, no-accessibility, no-objectives on outcome-bearing actions, certification-without-accreditor

21 tests covering all 8 action kinds, prerequisite/accessibility constraint emission, accreditor-attaches-conditionally, all 4 blast radii, end-to-end UCJA→SCCCE.

### `_cycle_helpers.py` — shared wiring

New module: [_cycle_helpers.py](mullu-control-plane/mcoi/mcoi_runtime/domain_adapters/_cycle_helpers.py).

Lifts the seven shared SCCCE step callbacks (`step_context_sensing`
through `step_value_evaluation`) into a single `run_default_cycle()`
function. Per-adapter variation flows through a `StepOverrides` dataclass
with sensible defaults matching `software_dev`.

The three new adapters use this helper. The existing three (`software_dev`,
`business_process`, `scientific_research`) keep their inline wiring because
each has slightly different defaults that pre-date the helper. Migration
to the helper is a separate cleanup workstream.

---

## Six domains, structurally distinct

| Domain | Authority shape | Primary constraint kind | Distinctive risk |
|--------|-----------------|-------------------------|------------------|
| `software_dev` | Repo write access + code reviewer | Acceptance criteria (block) | Cascade depth |
| `business_process` | Approval chain (per approver) | SLA deadline (escalate) | Dollar impact + blast radius |
| `scientific_research` | Peer reviewers (per reviewer) | Statistical significance (escalate) | Replication absence + power |
| `manufacturing` | QE + operator + ISO observers | Tolerance + yield + safety | Tight-tolerance × low-yield + safety-critical |
| `healthcare` | Clinician + specialists + consent | Contraindication + dosage + consent | Emergency mode + irreversibility |
| `education` | Instructor + committee + accreditor | Prerequisite + accessibility + objectives | Cert without accreditor + accessibility absence |

The framework's universality claim is now backed by six concrete data
points, each with distinct authority shape, constraint emission patterns,
reversibility logic, and risk flag conditions. Three is "evidence";
six is "the framework was actually built for this."

---

## Test counts

| Suite                                    | v4.6.0  | v4.7.0  |
| ---------------------------------------- | ------- | ------- |
| MUSIA-specific suites                    | 482     | 550     |
| manufacturing tests (new)                | n/a     | 24      |
| healthcare tests (new)                   | n/a     | 23      |
| education tests (new)                    | n/a     | 21      |

Doc/code consistency check passes.

---

## Compatibility

- All v4.6.0 endpoints unchanged
- All v4.6.0 adapters unchanged
- New adapters live alongside existing ones; pick whichever matches your domain
- The `_cycle_helpers.StepOverrides` API is internal — adapter authors can use it but its shape may change in cleanup releases

---

## What v4.7.0 still does NOT include

- **HTTP wrappers for domain adapters** — Python-only; no `POST /domains/<name>/process` endpoint
- **Existing adapters refactored to use `_cycle_helpers`** — `software_dev`, `business_process`, `scientific_research` still have inline wiring
- **Multi-process persistence backend** — `FileBackedPersistence` is single-process
- **Tenant onboarding/quotas/rate limits**
- **Φ_gov ↔ existing `governance_guard.py`** integration
- **Rust port** of substrate constructs
- **JWKS-based JWT key rotation**
- **Migration runner integration with the live audit log shape**

---

## Cumulative MUSIA progress

```
v4.0.0   substrate (Mfidel + Tier 1)
v4.1.0   full 25 constructs + cascade + Φ_gov + cognition + UCJA
v4.2.0   HTTP surface + governed writes + business_process adapter
v4.3.0   multi-tenant registry isolation
v4.3.1   auth-derived tenant resolution
v4.4.0   persistent tenant state
v4.5.0   auto-snapshot + JWT + scope enforcement
v4.6.0   scientific_research adapter + bulk migration runner
v4.7.0   manufacturing + healthcare + education adapters
```

550 MUSIA-specific tests; 99 docs; **six concrete domain adapters
covering all MUSIA v3.0 spec domains**; full HTTP surface; multi-tenant /
multi-auth / persistent / scope-enforced / migration-tooled.

---

## Honest assessment

v4.7.0 is the "spec coverage" release. The MUSIA v3.0 specification
listed six application domains. As of this release, all six exist as
concrete Python adapters with their own action kinds, distinctive
constraint shapes, and risk-flag heuristics. Anyone evaluating the
framework's reach can run all six end-to-end and see the same
substrate carry six structurally different domain shapes.

What it is not, yet: validated against actual production users in any
of the new domains. The shapes are designed from spec patterns; real
clinical informaticists, manufacturing engineers, and education
administrators may surface mismatches the unit tests don't catch.

**We recommend:**
- Upgrade in place. v4.7.0 is additive.
- For new domain adopters: pick the adapter closest to your shape, copy as a starting point, customize.
- The `_cycle_helpers.StepOverrides` pattern is the recommended foundation for adapter #7 onward.

---

## Contributors

Same single architect, same Mullusi project. v4.7.0 closes the v3.0 spec's
domain coverage list — six listed, six shipped.
