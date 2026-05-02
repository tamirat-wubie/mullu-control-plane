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

## Gateway MCP Capability Imports

Gateway MCP tools are activated through a governed manifest, not by ad-hoc
runtime registration. The operator procedure is documented in
[`docs/55_mcp_capability_manifest.md`](docs/55_mcp_capability_manifest.md).
The machine-readable handoff checklist is
`examples/mcp_operator_handoff_checklist.json`.

Minimum sequence:

1. Validate the checklist and manifest:

```powershell
python scripts\validate_mcp_operator_checklist.py --checklist examples\mcp_operator_handoff_checklist.json --json
python scripts\validate_mcp_capability_manifest.py --manifest examples\mcp_capability_manifest.json --json
```

2. Start the gateway with the same manifest:

```powershell
$env:MULLU_MCP_CAPABILITY_MANIFEST_PATH = "examples\mcp_capability_manifest.json"
python -m gateway.server
```

3. Inspect `/mcp/operator/read-model` for `mcp_manifest_valid: true`.
4. Collect `/runtime/conformance` and verify `mcp_capability_manifest_valid: true`.
5. Verify `/runtime/conformance` also reports `capability_plan_bundle_canary_passed: true`.
6. Run deployment preflight with the manifest path before witness dispatch.
7. Persist the deployment orchestration receipt at
   `$env:MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT`.

If the manifest is invalid, gateway deployment readiness remains blocked until
the manifest produces certified capabilities, ownership records, approval
policies, and an escalation policy. If capability plan evidence bundle export
is not wired, deployment readiness remains blocked until `/capability-plans/{plan_id}/closure`
can return the terminal certificate and `plan_evidence_bundle`.

## General-Agent Promotion Handoff

General-agent production promotion is executed from a governed handoff packet,
not from ad-hoc shell steps. Start with
[`docs/59_general_agent_promotion_handoff_packet.md`](docs/59_general_agent_promotion_handoff_packet.md).

Minimum sequence:

1. Validate the machine-readable handoff packet:

```powershell
python scripts\validate_general_agent_promotion_handoff_packet.py --packet examples\general_agent_promotion_handoff_packet.json --json
```

2. Validate the machine-readable checklist:

```powershell
python scripts\validate_general_agent_promotion_operator_checklist.py --checklist examples\general_agent_promotion_operator_checklist.json --json
```

3. Follow the operator runbook:

```text
docs/58_general_agent_promotion_operator_runbook.md
```

4. Validate the aggregate closure plan before approval or execution:

```powershell
python scripts\validate_general_agent_promotion_closure_plan_schema.py --output .change_assurance\general_agent_promotion_closure_plan_schema_validation.json --strict
python scripts\validate_general_agent_promotion_closure_plan.py --output .change_assurance\general_agent_promotion_closure_plan_validation.json --strict
```

5. Run the handoff preflight without printing secret values:

```powershell
python scripts\preflight_general_agent_promotion_handoff.py --output .change_assurance\general_agent_promotion_handoff_preflight.json --json
```

6. Keep promotion blocked until the final strict validator passes:

```powershell
python scripts\validate_general_agent_promotion.py --strict --output .change_assurance\general_agent_promotion_readiness.json
```

The current handoff remains `pilot-governed-core` until live adapter receipts,
governed credential approvals, deployment witness publication, and public health
evidence are all closed.

## Limitations

This is an internal alpha with significant limitations. See
[KNOWN_LIMITATIONS_v0.1.md](KNOWN_LIMITATIONS_v0.1.md) for the full list. Key
points for operators:

- Working/episodic memory persistence is available, but only when you wire a
  local memory store and request restore explicitly.
- Coordination state persistence is available via explicit checkpoint/restore.
  Set `MULLU_COORDINATION_DIR` to control storage location (defaults to
  `$MULLU_DATA_DIR/mullu-coordination` or system temp). Checkpoints carry lease
  expiration (default 1 hour), retry counts (max 3), and policy pack identity.
  On restore, expired leases are rejected, policy pack drift triggers operator
  review, and excessive retries cause abort.
- LLM providers follow a 3-tier stack:
  - **Tier 1 (certified):** Anthropic (`ANTHROPIC_API_KEY`), OpenAI (`OPENAI_API_KEY`)
  - **Tier 2 (hosted free-tier):** Gemini (`GEMINI_API_KEY`) — cheap bulk inference, dev/testing
  - **Tier 3 (local/private):** Ollama (`OLLAMA_BASE_URL`, default `http://localhost:11434`) — offline fallback, private workloads
  Set `MULLU_LLM_BACKEND` to select default provider (auto-detects from available keys).
- Policy packs are enforced during evaluation through the runtime policy gate.
- No web UI -- CLI only.
- No background scheduling -- temporal contracts exist but no daemon monitors them.
- Shell executor inherits OS permissions with no additional sandboxing.
