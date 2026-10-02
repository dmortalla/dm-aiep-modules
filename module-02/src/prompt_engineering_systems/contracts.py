"""Shared strict model policy, JSON types, and bounded-validation budgets."""

from pydantic import BaseModel, ConfigDict, Field

type JSONValue = (
    None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]
)


class StrictContract(BaseModel):
    """Application-owned contract rejecting coercion, extra fields, and NaN.

    Pydantic hides input values in error text, but field paths and internal error
    context can still contain rejected content. Render domain errors from the
    validation pipeline instead of exposing direct Pydantic failures.
    Assignment is revalidated, but
    containers remain mutable: validation establishes a boundary-time contract,
    not permission to perform actions or an immutable object guarantee.

    Raises:
        ValidationError: If direct construction or assignment violates fields
            or model invariants. These are native Pydantic errors.
    """

    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        allow_inf_nan=False,
        hide_input_in_errors=True,
        validate_default=True,
        validate_assignment=True,
        revalidate_instances="always",
    )


class ValidationLimits(StrictContract):
    """Resource budgets for a small instructional structured-output document.

    Defaults allow 64 KiB of UTF-8 text, 32 container levels, 2,048 JSON nodes,
    and 100,000 schema-node/instance-node work units. These bound memory,
    parser/validator recursion, and repeated schema branch/reference evaluation.
    Higher budgets can be explicitly selected within the hard ceilings below;
    this layer is not an unrestricted large-document schema service.

    Attributes:
        max_text_bytes: UTF-8 document ceiling; default 65,536, maximum 1,048,576.
        max_depth: Container/expanded-schema depth; default 32, maximum 64.
        max_nodes: JSON value-node ceiling; default 2,048, maximum 10,000.
        max_validation_work: Estimated schema/instance work ceiling; default
            100,000, maximum 1,000,000. This is not a measured time limit.

    Raises:
        ValidationError: If a budget is nonpositive, exceeds its hard ceiling,
            has the wrong type, or includes an unknown field.
    """

    max_text_bytes: int = Field(default=65_536, ge=1, le=1_048_576)
    max_depth: int = Field(default=32, ge=1, le=64)
    max_nodes: int = Field(default=2_048, ge=1, le=10_000)
    max_validation_work: int = Field(default=100_000, ge=1, le=1_000_000)
