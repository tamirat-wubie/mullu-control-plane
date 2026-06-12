# Connector orchestration

v25 introduces an orchestration layer for evidence-producing connector workers.

The orchestration object does not execute provider side effects itself. It binds evidence from:

- live secret connector receipts
- GitHub token exchange worker receipts
- Kubernetes audit-log collector reports
- notification delivery client receipts
- optional external evidence artifacts

The default required artifact set is:

```text
secret
github_token
kubernetes_audit
notification
```

A connector orchestration report is blocked until all required evidence artifacts are present. In `execute_approved` mode, a complete evidence set yields `evidence_complete`.
