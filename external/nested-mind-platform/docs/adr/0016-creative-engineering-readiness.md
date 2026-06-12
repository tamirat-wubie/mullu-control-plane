# ADR 0016: Creative Engineering and Readiness Gates

## Decision

Introduce a v17 creative-engineering layer that treats suggestions, rehearsals, fuzz cases, and readiness gates as auditable artifacts.

## Rationale

The platform has accumulated strong production boundaries: append-only events, signatures, snapshots, backup verification, worker receipts, provider boundaries, and consensus retention governance. The next weakness is not another isolated component; it is the lack of a systematic way to convert fractures into testable hardening work.

## Consequences

Constructive:

```text
+ suggestions become mechanism-bound and validation-bound
+ chaos rehearsal becomes a release input
+ invariant fuzzing becomes deterministic and replayable
+ readiness gates can block promotion with explicit evidence
```

Fracture:

```text
- generated suggestions do not replace implementation
- rehearsal execution still requires staging harnesses
- fuzz cases are generated, not yet automatically run in CI in this environment
```
