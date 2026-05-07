"""Phase 124D — Pilot Data Import / Backfill."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
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


def _bounded_import_error(summary: str, exc: Exception) -> str:
    return f"{summary} ({type(exc).__name__})"

class PilotDataImporter:
    """Import historical data for pilot tenant."""

    def __init__(self, event_spine: EventSpineEngine):
        self._es = event_spine
        self._case_engine = CaseRuntimeEngine(event_spine)
        self._remediation_engine = RemediationRuntimeEngine(event_spine)
        self._records_engine = RecordsRuntimeEngine(event_spine)
        self._workflow_engine = HumanWorkflowEngine(event_spine)

    def _append_rejection(
        self,
        errors: list[str],
        record_id: str,
        summary: str,
        exc: Exception,
    ) -> None:
        errors.append(f"{record_id}: {_bounded_import_error(summary, exc)}")

    def _classify_duplicate_conflict(
        self,
        *,
        candidate_id: object,
        current_ids: set[str],
        result: ImportResult,
        known_ids: set[str],
    ) -> bool:
        if isinstance(candidate_id, str) and candidate_id in current_ids:
            known_ids.add(candidate_id)
            result.conflicts += 1
            return True
        return False

    def import_cases(self, tenant_id: str, cases: list[dict[str, Any]]) -> ImportResult:
        result = ImportResult(source_system="cases")
        result.total_records = len(cases)
        existing_ids = {case.case_id for case in self._case_engine.cases_for_tenant(tenant_id)}
        for case in cases:
            case_id = case.get("case_id")
            if isinstance(case_id, str) and case_id in existing_ids:
                result.conflicts += 1
                continue
            try:
                self._case_engine.open_case(
                    case["case_id"], tenant_id, case.get("title", "Imported case"),
                )
                existing_ids.add(case["case_id"])
                result.accepted += 1
            except Exception as exc:
                current_ids = {existing.case_id for existing in self._case_engine.cases_for_tenant(tenant_id)}
                if self._classify_duplicate_conflict(
                    candidate_id=case_id,
                    current_ids=current_ids,
                    result=result,
                    known_ids=existing_ids,
                ):
                    pass
                else:
                    result.rejected += 1
                    self._append_rejection(
                        result.errors,
                        str(case_id or "?"),
                        "case import failed",
                        exc,
                    )
        return result

    def import_remediations(self, tenant_id: str, items: list[dict[str, Any]]) -> ImportResult:
        result = ImportResult(source_system="remediations")
        result.total_records = len(items)
        existing_ids = {
            remediation.remediation_id
            for remediation in self._remediation_engine.remediations_for_tenant(tenant_id)
        }
        for item in items:
            remediation_id = item.get("remediation_id")
            if isinstance(remediation_id, str) and remediation_id in existing_ids:
                result.conflicts += 1
                continue
            try:
                self._remediation_engine.create_remediation(
                    item["remediation_id"], tenant_id,
                    item.get("title", "Imported remediation"),
                    case_id=item.get("case_ref", "unknown"),
                )
                existing_ids.add(item["remediation_id"])
                result.accepted += 1
            except Exception as exc:
                current_ids = {
                    remediation.remediation_id
                    for remediation in self._remediation_engine.remediations_for_tenant(tenant_id)
                }
                if self._classify_duplicate_conflict(
                    candidate_id=remediation_id,
                    current_ids=current_ids,
                    result=result,
                    known_ids=existing_ids,
                ):
                    pass
                else:
                    result.rejected += 1
                    self._append_rejection(
                        result.errors,
                        str(remediation_id or "?"),
                        "remediation import failed",
                        exc,
                    )
        return result

    def import_records(self, tenant_id: str, records: list[dict[str, Any]]) -> ImportResult:
        result = ImportResult(source_system="records")
        result.total_records = len(records)
        existing_ids = {
            record.record_id
            for record in self._records_engine.records_for_tenant(tenant_id)
        }
        for rec in records:
            record_id = rec.get("record_id")
            if isinstance(record_id, str) and record_id in existing_ids:
                result.conflicts += 1
                continue
            try:
                self._records_engine.register_record(
                    rec["record_id"], tenant_id,
                    rec.get("title", "Imported record"),
                )
                existing_ids.add(rec["record_id"])
                result.accepted += 1
            except Exception as exc:
                current_ids = {
                    record.record_id
                    for record in self._records_engine.records_for_tenant(tenant_id)
                }
                if self._classify_duplicate_conflict(
                    candidate_id=record_id,
                    current_ids=current_ids,
                    result=result,
                    known_ids=existing_ids,
                ):
                    pass
                else:
                    result.rejected += 1
                    self._append_rejection(
                        result.errors,
                        str(record_id or "?"),
                        "record import failed",
                        exc,
                    )
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
