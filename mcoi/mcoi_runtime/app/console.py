"""Purpose: read-only operator console — text rendering of runtime artifact views.
Governance scope: operator-facing display only.
Dependencies: view models module.
Invariants:
  - Read-only. No mutation of runtime state.
  - No background work. No daemon. No live refresh.
  - Deterministic output for same input.
"""

from __future__ import annotations

from .view_models import (
    CoordinationSummaryView,
    ErrorView,
    ExecutionSummaryView,
    ReplaySummaryView,
    RunbookSummaryView,
    RunSummaryView,
    TemporalTaskView,
)


def render_run_summary(view: RunSummaryView) -> str:
    """Render a single operator run as text."""
    lines = [
        "=== Run Summary ===",
        f"  request_id:         {view.request_id}",
        f"  goal_id:            {view.goal_id}",
        f"  policy_decision_id: {view.policy_decision_id}",
        f"  execution_id:       {view.execution_id or '(none)'}",
        f"  verification_id:    {view.verification_id or '(none)'}",
        f"  dispatched:         {view.dispatched}",
        f"  validation_passed:  {view.validation_passed}",
        f"  verification_closed:{view.verification_closed}",
        f"  completed:          {view.completed}",
    ]
    if view.validation_error:
        lines.append(f"  validation_error:   {view.validation_error}")
    if view.verification_error:
        lines.append(f"  verification_error: {view.verification_error}")
    if view.structured_errors:
        lines.append(f"  errors ({len(view.structured_errors)}):")
        for err in view.structured_errors:
            lines.append(f"    [{err.family}] {err.error_code}: {err.message}")
            lines.append(f"      source: {err.source_plane}  recoverability: {err.recoverability}")
            if err.related_ids:
                lines.append(f"      related: {', '.join(err.related_ids)}")
    if view.world_state_hash:
        lines.append(f"  world_state_hash:   {view.world_state_hash[:16]}...")
        lines.append(f"  entities:           {view.world_state_entity_count}")
        lines.append(f"  contradictions:     {view.world_state_contradiction_count}")
    if view.degraded_capabilities:
        lines.append(f"  degraded:           {', '.join(view.degraded_capabilities)}")
    if view.escalation_recommendations:
        lines.append(f"  escalations:        {len(view.escalation_recommendations)}")
    if view.execution_route:
        lines.append(f"  execution_route:    {view.execution_route}")
    if view.provider_count > 0:
        lines.append(f"  providers:          {view.provider_count}")
        if view.unhealthy_providers:
            lines.append(f"  unhealthy:          {', '.join(view.unhealthy_providers)}")
    return "\n".join(lines)


def render_execution_summary(view: ExecutionSummaryView) -> str:
    """Render execution outcome as text."""
    lines = [
        "=== Execution Summary ===",
        f"  dispatched:          {view.dispatched}",
        f"  goal_id:             {view.goal_id}",
    ]
    if view.dispatched:
        lines.extend([
            f"  execution_id:        {view.execution_id}",
            f"  status:              {view.status}",
            f"  effect_count:        {view.effect_count}",
            f"  verification_closed: {view.verification_closed}",
        ])
    else:
        lines.append("  (not dispatched)")
    return "\n".join(lines)


def render_replay_summary(view: ReplaySummaryView) -> str:
    """Render replay validation result as text."""
    lines = [
        "=== Replay Summary ===",
        f"  replay_id:        {view.replay_id}",
        f"  trace_id:         {view.trace_id}",
        f"  verdict:          {view.verdict}",
        f"  ready:            {view.ready}",
        f"  trace_found:      {view.trace_found}",
        f"  trace_hash_match: {view.trace_hash_matches}",
    ]
    if view.reasons:
        lines.append("  reasons:")
        for reason in view.reasons:
            lines.append(f"    - {reason}")
    return "\n".join(lines)


def render_temporal_task(view: TemporalTaskView) -> str:
    """Render a temporal task as text."""
    lines = [
        "=== Temporal Task ===",
        f"  task_id:          {view.task_id}",
        f"  goal_id:          {view.goal_id}",
        f"  state:            {view.state}",
        f"  trigger_type:     {view.trigger_type}",
        f"  deadline:         {view.deadline or '(none)'}",
        f"  has_checkpoint:   {view.has_checkpoint}",
        f"  transitions:      {view.transition_count}",
    ]
    return "\n".join(lines)


def render_coordination_summary(view: CoordinationSummaryView) -> str:
    """Render coordination state as text."""
    lines = [
        "=== Coordination Summary ===",
        f"  delegations:            {view.delegation_count}",
        f"  handoffs:               {view.handoff_count}",
        f"  merges:                 {view.merge_count}",
        f"  unresolved_conflicts:   {view.unresolved_conflict_count}",
    ]
    return "\n".join(lines)


def render_runbook_summary(view: RunbookSummaryView) -> str:
    """Render runbook admission result as text."""
    lines = [
        "=== Runbook Summary ===",
        f"  runbook_id:             {view.runbook_id}",
        f"  status:                 {view.status}",
        f"  reasons:                {', '.join(view.reasons)}",
    ]
    if view.provenance_execution_id:
        lines.append(f"  provenance_execution:   {view.provenance_execution_id}")
    if view.provenance_replay_id:
        lines.append(f"  provenance_replay:      {view.provenance_replay_id}")
    return "\n".join(lines)
