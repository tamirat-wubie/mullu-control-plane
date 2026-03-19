# Error Taxonomy

Scope: all Mullu Platform modules. Every error MUST be classifiable, attributable, and actionable.

An unclassified error is a platform defect. An error without a source plane is untraceable. An error without a recoverability class leaves the caller guessing.

## Required fields per error

Every error record MUST contain these fields, in order:

`error_id`, `family`, `source_plane`, `recoverability`, `message`, `context`, `trace_id`, `timestamp`

Rules:
- `error_id` MUST be unique per error instance.
- `family` MUST be one of the defined error families below.
- `source_plane` MUST identify which capability plane produced the error.
- `recoverability` MUST be one of the defined recoverability classes below.
- `context` MUST include the identity chain sufficient to locate the failure point.
- `trace_id` MUST link the error to its causal trace entry.

## Error families

### ValidationError

Source plane: any plane performing input validation.
Meaning: input data fails structural or semantic checks before processing begins.
Typical recoverability: `retryable` (after caller fixes input).

### ObservationError

Source plane: Perception Plane.
Meaning: raw input could not be converted to a structured observation.
Typical recoverability: `reobserve_required`.

### AdmissibilityError

Source plane: Memory Plane, Planning Plane.
Meaning: knowledge or data failed the learning admission gate and cannot be used.
Typical recoverability: `approval_required`.

### PolicyError

Source plane: Governance Plane.
Meaning: the policy gate denied or escalated the requested action.
Typical recoverability: `approval_required` (if escalatable), `fatal_for_run` (if hard deny).

### ExecutionError

Source plane: Execution Plane.
Meaning: an approved action failed during execution.
Typical recoverability: `retryable`, `replan_required`, or `fatal_for_run` depending on failure mode.

### VerificationError

Source plane: Verification Plane.
Meaning: verification of an execution result failed or could not be completed.
Typical recoverability: `reobserve_required` or `replan_required`.

### ReplayError

Source plane: any plane during replay.
Meaning: replay diverged from the recorded trace or encountered an unreplayable effect.
Typical recoverability: `fatal_for_run` (replay cannot fabricate missing data).

### PersistenceError

Source plane: Memory Plane, any plane performing storage operations.
Meaning: data could not be stored, retrieved, or integrity-verified.
Typical recoverability: `retryable` (transient), `fatal_for_run` (corruption).

### IntegrationError

Source plane: External Integration Plane.
Meaning: an external system call failed, timed out, or returned unexpected data.
Typical recoverability: `retryable` (transient), `reobserve_required` (stale data).

### CapabilityError

Source plane: Capability Plane.
Meaning: a required capability is missing, revoked, or incompatible.
Typical recoverability: `unsupported` (if capability does not exist), `approval_required` (if capability is restricted).

### ConfigurationError

Source plane: any plane during initialization.
Meaning: platform or module configuration is missing, malformed, or contradictory.
Typical recoverability: `fatal_for_run` (cannot proceed with bad configuration).

## Recoverability classes

- `retryable` — the same operation may be retried with the same or corrected inputs. Retry limits MUST be declared by the consuming implementation.
- `reobserve_required` — the operation requires fresh observation before retry. Stale data MUST NOT be reused.
- `replan_required` — the current plan is invalidated. The Planning Plane MUST produce a new plan.
- `approval_required` — human or policy approval is needed before the operation can proceed.
- `fatal_for_run` — the current run cannot recover. The run MUST terminate with this error recorded.
- `unsupported` — the requested operation is not supported by the platform. No retry or workaround exists within the current capability set.

## Source plane attribution rules

1. The plane that detects the error MUST be recorded as `source_plane`.
2. If an error originates in one plane but is detected in another, both MUST be recorded: `source_plane` for detection, `originating_plane` as an additional context field.
3. Errors that cross plane boundaries MUST NOT lose their original source attribution.
4. A plane MUST NOT reclassify another plane's error family. It MAY wrap it with additional context.

## Propagation rules

1. Errors MUST propagate up the call chain until a handler accepts responsibility.
2. Silent error swallowing is prohibited. Every error MUST be recorded in the trace.
3. Error aggregation (combining multiple errors into one) MUST preserve all constituent error IDs.
4. A plane receiving an error from a dependency MUST either handle it, escalate it, or fail explicitly. No other option exists.
