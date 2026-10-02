"""Shared bounded inspection of JSON trees for parsing and schema validation."""

import json
import math

from ..contracts import JSONValue, ValidationLimits
from ..errors import JSONParsingError, ValidationLimitError


def inspect_json(value: JSONValue, limits: ValidationLimits) -> int:
    """Check plain JSON values iteratively and return their bounded node count.

    Args:
        value: A JSON tree to inspect without invoking custom object methods.
        limits: Resource budgets for the tree and serialized document.

    Returns:
        Number of value nodes, including container nodes.

    Raises:
        JSONParsingError: For non-JSON types, cycles, non-string keys, or NaN.
        ValidationLimitError: If tree size, depth, or UTF-8 size is excessive.
    """
    pending = [(value, 0, frozenset())]
    count = 0
    text_units = 0
    while pending:
        item, depth, ancestors = pending.pop()
        count += 1
        if count > limits.max_nodes:
            raise ValidationLimitError(
                "JSON node budget exceeded; reduce document size."
            )
        if type(item) in (dict, list):
            depth += 1
            if depth > limits.max_depth:
                raise ValidationLimitError(
                    "JSON depth budget exceeded; reduce nesting."
                )
            if id(item) in ancestors:
                raise JSONParsingError("Cyclic objects are not JSON documents.")
            ancestors = ancestors | {id(item)}
            if type(item) is dict:
                if any(type(key) is not str for key in item):
                    raise JSONParsingError("JSON object keys must be strings.")
                children = item.values()
                text_units += sum(len(key) for key in item)
            else:
                children = item
            if count + len(pending) + len(children) > limits.max_nodes:
                raise ValidationLimitError(
                    "JSON node budget exceeded; reduce document size."
                )
            pending.extend((child, depth, ancestors) for child in children)
        elif type(item) not in (str, int, float, bool, type(None)):
            raise JSONParsingError("Only plain JSON values are accepted.")
        elif type(item) is float and not math.isfinite(item):
            raise JSONParsingError("Non-finite numbers are not accepted in JSON.")
        elif type(item) is str:
            text_units += len(item)
        if text_units > limits.max_text_bytes:
            raise ValidationLimitError(
                "JSON byte budget exceeded; reduce document size."
            )
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
    except (UnicodeError, ValueError) as exc:
        raise JSONParsingError(
            "JSON cannot be represented as finite UTF-8 data."
        ) from exc
    if len(encoded) > limits.max_text_bytes:
        raise ValidationLimitError("JSON byte budget exceeded; reduce document size.")
    return count
