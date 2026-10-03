"""Offline embedding and metric demonstration; no semantic quality claims.

Run: uv run python module-03/examples/embedding_metrics.py
"""

from rag_engineering_foundations.embeddings import LocalHashEmbedder
from rag_engineering_foundations.vectors import (
    cosine_similarity,
    dot_product,
    euclidean_distance,
)


def main() -> None:
    """Show deterministic lexical features and what the three metrics measure."""
    texts = ("apple pear fruit", "apple fruit", "rocket orbit space")
    embedder = LocalHashEmbedder(dimension=64)
    batch = embedder.embed(texts)
    print("Deterministic offline lexical hashing; not a production semantic model.")
    print(f"Dimension: {batch.dimension}; vectors: {len(batch.vectors)}")
    print(f"Repeated execution identical: {batch == embedder.embed(texts)}")
    print("Cosine: directional alignment [-1,1]; zero vectors are rejected.")
    print("Dot product: unnormalized alignment affected by magnitude.")
    print("Euclidean distance: geometric separation; smaller is closer.")
    for i, text in enumerate(texts):
        print(f"Input {i}: {text!r}; vector preview: {batch.vectors[i].values[:8]}")
    for index in (0, 1, 2):
        left, right = batch.vectors[0], batch.vectors[index]
        print(
            f"0 vs {index}: cosine={cosine_similarity(left, right):.6f}, "
            f"dot={dot_product(left, right):.6f}, "
            f"distance={euclidean_distance(left, right):.6f}"
        )
    print("Local vectors are normalized: dot and cosine coincide here.")


if __name__ == "__main__":
    main()
