# SDLC Release Policy

Purpose: define release and deployment readiness rules for governed software changes.
Governance scope: OCE release fields, RAG release-to-deployment linkage, CDCV evidence-bound claims, CQTE decidable readiness checks, UWMA release receipts, and PRS deployment closure.
Dependencies: `docs/SDLC.md`, `schemas/sdlc_release_candidate.schema.json`, `schemas/sdlc_deployment_candidate.schema.json`, `schemas/sdlc_recovery_handoff_receipt.schema.json`, and `scripts/validate_sdlc_release_readiness.py`.
Invariants: no release claim may exceed evidence; no production claim may pass without deployment witness, public health evidence, runtime conformance, proof verification, and audit verification.

## Release Candidate

A release candidate must include:

```text
release_id
version
commit_range
change_set
breaking_changes
migration_required
schemas_changed
validators_changed
security_fixes
known_limitations
deployment_status
rollback_plan
release_receipt
evidence_bound_claims
```

Release is allowed when:

```text
tests_passed
and security_high_open = 0
and schemas_valid
and release_notes_exist
and rollback_plan_exists
and evidence_bound_claims
```

## Deployment Candidate

A deployment candidate must include:

```text
deployment_id
release_id
environment
runtime_host
health_endpoint
runtime_conformance_certificate
deployment_witness
rollback_command
operator
approved_at
public_production_claim
```

Production claim is allowed when:

```text
deployment_witness = published
and public_health = declared
and runtime_conformance = passing
and proof_verify_endpoint = reachable
and audit_verify_endpoint = reachable
```

Pilot, staging, or not-published candidates may remain `not_published` when the artifact explicitly records the claim boundary and keeps public production health undeclared.

## Rollback And Incident Linkage

Effect-bearing release and deployment candidates must state the rollback or incident handoff path before publication.

```text
release_or_deployment_effect
-> rollback_plan
-> incident_recovery_path_if_rollback_fails
-> terminal_closure_certificate_or_sdlc_closure_receipt
```

Rollback evidence may reference `rollback_plan`, `rollback_command`, deployment witness receipts, incident recovery plans, terminal closure certificates, or SDLC closure receipts. Incident handoff is required when rollback is partial, blocked, or leaves an accepted residual risk.

Terminal closure must retain `sdlc_recovery_handoff_receipt` evidence:

```text
sdlc_recovery_handoff_receipt
-> rollback_state
-> rollback_refs
-> incident_recovery_refs
-> accepted_risk_refs
-> terminal_closure_ref
```
