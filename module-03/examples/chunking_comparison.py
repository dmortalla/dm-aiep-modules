"""Run an offline comparison with a small explicit fruit/space topic ontology.

Run: uv run python module-03/examples/chunking_comparison.py
This local meaning signal demonstrates semantic grouping on a controlled corpus;
it is not a general semantic model, embedding service, or vector metric API.
"""

import json
import re

from rag_engineering_foundations.chunking import (
    FixedConfig,
    RecursiveConfig,
    SemanticConfig,
    chunk_fixed,
    chunk_recursive,
    chunk_semantic,
)
from rag_engineering_foundations.ingestion import ingest_text


def topic_similarity(left: str, right: str) -> float:
    """Compare meanings using an explicit tiny synonym/topic vocabulary.

    Args:
        left: Exact left-hand text unit.
        right: Exact right-hand text unit.

    Returns:
        0.9 for a shared known topic, 0.1 for different known topics, 0.5 otherwise.
    """
    vocabulary = {
        "fruit": {"apples", "pears", "orchards", "fruit"},
        "space": {"rockets", "satellites", "orbit", "space"},
    }

    def topics(text: str) -> set[str]:
        words = set(re.findall(r"\w+", text.casefold()))
        return {topic for topic, terms in vocabulary.items() if terms & words}

    a, b = topics(left), topics(right)
    return 0.9 if a & b else (0.1 if a and b else 0.5)


def main() -> None:
    """Print inspectable exact slices, offsets, identities, and semantic evidence."""
    document = ingest_text(
        "Apples ripen in orchards. Pears grow on fruit trees. "
        "Rockets launch into orbit. Satellites travel through space.",
        source_key="story-03-controlled-topic-comparison",
    )
    results = {
        "fixed": chunk_fixed(document, FixedConfig(size=70)),
        "recursive": chunk_recursive(document, RecursiveConfig(size=70)),
        "semantic": chunk_semantic(document, topic_similarity, SemanticConfig(size=70)),
    }
    print(
        json.dumps(
            {
                name: {
                    "chunks": [
                        {
                            "index": c.index,
                            "start": c.start,
                            "end": c.end,
                            "text": c.content,
                            "chunk_id": c.chunk_id,
                        }
                        for c in result.chunks
                    ],
                    "semantic_evidence": [
                        {"offset": e.offset, "similarity": e.similarity}
                        for e in result.semantic_evidence
                    ],
                }
                for name, result in results.items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
