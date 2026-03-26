"""Phase 221A — Semantic Memory Search.

Purpose: TF-IDF-style relevance scoring for agent memory search.
    Provides better recall than simple keyword matching by computing
    term frequency and inverse document frequency across memories.
Governance scope: search scoring only — never modifies memories.
Invariants:
  - Scoring is deterministic for same corpus.
  - Zero-relevance results are excluded.
  - Search is bounded by limit parameter.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ScoredDocument:
    """Document with relevance score."""

    doc_id: str
    content: str
    score: float
    matched_terms: tuple[str, ...]


class SemanticSearchEngine:
    """TF-IDF based search over a document corpus."""

    def __init__(self) -> None:
        self._documents: dict[str, str] = {}  # doc_id -> content
        self._term_docs: dict[str, set[str]] = {}  # term -> doc_ids containing it

    def index(self, doc_id: str, content: str) -> None:
        """Add or update a document in the index."""
        # Remove old terms if re-indexing
        if doc_id in self._documents:
            old_terms = self._tokenize(self._documents[doc_id])
            for term in old_terms:
                if term in self._term_docs:
                    self._term_docs[term].discard(doc_id)

        self._documents[doc_id] = content
        terms = self._tokenize(content)
        for term in terms:
            if term not in self._term_docs:
                self._term_docs[term] = set()
            self._term_docs[term].add(doc_id)

    def remove(self, doc_id: str) -> bool:
        if doc_id not in self._documents:
            return False
        terms = self._tokenize(self._documents[doc_id])
        for term in terms:
            if term in self._term_docs:
                self._term_docs[term].discard(doc_id)
        del self._documents[doc_id]
        return True

    def search(self, query: str, limit: int = 10) -> list[ScoredDocument]:
        """Search documents by TF-IDF relevance."""
        query_terms = self._tokenize(query)
        if not query_terms or not self._documents:
            return []

        n_docs = len(self._documents)
        scores: dict[str, float] = {}
        matches: dict[str, list[str]] = {}

        for term in query_terms:
            doc_ids = self._term_docs.get(term, set())
            if not doc_ids:
                continue
            idf = math.log(n_docs / len(doc_ids)) + 1  # Smoothed IDF

            for doc_id in doc_ids:
                content = self._documents[doc_id]
                tf = self._tf(term, content)
                score = tf * idf
                scores[doc_id] = scores.get(doc_id, 0.0) + score
                if doc_id not in matches:
                    matches[doc_id] = []
                if term not in matches[doc_id]:
                    matches[doc_id].append(term)

        results = [
            ScoredDocument(
                doc_id=doc_id, content=self._documents[doc_id],
                score=round(score, 4),
                matched_terms=tuple(matches.get(doc_id, [])),
            )
            for doc_id, score in scores.items()
            if score > 0
        ]
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def _tokenize(self, text: str) -> list[str]:
        """Simple whitespace + lowercase tokenization."""
        return [w.strip(".,!?;:'\"()[]{}") for w in text.lower().split() if len(w) > 1]

    def _tf(self, term: str, content: str) -> float:
        """Term frequency (normalized)."""
        tokens = self._tokenize(content)
        if not tokens:
            return 0.0
        count = tokens.count(term)
        return count / len(tokens)

    @property
    def doc_count(self) -> int:
        return len(self._documents)

    @property
    def term_count(self) -> int:
        return len(self._term_docs)

    def summary(self) -> dict[str, Any]:
        return {"documents": self.doc_count, "terms": self.term_count}
