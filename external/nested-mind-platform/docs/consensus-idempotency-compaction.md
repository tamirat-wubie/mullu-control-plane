# Consensus idempotency and compaction

Consensus-certified apply now has an idempotency guard. Before applying a certificate, the platform checks previous apply reports.

Rules:

```text
no prior matching report                         → ready
same certificate + same operation + applied      → already_applied / skip
same entry id + different operation hash         → conflict / reject
```

Compaction is modeled as a decision, not an immediate destructive delete:

```text
certificates + apply reports + retention policy
  → ConsensusLogCompactionDecision
```

The decision identifies certificates to keep and certificates eligible for physical compaction. Physical deletion is intentionally separate so operators can review the decision or require backup verification before removing ledger rows.
