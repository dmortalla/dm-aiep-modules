"""Contract tests for the source-faithful Postman collection."""

import json
from pathlib import Path

COLLECTION_PATH = (
    Path(__file__).parents[1]
    / "postman"
    / "module-01-rest-api-foundations.postman_collection.json"
)


def load_collection() -> dict:
    """Load the committed Postman collection."""
    return json.loads(COLLECTION_PATH.read_text(encoding="utf-8"))


def test_postman_collection_is_valid_json() -> None:
    """The Postman artifact should remain parseable JSON."""
    collection = load_collection()

    assert collection["info"]["name"] == "Module 1 - REST API Foundations"
    assert "v2.1.0" in collection["info"]["schema"]


def test_postman_collection_demonstrates_get_and_post() -> None:
    """The lab should demonstrate core REST HTTP methods."""
    collection = load_collection()
    methods = {item["request"]["method"] for item in collection["item"]}

    assert {"GET", "POST"} <= methods


def test_postman_collection_demonstrates_authentication() -> None:
    """The lab should demonstrate bearer authentication without a real secret."""
    collection = load_collection()
    serialized = json.dumps(collection)

    assert "Authorization" in serialized
    assert "Bearer {{api_key}}" in serialized

    variables = {
        variable["key"]: variable["value"]
        for variable in collection["variable"]
    }

    assert variables["api_key"] == ""


def test_postman_collection_contains_response_test() -> None:
    """The collection should demonstrate Postman response validation."""
    collection = load_collection()
    serialized = json.dumps(collection)

    assert 'pm.response.to.have.status(200)' in serialized