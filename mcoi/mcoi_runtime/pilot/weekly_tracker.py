"""Phase 126E+F — Weekly Pilot Tracking and Feedback Collection."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

@dataclass
class WeeklySnapshot:
    week_number: int
    tenant_id: str
    captured_at: str = ""
    # Operational KPIs
    cases_created: int = 0
    cases_closed: int = 0
    remediations_completed: int = 0
    approvals_processed: int = 0
    evidence_bundles_generated: int = 0
    reports_generated: int = 0
    # Connector health
    connector_uptime_percent: float = 100.0
    connector_failures: int = 0
    # Usage
    dashboard_views: int = 0
    copilot_queries: int = 0
    # Business value
    time_saved_hours: float = 0.0
    missed_work_reduction_percent: float = 0.0
    # Satisfaction
    operator_satisfaction: float = 0.0  # 0-10
    executive_satisfaction: float = 0.0  # 0-10

    def __post_init__(self):
        if not self.captured_at:
            object.__setattr__(self, "captured_at", datetime.now(timezone.utc).isoformat())

@dataclass
class FeedbackEntry:
    respondent_role: str  # "operator", "admin", "executive"
    question: str
    response: str
    sentiment: str = "neutral"  # "positive", "neutral", "negative"
    week_number: int = 0

@dataclass
class PilotDecision:
    decision: str  # "promote", "extend", "stop"
    reason: str
    criteria_met: dict[str, bool] = field(default_factory=dict)

class WeeklyPilotTracker:
    """Tracks weekly pilot metrics and feedback."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self._snapshots: list[WeeklySnapshot] = []
        self._feedback: list[FeedbackEntry] = []

    def record_week(self, snapshot: WeeklySnapshot) -> None:
        self._snapshots.append(snapshot)

    def record_feedback(self, entry: FeedbackEntry) -> None:
        self._feedback.append(entry)

    def evaluate_promotion(self) -> PilotDecision:
        if not self._snapshots:
            return PilotDecision("stop", "No data collected", {})

        latest = self._snapshots[-1]
        criteria = {
            "connectors_stable": latest.connector_uptime_percent >= 99.0,
            "workflows_completing": latest.cases_closed > 0,
            "evidence_trusted": latest.evidence_bundles_generated > 0,
            "operators_adopting": latest.dashboard_views >= 10,
            "executive_sees_value": latest.executive_satisfaction >= 7.0,
            "support_acceptable": latest.connector_failures <= 2,
        }

        met = sum(1 for v in criteria.values() if v)
        if met >= 5:
            return PilotDecision("promote", f"Met {met}/6 criteria", criteria)
        elif met >= 3:
            return PilotDecision("extend", f"Met {met}/6 criteria — needs improvement", criteria)
        else:
            return PilotDecision("stop", f"Only met {met}/6 criteria", criteria)

    @property
    def snapshots(self) -> tuple[WeeklySnapshot, ...]:
        return tuple(self._snapshots)

    @property
    def feedback(self) -> tuple[FeedbackEntry, ...]:
        return tuple(self._feedback)

    def summary(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "weeks_tracked": len(self._snapshots),
            "feedback_entries": len(self._feedback),
            "latest_decision": self.evaluate_promotion().decision if self._snapshots else "no_data",
        }
