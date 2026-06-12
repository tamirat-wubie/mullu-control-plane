# Engineering implementation jobs

v18 converts creative-engineering suggestions into scheduled implementation jobs.

```text
CreativeEngineeringReport
  → priority sorted suggestions
  → EngineeringImplementationJobPlan
  → ScheduledJob records
```

Each generated job carries:

```text
suggestion id
title
priority
mechanism
invariant guard
implementation delta
validation probe
rollback plan
acceptance criteria
scheduled job payload hash
```

This prevents hardening suggestions from remaining advisory text. The scheduler can now own the implementation backlog as operational evidence.
