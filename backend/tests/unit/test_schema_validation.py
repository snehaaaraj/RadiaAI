"""Unit tests for the dependency-free JSON Schema validator (app.services.mcp.schema_validation).

Schemas here are copied from real output observed from mcp-radia's tools/list
(Pydantic/Annotated-generated schemas), not hand-invented - the goal is
parity with what this module actually has to validate in production, not
general JSON Schema spec coverage.
"""

from __future__ import annotations

import pytest

from app.services.mcp.schema_validation import SchemaValidationError, validate

pytestmark = pytest.mark.unit

_JAMA_GET_ITEM_SCHEMA = {
    "properties": {
        "item_id": {
            "description": "Numeric Jama item id, e.g. 12345.",
            "exclusiveMinimum": 0,
            "title": "Item Id",
            "type": "integer",
        }
    },
    "required": ["item_id"],
    "type": "object",
    "title": "jama_get_itemArguments",
}

_JAMA_SEARCH_SCHEMA = {
    "properties": {
        "query": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None,
            "title": "Query",
        },
        "project_id": {
            "anyOf": [{"type": "integer"}, {"type": "null"}],
            "default": None,
            "title": "Project Id",
        },
        "start_at": {"default": 0, "minimum": 0, "title": "Start At", "type": "integer"},
        "max_results": {
            "default": 50,
            "maximum": 50,
            "minimum": 1,
            "title": "Max Results",
            "type": "integer",
        },
    },
    "type": "object",
    "title": "jama_searchArguments",
}

_LIST_RELATED_ITEMS_SCHEMA = {
    "properties": {
        "system": {
            "enum": ["jama", "jira", "confluence", "genesys"],
            "title": "System",
            "type": "string",
        },
        "item_id": {"minLength": 1, "title": "Item Id", "type": "string"},
        "include_text_references": {
            "default": False,
            "title": "Include Text References",
            "type": "boolean",
        },
    },
    "required": ["system", "item_id"],
    "type": "object",
    "title": "list_related_itemsArguments",
}


def test_valid_arguments_pass() -> None:
    validate({"item_id": 123}, _JAMA_GET_ITEM_SCHEMA)  # does not raise


def test_missing_required_property_is_rejected() -> None:
    with pytest.raises(SchemaValidationError, match="item_id"):
        validate({}, _JAMA_GET_ITEM_SCHEMA)


def test_wrong_type_is_rejected() -> None:
    with pytest.raises(SchemaValidationError):
        validate({"item_id": "not-a-number"}, _JAMA_GET_ITEM_SCHEMA)


def test_exclusive_minimum_is_enforced() -> None:
    with pytest.raises(SchemaValidationError):
        validate({"item_id": 0}, _JAMA_GET_ITEM_SCHEMA)


def test_boolean_is_rejected_for_integer_type() -> None:
    """bool is a subclass of int in Python - must not silently pass as an integer."""
    with pytest.raises(SchemaValidationError):
        validate({"item_id": True}, _JAMA_GET_ITEM_SCHEMA)


def test_any_of_accepts_either_branch() -> None:
    validate({"query": "battery"}, _JAMA_SEARCH_SCHEMA)
    validate({"query": None}, _JAMA_SEARCH_SCHEMA)
    validate({"project_id": 7}, _JAMA_SEARCH_SCHEMA)


def test_any_of_rejects_a_value_matching_no_branch() -> None:
    with pytest.raises(SchemaValidationError):
        validate({"query": 123}, _JAMA_SEARCH_SCHEMA)


def test_all_fields_optional_so_empty_arguments_are_valid() -> None:
    validate({}, _JAMA_SEARCH_SCHEMA)


def test_minimum_and_maximum_are_enforced() -> None:
    validate({"max_results": 50}, _JAMA_SEARCH_SCHEMA)
    with pytest.raises(SchemaValidationError):
        validate({"max_results": 51}, _JAMA_SEARCH_SCHEMA)
    with pytest.raises(SchemaValidationError):
        validate({"start_at": -1}, _JAMA_SEARCH_SCHEMA)


def test_enum_is_enforced() -> None:
    validate({"system": "jama", "item_id": "1"}, _LIST_RELATED_ITEMS_SCHEMA)
    with pytest.raises(SchemaValidationError):
        validate({"system": "not-a-real-system", "item_id": "1"}, _LIST_RELATED_ITEMS_SCHEMA)


def test_min_length_is_enforced() -> None:
    with pytest.raises(SchemaValidationError):
        validate({"system": "jama", "item_id": ""}, _LIST_RELATED_ITEMS_SCHEMA)


def test_boolean_field_accepts_only_booleans() -> None:
    validate(
        {"system": "jama", "item_id": "1", "include_text_references": True},
        _LIST_RELATED_ITEMS_SCHEMA,
    )
    with pytest.raises(SchemaValidationError):
        validate(
            {"system": "jama", "item_id": "1", "include_text_references": "yes"},
            _LIST_RELATED_ITEMS_SCHEMA,
        )


def test_empty_schema_accepts_anything() -> None:
    validate({"anything": "goes"}, {})


def test_malformed_schema_fails_safe_rather_than_crashing() -> None:
    """'required' must be a list; a string here would raise TypeError inside a bare 'in' check."""
    with pytest.raises(SchemaValidationError, match="malformed"):
        validate(
            {"item_id": 1},
            {"type": "object", "properties": {"item_id": {"type": "integer"}}, "required": 5},
        )
