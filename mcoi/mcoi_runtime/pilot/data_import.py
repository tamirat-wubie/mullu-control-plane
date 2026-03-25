"""Phase 124D — Pilot Data Import / Backfill."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.case_runtime import CaseRuntimeEngine
from mcoi_runtime.core.remediation_runtime import RemediationRuntimeEngine
from mcoi_runtime.core.records_runtime import RecordsRuntimeEngine
from mcoi_runtime.core.human_workflow import HumanWorkflowEngine

@dataclass
class ImportResult:
    source_system: str
    total_records: int = 0
    accepted: int = 0
    rejected: int = 0
    conflicts: int = 0
    errors: list[str] = field(default_factory=list)

class PilotDataImporter:
    """Import historical data for pilot tenant."""

    def __init__(self, event_spine: EventSpineEngine):
        self._es = event_spine
        self._case_engine = CaseRuntimeEngine(event_spine)
        self._remediation_engine = RemediationRuntimeEngine(event_spine)
        self._records_engine = RecordsRuntimeEngine(event_spine)
        self._workflow_engine = HumanWorkflowEngine(event_spine)

    def import_cases(self, tenant_id: str, cases: list[dict[str, Any]]) -> ImportResult:
        result = ImportResult(source_system="cases")
        result.total_records = len(cases)
        for case in cases:
            try:
                self._case_engine.open_case(
                    case["case_id"], tenant_id, case.get("title", "Imported case"),
                )
                result.accepted += 1
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    result.conflicts += 1
                else:
                    result.rejected += 1
                    result.errors.append(f"{case.get('case_id', '?')}: {e}")
        return result

    def import_remediations(self, tenant_id: str, items: list[dict[str, Any]]) -> ImportResult:
        result = ImportResult(source_system="remediations")
        result.total_records = len(items)
        for item in items:
            try:
                self._remediation_engine.create_remediation(
                    item["remediation_id"], tenant_id,
                    item.get("title", "Imported remediation"),
                    case_id=item.get("case_ref", "unknown"),
                )
                result.accepted += 1
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    result.conflicts += 1
                else:
                    result.rejected += 1
                    result.errors.append(f"{item.get('remediation_id', '?')}: {e}")
        return result

    def import_records(self, tenant_id: str, records: list[dict[str, Any]]) -> ImportResult:
        result = ImportResult(source_system="records")
        result.total_records = len(records)
        for rec in records:
            try:
                self._records_engine.register_record(
                    rec["record_id"], tenant_id,
                    rec.get("title", "Imported record"),
                )
                result.accepted += 1
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    result.conflicts += 1
                else:
                    result.rejected += 1
                    result.errors.append(f"{rec.get('record_id', '?')}: {e}")
        return result

    def import_all(self, tenant_id: str, dataset: dict[str, list[dict[str, Any]]]) -> dict[str, ImportResult]:
        results = {}
        if "cases" in dataset:
            results["cases"] = self.import_cases(tenant_id, dataset["cases"])
        if "remediations" in dataset:
            results["remediations"] = self.import_remediations(tenant_id, dataset["remediations"])
        if "records" in dataset:
            results["records"] = self.import_records(tenant_id, dataset["records"])
        return results
