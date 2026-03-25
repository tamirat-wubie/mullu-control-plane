"""Phase 125F — Pilot Operations Tracking / Metrics."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class PilotMetrics:
    """Tracks operational metrics for a live pilot."""
    tenant_id: str
    setup_time_minutes: float = 0.0
    connector_activation_minutes: float = 0.0
    import_success_rate: float = 0.0
    time_to_first_intake_minutes: float = 0.0
    time_to_remediation_closure_hours: float = 0.0
    approval_burden_per_case: float = 0.0
    evidence_completeness_rate: float = 0.0
    report_generation_minutes: float = 0.0
    dashboard_daily_views: int = 0
    copilot_queries_per_day: int = 0
    operator_satisfaction_score: float = 0.0  # 0-10

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "setup_time_minutes": self.setup_time_minutes,
            "connector_activation_minutes": self.connector_activation_minutes,
            "import_success_rate": self.import_success_rate,
            "time_to_first_intake_minutes": self.time_to_first_intake_minutes,
            "time_to_remediation_closure_hours": self.time_to_remediation_closure_hours,
            "approval_burden_per_case": self.approval_burden_per_case,
            "evidence_completeness_rate": self.evidence_completeness_rate,
            "report_generation_minutes": self.report_generation_minutes,
            "dashboard_daily_views": self.dashboard_daily_views,
            "copilot_queries_per_day": self.copilot_queries_per_day,
            "operator_satisfaction_score": self.operator_satisfaction_score,
        }

    @property
    def health_summary(self) -> str:
        issues = []
        if self.import_success_rate < 0.9:
            issues.append("low_import_success")
        if self.evidence_completeness_rate < 0.8:
            issues.append("incomplete_evidence")
        if self.operator_satisfaction_score < 6.0 and self.operator_satisfaction_score > 0:
            issues.append("low_satisfaction")
        return "healthy" if not issues else f"attention_needed: {', '.join(issues)}"
