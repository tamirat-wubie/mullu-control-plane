"""Purpose: knowledge search / retrieval / evidence query runtime engine.
Governance scope: registering queries, searching across runtimes, applying
    filters, ranking results, assembling evidence bundles, detecting violations,
    producing immutable snapshots.
Dependencies: knowledge_query contracts, event_spine, core invariants.
Invariants:
  - Cross-tenant queries are blocked fail-closed.
  - Completed queries cannot be re-executed.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.knowledge_query import (
    EvidenceBundle,
    EvidenceKind,
    EvidenceReference,
    KnowledgeQuery,
    KnowledgeQueryClosureReport,
    MatchDisposition,
    MatchRecord,
    QueryAssessment,
    QueryExecutionRecord,
    QueryFilter,
    QueryResultStatus,
    QueryScope,
    QuerySnapshot,
    QueryStatus,
    QueryViolation,
    RankedResult,
    RankingStrategy,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-kqry", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_QUERY_TERMINAL = frozenset({QueryStatus.COMPLETED, QueryStatus.FAILED, QueryStatus.CANCELLED})


class KnowledgeQueryEngine:
    """Knowledge search, retrieval, and evidence query engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._queries: dict[str, KnowledgeQuery] = {}
        self._filters: dict[str, QueryFilter] = {}
        self._references: dict[str, EvidenceReference] = {}
        self._matches: dict[str, MatchRecord] = {}
        self._results: dict[str, RankedResult] = {}
        self._executions: dict[str, QueryExecutionRecord] = {}
        self._bundles: dict[str, EvidenceBundle] = {}
        self._violations: dict[str, QueryViolation] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def query_count(self) -> int:
        return len(self._queries)

    @property
    def filter_count(self) -> int:
        return len(self._filters)

    @property
    def reference_count(self) -> int:
        return len(self._references)

    @property
    def match_count(self) -> int:
        return len(self._matches)

    @property
    def result_count(self) -> int:
        return len(self._results)

    @property
    def execution_count(self) -> int:
        return len(self._executions)

    @property
    def bundle_count(self) -> int:
        return len(self._bundles)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def register_query(
        self,
        query_id: str,
        tenant_id: str,
        *,
        scope: QueryScope = QueryScope.TENANT,
        scope_ref_id: str = "",
        search_text: str = "",
        max_results: int = 100,
    ) -> KnowledgeQuery:
        """Register a new knowledge query."""
        if query_id in self._queries:
            raise RuntimeCoreInvariantError("Duplicate query_id")
        now = _now_iso()
        query = KnowledgeQuery(
            query_id=query_id, tenant_id=tenant_id,
            scope=scope, scope_ref_id=scope_ref_id,
            search_text=search_text, status=QueryStatus.PENDING,
            max_results=max_results, created_at=now,
        )
        self._queries[query_id] = query
        _emit(self._events, "query_registered", {
            "query_id": query_id, "scope": scope.value,
        }, query_id)
        return query

    def get_query(self, query_id: str) -> KnowledgeQuery:
        """Get a query by ID."""
        q = self._queries.get(query_id)
        if q is None:
            raise RuntimeCoreInvariantError("Unknown query_id")
        return q

    def cancel_query(self, query_id: str) -> KnowledgeQuery:
        """Cancel a query."""
        old = self.get_query(query_id)
        if old.status in _QUERY_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot cancel query in current status")
        updated = KnowledgeQuery(
            query_id=old.query_id, tenant_id=old.tenant_id,
            scope=old.scope, scope_ref_id=old.scope_ref_id,
            search_text=old.search_text, status=QueryStatus.CANCELLED,
            max_results=old.max_results, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._queries[query_id] = updated
        _emit(self._events, "query_cancelled", {"query_id": query_id}, query_id)
        return updated

    def queries_for_tenant(self, tenant_id: str) -> tuple[KnowledgeQuery, ...]:
        """Return all queries for a tenant."""
        return tuple(q for q in self._queries.values() if q.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    def add_filter(
        self,
        filter_id: str,
        query_id: str,
        *,
        field_name: str = "status",
        field_value: str = "",
        evidence_kind: EvidenceKind = EvidenceKind.RECORD,
    ) -> QueryFilter:
        """Add a filter to a query."""
        if filter_id in self._filters:
            raise RuntimeCoreInvariantError("Duplicate filter_id")
        self.get_query(query_id)  # validate query exists
        now = _now_iso()
        f = QueryFilter(
            filter_id=filter_id, query_id=query_id,
            field_name=field_name, field_value=field_value,
            evidence_kind=evidence_kind, created_at=now,
        )
        self._filters[filter_id] = f
        _emit(self._events, "filter_added", {
            "filter_id": filter_id, "query_id": query_id,
        }, query_id)
        return f

    def filters_for_query(self, query_id: str) -> tuple[QueryFilter, ...]:
        """Return all filters for a query."""
        return tuple(f for f in self._filters.values() if f.query_id == query_id)

    # ------------------------------------------------------------------
    # Evidence references
    # ------------------------------------------------------------------

    def register_evidence(
        self,
        reference_id: str,
        source_id: str,
        tenant_id: str,
        *,
        evidence_kind: EvidenceKind = EvidenceKind.RECORD,
        scope_ref_id: str = "",
        title: str = "Evidence",
        confidence: float = 0.5,
    ) -> EvidenceReference:
        """Register a piece of evidence."""
        if reference_id in self._references:
            raise RuntimeCoreInvariantError("Duplicate reference_id")
        now = _now_iso()
        ref = EvidenceReference(
            reference_id=reference_id, source_id=source_id,
            evidence_kind=evidence_kind, tenant_id=tenant_id,
            scope_ref_id=scope_ref_id, title=title,
            confidence=confidence, created_at=now,
        )
        self._references[reference_id] = ref
        _emit(self._events, "evidence_registered", {
            "reference_id": reference_id, "kind": evidence_kind.value,
        }, reference_id)
        return ref

    def get_evidence(self, reference_id: str) -> EvidenceReference:
        """Get an evidence reference by ID."""
        r = self._references.get(reference_id)
        if r is None:
            raise RuntimeCoreInvariantError("Unknown reference_id")
        return r

    def evidence_for_tenant(self, tenant_id: str) -> tuple[EvidenceReference, ...]:
        """Return all evidence for a tenant."""
        return tuple(r for r in self._references.values() if r.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Search methods
    # ------------------------------------------------------------------

    def search_memory(
        self,
        query_id: str,
        tenant_id: str,
        *,
        search_text: str = "",
    ) -> tuple[MatchRecord, ...]:
        """Search memory mesh for evidence matching query."""
        query = self.get_query(query_id)
        # Fail-closed: cross-tenant search blocked
        if query.tenant_id != tenant_id:
            self._record_cross_tenant_violation(query_id, query.tenant_id, tenant_id)
            return ()
        return self._search_by_kind(query_id, EvidenceKind.MEMORY, search_text or query.search_text)

    def search_records(
        self,
        query_id: str,
        tenant_id: str,
        *,
        search_text: str = "",
    ) -> tuple[MatchRecord, ...]:
        """Search records for evidence matching query."""
        query = self.get_query(query_id)
        if query.tenant_id != tenant_id:
            self._record_cross_tenant_violation(query_id, query.tenant_id, tenant_id)
            return ()
        return self._search_by_kind(query_id, EvidenceKind.RECORD, search_text or query.search_text)

    def search_cases(
        self,
        query_id: str,
        tenant_id: str,
        *,
        search_text: str = "",
    ) -> tuple[MatchRecord, ...]:
        """Search cases for evidence matching query."""
        query = self.get_query(query_id)
        if query.tenant_id != tenant_id:
            self._record_cross_tenant_violation(query_id, query.tenant_id, tenant_id)
            return ()
        return self._search_by_kind(query_id, EvidenceKind.CASE, search_text or query.search_text)

    def search_assurance(
        self,
        query_id: str,
        tenant_id: str,
        *,
        search_text: str = "",
    ) -> tuple[MatchRecord, ...]:
        """Search assurance evidence matching query."""
        query = self.get_query(query_id)
        if query.tenant_id != tenant_id:
            self._record_cross_tenant_violation(query_id, query.tenant_id, tenant_id)
            return ()
        return self._search_by_kind(query_id, EvidenceKind.ASSURANCE, search_text or query.search_text)

    def search_reporting(
        self,
        query_id: str,
        tenant_id: str,
        *,
        search_text: str = "",
    ) -> tuple[MatchRecord, ...]:
        """Search reporting evidence matching query."""
        query = self.get_query(query_id)
        if query.tenant_id != tenant_id:
            self._record_cross_tenant_violation(query_id, query.tenant_id, tenant_id)
            return ()
        return self._search_by_kind(query_id, EvidenceKind.REPORTING, search_text or query.search_text)

    def search_graph(
        self,
        query_id: str,
        tenant_id: str,
        *,
        search_text: str = "",
    ) -> tuple[MatchRecord, ...]:
        """Search graph for evidence matching query."""
        query = self.get_query(query_id)
        if query.tenant_id != tenant_id:
            self._record_cross_tenant_violation(query_id, query.tenant_id, tenant_id)
            return ()
        # Graph searches match artifacts
        return self._search_by_kind(query_id, EvidenceKind.ARTIFACT, search_text or query.search_text)

    def _search_by_kind(
        self,
        query_id: str,
        kind: EvidenceKind,
        search_text: str,
    ) -> tuple[MatchRecord, ...]:
        """Internal: find matching evidence of a given kind."""
        query = self.get_query(query_id)
        matches: list[MatchRecord] = []
        now = _now_iso()
        for ref in self._references.values():
            if ref.tenant_id != query.tenant_id:
                continue
            if ref.evidence_kind != kind:
                continue
            # Text match: exact if search_text in title, partial if overlap
            if search_text and search_text.lower() in ref.title.lower():
                disposition = MatchDisposition.EXACT
                relevance = ref.confidence
            elif search_text:
                # Check for partial word overlap
                search_words = set(search_text.lower().split())
                title_words = set(ref.title.lower().split())
                overlap = search_words & title_words
                if overlap:
                    disposition = MatchDisposition.PARTIAL
                    relevance = ref.confidence * (len(overlap) / max(len(search_words), 1))
                else:
                    continue
            else:
                # No search text — include all as related
                disposition = MatchDisposition.RELATED
                relevance = ref.confidence * 0.5

            mid = stable_identifier("match", {
                "query": query_id, "ref": ref.reference_id, "kind": kind.value,
            })
            if mid not in self._matches:
                match = MatchRecord(
                    match_id=mid, query_id=query_id,
                    reference_id=ref.reference_id,
                    disposition=disposition,
                    relevance_score=min(relevance, 1.0),
                    matched_at=now,
                )
                self._matches[mid] = match
                matches.append(match)

        if matches:
            _emit(self._events, f"search_{kind.value}_completed", {
                "query_id": query_id, "match_count": len(matches),
            }, query_id)
        return tuple(matches)

    def _record_cross_tenant_violation(
        self, query_id: str, owner_tenant: str, search_tenant: str,
    ) -> None:
        """Record a cross-tenant search violation."""
        now = _now_iso()
        vid = stable_identifier("viol-kqry", {
            "query": query_id, "op": "cross_tenant",
            "owner": owner_tenant, "search": search_tenant,
        })
        if vid not in self._violations:
            v = QueryViolation(
                violation_id=vid, tenant_id=owner_tenant,
                query_id=query_id, operation="cross_tenant",
                reason="Cross-tenant search attempt",
                detected_at=now,
            )
            self._violations[vid] = v
            _emit(self._events, "cross_tenant_violation", {
                "query_id": query_id, "owner": owner_tenant, "search": search_tenant,
            }, query_id)

    # ------------------------------------------------------------------
    # Execute query (full pipeline)
    # ------------------------------------------------------------------

    def execute_query(
        self,
        execution_id: str,
        query_id: str,
        *,
        ranking_strategy: RankingStrategy = RankingStrategy.RELEVANCE,
    ) -> QueryExecutionRecord:
        """Execute a full query pipeline: search, match, rank, record."""
        if execution_id in self._executions:
            raise RuntimeCoreInvariantError("Duplicate execution_id")
        query = self.get_query(query_id)
        if query.status in _QUERY_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot execute query in current status")

        # Mark as executing
        executing = KnowledgeQuery(
            query_id=query.query_id, tenant_id=query.tenant_id,
            scope=query.scope, scope_ref_id=query.scope_ref_id,
            search_text=query.search_text, status=QueryStatus.EXECUTING,
            max_results=query.max_results, created_at=query.created_at,
            metadata=query.metadata,
        )
        self._queries[query_id] = executing

        # Search all evidence kinds for this tenant
        all_matches: list[MatchRecord] = []
        for kind in EvidenceKind:
            matches = self._search_by_kind(query_id, kind, query.search_text)
            all_matches.extend(matches)

        # Rank results
        if ranking_strategy == RankingStrategy.RECENCY:
            sorted_matches = sorted(all_matches, key=lambda m: m.matched_at, reverse=True)
        elif ranking_strategy == RankingStrategy.CONFIDENCE:
            sorted_matches = sorted(all_matches, key=lambda m: m.relevance_score, reverse=True)
        else:
            # RELEVANCE or SEVERITY — sort by relevance_score desc
            sorted_matches = sorted(all_matches, key=lambda m: m.relevance_score, reverse=True)

        # Trim to max_results
        max_r = query.max_results if query.max_results > 0 else len(sorted_matches)
        trimmed = sorted_matches[:max_r]
        now = _now_iso()

        # Create ranked results
        for rank, match in enumerate(trimmed):
            rid = stable_identifier("rank", {
                "query": query_id, "match": match.match_id, "rank": str(rank),
            })
            if rid not in self._results:
                result = RankedResult(
                    result_id=rid, query_id=query_id,
                    reference_id=match.reference_id,
                    rank=rank, score=match.relevance_score,
                    ranking_strategy=ranking_strategy,
                    ranked_at=now,
                )
                self._results[rid] = result

        # Determine result status
        if not all_matches:
            result_status = QueryResultStatus.EMPTY
        elif len(trimmed) < len(sorted_matches):
            result_status = QueryResultStatus.TRUNCATED
        else:
            result_status = QueryResultStatus.COMPLETE

        # Mark query as completed
        completed = KnowledgeQuery(
            query_id=query.query_id, tenant_id=query.tenant_id,
            scope=query.scope, scope_ref_id=query.scope_ref_id,
            search_text=query.search_text, status=QueryStatus.COMPLETED,
            max_results=query.max_results, created_at=query.created_at,
            metadata=query.metadata,
        )
        self._queries[query_id] = completed

        execution = QueryExecutionRecord(
            execution_id=execution_id, query_id=query_id,
            status=result_status,
            total_matches=len(all_matches),
            total_results=len(trimmed),
            execution_ms=0.0, executed_at=now,
        )
        self._executions[execution_id] = execution
        _emit(self._events, "query_executed", {
            "execution_id": execution_id, "query_id": query_id,
            "matches": len(all_matches), "results": len(trimmed),
        }, execution_id)
        return execution

    def get_execution(self, execution_id: str) -> QueryExecutionRecord:
        """Get an execution record by ID."""
        e = self._executions.get(execution_id)
        if e is None:
            raise RuntimeCoreInvariantError("Unknown execution_id")
        return e

    def results_for_query(self, query_id: str) -> tuple[RankedResult, ...]:
        """Return ranked results for a query, sorted by rank."""
        results = [r for r in self._results.values() if r.query_id == query_id]
        return tuple(sorted(results, key=lambda r: r.rank))

    # ------------------------------------------------------------------
    # Evidence bundles
    # ------------------------------------------------------------------

    def build_evidence_bundle(
        self,
        bundle_id: str,
        query_id: str,
        tenant_id: str,
        *,
        title: str = "Evidence bundle",
    ) -> EvidenceBundle:
        """Assemble an evidence bundle from query results."""
        if bundle_id in self._bundles:
            raise RuntimeCoreInvariantError("Duplicate bundle_id")
        query = self.get_query(query_id)
        if query.tenant_id != tenant_id:
            raise RuntimeCoreInvariantError("Bundle tenant does not match query tenant")

        # Collect results for this query
        results = self.results_for_query(query_id)
        evidence_count = len(results)

        # Compute average confidence from matched evidence
        total_conf = 0.0
        for result in results:
            ref = self._references.get(result.reference_id)
            if ref:
                total_conf += ref.confidence
        avg_confidence = total_conf / max(evidence_count, 1)

        now = _now_iso()
        bundle = EvidenceBundle(
            bundle_id=bundle_id, query_id=query_id,
            tenant_id=tenant_id, title=title,
            evidence_count=evidence_count,
            confidence=min(avg_confidence, 1.0),
            assembled_at=now,
        )
        self._bundles[bundle_id] = bundle
        _emit(self._events, "evidence_bundle_assembled", {
            "bundle_id": bundle_id, "evidence_count": evidence_count,
        }, bundle_id)
        return bundle

    def get_bundle(self, bundle_id: str) -> EvidenceBundle:
        """Get a bundle by ID."""
        b = self._bundles.get(bundle_id)
        if b is None:
            raise RuntimeCoreInvariantError("Unknown bundle_id")
        return b

    def bundles_for_query(self, query_id: str) -> tuple[EvidenceBundle, ...]:
        """Return all bundles for a query."""
        return tuple(b for b in self._bundles.values() if b.query_id == query_id)

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_query_violations(self) -> tuple[QueryViolation, ...]:
        """Detect query violations beyond cross-tenant (which is inline)."""
        now = _now_iso()
        new_violations: list[QueryViolation] = []

        # Completed queries with zero matches
        for exec_rec in self._executions.values():
            if exec_rec.status == QueryResultStatus.EMPTY:
                vid = stable_identifier("viol-kqry", {
                    "execution": exec_rec.execution_id, "op": "empty_results",
                })
                if vid not in self._violations:
                    query = self._queries.get(exec_rec.query_id)
                    tenant = query.tenant_id if query else "unknown"
                    v = QueryViolation(
                        violation_id=vid, tenant_id=tenant,
                        query_id=exec_rec.query_id,
                        operation="empty_results",
                        reason="Query returned zero results",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # Queries stuck in EXECUTING status
        for query in self._queries.values():
            if query.status == QueryStatus.EXECUTING:
                vid = stable_identifier("viol-kqry", {
                    "query": query.query_id, "op": "stuck_executing",
                })
                if vid not in self._violations:
                    v = QueryViolation(
                        violation_id=vid, tenant_id=query.tenant_id,
                        query_id=query.query_id,
                        operation="stuck_executing",
                        reason="Query stuck in executing status",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "query_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def query_snapshot(self, snapshot_id: str) -> QuerySnapshot:
        """Capture a point-in-time query snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")
        now = _now_iso()
        snap = QuerySnapshot(
            snapshot_id=snapshot_id,
            total_queries=self.query_count,
            total_filters=self.filter_count,
            total_references=self.reference_count,
            total_matches=self.match_count,
            total_results=self.result_count,
            total_executions=self.execution_count,
            total_bundles=self.bundle_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "query_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def query_assessment(self, assessment_id: str, tenant_id: str) -> QueryAssessment:
        now = _now_iso()
        tenant_qids = {q.query_id for q in self._queries.values() if q.tenant_id == tenant_id}
        t_queries = len(tenant_qids)
        t_executions = sum(1 for e in self._executions.values() if e.query_id in tenant_qids)
        t_bundles = sum(1 for b in self._bundles.values() if b.tenant_id == tenant_id)
        t_violations = sum(1 for v in self._violations.values() if v.tenant_id == tenant_id)
        completed = sum(
            1 for q in self._queries.values()
            if q.tenant_id == tenant_id and q.status == QueryStatus.COMPLETED
        )
        rate = completed / t_queries if t_queries else 0.0
        assessment = QueryAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_queries=t_queries, total_executions=t_executions,
            total_bundles=t_bundles, total_violations=t_violations,
            completion_rate=round(rate, 4),
            assessed_at=now,
        )
        _emit(self._events, "query_assessment", {"assessment_id": assessment_id}, assessment_id)
        return assessment

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def query_closure_report(self, report_id: str, tenant_id: str) -> KnowledgeQueryClosureReport:
        now = _now_iso()
        tenant_qids = {q.query_id for q in self._queries.values() if q.tenant_id == tenant_id}
        report = KnowledgeQueryClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_queries=len(tenant_qids),
            total_executions=sum(1 for e in self._executions.values() if e.query_id in tenant_qids),
            total_bundles=sum(1 for b in self._bundles.values() if b.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            total_matches=sum(1 for m in self._matches.values() if m.query_id in tenant_qids),
            total_results=sum(1 for r in self._results.values() if r.query_id in tenant_qids),
            closed_at=now,
        )
        _emit(self._events, "query_closure_report", {"report_id": report_id}, report_id)
        return report

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"queries={self.query_count}",
            f"filters={self.filter_count}",
            f"references={self.reference_count}",
            f"matches={self.match_count}",
            f"results={self.result_count}",
            f"executions={self.execution_count}",
            f"bundles={self.bundle_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
