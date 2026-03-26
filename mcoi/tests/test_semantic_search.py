"""Phase 221A — Semantic search tests."""

import pytest
from mcoi_runtime.core.semantic_search import SemanticSearchEngine


class TestSemanticSearch:
    def test_index_and_search(self):
        eng = SemanticSearchEngine()
        eng.index("d1", "Python is a programming language")
        eng.index("d2", "Rust is a systems programming language")
        eng.index("d3", "Docker is a container platform")
        results = eng.search("programming language")
        assert len(results) >= 2
        ids = [r.doc_id for r in results]
        assert "d1" in ids
        assert "d2" in ids

    def test_relevance_ranking(self):
        eng = SemanticSearchEngine()
        eng.index("d1", "Python Python Python programming")
        eng.index("d2", "Rust programming")
        results = eng.search("Python")
        assert results[0].doc_id == "d1"  # Higher TF for "python"

    def test_no_results(self):
        eng = SemanticSearchEngine()
        eng.index("d1", "hello world")
        results = eng.search("nonexistent term")
        assert len(results) == 0

    def test_empty_corpus(self):
        eng = SemanticSearchEngine()
        assert eng.search("anything") == []

    def test_remove(self):
        eng = SemanticSearchEngine()
        eng.index("d1", "test document")
        eng.remove("d1")
        assert eng.doc_count == 0
        assert eng.search("test") == []

    def test_update(self):
        eng = SemanticSearchEngine()
        eng.index("d1", "old content about cats")
        eng.index("d1", "new content about dogs")
        results = eng.search("dogs")
        assert len(results) == 1
        assert results[0].doc_id == "d1"

    def test_matched_terms(self):
        eng = SemanticSearchEngine()
        eng.index("d1", "Python programming language")
        results = eng.search("Python language")
        assert "python" in results[0].matched_terms

    def test_limit(self):
        eng = SemanticSearchEngine()
        for i in range(20):
            eng.index(f"d{i}", f"common term document {i}")
        results = eng.search("common term", limit=5)
        assert len(results) == 5

    def test_summary(self):
        eng = SemanticSearchEngine()
        eng.index("d1", "hello world")
        s = eng.summary()
        assert s["documents"] == 1
        assert s["terms"] >= 2
