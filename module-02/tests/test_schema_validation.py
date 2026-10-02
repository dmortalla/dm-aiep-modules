"""Bounded Draft 2020-12 enforcement, local references, and safe errors."""

import socket
import traceback
from typing import NoReturn

import pytest
from jsonschema import Draft202012Validator
from prompt_engineering_systems.contracts import (
    JSONValue,
    StrictContract,
    ValidationLimits,
)
from prompt_engineering_systems.errors import (
    JSONParsingError,
    SchemaDefinitionError,
    SchemaValidationError,
    UnsupportedSchemaError,
    ValidationLimitError,
)
from prompt_engineering_systems.structured.models import StructuredAnswer
from prompt_engineering_systems.structured.schemas import (
    DRAFT_2020_12,
    Schema,
    schema_for_model,
    validate_against_schema,
)
from pydantic import ConfigDict


def test_generated_schema_exposes_nested_strict_contracts() -> None:
    """Pydantic schemas must declare dialect, bounds, required fields, and extras."""
    schema = schema_for_model(StructuredAnswer)
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == DRAFT_2020_12
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["answer"]
    assert schema["properties"]["answer"]["maxLength"] == 8_192
    assert schema["$defs"]["SourceReference"]["additionalProperties"] is False
    validate_against_schema(
        {"answer": "ok", "sources": [{"source_id": "s", "excerpt": "fact"}]}, schema
    )
    schema["required"].clear()
    assert schema_for_model(StructuredAnswer)["required"] == ["answer"]


@pytest.mark.parametrize(
    ("schema", "instance"),
    [
        ({"type": "integer", "minimum": 1, "maximum": 5}, 3),
        ({"type": "string", "enum": ["a", "b"]}, "a"),
        ({"const": {"x": 1}}, {"x": 1}),
        ({"anyOf": [{"type": "string"}, {"type": "null"}]}, None),
        ({"allOf": [{"type": "integer"}, {"exclusiveMinimum": 0}]}, 2),
        ({"oneOf": [{"const": "a"}, {"const": "b"}]}, "b"),
        ({"not": {"const": 0}}, 1),
        ({"type": "array", "prefixItems": [{"type": "string"}], "items": False}, ["a"]),
        (True, {"any": "JSON"}),
        (
            {"const": {"$ref": "https://example.invalid/inert-data"}},
            {"$ref": "https://example.invalid/inert-data"},
        ),
    ],
)
def test_supported_schema_behavior(schema: Schema, instance: JSONValue) -> None:
    """Validate actual supported constraints, including references as inert data.

    Args:
        schema: Supported bounded schema.
        instance: Matching JSON instance.
    """
    validate_against_schema(instance, schema)


def test_local_reference_pointer_escaping_and_no_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Escaped local definition names must resolve without socket access.

    Args:
        monkeypatch: Fixture replacing network connection attempts.
    """

    def reject_network(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("Schema validation attempted network access.")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    schema = {"$defs": {"a/b~c": {"type": "string"}}, "$ref": "#/$defs/a~1b~0c"}
    validate_against_schema("ok", schema)


@pytest.mark.parametrize(
    "schema",
    [
        {"$ref": "https://example.invalid/schema"},
        {"$ref": "file:///private/schema.json"},
        {"$ref": "other.json#/$defs/X"},
        {"$ref": "#"},
        {"$ref": "#/$defs/X/properties/value"},
        {"$ref": "#/$defs/a%20b"},
        {"$ref": "#/$defs/a~2b"},
        {"$id": "https://example.invalid/base"},
        {"$anchor": "node"},
        {"$dynamicRef": "#node"},
        {"pattern": "(a+)+$"},
        {"format": "uri"},
        {"uniqueItems": True},
        {"unknownKeyword": True},
        {"$schema": "http://json-schema.org/draft-07/schema#"},
        {"properties": {"x": {"$ref": "https://example.invalid/nested"}}},
        {"$defs": {"unused": {"$ref": "https://example.invalid/unused"}}},
    ],
)
def test_unsupported_schema_behavior_is_rejected(schema: Schema) -> None:
    """Unsafe constructs must fail before any schema instance is accepted.

    Args:
        schema: Unsupported or unsafe schema.
    """
    with pytest.raises(UnsupportedSchemaError):
        validate_against_schema({}, schema)


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "not-a-type"},
        {"required": "answer"},
        {"minLength": -1},
        {"properties": []},
        {"allOf": {}},
        {"items": 3},
        {"$ref": 1},
        {"$ref": "#/$defs/missing"},
    ],
)
def test_invalid_schema_definition_is_distinct_from_instance_failure(
    schema: Schema,
) -> None:
    """Malformed keyword values and missing definitions are authoring errors.

    Args:
        schema: Invalid schema definition.
    """
    with pytest.raises(SchemaDefinitionError):
        validate_against_schema({}, schema)


@pytest.mark.parametrize(
    "schema",
    [
        {"$defs": {"A": {"$ref": "#/$defs/A"}}, "$ref": "#/$defs/A"},
        {"$defs": {"A": {"$ref": "#/$defs/B"}, "B": {"$ref": "#/$defs/A"}}},
    ],
)
def test_recursive_reference_graphs_are_rejected(schema: Schema) -> None:
    """Reject both used self-recursion and unused mutual recursion.

    Args:
        schema: Cyclic local definition graph.
    """
    with pytest.raises(UnsupportedSchemaError):
        validate_against_schema({}, schema)


def test_schema_instance_failure_has_safe_constraint_diagnostics() -> None:
    """Domain diagnostics retain the constraint without exposing rejected content."""
    schema = {"type": "integer"}
    instance = "PRIVATE_CANARY"
    with pytest.raises(SchemaValidationError) as caught:
        validate_against_schema(instance, schema)
    assert "type" in str(caught.value)
    assert caught.value.__cause__ is None
    assert "PRIVATE_CANARY" not in "".join(traceback.format_exception(caught.value))


def test_schema_definition_failure_suppresses_sensitive_library_context() -> None:
    """Schema errors stay actionable without rendering raw library diagnostics."""
    schema = {"type": "PRIVATE_CANARY"}
    with pytest.raises(SchemaDefinitionError) as caught:
        validate_against_schema({}, schema)
    assert "keyword types" in str(caught.value)
    assert caught.value.__cause__ is None
    assert "PRIVATE_CANARY" not in "".join(traceback.format_exception(caught.value))


def test_boolean_false_schema_rejects_any_instance() -> None:
    """A false schema is supported and must always reject its instance."""
    with pytest.raises(SchemaValidationError):
        validate_against_schema(None, False)


def test_schema_instance_work_product_is_bounded() -> None:
    """Large combinations must fail before unbounded validator evaluation."""
    with pytest.raises(ValidationLimitError):
        validate_against_schema(
            [1] * 10,
            {"items": {"type": "integer"}},
            limits=ValidationLimits(max_validation_work=10),
        )


def test_reference_expansion_is_bounded_without_recursion() -> None:
    """An acyclic exponentially branching reference graph still needs a budget."""
    definitions = {"D0": {"type": "integer"}}
    for index in range(1, 12):
        definitions[f"D{index}"] = {"allOf": [{"$ref": f"#/$defs/D{index - 1}"}] * 2}
    schema = {"$defs": definitions, "$ref": "#/$defs/D11"}
    with pytest.raises(ValidationLimitError):
        validate_against_schema(
            1, schema, limits=ValidationLimits(max_validation_work=100)
        )


def test_non_json_schema_objects_and_cyclic_instances_are_rejected() -> None:
    """Native object graphs must not invoke custom resolution or loop forever."""
    with pytest.raises(JSONParsingError):
        validate_against_schema(object(), True)
    instance: list[JSONValue] = []
    instance.append(instance)
    with pytest.raises(JSONParsingError):
        validate_against_schema(instance, True)


@pytest.mark.parametrize("instance", [float("nan"), float("inf"), float("-inf")])
def test_programmatic_instances_cannot_bypass_finite_json_policy(
    instance: float,
) -> None:
    """The schema-only entry point must enforce finite JSON even without parsing.

    Args:
        instance: Non-finite programmatic value.
    """
    with pytest.raises(JSONParsingError):
        validate_against_schema(instance, True)


def test_remote_references_are_rejected_without_dns_or_socket_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An external reference must be rejected locally even with networking denied.

    Args:
        monkeypatch: Fixture blocking DNS and socket connection attempts.
    """

    def reject_network(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("Remote reference attempted network access.")

    monkeypatch.setattr(socket, "getaddrinfo", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)
    with pytest.raises(UnsupportedSchemaError):
        validate_against_schema({}, {"$ref": "https://example.invalid/schema"})


@pytest.mark.parametrize("schema", [None, [], "PRIVATE_CANARY", object()])
def test_invalid_schema_roots_have_a_domain_failure(schema: object) -> None:
    """Root misuse must be classified as a schema authoring error.

    Args:
        schema: Invalid public schema argument.
    """
    with pytest.raises(SchemaDefinitionError, match="plain JSON object or boolean"):
        validate_against_schema({}, schema)


def test_model_without_json_schema_support_has_a_domain_failure() -> None:
    """Pydantic's expected unsupported-field failure is translated safely."""

    class OpaqueValue:
        """A trusted application type without a JSON Schema representation."""

    class UnsupportedContract(StrictContract):
        """A valid Pydantic contract whose field cannot generate JSON Schema."""

        model_config = ConfigDict(arbitrary_types_allowed=True)
        value: OpaqueValue

    with pytest.raises(UnsupportedSchemaError, match="represented as JSON Schema"):
        schema_for_model(UnsupportedContract)


def test_non_json_schema_content_is_a_schema_authoring_failure() -> None:
    """A non-finite schema value is distinguished from invalid instance JSON."""
    with pytest.raises(SchemaDefinitionError, match="finite, acyclic JSON"):
        validate_against_schema({}, {"const": float("nan")})


def test_unexpected_schema_generation_defect_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Schema-generation programmer defects must not become schema input errors.

    Args:
        monkeypatch: Fixture injecting an unexpected generation TypeError.
    """
    defect = TypeError("Unexpected schema generation defect.")

    def broken_generator(*args: object, **kwargs: object) -> None:
        raise defect

    monkeypatch.setattr(StructuredAnswer, "model_json_schema", broken_generator)
    with pytest.raises(TypeError) as caught:
        schema_for_model(StructuredAnswer)
    assert caught.value is defect
