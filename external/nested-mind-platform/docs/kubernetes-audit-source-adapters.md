# Kubernetes audit source adapters

The Kubernetes audit source adapter converts audit collector reports into source-specific receipts.

Supported source labels:

```text
api_server_audit_log
webhook_sink
file_tail
external_gateway
```

The adapter receipt binds:

```text
source plan id
collector report id
source kind
observed event count
audit UIDs
provider response hash
failure list
receipt hash
```

A collected receipt must include at least one audit UID. This prevents staging chaos promotion from relying on a generic log scrape with no event identity.
