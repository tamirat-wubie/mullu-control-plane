# Mullu Platform MCOI Runtime -- Operator Guide v0.1.0

**Version:** 0.1.0 (internal alpha)
**Date:** 2026-03-19

## Installation

From the repository root, install in development mode:

```
cd mcoi/
pip install -e .
```

This makes the `mcoi` CLI available in your active Python environment.

## CLI Commands

### mcoi run

Execute a single operator request from a JSON file or inline JSON.

```
mcoi run mcoi/examples/request-echo.json
mcoi run --profile local-dev mcoi/examples/request-echo.json
mcoi run --config mcoi/examples/config-local-dev.json mcoi/examples/request-with-bindings.json
```

The command prints a run summary followed by an execution summary, then exits with
code 0 on success or 1 on failure.

### mcoi status

Display current runtime configuration and provider state.

```
mcoi status
mcoi status --profile local-dev
```

Output includes enabled executor routes, observer routes, allowed planning classes,
and registered provider count.

### mcoi profiles

List available named configuration profiles.

```
mcoi profiles
```

### mcoi packs

List available policy packs with their IDs, names, descriptions, and rule counts.

```
mcoi packs
```

## Configuration Profiles

Profiles provide named, deterministic configurations. Use `--profile <name>` with
any CLI command.

| Profile | Autonomy Mode | Planning Classes | Executor Routes | Observer Routes |
|---|---|---|---|---|
| `local-dev` | bounded_autonomous | constraint | shell_command | filesystem, process |
| `safe-readonly` | observe_only | constraint | shell_command | filesystem, process |
| `operator-approved` | approval_required | constraint | shell_command | filesystem, process |
| `sandboxed` | suggest_only | constraint | shell_command | filesystem |
| `pilot-prod` | approval_required | constraint | shell_command | filesystem, process |

You can also pass a JSON config file directly with `--config path/to/config.json`.
Config files use the same keys:

```json
{
  "allowed_planning_classes": ["constraint"],
  "enabled_executor_routes": ["shell_command"],
  "enabled_observer_routes": ["filesystem", "process"]
}
```

## Example Request Files

### mcoi/examples/request-echo.json

Runs a portable Python print command through the shell executor:

```json
{
  "request_id": "example-001",
  "subject_id": "operator",
  "goal_id": "run-print",
  "template": {
    "template_id": "python-print-tpl",
    "action_type": "shell_command",
    "command_argv": ["{python_executable}", "-c", "print('Hello from MCOI')"]
  },
  "bindings": {}
}
```

### mcoi/examples/request-with-bindings.json

Runs a portable Python print command with a bound message:

```json
{
  "request_id": "example-002",
  "subject_id": "operator",
  "goal_id": "run-print-with-binding",
  "template": {
    "template_id": "python-print-binding-tpl",
    "action_type": "shell_command",
    "command_argv": ["{python_executable}", "-c", "import sys; print(sys.argv[1])", "{message}"],
    "required_parameters": ["message"]
  },
  "bindings": {
    "message": "Hello from MCOI bindings"
  }
}
```

The CLI injects `python_executable` automatically from the local interpreter.
Override it explicitly with the `MCOI_PYTHON_EXECUTABLE` environment variable if
you need a different Python binary.

### Shipped Config Files

- `mcoi/examples/config-local-dev.json` mirrors the local development route set.
- `mcoi/examples/config-safe-readonly.json` keeps the same planning class but limits
  observation to the filesystem surface.

## Reading Operator Reports

After `mcoi run`, the CLI prints two report sections.

### Run Summary

| Field | Meaning |
|---|---|
| `request_id` | The ID from your request file |
| `goal_id` | The goal being pursued |
| `completed` | Whether the full run cycle finished (policy, dispatch, verification) |
| `dispatched` | Whether the policy gate allowed execution |
| `verification_closed` | Whether verification produced a definitive result |
| `validation_passed` | Whether the request passed structural validation |
| `execution_route` | Which executor adapter handled the action |
| `provider_count` | Number of registered providers |
| `unhealthy_providers` | Providers in degraded or unavailable state |

### Execution Summary

Contains detailed execution results, trace references, and timing information for
the dispatched action.

## Understanding Verification Closure

Every run produces a verification state:

- **Closed (pass):** The action was executed and verification confirmed the expected
  outcome. The run is complete.
- **Closed (fail):** The action was executed but verification found the outcome did
  not match expectations. The run is complete but unsuccessful.
- **Open:** Verification has not yet produced a result. This can happen if the
  policy gate blocked dispatch (no execution to verify) or if the verification
  engine encountered an error.

A run with `completed: true` always has closed verification. A run with
`completed: false` may have open verification or may have been blocked before
dispatch.

## Understanding Structured Errors

When a run encounters problems, the report includes structured errors with three
classification axes:

**Error families:** ValidationError, ObservationError, AdmissibilityError,
PolicyError, ExecutionError, VerificationError, ReplayError, PersistenceError,
IntegrationError, CapabilityError, ConfigurationError.

**Recoverability:** retryable, reobserve_required, replan_required,
approval_required, fatal_for_run, unsupported.

**Source planes:** governance, perception, world_state, capability, planning,
execution, verification, memory, communication, external_integration, temporal,
coordination, meta_reasoning.

These classifications tell you what went wrong, whether it is recoverable, and which
subsystem produced the error.

## Provider Health

Providers transition between three states:

- **Healthy:** Operating normally within declared scope and rate limits.
- **Degraded:** Responding but with elevated error rates or latency. Operations may
  still succeed but reliability is reduced.
- **Unavailable:** Not responding or consistently failing. Operations routed to this
  provider will fail.

Unhealthy providers appear in the run summary. Use `mcoi status` to check the
current provider state before executing requests.

## Limitations

This is an internal alpha with significant limitations. See
[KNOWN_LIMITATIONS_v0.1.md](KNOWN_LIMITATIONS_v0.1.md) for the full list. Key
points for operators:

- Working/episodic memory is lost on restart (in-memory only).
- Policy packs can be listed but are not yet enforced during evaluation.
- No web UI -- CLI only.
- No background scheduling -- temporal contracts exist but no daemon monitors them.
- Shell executor inherits OS permissions with no additional sandboxing.
