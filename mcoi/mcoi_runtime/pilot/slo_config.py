"""Phase 124F — SLO Definitions and Runbook Configuration."""
from __future__ import annotations

PILOT_SLOS = {
    "availability": {"metric": "uptime_percent", "target": 99.5, "unit": "percent"},
    "queue_freshness": {"metric": "queue_staleness_seconds", "target": 300, "unit": "seconds"},
    "evidence_retrieval_latency": {"metric": "evidence_p95_ms", "target": 2000, "unit": "ms"},
    "report_generation": {"metric": "report_gen_p95_ms", "target": 10000, "unit": "ms"},
    "connector_reliability": {"metric": "connector_success_rate", "target": 99.0, "unit": "percent"},
}

PILOT_RUNBOOKS = {
    "connector_failure": {
        "title": "Connector Failure Recovery",
        "category": "incident",
        "procedure": "1. Check connector health endpoint. 2. Verify credentials. 3. Check network/firewall. 4. Restart connector. 5. If persistent, switch to degraded mode. 6. Escalate to engineering.",
    },
    "degraded_mode": {
        "title": "Degraded Mode Operation",
        "category": "incident",
        "procedure": "1. Identify degraded components. 2. Activate backup connectors if available. 3. Notify operators. 4. Queue non-critical work. 5. Monitor recovery.",
    },
    "backup_restore": {
        "title": "Backup and Restore",
        "category": "maintenance",
        "procedure": "1. Trigger state snapshot across all engines. 2. Export to durable storage. 3. For restore: stop all engines, load snapshot, verify state_hash, resume.",
    },
    "tenant_support": {
        "title": "Tenant Support Workflow",
        "category": "support",
        "procedure": "1. Verify tenant identity. 2. Check tenant bootstrap status. 3. Review connector health. 4. Check SLO compliance. 5. Escalate if needed.",
    },
    "rollback": {
        "title": "Pilot Rollback Procedure",
        "category": "incident",
        "procedure": "1. Stop all active workflows. 2. Snapshot current state. 3. Rollback bootstrap. 4. Verify clean state. 5. Re-bootstrap if needed.",
    },
}
