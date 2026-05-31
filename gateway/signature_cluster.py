"""Gateway signature clustering.

Purpose: Recognize when two problem signatures are the *same kind of problem*
    even though their `signature_hash` values differ, so the comparison
    ledger's evidence can transfer across related signatures. This is the
    "cross-signature learning" layer: for a new signature it can answer "which
    method families have won on problems like this before?".
Governance scope: read-only analysis. The index computes a deterministic
    similarity from signatures' declared structure and reads winners from the
    ledger. It NEVER promotes, scores, mutates a record, or composes a
    candidate. It is advisory only.
Dependencies: gateway.problem_signature (ProblemSignature), gateway.candidate_ledger
    (CandidateLedger, only read via winners_for).
Invariants:
  - Similarity is deterministic and symmetric: identical content -> 1.0.
  - Similarity is a transparent feature-overlap heuristic (domain, goal tokens,
    success-metric ids, allowed families, risk), NOT a learned model. The
    weights and threshold are explicit and tunable.
  - The index never recommends an action; `prior_winning_families` returns
    evidence counts, not a decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gateway.candidate_ledger import CandidateLedger
from gateway.problem_signature import ProblemSignature


@dataclass(frozen=True, slots=True)
class SimilarityWeights:
    """Relative weights for the feature-overlap similarity. Normalized by their
    sum, so they need not add to 1."""

    domain: float = 0.35
    goal: float = 0.20
    metrics: float = 0.20
    families: float = 0.15
    risk: float = 0.10


DEFAULT_WEIGHTS = SimilarityWeights()
DEFAULT_THRESHOLD = 0.6


def _tokens(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _success_metric_ids(signature: ProblemSignature) -> frozenset[str]:
    return frozenset(m.metric_id for m in signature.success_metrics())


def signature_similarity(
    a: ProblemSignature,
    b: ProblemSignature,
    *,
    weights: SimilarityWeights = DEFAULT_WEIGHTS,
) -> float:
    """Deterministic, symmetric similarity in [0, 1]."""
    domain = 1.0 if a.domain == b.domain else 0.0
    goal = _jaccard(_tokens(a.goal), _tokens(b.goal))
    metrics = _jaccard(_success_metric_ids(a), _success_metric_ids(b))
    families = _jaccard(
        frozenset(a.allowed_method_families), frozenset(b.allowed_method_families)
    )
    risk = 1.0 if a.risk == b.risk else 0.0

    total = weights.domain + weights.goal + weights.metrics + weights.families + weights.risk
    if total <= 0:
        return 0.0
    score = (
        weights.domain * domain
        + weights.goal * goal
        + weights.metrics * metrics
        + weights.families * families
        + weights.risk * risk
    )
    return score / total


class SignatureClusterIndex:
    """Groups registered signatures into problem classes by similarity."""

    def __init__(
        self,
        *,
        threshold: float = DEFAULT_THRESHOLD,
        weights: SimilarityWeights = DEFAULT_WEIGHTS,
    ) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold_must_be_between_0_and_1")
        self._threshold = threshold
        self._weights = weights
        self._signatures: dict[str, ProblemSignature] = {}

    def add(self, signature: ProblemSignature) -> None:
        self._signatures[signature.signature_hash] = signature

    def add_all(self, signatures: tuple[ProblemSignature, ...]) -> None:
        for signature in signatures:
            self.add(signature)

    def signatures(self) -> tuple[ProblemSignature, ...]:
        return tuple(self._signatures.values())

    def similarity(self, a: ProblemSignature, b: ProblemSignature) -> float:
        return signature_similarity(a, b, weights=self._weights)

    def related(
        self, signature: ProblemSignature
    ) -> tuple[tuple[ProblemSignature, float], ...]:
        """Registered signatures whose similarity to `signature` meets the
        threshold, excluding the signature itself (by hash), sorted by
        descending score then problem_id for determinism. `signature` need not
        be registered."""
        scored: list[tuple[ProblemSignature, float]] = []
        for candidate in self._signatures.values():
            if candidate.signature_hash == signature.signature_hash:
                continue
            score = self.similarity(signature, candidate)
            if score >= self._threshold:
                scored.append((candidate, score))
        scored.sort(key=lambda pair: (-pair[1], pair[0].problem_id))
        return tuple(scored)

    def clusters(self) -> tuple[frozenset[str], ...]:
        """Connected components of registered signatures (edges where similarity
        meets the threshold), as frozensets of signature_hash, deterministically
        ordered."""
        hashes = list(self._signatures)
        parent = {h: h for h in hashes}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: str, y: str) -> None:
            parent[find(x)] = find(y)

        for i in range(len(hashes)):
            for j in range(i + 1, len(hashes)):
                a, b = self._signatures[hashes[i]], self._signatures[hashes[j]]
                if self.similarity(a, b) >= self._threshold:
                    union(hashes[i], hashes[j])

        groups: dict[str, set[str]] = {}
        for h in hashes:
            groups.setdefault(find(h), set()).add(h)
        # Deterministic order: by smallest member hash within each group.
        return tuple(
            sorted((frozenset(g) for g in groups.values()), key=lambda s: min(s))
        )

    def prior_winning_families(
        self, signature: ProblemSignature, ledger: CandidateLedger
    ) -> dict[str, int]:
        """Tally the method families that have won on signatures related to
        `signature`, read from the ledger. Evidence, not a recommendation.

        For each related signature, winners are read with that signature's own
        primary success metric.
        """
        tally: dict[str, int] = {}
        for related_sig, _score in self.related(signature):
            success = related_sig.success_metrics()
            if not success:
                continue
            primary = success[0].metric_id
            for winner in ledger.winners_for(
                related_sig.signature_hash, primary_metric_id=primary
            ):
                for family in winner.method_families:
                    tally[family] = tally.get(family, 0) + 1
        return dict(sorted(tally.items()))
