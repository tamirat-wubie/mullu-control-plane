# Action promotion gates

The v25 action promotion gate evaluates whether connector-side action evidence is sufficient to permit an approved live action.

Default requirements:

```text
connector evidence complete
Kubernetes audit source receipt present
notification provider receipt present
```

A report can be:

```text
blocked
ready_for_staging_action
ready_for_approved_live_action
```

The current implementation uses the strongest status only when all configured evidence is present. This keeps action promotion separate from symbolic mind-state mutation.
