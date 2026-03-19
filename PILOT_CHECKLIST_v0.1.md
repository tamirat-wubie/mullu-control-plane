# Pilot Checklist v0.1

## Pre-flight

- [ ] All 556+ Python tests pass
- [ ] All 21 Rust tests pass
- [ ] Config profile matches pilot workflow requirements
- [ ] Autonomy mode is explicitly set in config
- [ ] Example request files are valid JSON

## Per-pilot verification

### Pilot 1: Approval-Gated Command
- [ ] Autonomy mode is `approval_required`
- [ ] Execution blocked without approval artifact
- [ ] Approval email generated with correlation_id
- [ ] Approval response parsed correctly
- [ ] Execution proceeds after approval
- [ ] Run report shows `autonomy_mode: approval_required`
- [ ] Console renders autonomy mode

### Pilot 2: Document-to-Action
- [ ] Autonomy mode is `bounded_autonomous`
- [ ] Document fingerprint is deterministic
- [ ] All expected fields extracted
- [ ] Verification passes with correct values
- [ ] Verification fails with wrong values
- [ ] Correct skill selected and executed
- [ ] Completion notice carries execution_id and skill_id

### Pilot 3: Failure-Escalation
- [ ] Autonomy mode is `bounded_autonomous`
- [ ] Skill failure produces structured error
- [ ] Confidence decreases after failure
- [ ] Degraded capability detected by meta-reasoning
- [ ] Escalation email generated with goal_id linkage
- [ ] Run report shows provider IDs (or None if none registered)

## Post-flight

- [ ] No silent failures in any pilot
- [ ] All structured errors have error_code, family, source_plane
- [ ] All reports have autonomy_mode populated
- [ ] Known limitations reviewed and accepted

## Known acceptable limitations (v0.1)

- Shell executor may fail in test environment (no real shell)
- Provider IDs are None when no providers are registered
- Skill execution through governed path may fail on template validation
- This is expected behavior, not a bug
