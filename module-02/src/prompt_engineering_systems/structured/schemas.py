"""Bounded Draft 2020-12 enforcement with local, acyclic definitions only.

Supported keywords cover types, object properties, required/extra fields,
arrays, scalar/collection bounds, enums/constants, and logical combinations.
References must address a top-level $defs entry. Other drafts, resource IDs,
anchors, dynamic references, regex/format evaluation, uniqueItems, and unknown
keywords are rejected. Restricting these operations prevents remote retrieval,
uncontrolled recursive resolution, and regex/quadratic validation work.
"""

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError as JSONSchemaDefinitionError
from pydantic.errors import PydanticInvalidForJsonSchema

from ..contracts import JSONValue, StrictContract, ValidationLimits
from ..errors import (
    JSONParsingError,
    SchemaDefinitionError,
    SchemaValidationError,
    UnsupportedSchemaError,
    ValidationLimitError,
)
from ._bounds import inspect_json

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
type Schema = dict[str, JSONValue] | bool

_KEYWORDS = {
    "$schema",
    "$defs",
    "$ref",
    "$comment",
    "title",
    "description",
    "default",
    "examples",
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "prefixItems",
    "minItems",
    "maxItems",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "const",
    "enum",
    "allOf",
    "anyOf",
    "oneOf",
    "not",
    "minProperties",
    "maxProperties",
}


def _children(schema: Schema, *, include_definitions: bool) -> list[Schema]:
    """Enumerate only schema positions, keeping metadata/constant values inert."""
    if type(schema) is bool:
        return []
    if type(schema) is not dict:
        raise SchemaDefinitionError("Each schema must be an object or boolean.")
    if set(schema) - _KEYWORDS:
        raise UnsupportedSchemaError("Schema contains an unsupported keyword.")
    if "$schema" in schema and schema["$schema"] != DRAFT_2020_12:
        raise UnsupportedSchemaError("Only Draft 2020-12 schemas are supported.")
    children = []
    for name in ("properties", "$defs"):
        if name in schema:
            mapping = schema[name]
            if type(mapping) is not dict:
                raise SchemaDefinitionError(
                    "Schema property/definition maps must be objects."
                )
            if name != "$defs" or include_definitions:
                children.extend(mapping.values())
    for name in ("allOf", "anyOf", "oneOf", "prefixItems"):
        if name in schema:
            sequence = schema[name]
            if type(sequence) is not list:
                raise SchemaDefinitionError(
                    "Schema branch/item collections must be arrays."
                )
            children.extend(sequence)
    for name in ("additionalProperties", "items", "not"):
        if name in schema:
            children.append(schema[name])
    return children


def _reference_target(schema: Schema, document: Schema) -> Schema | None:
    """Resolve one escaped top-level definition without URI rebasing/retrieval."""
    if type(schema) is bool or "$ref" not in schema:
        return None
    reference = schema["$ref"]
    if type(reference) is not str:
        raise SchemaDefinitionError("A schema reference must be a string.")
    parts = reference.split("/")
    if len(parts) != 3 or parts[:2] != ["#", "$defs"] or "%" in reference:
        raise UnsupportedSchemaError(
            "References must target a local top-level $defs entry."
        )
    name = parts[2]
    if "~" in name.replace("~0", "").replace("~1", ""):
        raise UnsupportedSchemaError(
            "Local references must use valid JSON Pointer escaping."
        )
    name = name.replace("~1", "/").replace("~0", "~")
    definitions = document.get("$defs", {})
    if type(definitions) is not dict or name not in definitions:
        raise SchemaDefinitionError(
            "Local reference target is missing; define it in $defs."
        )
    return definitions[name]


def _prepare_schema(schema: Schema, limits: ValidationLimits) -> int:
    """Preflight all definitions and bound reference expansion before validation."""
    if type(schema) not in (dict, bool):
        raise SchemaDefinitionError("Schema must be a plain JSON object or boolean.")
    try:
        inspect_json(schema, limits)
    except JSONParsingError:
        raise SchemaDefinitionError(
            "Schema must contain only finite, acyclic JSON data."
        ) from None
    pending = [schema]
    nodes = []
    while pending:
        node = pending.pop()
        nodes.append(node)
        pending.extend(_children(node, include_definitions=True))

    memo: dict[int, tuple[int, int]] = {}

    def expand(node: Schema, active: frozenset[int]) -> tuple[int, int]:
        identity = id(node)
        if identity in active:
            raise UnsupportedSchemaError(
                "Recursive schema references are not supported."
            )
        if len(active) >= limits.max_depth:
            raise ValidationLimitError(
                "Expanded schema depth exceeds the validation budget."
            )
        if identity in memo:
            cost, height = memo[identity]
            if len(active) + height > limits.max_depth:
                raise ValidationLimitError(
                    "Expanded schema depth exceeds the validation budget."
                )
            return cost, height
        children = _children(node, include_definitions=False)
        target = _reference_target(node, schema)
        if target is not None:
            children.append(target)
        cost, height = 1, 1
        for child in children:
            child_cost, child_height = expand(child, active | {identity})
            cost += child_cost
            height = max(height, child_height + 1)
            if cost > limits.max_validation_work:
                raise ValidationLimitError(
                    "Expanded schema work exceeds the validation budget."
                )
        memo[identity] = cost, height
        return cost, height

    for node in nodes:
        expand(node, frozenset())
    try:
        Draft202012Validator.check_schema(schema)
    except JSONSchemaDefinitionError:
        # The library error embeds schema values; classification is the safe diagnostic.
        raise SchemaDefinitionError(
            "Invalid schema; check Draft 2020-12 keyword types."
        ) from None
    return memo[id(schema)][0]


def schema_for_model(
    contract: type[StrictContract], *, limits: ValidationLimits | None = None
) -> dict[str, JSONValue]:
    """Expose a checked Draft 2020-12 schema derived from an application model.

    Args:
        contract: Application-owned StrictContract subclass, not a model instance.
        limits: Optional explicit resource budgets.

    Returns:
        A fresh JSON Schema dictionary, including its dialect identifier.

    Raises:
        SchemaDefinitionError: If contract is not a StrictContract model class or
            the generated schema is malformed.
        UnsupportedSchemaError: If the model cannot produce JSON Schema or uses
            constructs outside the supported subset.
        ValidationLimitError: If the generated schema exceeds resource budgets.
    """
    if not isinstance(contract, type) or not issubclass(contract, StrictContract):
        raise SchemaDefinitionError("Contract must be a StrictContract model class.")
    try:
        schema = contract.model_json_schema()
    except PydanticInvalidForJsonSchema:
        raise UnsupportedSchemaError(
            "Model fields cannot be represented as JSON Schema."
        ) from None
    schema["$schema"] = DRAFT_2020_12
    _prepare_schema(schema, limits or ValidationLimits())
    return schema


def validate_against_schema(
    instance: JSONValue, schema: Schema, *, limits: ValidationLimits | None = None
) -> None:
    """Validate plain JSON against the supported, bounded schema subset.

    A match alone does not establish application trust; callers requiring an
    application object must also apply its strict typed contract.

    Args:
        instance: Parsed JSON value, still untrusted.
        schema: Draft 2020-12 object or boolean schema with local definitions.
        limits: Optional explicit resource budgets.

    Raises:
        SchemaDefinitionError: If schema is not a plain object/boolean, contains
            non-JSON data, or has invalid keyword values.
        UnsupportedSchemaError: If the schema violates the bounded local policy.
        SchemaValidationError: If the JSON instance does not match.
        JSONParsingError: If the instance tree contains non-JSON values.
        ValidationLimitError: If document or estimated validation work is excessive.
    """
    budgets = limits or ValidationLimits()
    instance_nodes = inspect_json(instance, budgets)
    schema_work = _prepare_schema(schema, budgets)
    if instance_nodes * schema_work > budgets.max_validation_work:
        raise ValidationLimitError(
            "Schema/instance work budget exceeded; simplify the documents."
        )
    # Every reference was preflighted as local/acyclic; URI rebasing is forbidden.
    error = next(Draft202012Validator(schema).iter_errors(instance), None)
    if error is not None:
        # Report a supported keyword only; paths and rejected values remain internal.
        constraint = error.validator if error.validator in _KEYWORDS else "constraint"
        raise SchemaValidationError(
            f"JSON fails schema {constraint}; correct fields or constraints."
        )
