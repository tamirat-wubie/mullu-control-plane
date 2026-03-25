"""Phase 129C — Revenue Funnel and Commercial Instrumentation."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class FunnelStage:
    stage: str
    count: int = 0
    converted: int = 0

    @property
    def conversion_rate(self) -> float:
        return self.converted / self.count if self.count else 0.0

class RevenueFunnel:
    """Tracks the commercial funnel from demo to renewal."""

    def __init__(self):
        self._stages = {
            "demo": FunnelStage("demo"),
            "pilot": FunnelStage("pilot"),
            "paid": FunnelStage("paid"),
            "renewed": FunnelStage("renewed"),
            "expanded": FunnelStage("expanded"),
        }
        self._metrics: list[dict[str, Any]] = []

    def record_demo(self, customer_id: str) -> None:
        self._stages["demo"].count += 1
        self._metrics.append({"customer_id": customer_id, "stage": "demo", "action": "entered"})

    def convert_to_pilot(self, customer_id: str) -> None:
        self._stages["demo"].converted += 1
        self._stages["pilot"].count += 1
        self._metrics.append({"customer_id": customer_id, "stage": "pilot", "action": "converted"})

    def convert_to_paid(self, customer_id: str, monthly_revenue: float = 2500.0) -> None:
        self._stages["pilot"].converted += 1
        self._stages["paid"].count += 1
        self._metrics.append({"customer_id": customer_id, "stage": "paid", "action": "converted", "mrr": monthly_revenue})

    def record_renewal(self, customer_id: str) -> None:
        self._stages["paid"].converted += 1
        self._stages["renewed"].count += 1
        self._metrics.append({"customer_id": customer_id, "stage": "renewed", "action": "renewed"})

    def record_expansion(self, customer_id: str, additional_mrr: float = 0.0) -> None:
        self._stages["renewed"].converted += 1
        self._stages["expanded"].count += 1
        self._metrics.append({"customer_id": customer_id, "stage": "expanded", "action": "expanded", "additional_mrr": additional_mrr})

    @property
    def total_mrr(self) -> float:
        return sum(m.get("mrr", 0) for m in self._metrics if m.get("mrr"))

    @property
    def total_arr(self) -> float:
        return self.total_mrr * 12

    def funnel_summary(self) -> dict[str, Any]:
        return {
            "stages": {name: {"count": s.count, "converted": s.converted, "rate": round(s.conversion_rate, 3)} for name, s in self._stages.items()},
            "total_mrr": self.total_mrr,
            "total_arr": self.total_arr,
            "total_events": len(self._metrics),
        }
