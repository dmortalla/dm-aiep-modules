"""Immutable finite vectors and standard-library metrics, without store SDKs."""

import math
from dataclasses import dataclass, field

from .errors import VectorError

MAX_DIMENSIONS = 16_384


def _dimension(value: int) -> None:
    if type(value) is not int or not 1 <= value <= MAX_DIMENSIONS:
        raise VectorError("Use an integer vector dimension from 1 to 16384.")


@dataclass(frozen=True, slots=True)
class Vector:
    """A nonempty immutable finite float vector; numeric values are hidden in repr.

    Args:
        values: Tuple of 1..16384 Python int/float values. Bool, coercion, and
            nonfinite values are rejected; valid integers are converted to float.

    Raises:
        VectorError: For malformed, nonfinite, or unrepresentable numeric values.
    """

    values: tuple[float, ...] = field(repr=False)

    def __post_init__(self) -> None:
        """Validate and copy numeric values into the immutable float contract."""
        if type(self.values) is not tuple:
            raise VectorError("Supply vector values as a nonempty numeric tuple.")
        _dimension(len(self.values))
        normalized = []
        for value in self.values:
            if type(value) not in (int, float):
                raise VectorError(
                    "Use finite int/float values; bool and coercion are unsupported."
                )
            try:
                number = float(value)
            except OverflowError:
                raise VectorError(
                    "Reduce vector values to finite float magnitudes."
                ) from None
            if not math.isfinite(number):
                raise VectorError("Replace NaN/infinity with finite vector values.")
            normalized.append(number)
        object.__setattr__(self, "values", tuple(normalized))

    @property
    def dimension(self) -> int:
        """Return the validated number of vector coordinates."""
        return len(self.values)


def _pair(left: Vector, right: Vector) -> None:
    if type(left) is not Vector or type(right) is not Vector:
        raise VectorError("Supply two validated Vector objects.")
    if left.dimension != right.dimension:
        raise VectorError("Use vectors with equal nonzero dimensions.")


def dot_product(left: Vector, right: Vector) -> float:
    """Compute sum(left[i] * right[i]); magnitude affects this unnormalized score.

    Args:
        left: Validated finite vector.
        right: Validated finite vector of the same dimension.

    Returns:
        Finite symmetric dot product; ordinary float rounding/underflow applies.

    Raises:
        VectorError: For wrong inputs, dimension mismatch, or numeric overflow.
    """
    _pair(left, right)
    products = []
    for a, b in zip(left.values, right.values, strict=True):
        product = a * b
        if not math.isfinite(product):
            raise VectorError("Reduce vector magnitudes; dot-product terms overflow.")
        products.append(product)
    try:
        return math.fsum(products)
    except OverflowError as exc:
        # fsum's fixed diagnostic has no vector or user payload; retain this cause.
        raise VectorError(
            "Reduce vector magnitudes; dot-product sum overflows."
        ) from exc


def cosine_similarity(left: Vector, right: Vector) -> float:
    """Compute the normalized dot product in [-1, 1], rejecting zero vectors.

    Scaled normalization avoids overflow/underflow of the vector norm. Final
    rounding outside [-1,1] is clamped to that mathematical range.

    Args:
        left: Validated finite nonzero vector.
        right: Validated finite nonzero vector of the same dimension.

    Returns:
        Symmetric direction similarity: 1 aligned, 0 orthogonal, -1 opposite.

    Raises:
        VectorError: For wrong inputs, mismatched dimensions, or a zero vector.
    """
    _pair(left, right)
    normalized = []
    for vector in (left, right):
        scale = max(abs(value) for value in vector.values)
        if scale == 0:
            raise VectorError(
                "Cosine is undefined for zero vectors; supply nonzero vectors."
            )
        scaled = tuple(value / scale for value in vector.values)
        norm = math.hypot(*scaled)
        normalized.append(tuple(value / norm for value in scaled))
    result = math.fsum(a * b for a, b in zip(*normalized, strict=True))
    return min(1.0, max(-1.0, result))


def euclidean_distance(left: Vector, right: Vector) -> float:
    """Compute sqrt(sum((left[i] - right[i])**2)), with stable norm arithmetic.

    Args:
        left: Validated finite vector.
        right: Validated finite vector of the same dimension.

    Returns:
        Finite symmetric nonnegative distance; identical vectors have distance 0.

    Raises:
        VectorError: For wrong inputs, mismatched dimensions, or distance overflow.
    """
    _pair(left, right)
    result = math.dist(left.values, right.values)
    if not math.isfinite(result):
        raise VectorError("Reduce vector magnitudes; Euclidean distance overflows.")
    return result
