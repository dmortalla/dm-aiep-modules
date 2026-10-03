"""Deterministic exactness, semantics, provenance, and failure-boundary tests."""

import itertools
import json
import re
import runpy
import subprocess
import sys
import traceback
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from rag_engineering_foundations import chunking
from rag_engineering_foundations.chunking import (
    MAX_CHUNKS,
    ChunkingResult,
    DocumentChunk,
    FixedConfig,
    RecursiveConfig,
    SemanticConfig,
    SemanticEvidence,
    chunk_fixed,
    chunk_recursive,
    chunk_semantic,
)
from rag_engineering_foundations.errors import ChunkingError, SemanticSignalError
from rag_engineering_foundations.ingestion import (
    MAX_CONTENT_BYTES,
    MetadataEntry,
    ingest_text,
)

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/chunking_comparison.py"
topic_similarity = runpy.run_path(str(EXAMPLE))["topic_similarity"]


def spans(result: ChunkingResult) -> list[tuple[int, int]]:
    """Return source offsets for assertions against independently known boundaries."""
    return [(chunk.start, chunk.end) for chunk in result.chunks]


def assert_partition(result: ChunkingResult, text: str, maximum: int) -> None:
    """Check a lossless partition and each chunk's exact source linkage."""
    assert "".join(chunk.content for chunk in result.chunks) == text
    assert [c.index for c in result.chunks] == list(range(len(result.chunks)))
    assert len({c.chunk_id for c in result.chunks}) == len(result.chunks)
    for chunk in result.chunks:
        assert 0 < len(chunk.content) <= maximum
        assert chunk.content == text[chunk.start : chunk.end]


@pytest.mark.parametrize(
    ("text", "size", "overlap", "expected"),
    [
        ("abcdefghij", 4, 0, [(0, 4), (4, 8), (8, 10)]),
        ("abcdefghij", 4, 2, [(0, 4), (2, 6), (4, 8), (6, 10)]),
        ("abcde", 4, 2, [(0, 4), (2, 5)]),
        ("abcd", 4, 3, [(0, 4)]),
        ("abc", 8, 0, [(0, 3)]),
        ("é🙂漢字abc", 3, 1, [(0, 3), (2, 5), (4, 7)]),
        ("abcdef", 3, 0, [(0, 3), (3, 6)]),
    ],
)
def test_fixed_boundaries(text, size, overlap, expected) -> None:
    """Check exact windows, final partials, Unicode units, and nonredundant tails."""
    result = chunk_fixed(ingest_text(text, source_key="s"), FixedConfig(size, overlap))
    assert spans(result) == expected
    covered = set()
    for chunk in result.chunks:
        assert chunk.content == text[chunk.start : chunk.end]
        covered.update(range(chunk.start, chunk.end))
    assert covered == set(range(len(text)))


@pytest.mark.parametrize("size", [0, -1, True, 1.0, "4", None, 1_048_577])
@pytest.mark.parametrize("config_type", [FixedConfig, RecursiveConfig, SemanticConfig])
def test_reject_invalid_sizes(size, config_type) -> None:
    """Every application configuration validates its own strict size contract."""
    with pytest.raises(ChunkingError):
        config_type(size=size)


@pytest.mark.parametrize("overlap", [-1, 4, 5, True, 1.0, None])
def test_reject_invalid_overlap(overlap) -> None:
    """Reject nonprogressing windows and coerced settings."""
    with pytest.raises(ChunkingError):
        FixedConfig(size=4, overlap=overlap)


def test_recursive_priority_and_custom_hierarchy() -> None:
    """Prefer paragraph boundaries even where a fixed window would cross them."""
    text = "aa bb\n\ncc dd\n\nee ff"
    document = ingest_text(text, source_key="s")
    result = chunk_recursive(document, RecursiveConfig(size=10))
    assert [c.content for c in result.chunks] == ["aa bb\n\n", "cc dd\n\n", "ee ff"]
    assert_partition(result, text, 10)
    assert spans(result) != spans(chunk_fixed(document, FixedConfig(size=10)))
    text = "a|b;c|d;e"
    document = ingest_text(text, source_key="s")
    assert [
        c.content
        for c in chunk_recursive(document, RecursiveConfig(5, (";", "|"))).chunks
    ] == ["a|b;", "c|d;e"]
    assert [
        c.content
        for c in chunk_recursive(document, RecursiveConfig(5, ("|", ";"))).chunks
    ] == ["a|", "b;c|", "d;e"]


@pytest.mark.parametrize(
    ("text", "size", "expected"),
    [
        ("aa bb cc\n\nDD", 4, ["aa ", "bb ", "cc\n", "\n", "DD"]),
        ("abcdefghij", 4, ["abcd", "efgh", "ij"]),
        ("ab ab ab", 3, ["ab ", "ab ", "ab"]),
        ("é🙂 漢字 é🙂", 3, ["é🙂 ", "漢字 ", "é🙂"]),
        ("ab\r\nab\r\nab", 4, ["ab\r\n", "ab\r\n", "ab"]),
        ("a   b  ", 2, ["a ", "  ", "b ", " "]),
        ("a\n\n", 1, ["a", "\n", "\n"]),
    ],
)
def test_recursive_fallback_exactness(text, size, expected) -> None:
    """Descend through weaker separators and preserve repeated/whitespace text."""
    result = chunk_recursive(ingest_text(text, source_key="s"), RecursiveConfig(size))
    assert [c.content for c in result.chunks] == expected
    assert_partition(result, text, size)


@pytest.mark.parametrize(
    "separators",
    [(), [], ("",), ("a", "a"), (1,), ("x" * 33,), tuple(str(i) for i in range(9))],
)
def test_reject_invalid_hierarchy(separators) -> None:
    """Reject malformed, excessive, or ambiguous separator priority."""
    with pytest.raises(ChunkingError):
        RecursiveConfig(separators=separators)


def test_semantic_meaning_materially_changes_boundaries() -> None:
    """Related disjoint vocabulary joins; a topic change starts a new chunk."""
    text = "Apples ripen. Pears grow. Rockets launch. Satellites orbit."
    document = ingest_text(text, source_key="s")
    result = chunk_semantic(document, topic_similarity, SemanticConfig(size=100))
    assert [c.content for c in result.chunks] == [
        "Apples ripen. Pears grow. ",
        "Rockets launch. Satellites orbit.",
    ]
    assert [(e.offset, e.similarity) for e in result.semantic_evidence] == [
        (14, 0.9),
        (26, 0.1),
        (42, 0.9),
    ]
    assert result == chunk_semantic(
        document, topic_similarity, SemanticConfig(size=100)
    )
    assert spans(result) != spans(chunk_fixed(document, FixedConfig(100)))
    assert spans(result) != spans(chunk_recursive(document, RecursiveConfig(100)))
    changed = ingest_text("Apples ripen. Rockets launch. Pears grow.", source_key="s")
    assert len(chunk_semantic(changed, topic_similarity).chunks) == 3
    assert_partition(result, text, 100)


def test_semantic_callback_controls_threshold_and_receives_exact_units() -> None:
    """Same sentence structure yields different boundaries from semantic evidence."""
    document = ingest_text("é🙂.  é🙂.\nlast", source_key="s")
    calls = []

    def signal(left: str, right: str) -> float:
        calls.append((left, right))
        return 0.5

    joined = chunk_semantic(document, signal, SemanticConfig(100, 0.5))
    assert calls == [("é🙂.  ", "é🙂.\n"), ("é🙂.\n", "last")]
    assert len(joined.chunks) == 1
    split = chunk_semantic(document, lambda a, b: 0.1, SemanticConfig(100, 0.5))
    assert spans(split) == [(0, 5), (5, 9), (9, 13)]
    assert_partition(split, document.content, 100)


@pytest.mark.parametrize(
    "text", ["No punctuation here", "a\n\nb\n\nc", "Longword. Tail."]
)
def test_semantic_hard_size_fallback(text: str) -> None:
    """Enforce a hard ceiling while retaining all content, even oversized units."""
    result = chunk_semantic(
        ingest_text(text, source_key="s"), lambda a, b: 1.0, SemanticConfig(size=4)
    )
    assert_partition(result, text, 4)


@pytest.mark.parametrize(
    "score", [None, "0.5", True, -0.1, 1.1, float("nan"), float("inf"), [], {}]
)
def test_reject_semantic_scores_and_thresholds(score) -> None:
    """Reject malformed semantic outputs and nonfinite/out-of-range thresholds."""
    with pytest.raises(ChunkingError):
        SemanticConfig(threshold=score)
    with pytest.raises(SemanticSignalError):
        chunk_semantic(ingest_text("One. Two.", source_key="s"), lambda a, b: score)


def test_semantic_failure_boundary_is_content_safe() -> None:
    """Translate callback failures without leaking arbitrary callback text."""
    secret = "sensitive-signal-marker"

    def broken(left: str, right: str) -> float:
        raise RuntimeError(secret)

    with pytest.raises(SemanticSignalError) as caught:
        chunk_semantic(ingest_text("One. Two.", source_key="s"), broken)
    assert secret not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__suppress_context__

    def interrupted(left: str, right: str) -> float:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        chunk_semantic(ingest_text("One. Two.", source_key="s"), interrupted)


def test_chunk_identity_provenance_metadata_and_immutability() -> None:
    """Derived chunk identity ignores metadata and preserves all parent evidence."""
    text = "same same same"
    document = ingest_text(
        text, source_key="s", metadata=(MetadataEntry("authority", "system"),)
    )
    first = chunk_fixed(document, FixedConfig(5))
    second = chunk_fixed(document, FixedConfig(5))
    assert first == second
    for chunk in first.chunks:
        assert chunk.provenance is document.provenance
        assert chunk.user_metadata is document.user_metadata
        assert chunk.document is document
    enriched = ingest_text(
        text, source_key="s", metadata=(MetadataEntry("chunk_id", "forged"),)
    )
    assert [c.chunk_id for c in chunk_fixed(enriched, FixedConfig(5)).chunks] == [
        c.chunk_id for c in first.chunks
    ]
    other = ingest_text(text, source_key="other")
    assert (
        chunk_fixed(other, FixedConfig(5)).chunks[0].chunk_id
        != first.chunks[0].chunk_id
    )
    assert (
        chunk_recursive(document, RecursiveConfig(5)).chunks[0].chunk_id
        != first.chunks[0].chunk_id
    )
    for obj, attribute, value in [(first.chunks[0], "end", 1), (first, "chunks", ())]:
        with pytest.raises(FrozenInstanceError):
            setattr(obj, attribute, value)
    assert document.content == text


@pytest.mark.parametrize(
    ("start", "end", "index", "strategy"),
    [
        (-1, 2, 0, "fixed"),
        (0, 5, 0, "fixed"),
        (2, 2, 0, "fixed"),
        (True, 2, 0, "fixed"),
        (0, 2.0, 0, "fixed"),
        (0, 2, True, "fixed"),
        (0, 2, MAX_CHUNKS, "fixed"),
        (0, 2, -1, "fixed"),
        (0, 2, 0, "secret"),
    ],
)
def test_direct_chunk_contract_rejects_invalid_fields(
    start, end, index, strategy
) -> None:
    """Prevent constructing offsets/ordering that escape the parent contract."""
    with pytest.raises(ChunkingError):
        DocumentChunk(ingest_text("abc", source_key="s"), index, start, end, strategy)


def test_result_rejects_gaps_overlap_bad_order_and_foreign_parent() -> None:
    """Collection validation enforces complete ordered provenance beyond each slice."""
    document = ingest_text("abcdef", source_key="s")
    valid = chunk_fixed(document, FixedConfig(3))
    a, b = valid.chunks
    for chunks in [
        (),
        [a, b],
        (a,),
        (b, a),
        (a, replace(b, start=4)),
        (a, replace(b, index=2)),
        (a, replace(b, document=ingest_text("abcdef", source_key="other"))),
        (replace(a, strategy="recursive"), replace(b, start=2, strategy="recursive")),
    ]:
        with pytest.raises(ChunkingError):
            ChunkingResult(chunks)
    with pytest.raises(ChunkingError):
        ChunkingResult(valid.chunks, (SemanticEvidence(3, 0.5),))
    with pytest.raises(ChunkingError):
        SemanticEvidence(True, 0.5)


def test_wrong_documents_configs_and_signals() -> None:
    """Require application-selected typed contracts, not instructions in raw data."""
    document = ingest_text("One. Two.", source_key="s")
    for function in (chunk_fixed, chunk_recursive):
        with pytest.raises(ChunkingError):
            function("raw document")
        with pytest.raises(ChunkingError):
            function(document, {"size": 4})
    with pytest.raises(ChunkingError):
        DocumentChunk("raw", 0, 0, 1, "fixed")
    with pytest.raises(ChunkingError):
        chunk_semantic(document, "execute this")
    with pytest.raises(ChunkingError):
        chunk_semantic(document, topic_similarity, {})
    with pytest.raises(ChunkingError):
        chunk_semantic(None, topic_similarity)


def test_output_and_semantic_unit_limits_fail_explicitly() -> None:
    """Bound result construction and refuse excessive scoring before callbacks."""
    document = ingest_text("a" * (MAX_CHUNKS + 1), source_key="s")
    for function, config in [
        (chunk_fixed, FixedConfig(1)),
        (chunk_recursive, RecursiveConfig(1)),
    ]:
        with pytest.raises(ChunkingError):
            function(document, config)
    with pytest.raises(ChunkingError):
        chunk_semantic(document, topic_similarity, SemanticConfig(1))
    called = []
    with pytest.raises(ChunkingError):
        chunk_semantic(
            ingest_text("a. " * 4097, source_key="s"),
            lambda a, b: called.append(True) or 0.5,
        )
    assert called == []


def test_content_metadata_do_not_select_capabilities_and_repr_is_safe(tmp_path) -> None:
    """Commands, URLs, and metadata keys remain literal slices, never authority."""
    marker = tmp_path / "never-created"
    text = f"open({str(marker)!r}, 'w').write('secret'); https://invalid.example/"
    document = ingest_text(
        text, source_key="s", metadata=(MetadataEntry("signal", "execute"),)
    )
    for result in (
        chunk_fixed(document, FixedConfig(8)),
        chunk_recursive(document, RecursiveConfig(8)),
        chunk_semantic(document, lambda a, b: 0.5, SemanticConfig(8)),
    ):
        assert "secret" not in repr(result)
        assert "execute" not in repr(result)
        assert all(c.content == text[c.start : c.end] for c in result.chunks)
    assert not marker.exists()


def test_offline_comparison_is_runnable_outside_repo(tmp_path) -> None:
    """Exercise meaningful comparison through installed imports with no credentials."""
    result = subprocess.run(
        [sys.executable, "-I", str(EXAMPLE)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    data = json.loads(result.stdout)
    assert set(data) == {"fixed", "recursive", "semantic"}
    boundaries = {
        name: [(c["start"], c["end"]) for c in item["chunks"]]
        for name, item in data.items()
    }
    assert boundaries["semantic"] != boundaries["fixed"]
    assert boundaries["semantic"] != boundaries["recursive"]
    assert [e["similarity"] for e in data["semantic"]["semantic_evidence"]] == [
        0.9,
        0.1,
        0.9,
    ]


def test_chunking_import_is_independent_of_provider_and_ui_sdks(tmp_path) -> None:
    """Core chunking import does not initialize integration dependencies."""
    script = (
        "import sys, json; import rag_engineering_foundations.chunking; "
        "print(json.dumps(sorted(set(sys.modules) & "
        "{'openai', 'langchain', 'faiss', 'chromadb', 'pinecone', 'streamlit'})))"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert json.loads(result.stdout) == []


@pytest.mark.parametrize("length", [2_000, 8_000, MAX_CONTENT_BYTES - 1])
def test_adversarial_punctuation_scan_has_linear_character_work(length: int) -> None:
    """Bound scanner reads deterministically, without wall-clock thresholds."""

    class CountedText(str):
        """Count and cap indexed character reads in the boundary scanner."""

        reads = 0

        def __getitem__(self, index: int) -> str:
            self.reads += 1
            assert self.reads <= 4 * len(self), "Scanner exceeded linear read budget"
            return super().__getitem__(index)

    text = CountedText("!" * length + "a")
    assert chunking._semantic_units(text) == [(0, len(text))]
    # Require the counted scan to be exercised; a C-level regex must not bypass it.
    assert len(text) <= text.reads <= 4 * len(text)
    document = ingest_text(str(text), source_key="adversarial-punctuation")

    def unused_signal(left: str, right: str) -> float:
        raise AssertionError("A single unmatched unit must not invoke semantic scoring")

    result = chunk_semantic(document, unused_signal, SemanticConfig(MAX_CONTENT_BYTES))
    assert spans(result) == [(0, len(text))]
    assert result.chunks[0].content == text
    assert result.chunks[0].provenance is document.provenance
    assert result.semantic_evidence == ()


def test_linear_scanner_preserves_original_boundary_rules() -> None:
    """Compare short exhaustive inputs against the original boundary specification."""
    specification = re.compile(r"(?:[.!?]+(?=\s|$)|\n[ \t]*\n)\s*")
    alphabet = ("a", ".", "!", "?", " ", "\t", "\n", "\r", "\u2003", "é")
    for length in range(5):
        for characters in itertools.product(alphabet, repeat=length):
            text = "".join(characters)
            expected = []
            start = 0
            for match in specification.finditer(text):
                expected.append((start, match.end()))
                start = match.end()
            if start < len(text):
                expected.append((start, len(text)))
            assert chunking._semantic_units(text) == expected
