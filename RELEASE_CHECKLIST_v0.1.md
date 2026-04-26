# Release Checklist — v0.1 Internal Alpha

## Test Gates

- [x] All Python tests pass (`pytest -q`)
- [x] All Rust tests pass (`cargo test`)
- [x] Red-team harness passes (`python scripts/run_red_team_harness.py --output .change_assurance/red_team_harness.json --min-pass-rate 1.0`)
- [x] Golden scenario suite passes (12 end-to-end scenarios)
- [x] Deserialization hardening tests pass (nested dataclass round-trips)
- [x] Persistence round-trip tests pass (all stores)
- [x] No bare except clauses in codebase
- [x] No TODO/FIXME/HACK comments in codebase

## Documentation Gates

- [x] RELEASE_NOTES_v0.1.md written
- [x] KNOWN_LIMITATIONS_v0.1.md written and current
- [x] SECURITY_MODEL_v0.1.md written
- [x] OPERATOR_GUIDE_v0.1.md written
- [x] PILOT_WORKFLOWS_v0.1.md written
- [x] PILOT_CHECKLIST_v0.1.md written
- [x] PILOT_OPERATIONS_GUIDE_v0.1.md written
- [x] Shared schemas validate with `scripts/validate_schemas.py --strict`
- [x] Shipped artifacts and document references validate with `scripts/validate_artifacts.py --strict`
- [x] Release status derives from `scripts/validate_release_status.py --strict`
- [x] CI workflow retains the full gated release command set in `.github/workflows/ci.yml`
- [x] Release notes publish red-team pass rate and witness hash from `.change_assurance/red_team_harness.json`

## Configuration Gates

- [x] All example configs validated (examples/*.json)
- [x] All CLI commands documented and tested (run, status, profiles, packs)
- [x] All built-in profiles load correctly (local-dev, safe-readonly, operator-approved, sandboxed, pilot-prod)
- [x] All 3 policy packs load correctly (default-safe, strict-approval, readonly-only)
- [x] Builtin profiles are frozen (MappingProxyType)

## Provider Gates

- [x] Provider registry checks invocability before dispatch
- [x] Disabled providers fail closed
- [x] Unavailable providers fail closed (3 consecutive failures)
- [x] URL scope enforcement works
- [x] Provider health updates from invocation results
- [x] Provider health recovery on success

## Runtime Integrity Gates

- [x] Policy gate precedes execution (Invariant 6)
- [x] No action complete without verification closure (Invariant 7)
- [x] Replay never re-executes uncontrolled effects (Invariant 4)
- [x] Same inputs produce same outputs (deterministic serialization)
- [x] Early-exit reports include runtime state (world-state, providers, meta-reasoning)
- [x] Temporal evaluation samples clock once (no TOCTOU)
- [x] Memory promotion catches duplicates (returns REJECTED, not throws)
- [x] World-state confidence propagation handles cycles (returns 0.0)

## Audit Findings

- [x] Audit 1 complete — 7 bugs fixed
- [x] Audit 2 complete — 5 bugs fixed
- [x] All 12 bugs verified fixed with regression tests

## Known Accepted Limitations

- [ ] Registry backend uses dynamic make_dataclass for opaque restoration
- [x] Coordination engine supports explicit checkpoint/restore persistence
- [ ] Working/episodic memory persistence is explicit and opt-in
- [x] HTTP connector read timeout enforcement added (v3.9.1)
- [x] API key auth with scopes, JWT auth, per-session RBAC checks
- [x] Field-level encryption at rest (AES-256-GCM, optional cryptography dep)

## Release Decision

Status: **READY FOR INTERNAL ALPHA / CONTROLLED PILOT**

Release status source:
- `python scripts/validate_release_status.py --strict`

Conditions for use:
- Internal development and experimentation only
- Operator-supervised execution
- Local/bounded provider configurations
- Known limitations explicitly accepted by pilot participants
