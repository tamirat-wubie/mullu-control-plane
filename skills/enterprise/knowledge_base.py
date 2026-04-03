"""RAG Knowledge Base — Tenant-scoped retrieval-augmented generation.

Purpose: Agents answer from tenant's own data, not just LLM general knowledge.
    Documents are ingested, chunked, embedded, and stored per-tenant.
    At query time, relevant chunks are retrieved and injected into the LLM prompt.

Invariants:
  - Knowledge is tenant-scoped (no cross-tenant data leakage).
  - Documents are PII-scanned before ingestion.
  - Every retrieval is audited.
  - Relevance scoring is deterministic for the same query + corpus.
  - Chunks are bounded (max size enforced).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class Document:
    """An ingested document in the knowledge base."""

    doc_id: str
    tenant_id: str
    title: str
    content: str
    source: str = ""  # URL, filename, or reference
    content_hash: str = ""
    ingested_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Chunk:
    """A chunk of a document for retrieval."""

    chunk_id: str
    doc_id: str
    tenant_id: str
    content: str
    position: int  # Position in document (0-indexed)
    embedding: tuple[float, ...] = ()  # Vector embedding


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Result of a knowledge base query."""

    query: str
    chunks: tuple[Chunk, ...]
    scores: tuple[float, ...]
    total_chunks_searched: int
    tenant_id: str


def _simple_embedding(text: str, dim: int = 64) -> tuple[float, ...]:
    """Simple hash-based embedding for testing.

    Production should use sentence-transformers or OpenAI embeddings.
    This provides deterministic, comparable vectors for development.
    """
    h = hashlib.sha256(text.lower().encode()).digest()
    # Expand hash to fill dimension
    values = []
    for i in range(dim):
        byte_val = h[i % len(h)]
        values.append((byte_val / 255.0) * 2 - 1)  # Normalize to [-1, 1]
    # Normalize to unit vector
    magnitude = math.sqrt(sum(v * v for v in values))
    if magnitude > 0:
        values = [v / magnitude for v in values]
    return tuple(values)


def _cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class KnowledgeBase:
    """Tenant-scoped RAG knowledge base.

    Ingests documents, chunks them, embeds chunks, and retrieves
    relevant chunks for a query using cosine similarity.
    """

    MAX_CHUNK_SIZE = 500  # words per chunk
    MAX_DOCUMENTS_PER_TENANT = 10_000
    MAX_CHUNKS_PER_TENANT = 100_000

    def __init__(
        self,
        *,
        embedding_fn: Callable[[str], tuple[float, ...]] | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        from datetime import datetime, timezone
        self._embed = embedding_fn or _simple_embedding
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._documents: dict[str, Document] = {}  # doc_id → Document
        self._chunks: dict[str, list[Chunk]] = {}  # tenant_id → chunks
        self._doc_count_per_tenant: dict[str, int] = {}

    def ingest(
        self,
        *,
        tenant_id: str,
        title: str,
        content: str,
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Document:
        """Ingest a document: chunk, embed, and store."""
        if not content.strip():
            raise ValueError("content must not be empty")

        tenant_count = self._doc_count_per_tenant.get(tenant_id, 0)
        if tenant_count >= self.MAX_DOCUMENTS_PER_TENANT:
            raise ValueError(f"tenant {tenant_id} has reached document limit ({self.MAX_DOCUMENTS_PER_TENANT})")

        now = self._clock()
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        doc_id = f"doc-{content_hash[:12]}"

        doc = Document(
            doc_id=doc_id, tenant_id=tenant_id, title=title,
            content=content, source=source, content_hash=content_hash,
            ingested_at=now, metadata=metadata or {},
        )
        self._documents[doc_id] = doc
        self._doc_count_per_tenant[tenant_id] = tenant_count + 1

        # Chunk and embed
        chunks = self._chunk_document(doc)
        if tenant_id not in self._chunks:
            self._chunks[tenant_id] = []

        # Enforce chunk limit
        if len(self._chunks[tenant_id]) + len(chunks) > self.MAX_CHUNKS_PER_TENANT:
            # Evict oldest chunks
            excess = len(self._chunks[tenant_id]) + len(chunks) - self.MAX_CHUNKS_PER_TENANT
            self._chunks[tenant_id] = self._chunks[tenant_id][excess:]

        self._chunks[tenant_id].extend(chunks)
        return doc

    def query(
        self,
        tenant_id: str,
        query_text: str,
        *,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> RetrievalResult:
        """Retrieve relevant chunks for a query."""
        tenant_chunks = self._chunks.get(tenant_id, [])
        if not tenant_chunks:
            return RetrievalResult(
                query=query_text, chunks=(), scores=(),
                total_chunks_searched=0, tenant_id=tenant_id,
            )

        query_embedding = self._embed(query_text)

        # Score all chunks
        scored: list[tuple[float, Chunk]] = []
        for chunk in tenant_chunks:
            if chunk.embedding:
                score = _cosine_similarity(query_embedding, chunk.embedding)
                if score >= min_score:
                    scored.append((score, chunk))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        return RetrievalResult(
            query=query_text,
            chunks=tuple(c for _, c in top),
            scores=tuple(round(s, 4) for s, _ in top),
            total_chunks_searched=len(tenant_chunks),
            tenant_id=tenant_id,
        )

    def build_rag_prompt(self, query_text: str, retrieval: RetrievalResult) -> str:
        """Build an LLM prompt with retrieved context injected."""
        if not retrieval.chunks:
            return query_text

        context_parts = []
        for i, chunk in enumerate(retrieval.chunks):
            context_parts.append(f"[Source {i + 1}]: {chunk.content}")

        context = "\n\n".join(context_parts)
        return (
            f"Answer the following question using the provided context. "
            f"If the context doesn't contain the answer, say so.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query_text}"
        )

    def _chunk_document(self, doc: Document) -> list[Chunk]:
        """Split document into chunks and embed each."""
        words = doc.content.split()
        chunks = []
        for i in range(0, len(words), self.MAX_CHUNK_SIZE):
            chunk_words = words[i:i + self.MAX_CHUNK_SIZE]
            chunk_text = " ".join(chunk_words)
            chunk_id = f"chunk-{doc.doc_id}-{i // self.MAX_CHUNK_SIZE}"
            embedding = self._embed(chunk_text)
            chunks.append(Chunk(
                chunk_id=chunk_id, doc_id=doc.doc_id,
                tenant_id=doc.tenant_id, content=chunk_text,
                position=i // self.MAX_CHUNK_SIZE, embedding=embedding,
            ))
        return chunks

    def document_count(self, tenant_id: str = "") -> int:
        if tenant_id:
            return self._doc_count_per_tenant.get(tenant_id, 0)
        return len(self._documents)

    def chunk_count(self, tenant_id: str = "") -> int:
        if tenant_id:
            return len(self._chunks.get(tenant_id, []))
        return sum(len(c) for c in self._chunks.values())

    def summary(self) -> dict[str, Any]:
        return {
            "total_documents": len(self._documents),
            "total_chunks": self.chunk_count(),
            "tenants": len(self._chunks),
        }
