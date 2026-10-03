"""Offline contracts, deterministic embeddings, and numerical failure evidence."""

import math
import subprocess
import sys
import traceback
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from rag_engineering_foundations.embeddings import (
    EmbeddingBatch,
    LocalHashEmbedder,
    validate_texts,
)
from rag_engineering_foundations.errors import EmbeddingError, VectorError
from rag_engineering_foundations.vectors import (
    Vector,
    cosine_similarity,
    dot_product,
    euclidean_distance,
)


@pytest.mark.parametrize(
    "values",
    [
        (),
        [],
        (True,),
        ("secret",),
        (None,),
        (float("nan"),),
        (float("inf"),),
        (-float("inf"),),
        (10**400,),
        (0.0,) * 16_385,
    ],
)
def test_reject_malformed_vectors(values: object) -> None:
    """Reject coercion, empty input, bool, nonfinite data, and excessive dimensions."""
    with pytest.raises(VectorError):
        Vector(values)


def test_vector_is_immutable_finite_value_and_has_safe_repr() -> None:
    """Normalize valid ints without exposing coordinate payloads in representations."""
    vector = Vector((1234567, -0.5))
    assert vector.values == (1234567.0, -0.5)
    assert vector.dimension == 2
    assert vector == Vector((1234567.0, -0.5))
    assert "1234567" not in repr(vector)
    with pytest.raises(FrozenInstanceError):
        vector.values = (0.0,)


@pytest.mark.parametrize("dimension", [0, -1, True, "3", None, 1.0, 16_385])
def test_reject_invalid_embedding_dimensions(dimension: object) -> None:
    """Local and batch construction share the strict vector dimension policy."""
    with pytest.raises(EmbeddingError):
        LocalHashEmbedder(dimension)
    with pytest.raises(EmbeddingError):
        EmbeddingBatch((Vector((1.0,)),), dimension)


@pytest.mark.parametrize(
    "vectors", [(), [], ("raw",), (Vector((1.0,)),) * 65, (Vector((1.0, 2.0)),)]
)
def test_reject_invalid_batch_vectors(vectors: object) -> None:
    """Validate immutable batch shape and reject dimension mismatch."""
    with pytest.raises(EmbeddingError):
        EmbeddingBatch(vectors, 1)


@pytest.mark.parametrize(
    "texts",
    [
        (),
        [],
        (1,),
        (True,),
        ("",),
        (" \n",),
        ("\ud800",),
        ("a",) * 65,
        ("a" * 32_769,),
        ("é" * 16_385,),
        ("a" * 32_768,) * 33,
    ],
)
def test_reject_invalid_text_batches(texts: object) -> None:
    """Reject malformed and oversized input without retaining raw text in errors."""
    with pytest.raises(EmbeddingError):
        LocalHashEmbedder().embed(texts)


def test_exact_text_and_batch_byte_limits() -> None:
    """Accept valid UTF-8 limits without silently switching units to characters."""
    validate_texts(("é" * 16_384,))
    validate_texts(("a" * 32_768,) * 32)


def test_local_embedder_is_deterministic_ordered_and_not_fixture_lookup() -> None:
    """Generate novel lexical features, preserve repeats/order, and fix dimensions."""
    embedder = LocalHashEmbedder(128)
    texts = (
        "apple pear",
        "rocket orbit",
        "novel_generated_identifier_947",
        "apple pear",
    )
    batch = embedder.embed(texts)
    assert batch == embedder.embed(texts)
    assert batch.dimension == 128
    assert batch.vectors[0] == batch.vectors[3]
    assert batch.vectors[0] != batch.vectors[1]
    assert tuple(embedder.embed((text,)).vectors[0] for text in texts) == batch.vectors
    for vector in batch.vectors:
        assert vector.dimension == 128
        assert all(math.isfinite(value) for value in vector.values)
        assert math.hypot(*vector.values) == pytest.approx(1)
    assert embedder.embed(("APPLE PEAR",)) == embedder.embed(("apple pear",))
    assert math.hypot(*embedder.embed(("!!!",)).vectors[0].values) == pytest.approx(1)
    with pytest.raises(FrozenInstanceError):
        batch.vectors = ()
    with pytest.raises(FrozenInstanceError):
        embedder.dimension = 2


def test_local_repr_and_errors_do_not_expose_source() -> None:
    """Do not retain input text or display it in representation/error chains."""
    secret = "private-source-marker"
    batch = LocalHashEmbedder().embed((secret,))
    assert secret not in repr(batch)
    with pytest.raises(EmbeddingError) as caught:
        LocalHashEmbedder().embed((secret + "\ud800",))
    assert secret not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize(
    ("a", "b", "cosine", "dot", "distance"),
    [
        ((1, 0), (1, 0), 1, 1, 0),
        ((1, 0), (0, 1), 0, 0, math.sqrt(2)),
        ((1, 0), (-1, 0), -1, -1, 2),
        ((1, 2), (3, 4), 11 / math.sqrt(125), 11, math.sqrt(8)),
        ((3, 0), (6, 0), 1, 18, 3),
    ],
)
def test_known_metrics_and_symmetry(a, b, cosine, dot, distance) -> None:
    """Compare independently calculated examples in both argument orders."""
    left, right = Vector(a), Vector(b)
    for function, expected in [
        (cosine_similarity, cosine),
        (dot_product, dot),
        (euclidean_distance, distance),
    ]:
        assert function(left, right) == pytest.approx(expected)
        assert function(right, left) == pytest.approx(expected)


def test_zero_vector_semantics() -> None:
    """Cosine rejects either zero vector; dot/distance retain mathematical behavior."""
    zero, unit = Vector((0, 0)), Vector((1, 0))
    for pair in [(zero, unit), (unit, zero), (zero, zero)]:
        with pytest.raises(VectorError, match="zero"):
            cosine_similarity(*pair)
    assert dot_product(zero, unit) == 0
    assert euclidean_distance(zero, unit) == 1


@pytest.mark.parametrize(
    "function", [cosine_similarity, dot_product, euclidean_distance]
)
def test_metrics_reject_bad_inputs_and_dimension_mismatch(function) -> None:
    """Never truncate coordinate pairs or accept unvalidated containers."""
    with pytest.raises(VectorError):
        function(Vector((1,)), Vector((1, 2)))
    with pytest.raises(VectorError):
        function((1, 0), Vector((1, 0)))


def test_numerical_extremes_and_content_safe_overflow() -> None:
    """Stable cosine handles huge/subnormal norms; unrepresentable metrics fail."""
    for value in (1e308, 5e-324):
        vector = Vector((value, value))
        assert cosine_similarity(vector, vector) == pytest.approx(1)
    with pytest.raises(VectorError):
        dot_product(Vector((1e308,)), Vector((1e308,)))
    with pytest.raises(VectorError) as caught:
        dot_product(Vector((1e308, 1e308)), Vector((1, 1)))
    assert isinstance(caught.value.__cause__, OverflowError)
    with pytest.raises(VectorError):
        euclidean_distance(Vector((1e308,)), Vector((-1e308,)))


def test_offline_imports_and_example(tmp_path: Path) -> None:
    """Installed local modules work without provider/UI/store SDKs or credentials."""
    script = (
        "import sys; "
        "from rag_engineering_foundations.embeddings import LocalHashEmbedder; "
        "LocalHashEmbedder().embed(('novel words',)); "
        "assert not set(sys.modules) & "
        "{'openai','faiss','chromadb','pinecone','langchain','streamlit'}"
    )
    subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    example = Path(__file__).resolve().parents[1] / "examples/embedding_metrics.py"
    result = subprocess.run(
        [sys.executable, "-I", str(example)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert "Repeated execution identical: True" in result.stdout
    assert "Dimension: 64" in result.stdout
    assert "cosine=" in result.stdout and "distance=" in result.stdout
