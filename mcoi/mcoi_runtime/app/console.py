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
    ExecutionSummaryView,
    GoalSummaryView,
    GraphSummaryView,
    JobSummaryView,
    ReplaySummaryView,
    RunbookSummaryView,
    RunSummaryView,
    SimulationSummaryView,
    SkillSummaryView,
    TeamSummaryView,
    TemporalTaskView,
    WorkflowSummaryView,
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
    if view.integration_provider_id:
        lines.append(f"  integration_prov:   {view.integration_provider_id}")
    if view.communication_provider_id:
        lines.append(f"  communication_prov: {view.communication_provider_id}")
    if view.model_provider_id:
        lines.append(f"  model_prov:         {view.model_provider_id}")
    if view.autonomy_mode:
        lines.append(f"  autonomy_mode:      {view.autonomy_mode}")
    if view.autonomy_decision:
        lines.append(f"  autonomy_decision:  {view.autonomy_decision}")
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


def render_skill_summary(view: SkillSummaryView) -> str:
    """Render a skill execution result as text."""
    lines = [
        "=== Skill Summary ===",
        f"  request_id:       {view.request_id}",
        f"  goal_id:          {view.goal_id}",
        f"  skill_id:         {view.skill_id or '(none)'}",
        f"  status:           {view.status}",
        f"  completed:        {view.completed}",
        f"  selected_from:    {view.selected_from}",
        f"  steps:            {view.step_count}",
    ]
    if view.failed_step:
        lines.append(f"  failed_step:      {view.failed_step}")
    if view.structured_errors:
        lines.append(f"  errors ({len(view.structured_errors)}):")
        for err in view.structured_errors:
            lines.append(f"    [{err.family}] {err.error_code}: {err.message}")
    return "\n".join(lines)


def render_workflow_summary(view: WorkflowSummaryView) -> str:
    """Render a workflow execution result as text."""
    lines = [
        "=== Workflow Summary ===",
        f"  workflow_id:        {view.workflow_id}",
        f"  status:             {view.status}",
        f"  stage_count:        {view.stage_count}",
        f"  completed_stages:   {view.completed_stages}",
    ]
    if view.failed_stage_id:
        lines.append(f"  failed_stage_id:    {view.failed_stage_id}")
    return "\n".join(lines)


def render_goal_summary(view: GoalSummaryView) -> str:
    """Render a goal execution result as text."""
    lines = [
        "=== Goal Summary ===",
        f"  goal_id:            {view.goal_id}",
        f"  status:             {view.status}",
        f"  priority:           {view.priority}",
        f"  sub_goal_count:     {view.sub_goal_count}",
        f"  completed:          {view.completed}",
        f"  failed:             {view.failed}",
    ]
    return "\n".join(lines)


def render_job_summary(view: JobSummaryView) -> str:
    """Render a job execution summary as text."""
    lines = [
        "=== Job Summary ===",
        f"  job_id:             {view.job_id}",
        f"  name:               {view.name}",
        f"  status:             {view.status}",
        f"  priority:           {view.priority}",
        f"  sla_status:         {view.sla_status}",
        f"  assigned_to:        {view.assigned_to or '(unassigned)'}",
        f"  thread_id:          {view.thread_id or '(none)'}",
        f"  deadline:           {view.deadline or '(none)'}",
    ]
    return "\n".join(lines)


def render_team_summary(view: TeamSummaryView) -> str:
    """Render a team workload summary as text."""
    lines = [
        "=== Team Summary ===",
        f"  team_id:            {view.team_id}",
        f"  total_workers:      {view.total_workers}",
        f"  available_workers:  {view.available_workers}",
        f"  overloaded_workers: {view.overloaded_workers}",
        f"  queued_jobs:        {view.queued_jobs}",
        f"  assigned_jobs:      {view.assigned_jobs}",
    ]
    return "\n".join(lines)


def render_graph_summary(view: GraphSummaryView) -> str:
    """Render an operational graph summary as text."""
    lines = [
        "=== Graph Summary ===",
        f"  total_nodes:              {view.total_nodes}",
        f"  total_edges:              {view.total_edges}",
        f"  unfulfilled_obligations:  {view.unfulfilled_obligations}",
    ]
    if view.node_types:
        lines.append("  node_types:")
        for ntype, count in sorted(view.node_types.items()):
            lines.append(f"    {ntype}: {count}")
    return "\n".join(lines)


def render_simulation_summary(view: SimulationSummaryView) -> str:
    """Render a simulation result summary as text."""
    lines = [
        "=== Simulation Summary ===",
        f"  request_id:             {view.request_id}",
        f"  option_count:           {view.option_count}",
        f"  recommended_option:     {view.recommended_option_id}",
        f"  verdict_type:           {view.verdict_type}",
        f"  confidence:             {view.confidence:.2f}",
        f"  top_risk_level:         {view.top_risk_level}",
    ]
    return "\n".join(lines)
