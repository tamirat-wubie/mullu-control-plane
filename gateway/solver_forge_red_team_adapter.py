"""Gateway solver-forge red-team adapter.

Purpose: Provide a production-grade `AdversarialReviewCallback` for the
    Solver Forge composer that is backed by the platform's deterministic
    `RedTeamHarness` (prompt injection, budget evasion, audit tampering,
    policy bypass).
Governance scope: candidate-only second-gate evidence. The adapter never
    promotes, never mutates the registry, never bypasses the C0-C7 ladder.
    It runs the existing release-gate corpus and translates the report
    into the AdversarialReviewResult shape the composer expects.
Dependencies: gateway.candidate_composer (AdversarialReviewResult,
    AdversarialReviewCallback, CandidateEvaluation, CandidatePipeline),
    gateway.problem_signature (ProblemSignature),
    mcoi_runtime.core.red_team_harness (RedTeamHarness).
Invariants:
  - The harness tests *platform* safety invariants, not candidate-specific
    behavior. The adapter therefore returns the same verdict for every
    candidate in a given session: either the platform is safe (no
    findings) or it is not (all candidates fail with the same findings).
    Candidate-specific adversarial probes are intentionally out of scope
    for this adapter and tracked as follow-on work in
    docs/66_solver_forge_loop.md.
  - When the harness reports failed_count > severity_threshold, the
    adapter MUST return AdversarialReviewResult(passed=False) with
    findings derived from the category summary; a passing review on a
    failed harness would launder a broken platform into apparent safety.
  - The harness report_hash is carried into evidence_refs so reviewers
    can audit the exact report that justified the verdict.
  - Caching is opt-out: the default is to run the harness once per
    adapter instance and reuse the report. A new composer.run() session
    that wants fresh evidence should construct a new adapter instance
    (or call reset_cache()).
"""

from __future__ import annotations

from typing import Any

from gateway.candidate_composer import (
    AdversarialReviewResult,
    CandidateEvaluation,
    CandidatePipeline,
)
from gateway.problem_signature import ProblemSignature

from mcoi_runtime.core.red_team_harness import RedTeamHarness


class RedTeamPlatformReviewer:
    """AdversarialReviewCallback adapter backed by the platform RedTeamHarness.

    Construction is cheap; the harness is not run until the first call.
    The result is cached by default so subsequent calls within the same
    session are free.
    """

    def __init__(
        self,
        harness: RedTeamHarness | None = None,
        *,
        severity_threshold: int = 0,
        cache: bool = True,
    ) -> None:
        if severity_threshold < 0:
            raise ValueError("severity_threshold_must_be_non_negative")
        self._harness = harness or RedTeamHarness()
        self._severity_threshold = severity_threshold
        self._cache = cache
        self._cached_report: dict[str, Any] | None = None

    def __call__(
        self,
        signature: ProblemSignature,
        pipeline: CandidatePipeline,
        evaluation: CandidateEvaluation,
        seed: str,
    ) -> AdversarialReviewResult:
        report = self._report()
        failed = int(report.get("failed_count", 0))
        if failed <= self._severity_threshold:
            return AdversarialReviewResult(passed=True)

        findings = _findings_from_report(report)
        report_hash = str(report.get("report_hash", ""))
        evidence_refs = (report_hash,) if report_hash else ()
        return AdversarialReviewResult(
            passed=False,
            findings=findings,
            evidence_refs=evidence_refs,
            notes=(
                f"platform red-team failed {failed}/{report.get('case_count', 0)} cases; "
                f"all candidates inherit the verdict"
            ),
        )

    def latest_report(self) -> dict[str, Any] | None:
        """Return the most recently observed harness report, or None if the
        adapter has not been invoked yet (or cache is disabled).
        """
        return dict(self._cached_report) if self._cached_report else None

    def reset_cache(self) -> None:
        """Discard the cached report. The next call re-runs the harness."""
        self._cached_report = None

    def _report(self) -> dict[str, Any]:
        if self._cache and self._cached_report is not None:
            return self._cached_report
        report = self._harness.run()
        if self._cache:
            self._cached_report = report
        return report


def _findings_from_report(report: dict[str, Any]) -> tuple[str, ...]:
    """Derive a deterministic finding tuple from a harness report.

    One finding per category that recorded any failure. Findings are
    sorted so the tuple is stable across runs and across Python versions.
    """
    category_summary = report.get("category_summary", {})
    if not isinstance(category_summary, dict):
        return ("red_team_report_malformed",)
    findings: list[str] = []
    for category, summary in category_summary.items():
        if not isinstance(summary, dict):
            continue
        failed = int(summary.get("failed_count", 0))
        if failed > 0:
            findings.append(f"red_team_{category}_failed")
    if not findings:
        return ("red_team_report_inconsistent_no_categorized_failures",)
    return tuple(sorted(findings))
