<!--
Purpose: define the Foundation Mode repository observation evidence packet before live repository reads can become planning input.
Governance scope: OCE field completeness, RAG repository-source binding, CDCV observation-to-admission causality, CQTE freshness and proof-state gates, UWMA receipt anchoring, SRCA finite validation, and PRS focused validator closure.
Dependencies: docs/94_observation_evidence_acquisition_architecture.md, schemas/repository_observation_evidence_packet.schema.json, examples/repository_observation_evidence_packet.foundation.json, scripts/validate_repository_observation_evidence_packet.py, tests/test_validate_repository_observation_evidence_packet.py.
Invariants: repository observation is not execution; the Foundation example performs no live repository read, filesystem write, connector call, file-content read, secret read, runtime dispatch, deployment mutation, terminal closure, or success claim; hard-constraint planning remains blocked while proof state is Unknown.
-->

# Repository Observation Evidence Packet Contract

<!-- TYPE: Reference -->
<!-- AUDIENCE: architecture maintainers, repository adapter implementers, governance reviewers -->

> **In one box:** This page defines the first source-specific evidence packet
> for the observation architecture: local repository state. The checked-in
> packet is only a Foundation Mode shape and does not claim a live repository
> read.

---

## Boundary

`RepositoryObservationEvidencePacket` is a digest-only planning evidence packet.
It is not a repository worker, runtime dispatch, file reader, connector, or
terminal closure certificate.

It binds:

1. Repository and worktree references.
2. Branch, status, diff, and file-inventory digest refs.
3. Planning admission state.
4. Authority denials.
5. Privacy guards.
6. Recovery action for future live read-only observation.

It denies:

1. Live repository read in the Foundation example.
2. Filesystem writes.
3. File-content reads.
4. Secret reads.
5. Connector calls.
6. External writes.
7. Runtime dispatch.
8. Deployment mutation.
9. Terminal closure.
10. Success claims.

## Foundation Example

The Foundation Mode example is:

```text
examples/repository_observation_evidence_packet.foundation.json
```

It intentionally records:

```text
planning_admission = defer
proof_state = Unknown
solver_outcome = AwaitingEvidence
hard_constraint_planning_allowed = false
soft_utility_planning_allowed = true
live_evidence_required = true
```

The packet can support soft planning discussion only. It cannot support
hard-constraint planning until a live read-only repository observation receipt
exists.

## Required Validators

Run:

```powershell
python scripts/validate_repository_observation_evidence_packet.py
python -m pytest tests/test_validate_repository_observation_evidence_packet.py -q
python scripts/validate_observation_evidence_acquisition_architecture.py
python -m pytest tests/test_validate_observation_evidence_acquisition_architecture.py -q
```

STATUS:
  Completeness: 100%
  Invariants verified: digest-only repository observation, no live repository read claim, no filesystem write, no file-content read, no secret read, no connector call, no runtime dispatch, no deployment mutation, no terminal closure, hard-constraint planning blocked on Unknown proof state
  Open issues: live read-only repository observation producer remains AwaitingEvidence
  Next action: add a producer only after command allowlist, digest policy, and receipt persistence boundary are selected
