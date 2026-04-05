"""Purpose: Mfidel semantic overlay -- indexing, clustering, and retrieval by meaning.
Governance scope: semantic annotation, similarity, clustering, and explanation only.
Dependencies: Python standard library only (math, re, collections).
Invariants:
  - Annotations are frozen and immutable after creation.
  - Embeddings are simplified bag-of-words vectors (placeholder for model-backed).
  - Mfidel never mutates operational artifacts -- it produces annotations alongside them.
  - Clock injection ensures deterministic timestamps for replay.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Callable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_EMBEDDING_DIMS: int = 64
_ETHIOPIC_RANGES: tuple[tuple[int, int], ...] = (
    (0x1200, 0x137F),
    (0x1380, 0x139F),
    (0x2D80, 0x2DDF),
    (0xAB00, 0xAB2F),
)


# ---------------------------------------------------------------------------
# Data contracts (frozen dataclasses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SemanticTag:
    """A single semantic label attached to an artifact."""

    tag_id: str
    label: str
    category: str

    def __post_init__(self) -> None:
        if not isinstance(self.tag_id, str) or not self.tag_id.strip():
            raise ValueError("tag_id must be a non-empty string")
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("label must be a non-empty string")
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("category must be a non-empty string")


@dataclass(frozen=True, slots=True)
class SemanticAnnotation:
    """Semantic metadata for a single platform artifact."""

    artifact_id: str
    artifact_type: str
    tags: tuple[SemanticTag, ...]
    embedding: tuple[float, ...]
    description: str
    annotated_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_id, str) or not self.artifact_id.strip():
            raise ValueError("artifact_id must be a non-empty string")
        if not isinstance(self.artifact_type, str) or not self.artifact_type.strip():
            raise ValueError("artifact_type must be a non-empty string")
        if not isinstance(self.tags, tuple):
            raise ValueError("tags must be a tuple of SemanticTag")
        for tag in self.tags:
            if not isinstance(tag, SemanticTag):
                raise ValueError("each tag must be a SemanticTag instance")
        if not isinstance(self.embedding, tuple):
            raise ValueError("embedding must be a tuple of float")
        for val in self.embedding:
            if not isinstance(val, (int, float)):
                raise ValueError("each embedding value must be numeric")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string")
        if not isinstance(self.annotated_at, str) or not self.annotated_at.strip():
            raise ValueError("annotated_at must be a non-empty string")


@dataclass(frozen=True, slots=True)
class SemanticFamily:
    """A cluster of semantically related artifacts."""

    family_id: str
    name: str
    members: tuple[str, ...]
    description: str

    def __post_init__(self) -> None:
        if not isinstance(self.family_id, str) or not self.family_id.strip():
            raise ValueError("family_id must be a non-empty string")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if not isinstance(self.members, tuple):
            raise ValueError("members must be a tuple of artifact id strings")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_text(text: str) -> list[str]:
    """Split text into atomic semantic tokens without decomposing fidel."""
    tokens: list[str] = []
    current: list[str] = []

    for char in text:
        if _is_semantic_token_char(char):
            current.append(_normalize_semantic_char(char))
            continue
        if current:
            tokens.append("".join(current))
            current.clear()

    if current:
        tokens.append("".join(current))
    return tokens


def _is_ethiopic_char(char: str) -> bool:
    codepoint = ord(char)
    return any(start <= codepoint <= end for start, end in _ETHIOPIC_RANGES)


def _is_semantic_token_char(char: str) -> bool:
    if _is_ethiopic_char(char):
        return True
    return char.isascii() and char.isalnum()


def _normalize_semantic_char(char: str) -> str:
    if _is_ethiopic_char(char):
        return char
    return char.lower()


def _build_embedding(text: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
    """Build a simplified bag-of-words frequency vector with vocabulary.

    Returns (vocabulary, values) where vocabulary is sorted word keys
    and values are L2-normalized frequency counts.
    An empty text produces ((), (0.0,)).
    """
    words = _normalize_text(text)
    if not words:
        return ((), (0.0,))

    counts = Counter(words)
    sorted_vocab = sorted(counts.keys())[:_MAX_EMBEDDING_DIMS]
    raw = tuple(float(counts[w]) for w in sorted_vocab)

    # L2 normalize
    magnitude = math.sqrt(sum(v * v for v in raw))
    if magnitude == 0.0:
        return (tuple(sorted_vocab), raw)
    return (tuple(sorted_vocab), tuple(v / magnitude for v in raw))


def _cosine_similarity_vocab(
    vocab_a: tuple[str, ...],
    vals_a: tuple[float, ...],
    vocab_b: tuple[str, ...],
    vals_b: tuple[float, ...],
) -> float:
    """Cosine similarity using aligned vocabulary dimensions."""
    if not vals_a or not vals_b:
        return 0.0

    # Build word->value maps
    map_a = dict(zip(vocab_a, vals_a))
    map_b = dict(zip(vocab_b, vals_b))

    # Union of all words
    all_words = sorted(set(vocab_a) | set(vocab_b))
    if not all_words:
        return 0.0

    va = [map_a.get(w, 0.0) for w in all_words]
    vb = [map_b.get(w, 0.0) for w in all_words]

    dot = sum(x * y for x, y in zip(va, vb))
    mag_a = math.sqrt(sum(x * x for x in va))
    mag_b = math.sqrt(sum(x * x for x in vb))

    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# Semantic index
# ---------------------------------------------------------------------------


class MfidelSemanticIndex:
    """Algorithmic surface for the Mfidel semantic overlay.

    Provides annotation, similarity, search, clustering, and explanation
    over platform artifacts.  Uses an injected clock for deterministic
    timestamps.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._vocabs: dict[str, tuple[str, ...]] = {}  # artifact_id -> vocab

    # -- annotation --------------------------------------------------------

    def annotate(
        self,
        artifact_id: str,
        artifact_type: str,
        text_content: str,
        tags: tuple[SemanticTag, ...] = (),
    ) -> SemanticAnnotation:
        """Create a SemanticAnnotation for an artifact.

        Generates a simplified embedding from *text_content* using a
        bag-of-words frequency vector (top 64 dimensions, L2-normalized).
        """
        vocab, values = _build_embedding(text_content)
        self._vocabs[artifact_id] = vocab
        description = "Semantic annotation"
        return SemanticAnnotation(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            tags=tags,
            embedding=values,
            description=description,
            annotated_at=self._clock(),
        )

    # -- similarity --------------------------------------------------------

    def similarity(
        self,
        annotation_a: SemanticAnnotation,
        annotation_b: SemanticAnnotation,
    ) -> float:
        """Cosine similarity between two annotation embeddings (0.0--1.0)."""
        vocab_a = self._vocabs.get(annotation_a.artifact_id, ())
        vocab_b = self._vocabs.get(annotation_b.artifact_id, ())
        return _cosine_similarity_vocab(
            vocab_a, annotation_a.embedding,
            vocab_b, annotation_b.embedding,
        )

    # -- search ------------------------------------------------------------

    def find_similar(
        self,
        target: SemanticAnnotation,
        candidates: list[SemanticAnnotation],
        *,
        threshold: float = 0.3,
    ) -> list[tuple[SemanticAnnotation, float]]:
        """Return annotations whose similarity to *target* exceeds *threshold*.

        Results are sorted by score descending.  The target itself is excluded
        if present in *candidates*.
        """
        results: list[tuple[SemanticAnnotation, float]] = []
        for candidate in candidates:
            if candidate.artifact_id == target.artifact_id:
                continue
            score = self.similarity(target, candidate)
            if score >= threshold:
                results.append((candidate, score))
        results.sort(key=lambda pair: (-pair[1], pair[0].artifact_id))
        return results

    # -- clustering --------------------------------------------------------

    def cluster_into_families(
        self,
        annotations: list[SemanticAnnotation],
        *,
        threshold: float = 0.5,
    ) -> list[SemanticFamily]:
        """Group annotations into semantic families via single-linkage clustering.

        If any pair of annotations within a group exceeds *threshold*, they
        belong to the same family.  Returns families sorted by family_id.
        """
        if not annotations:
            return []

        n = len(annotations)
        # Union-Find
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[ry] = rx

        # Compare all pairs
        for i in range(n):
            for j in range(i + 1, n):
                score = self.similarity(annotations[i], annotations[j])
                if score >= threshold:
                    union(i, j)

        # Collect clusters
        clusters: dict[int, list[int]] = {}
        for i in range(n):
            root = find(i)
            clusters.setdefault(root, []).append(i)

        families: list[SemanticFamily] = []
        for cluster_indices in clusters.values():
            members = tuple(
                annotations[i].artifact_id for i in sorted(cluster_indices)
            )
            # Build name from first member
            first = annotations[cluster_indices[0]]
            all_tags: list[str] = []
            for idx in cluster_indices:
                for tag in annotations[idx].tags:
                    if tag.label not in all_tags:
                        all_tags.append(tag.label)
            tag_part = ", ".join(all_tags[:5]) if all_tags else "untagged"
            family_id = f"family-{first.artifact_id}"
            name = f"Family: {tag_part}"
            description = "Semantic family"
            families.append(SemanticFamily(
                family_id=family_id,
                name=name,
                members=members,
                description=description,
            ))

        families.sort(key=lambda f: f.family_id)
        return families

    # -- explanation -------------------------------------------------------

    def explain_family(self, family: SemanticFamily) -> str:
        """Generate a human-readable explanation for a semantic family."""
        member_count = len(family.members)
        if member_count == 0:
            return f"{family.name}: empty family with no members."
        member_list = ", ".join(family.members[:10])
        suffix = f" (and {member_count - 10} more)" if member_count > 10 else ""
        return (
            f"{family.name} -- {member_count} artifact(s): "
            f"{member_list}{suffix}. {family.description}"
        )
