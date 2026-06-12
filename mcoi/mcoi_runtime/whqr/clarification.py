"""Purpose: build deterministic clarification requests and binding admissions from WHQR binding gaps.
Governance scope: convert unresolved WHQR binding preflight issues into operator-facing questions and explicit binding candidates without side effects.
Dependencies: conversation contracts, WHQR binding preflight reports, and WHQR entity binding candidates.
Invariants: generation and admission are pure, deterministic, grouped by WHQR target, and preserve every unresolved issue in request context.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts.conversation import ClarificationRequest, ClarificationResponse
from mcoi_runtime.whqr.binding_preflight import BindingPreflightIssue, BindingPreflightReport
from mcoi_runtime.whqr.entity_binder import EntityBindingCandidate

_RESPONSE_BINDING_KEYS = frozenset(("entity_ref", "evidence_ref", "entity_type"))


@dataclass(frozen=True, slots=True)
class WHQRClarificationBundle:
    requests: tuple[ClarificationRequest, ...]

    @property
    def empty(self) -> bool:
        return not self.requests


@dataclass(frozen=True, slots=True)
class WHQRClarificationBindingResult:
    target: str
    candidate: EntityBindingCandidate | None
    accepted: bool
    reason: str

    def __post_init__(self) -> None:
        _require_text(self.target, "target")
        _require_text(self.reason, "reason")
        if self.candidate is not None and not isinstance(self.candidate, EntityBindingCandidate):
            raise ValueError("candidate must be an EntityBindingCandidate")
        if not isinstance(self.accepted, bool):
            raise ValueError("accepted must be a boolean")


@dataclass(frozen=True, slots=True)
class WHQRClarificationBindingMap:
    results: tuple[WHQRClarificationBindingResult, ...]
    bindings: tuple[tuple[str, EntityBindingCandidate], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.results, tuple):
            raise ValueError("results must be a tuple")
        if not isinstance(self.bindings, tuple):
            raise ValueError("bindings must be a tuple")
        for result in self.results:
            if not isinstance(result, WHQRClarificationBindingResult):
                raise ValueError("results must contain WHQRClarificationBindingResult values")
        for target, candidate in self.bindings:
            _require_text(target, "binding target")
            if not isinstance(candidate, EntityBindingCandidate):
                raise ValueError("bindings must contain EntityBindingCandidate values")

    @property
    def accepted_count(self) -> int:
        return len(self.bindings)

    @property
    def rejected_count(self) -> int:
        return sum(1 for result in self.results if not result.accepted)

    @property
    def passed(self) -> bool:
        return self.rejected_count == 0

    def as_binding_candidates(self) -> dict[str, EntityBindingCandidate]:
        """Return a mutable candidate map suitable for the pure WHQR entity binder."""
        return dict(self.bindings)


def build_binding_clarification_requests(
    report: BindingPreflightReport,
    *,
    thread_id: str,
    requested_from_id: str,
    requested_at: str,
    request_prefix: str = "whqr-binding",
) -> WHQRClarificationBundle:
    """Build grouped clarification requests for unresolved WHQR binding issues."""
    if report.passed:
        return WHQRClarificationBundle(())
    _require_text(thread_id, "thread_id")
    _require_text(requested_from_id, "requested_from_id")
    _require_text(request_prefix, "request_prefix")
    grouped = _group_issues(report.issues)
    requests = tuple(
        ClarificationRequest(
            request_id=f"{request_prefix}:{idx}:{_stable_ref(issues[0])}",
            thread_id=thread_id,
            question=_question(issues),
            context=_context(issues),
            requested_from_id=requested_from_id,
            requested_at=requested_at,
        )
        for idx, issues in enumerate(grouped, start=1)
    )
    return WHQRClarificationBundle(requests)


def admit_binding_clarification_response(
    request: ClarificationRequest,
    response: ClarificationResponse,
) -> WHQRClarificationBindingResult:
    """Admit one explicit clarification response as a WHQR entity binding candidate."""
    context = _parse_context(request.context)
    target = context.get("target") or "unknown"
    if request.request_id != response.request_id or request.thread_id != response.thread_id:
        return WHQRClarificationBindingResult(target, None, False, "request_mismatch")
    if target == "unknown":
        return WHQRClarificationBindingResult(target, None, False, "missing_target_context")
    fields = _parse_response_binding_fields(response.answer)
    if fields is None:
        return WHQRClarificationBindingResult(target, None, False, "invalid_response_binding_field")
    entity_ref = fields.get("entity_ref")
    evidence_ref = fields.get("evidence_ref")
    entity_type = fields.get("entity_type") or context.get("expected_type")
    if not entity_ref or not evidence_ref:
        return WHQRClarificationBindingResult(target, None, False, "missing_response_binding_field")
    if not entity_type or entity_type == "unspecified":
        return WHQRClarificationBindingResult(target, None, False, "missing_entity_type")
    candidate = EntityBindingCandidate(entity_ref=entity_ref, evidence_ref=evidence_ref, entity_type=entity_type)
    return WHQRClarificationBindingResult(target, candidate, True, "accepted")


def build_binding_map_from_clarification_responses(
    requests: tuple[ClarificationRequest, ...],
    responses: tuple[ClarificationResponse, ...],
) -> WHQRClarificationBindingMap:
    """Build a deterministic target-to-candidate map from explicit clarification responses."""
    request_index = _index_requests(requests)
    results: list[WHQRClarificationBindingResult] = []
    bindings: dict[str, EntityBindingCandidate] = {}
    for response in sorted(responses, key=lambda item: (item.request_id, item.responded_at, item.responded_by_id)):
        if not isinstance(response, ClarificationResponse):
            raise ValueError("responses must contain ClarificationResponse values")
        request = request_index.get(response.request_id)
        if request is None:
            results.append(WHQRClarificationBindingResult("unknown", None, False, "unknown_request"))
            continue
        result = admit_binding_clarification_response(request, response)
        if not result.accepted:
            results.append(result)
            continue
        if result.target in bindings:
            results.append(WHQRClarificationBindingResult(result.target, None, False, "duplicate_target_binding"))
            continue
        if result.candidate is None:
            results.append(WHQRClarificationBindingResult(result.target, None, False, "missing_response_binding_field"))
            continue
        bindings[result.target] = result.candidate
        results.append(result)
    return WHQRClarificationBindingMap(tuple(results), tuple(sorted(bindings.items())))


def _group_issues(issues: tuple[BindingPreflightIssue, ...]) -> tuple[tuple[BindingPreflightIssue, ...], ...]:
    groups: dict[tuple[str, str | None, str | None], list[BindingPreflightIssue]] = {}
    for issue in issues:
        key = (issue.target, issue.node_id, issue.expected_type)
        groups.setdefault(key, []).append(issue)
    return tuple(tuple(groups[key]) for key in sorted(groups))


def _question(issues: tuple[BindingPreflightIssue, ...]) -> str:
    first = issues[0]
    expected = first.expected_type or "entity"
    missing = {issue.code for issue in issues}
    if missing == {"missing_entity_ref"}:
        return f"Which {expected} entity reference binds WHQR target '{first.target}'?"
    if missing == {"missing_evidence_ref"}:
        return f"Which evidence reference proves WHQR target '{first.target}'?"
    return f"Which {expected} entity reference and evidence reference bind WHQR target '{first.target}'?"


def _context(issues: tuple[BindingPreflightIssue, ...]) -> str:
    first = issues[0]
    codes = ",".join(issue.code for issue in issues)
    node_ref = first.node_id or "unassigned"
    expected = first.expected_type or "unspecified"
    return f"whqr_binding_gap target={first.target} node_id={node_ref} expected_type={expected} issue_codes={codes}"


def _stable_ref(issue: BindingPreflightIssue) -> str:
    node_ref = issue.node_id or issue.target
    return node_ref.replace(":", "_").replace(" ", "_")


def _index_requests(requests: tuple[ClarificationRequest, ...]) -> dict[str, ClarificationRequest]:
    index: dict[str, ClarificationRequest] = {}
    for request in requests:
        if not isinstance(request, ClarificationRequest):
            raise ValueError("requests must contain ClarificationRequest values")
        if request.request_id in index:
            raise ValueError("clarification request ids must be unique")
        index[request.request_id] = request
    return index


def _parse_context(context: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in context.split():
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key:
            fields[key] = value
    return fields


def _parse_response_binding_fields(answer: str) -> dict[str, str] | None:
    fields: dict[str, str] = {}
    for part in answer.replace("\n", ";").split(";"):
        item = part.strip()
        if not item:
            continue
        if "=" not in item:
            return None
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in _RESPONSE_BINDING_KEYS or key in fields or not value:
            return None
        fields[key] = value
    return fields


def _require_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value
