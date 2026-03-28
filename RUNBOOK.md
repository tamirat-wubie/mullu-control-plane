# Operational Runbook

## Startup Checks

### Verify the platform started correctly

```bash
# Health check
curl -s http://localhost:8000/health | jq .status
# Expected: "healthy"

# Readiness check (all subsystems operational)
curl -s http://localhost:8000/api/v1/readiness | jq .ready
# Expected: true

# Check route count
curl -s http://localhost:8000/openapi.json | jq '.paths | length'
# Expected: ~100+
```

### Verify migrations applied

```bash
curl -s http://localhost:8000/api/v1/deploy/readiness | jq .
```

### Verify LLM backend is connected

```bash
curl -s http://localhost:8000/api/v1/bootstrap | jq .default_backend
# Expected: "anthropic", "openai", or "stub"
```

## State Restore After Restart

The platform automatically restores state from file snapshots on startup if `MULLU_STATE_DIR` is set.

### Manual restore verification

```bash
# Check if state was restored (look for startup log)
curl -s http://localhost:8000/api/v1/dashboard | jq .tenants

# Verify budget state was restored
curl -s http://localhost:8000/api/v1/tenants | jq .total_spent
```

### If state restoration fails

1. Check `MULLU_STATE_DIR` points to the correct directory
2. Verify snapshot files exist: `ls $MULLU_STATE_DIR/mullu_state_*.json`
3. Validate snapshot JSON: `python -m json.tool $MULLU_STATE_DIR/mullu_state_budgets.json`
4. If corrupt, delete the snapshot file — the platform starts fresh

## Migration Rollback

Schema migrations are forward-only by design. If a migration causes issues:

1. **Do NOT** delete the `schema_version` table
2. Stop the platform
3. Restore the database from backup
4. Fix the migration SQL
5. Restart — the migration engine reapplies from the failed version

### Check current migration state

```sql
SELECT version, name, applied_at FROM schema_version ORDER BY version;
```

## Secret Rotation

### API Key Rotation

```bash
# Create new key
curl -s -X POST http://localhost:8000/api/v1/api-keys \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "prod", "scopes": ["read", "write"], "description": "rotated key"}'

# Revoke old key
curl -s -X DELETE http://localhost:8000/api/v1/api-keys/{old_key_id}

# Verify
curl -s http://localhost:8000/api/v1/api-keys | jq '.keys | length'
```

### LLM Provider Key Rotation

1. Set new key in environment: `ANTHROPIC_API_KEY=new_key`
2. Restart the platform (graceful shutdown saves state first)
3. Verify with a test completion:
   ```bash
   curl -s -X POST http://localhost:8000/api/v1/complete \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Say hello", "tenant_id": "test"}'
   ```

### Database Password Rotation

1. Update password in PostgreSQL
2. Update `POSTGRES_PASSWORD` in secrets manager / `.env`
3. Update `MULLU_DB_URL` with new password
4. Restart the platform

## Incident Response

### High Error Rate

```bash
# Check error metrics
curl -s http://localhost:8000/api/v1/metrics | jq .counters.errors_total

# Check circuit breaker state
curl -s http://localhost:8000/api/v1/circuit-breaker | jq .state
# If "open": LLM provider is failing, requests are being rejected

# Check SLA violations
curl -s http://localhost:8000/api/v1/sla/violations | jq .count

# Check recent audit trail for errors
curl -s "http://localhost:8000/api/v1/audit?outcome=error&limit=10" | jq .entries
```

### Budget Exhaustion

```bash
# Check tenant budgets
curl -s http://localhost:8000/api/v1/tenants | jq .

# Check specific tenant
curl -s http://localhost:8000/api/v1/tenant/{tenant_id}/budget | jq .

# Reset budget if needed (create new budget policy)
curl -s -X POST http://localhost:8000/api/v1/tenant/budget \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "affected_tenant", "max_cost": 100.0}'
```

### LLM Provider Down

1. Check circuit breaker: `curl -s http://localhost:8000/api/v1/circuit-breaker`
2. If open, the platform is auto-protecting — requests return 503
3. The circuit breaker auto-recovers after `recovery_timeout_ms` (default 60s)
4. If persistent, check provider status pages
5. Consider switching to a different provider:
   - Set `MULLU_LLM_BACKEND=openai` (or `anthropic`)
   - Restart

### Database Connection Issues

```bash
# Check deep health
curl -s http://localhost:8000/api/v1/health/deep | jq .components

# Check store status
curl -s http://localhost:8000/api/v1/health | jq .ledger_entries
```

If database is unreachable:
1. Verify `MULLU_DB_URL` is correct
2. Check PostgreSQL is running: `pg_isready -h db_host -p 5432`
3. Check connection pool: `curl -s http://localhost:8000/api/v1/dashboard`
4. Restart if connection pool is exhausted

## Monitoring Dashboards

```bash
# Full system snapshot (all subsystems in one call)
curl -s http://localhost:8000/api/v1/snapshot | jq .

# Monitoring vitals (uptime, error rate, cost, health)
curl -s http://localhost:8000/api/v1/monitor | jq .

# Prometheus metrics (for Grafana)
curl -s http://localhost:8000/metrics

# Grafana dashboard JSON
curl -s http://localhost:8000/api/v1/grafana/dashboard
```

## Graceful Shutdown

The platform automatically:
1. Saves budget state, audit summary, and cost analytics to file snapshots
2. Flushes metrics
3. Closes database connections

To trigger manually: send `SIGTERM` to the uvicorn process.

Verify shutdown saved state:
```bash
ls -la $MULLU_STATE_DIR/mullu_state_*.json
```
