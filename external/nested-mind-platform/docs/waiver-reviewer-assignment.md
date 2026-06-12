# Waiver reviewer assignment and escalation

v21 adds operator assignment evidence for waiver reviews.

```text
WaiverReviewQueueItem
  + reviewer candidates
  + escalation targets
  → WaiverReviewerAssignmentPlan
  → optional WaiverEscalationCertificate
```

Assignment prefers available reviewers with lower queue depth while preserving role coverage and team separation. Missing roles become explicit blockers. If all missing roles have escalation targets, the assignment enters `needs_escalation`; otherwise it is rejected.

The escalation certificate binds the review id, proposal id, missing roles, target operators, reason, and timestamp.
