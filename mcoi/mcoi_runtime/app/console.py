"""Purpose: read-only operator console — text rendering of runtime artifact views.
Governance scope: operator-facing display only.
Dependencies: view models module.
Invariants:
  - Read-only. No mutation of runtime state.
  - No background work. No daemon. No live refresh.
  - Deterministic output for same input.
"""

from __future__ import annotations

from mcoi_runtime.contracts.dashboard import NoteMemorySummary

from .view_models import (
    AutonomousRequestEpisodeSummaryView,
    CoordinationSummaryView,
    ExecutionSummaryView,
    GoalSummaryView,
    GraphSummaryView,
    JobSummaryView,
    ReplaySummaryView,
    RunbookSummaryView,
    RunSummaryView,
    SimulationSummaryView,
    SkillPromotionReceiptReadView,
    SkillSummaryView,
    TeamSummaryView,
    TemporalTaskView,
    WHQRBindingClarificationStatusView,
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
    if view.provider_attributions:
        lines.append(f"  provider_attrs:     {len(view.provider_attributions)}")
        for attribution in view.provider_attributions:
            lines.append(
                "    "
                f"{attribution.provider_class.value}: {attribution.provider_id} "
                f"({attribution.source.value})"
            )
    if view.provider_attribution_count:
        lines.append(f"  provider_attr_total:{view.provider_attribution_count}")
        lines.append(f"  provider_attr_receipt:{view.receipt_attributed_provider_operation_count}")
        lines.append(f"  provider_attr_routing:{view.routing_attributed_provider_operation_count}")
        lines.append(f"  provider_attr_plane:{view.plane_attributed_provider_operation_count}")
    if view.autonomy_mode:
        lines.append(f"  autonomy_mode:      {view.autonomy_mode}")
    if view.autonomy_decision:
        lines.append(f"  autonomy_decision:  {view.autonomy_decision}")
    if view.mil_program_id:
        lines.append(f"  mil_program_id:     {view.mil_program_id}")
        lines.append(f"  mil_instructions:   {view.mil_instruction_count}")
        lines.append(f"  mil_verified:       {view.mil_verification_passed}")
        if view.mil_audit_record_id:
            lines.append(f"  mil_audit_record:   {view.mil_audit_record_id}")
        if view.mil_trace_ids:
            lines.append(f"  mil_trace_count:    {len(view.mil_trace_ids)}")
        if view.mil_verification_issues:
            lines.append(f"  mil_issues:         {', '.join(view.mil_verification_issues)}")
        if view.mil_instruction_trace:
            lines.append("  mil_trace:")
            for instruction in view.mil_instruction_trace:
                lines.append(f"    {instruction}")
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
    if view.trace_lookup_reason:
        lines.append(f"  trace_lookup:     {view.trace_lookup_reason}")
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
    if view.lifecycle_transition_warning:
        lines.append(f"  lifecycle_warning: {view.lifecycle_transition_warning}")
    if view.structured_errors:
        lines.append(f"  errors ({len(view.structured_errors)}):")
        for err in view.structured_errors:
            lines.append(f"    [{err.family}] {err.error_code}: {err.message}")
    return "\n".join(lines)


def render_skill_promotion_receipts(view: SkillPromotionReceiptReadView) -> str:
    """Render skill promotion receipt evidence as text."""
    lines = [
        "=== Skill Promotion Receipts ===",
        f"  request_id:         {view.request_id}",
        f"  store_configured:   {view.store_configured}",
        f"  receipt_count:      {view.receipt_count}",
        f"  skill_id_filter:    {view.skill_id_filter or '(none)'}",
        f"  lifecycle_filter:   {view.target_lifecycle_filter or '(none)'}",
    ]
    if view.structured_errors:
        lines.append(f"  errors ({len(view.structured_errors)}):")
        for err in view.structured_errors:
            lines.append(f"    [{err.family}] {err.error_code}: {err.message}")
    if view.receipts:
        lines.append("  receipts:")
        for receipt in view.receipts:
            lines.append(
                "    "
                f"{receipt.evidence_id} skill={receipt.skill_id} "
                f"target={receipt.target_lifecycle} "
                f"records={receipt.execution_record_count} "
                f"refs={receipt.evidence_ref_count} "
                f"verifications={receipt.verification_count}"
            )
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


def render_autonomous_request_episode_summary(
    view: AutonomousRequestEpisodeSummaryView,
) -> str:
    """Render an autonomous request episode continuation summary as text."""
    lines = [
        "=== Autonomous Request Episode Summary ===",
        f"  episode_id:         {view.episode_id}",
        f"  goal_id:            {view.goal_id}",
        f"  automation_state:   {view.automation_state}",
        f"  solver_outcome:     {view.solver_outcome}",
        f"  action_count:       {view.action_count}",
        f"  dispatched_count:   {view.dispatched_count}",
        f"  prompt_count:       {view.prompt_count}",
        f"  workflow_ref:       {view.workflow_descriptor_ref or '(none)'}",
        f"  workflow_stages:    {view.workflow_stage_count}",
        f"  approval_stages:    {view.workflow_approval_stage_count}",
        f"  external_stages:    {view.workflow_external_stage_count}",
        f"  plan_receipt_ref:   {view.plan_receipt_ref or '(none)'}",
        f"  rollback_ref:       {view.rollback_ref}",
    ]
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


def render_whqr_binding_clarification_status(view: WHQRBindingClarificationStatusView) -> str:
    """Render WHQR binding clarification replay status as text."""
    lines = [
        "=== WHQR Binding Clarification Status ===",
        f"  thread_id:          {view.thread_id}",
        f"  request_count:      {view.request_count}",
        f"  response_count:     {view.response_count}",
        f"  accepted_count:     {view.accepted_count}",
        f"  rejected_count:     {view.rejected_count}",
        f"  has_replay_pairs:   {view.has_replay_pairs}",
        f"  binding_map_passed: {view.binding_map_passed}",
        f"  next_step:          {view.next_step}",
        f"  pending_request_ids:{_render_tuple(view.pending_request_ids)}",
        f"  responded_request_ids:{_render_tuple(view.responded_request_ids)}",
        f"  rejected_reasons:   {_render_tuple(view.rejected_reasons)}",
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


def _render_tuple(values: tuple[str, ...]) -> str:
    if not values:
        return " (none)"
    return " " + ", ".join(values)


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


def render_note_memory_summary(view: NoteMemorySummary) -> str:
    """Render note-memory lifecycle posture as text."""
    lines = [
        "=== Note Memory Summary ===",
        f"  status:                 {view.status}",
        f"  extension_state:        {view.extension_state}",
        f"  events:                 {view.event_count}",
        f"  active_notes:           {view.active_note_count}",
        f"  rejected_deltas:        {view.rejected_delta_count}",
        f"  expiring_notes:         {view.expiring_note_count}",
        f"  pending_promotions:     {view.pending_promotion_count}",
        f"  memory_anchors:         {view.memory_anchor_count}",
        f"  episode_capsules:       {view.episode_capsule_count}",
        f"  contradictions:         {view.contradiction_count}",
        f"  retrieval_filter_active: {view.retrieval_filter_active}",
        f"  retrieval_filter_mode:  {view.retrieval_filter_mode}",
        f"  retrieval_influence:    {view.retrieval_influence_count}",
        f"  retrieval_influence_total: {view.retrieval_influence_total_count}",
        f"  retrieval_influence_filtered_out: {view.retrieval_influence_filtered_out_count}",
        f"  retrieval_receipts:     {view.retrieval_receipt_count}",
        f"  retrieval_receipts_total: {view.retrieval_receipt_total_count}",
        f"  retrieval_receipts_filtered_out: {view.retrieval_receipt_filtered_out_count}",
        f"  index_proof_state:      {view.index_proof_state}",
        f"  assessed_at:            {view.assessed_at}",
    ]
    return "\n".join(lines)
