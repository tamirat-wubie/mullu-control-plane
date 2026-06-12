# Multi-operator readiness waivers

v18 allowed waiver certificates. v19 adds a stronger certificate for risky staging exceptions.

```text
ReadinessWaiverProposal
  → MultiOperatorWaiverVote[]
  → MultiOperatorWaiverPolicy
  → MultiOperatorWaiverCertificate
```

Default policy requires:

```text
minimum approvals: 2
minimum distinct teams: 2
required roles: maintainer + security
risk owner cannot approve own waiver
security required for critical blockers
```

The certificate preserves all findings. Approval does not imply production readiness; it is a staging risk-control object.
