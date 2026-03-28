# Promotion Checklist: production-candidate → production-ready

## Gate Criteria

All gates must be green before promoting to production-ready.

### Gate 1: Default Test Suite
- [ ] `pytest tests/ -m "not soak and not live_provider and not infra_pg and not infra_smtp"` — all pass
- [ ] No regressions from previous release

### Gate 2: Nightly Infrastructure Certification
- [ ] PostgreSQL certification green (`pytest -m infra_pg`)
- [ ] SMTP certification green (`pytest -m infra_smtp`)
- [ ] Stable for 3+ consecutive nightly runs

### Gate 3: LLM Provider Certification
- [ ] Anthropic certification green (`pytest -m live_provider` with ANTHROPIC_API_KEY)
- [ ] OpenAI certification green (`pytest -m live_provider` with OPENAI_API_KEY)
- [ ] Budget enforcement proven with real costs
- [ ] Ledger entries created for real provider calls

### Gate 4: Staging Drill
- [ ] `python scripts/staging_drill.py` — all 13 steps pass
- [ ] Run against stub backend: ALL PASSED
- [ ] Run against real provider backend: ALL PASSED
- [ ] Restart server, re-run drill: state continuity verified

### Gate 5: Release Validation
- [ ] `python scripts/validate_release_status.py --strict` — passes
- [ ] Schema validation: `python scripts/validate_schemas.py --strict` — passes
- [ ] All release docs version-aligned

## How to Run

### Local (quick)
```bash
cd mcoi
pytest tests/ -m "not soak" --tb=short -q
python ../scripts/staging_drill.py
```

### Full certification (requires Docker)
```bash
# Start infra
docker compose -f docker-compose.nightly.yml up -d

# Wait for services
sleep 5

# Run infra certification
cd mcoi
MULLU_TEST_DB_URL="postgresql://mullu:test@localhost:5432/mullu_test" \
  pytest -m "infra_pg" -v --tb=short

pytest -m "infra_smtp" -v --tb=short

# Run provider certification (if keys available)
ANTHROPIC_API_KEY=... pytest -m "live_provider" -v --tb=short

# Staging drill
MULLU_ENV=test uvicorn mcoi_runtime.app.server:app --port 8000 &
python ../scripts/staging_drill.py
kill %1

# Cleanup
docker compose -f docker-compose.nightly.yml down
```

## Promotion Decision

```
production-candidate → production-ready
ONLY IF:
  Gate 1: green ✓
  Gate 2: green for 3+ nights ✓
  Gate 3: green ✓
  Gate 4: green (stub + real) ✓
  Gate 5: green ✓
  No P0/P1 regressions ✓
```

Sign-off: _______________  Date: _______________
