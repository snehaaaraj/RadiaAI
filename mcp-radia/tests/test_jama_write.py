"""Confirmed writes through real MCP framing and a recording Jama transport."""

import copy
import json

import httpx2
import pytest

from mcp_radia.config import ServerSettings
from mcp_radia.connectors.jama import JamaCredentials
from mcp_radia.server import build_server
from mcp_radia.tools.jama_write import JamaWriteService
from tests.conftest import connected_client
from tests.jama_fixtures import ITEM_PAYLOAD, jama_settings, make_client

pytestmark = pytest.mark.unit


def fixture_client(
    *,
    patch_status=200,
    patch_message="Required safety field is missing.",
    required_fields=None,
):
    raw = copy.deepcopy(ITEM_PAYLOAD["data"])
    patches = []

    def respond(request):
        if request.method == "PATCH":
            patches.append(json.loads(request.content))
            if patch_status != 200:
                return httpx2.Response(
                    patch_status,
                    json={"meta": {"message": patch_message}},
                )
            for patch in patches[-1]:
                raw["fields"][patch["path"].removeprefix("/fields/")] = patch["value"]
            raw["modifiedDate"] = "2026-11-06T12:00:00.000+0000"
            return httpx2.Response(200, json={"meta": {"status": "OK"}})
        if "itemtypes" in request.url.path:
            return httpx2.Response(
                200,
                json={
                    "data": {
                        "fields": [
                            {
                                "name": "description",
                                "label": "Description",
                                "fieldType": "RICHTEXT",
                            },
                            next(
                                (
                                    field
                                    for field in (required_fields or [])
                                    if field["name"] == "customField123"
                                ),
                                {"name": "customField123", "label": "Custom label"},
                            ),
                            {"name": "missing$31", "label": "Missing field"},
                            {"name": "locked", "label": "Locked", "readOnly": True},
                        ]
                        + [
                            field
                            for field in (required_fields or [])
                            if field["name"] != "customField123"
                        ]
                    }
                },
            )
        return httpx2.Response(200, json={"data": raw})

    client, handler = make_client(jama_settings(), respond)
    return client, handler, raw, patches


async def test_prepare_does_not_write_and_confirm_changes_only_requested_fields():
    client, handler, raw, patches = fixture_client()
    untouched = raw["fields"]["customField123"]
    server = build_server(ServerSettings(_env_file=None, service_token="test"), jama_client=client)
    async with connected_client(server) as session:
        prepared = await session.call_tool(
            "jama_prepare_field_update",
            {"item_id": 12345, "fields": {"Description": "Text < &"}},
        )
        assert not prepared.is_error
        preview = prepared.structured_content
        assert preview["changes"][0]["before"] == ITEM_PAYLOAD["data"]["fields"]["description"]
        assert preview["changes"][0]["after"] == "<p>Text &lt; &amp;</p>"
        assert patches == []
        assert all(request.method == "GET" for request in handler.requests)
        denied = await session.call_tool(
            "jama_confirm_field_update",
            {
                "confirmation_token": preview["confirmation_token"],
                "confirmed": False,
            },
        )
        assert denied.is_error
        assert patches == []
        written = await session.call_tool(
            "jama_confirm_field_update",
            {
                "confirmation_token": preview["confirmation_token"],
                "confirmed": True,
            },
        )
        assert not written.is_error
        assert written.structured_content["status"] == "written"
        assert patches == [
            [
                {
                    "op": "replace",
                    "path": "/fields/description",
                    "value": "<p>Text &lt; &amp;</p>",
                }
            ]
        ]
        assert raw["fields"]["customField123"] == untouched
        assert handler.last_request.headers["content-type"] == "application/json"
        replay = await session.call_tool(
            "jama_confirm_field_update",
            {
                "confirmation_token": preview["confirmation_token"],
                "confirmed": True,
            },
        )
        assert replay.is_error
        assert len(patches) == 1


@pytest.mark.parametrize(
    "case", ["tampered", "expired", "other-account", "changed", "other-server"]
)
async def test_unsafe_confirmations_never_patch(case, monkeypatch):
    client, _, raw, patches = fixture_client()
    service = JamaWriteService(b"test")
    preview = await service.prepare(client, 12345, {"customField123": 5})
    token = preview.confirmation_token
    if case == "tampered":
        token += "x"
    elif case == "expired":
        monkeypatch.setattr("mcp_radia.tools.jama_write.time.time", lambda: preview.expires_at + 1)
    elif case == "other-account":
        client._credentials = JamaCredentials(client_id="other", client_secret="other")
    elif case == "changed":
        raw["fields"]["customField123"] = "changed"
    elif case == "other-server":
        service = JamaWriteService(b"other")
    with pytest.raises(ValueError):
        await service.confirm(client, token, True)
    assert patches == []


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"cybersecurity_requirement$67": False},
        {"Locked": 1},
        {"Description": 1},
        {"Description": "one", "description": "two"},
        {"Custom label": "x" * 13000},
    ],
)
async def test_unknown_readonly_duplicate_or_oversized_fields_never_write(fields):
    client, _, _, patches = fixture_client()
    with pytest.raises(ValueError):
        await JamaWriteService(b"test").prepare(client, 12345, fields)
    assert patches == []


async def test_add_missing_field_and_preserve_json_value_types():
    client, _, _, patches = fixture_client()
    service = JamaWriteService(b"test")
    preview = await service.prepare(client, 12345, {"Missing field": [1, True, None]})
    await service.confirm(client, preview.confirmation_token, True)
    assert patches == [[{"op": "add", "path": "/fields/missing$31", "value": [1, True, None]}]]


async def test_jama_required_field_errors_are_not_bypassed_or_retried():
    client, _, _, patches = fixture_client(patch_status=400)
    server = build_server(ServerSettings(_env_file=None, service_token="test"), jama_client=client)
    async with connected_client(server) as session:
        preview = await session.call_tool(
            "jama_prepare_field_update",
            {"item_id": 12345, "fields": {"description": "text"}},
        )
        result = await session.call_tool(
            "jama_confirm_field_update",
            {
                "confirmation_token": preview.structured_content["confirmation_token"],
                "confirmed": True,
            },
        )
    assert result.is_error
    assert "Required safety field is missing." in str(result.content)
    assert len(patches) == 1


@pytest.mark.parametrize(
    "message",
    [
        "You must set the following required fields. fields: safety_requirement$67, cybersecurity_requirement$67",
        "You must set the following required fields. fields: custom_required$31",
    ],
)
async def test_missing_mandatory_fields_explain_jama_policy_in_tool_error(message):
    client, _, _, patches = fixture_client(patch_status=400, patch_message=message)
    server = build_server(ServerSettings(_env_file=None, service_token="test"), jama_client=client)
    async with connected_client(server) as session:
        preview = await session.call_tool(
            "jama_prepare_field_update",
            {"item_id": 12345, "fields": {"description": "text"}},
        )
        result = await session.call_tool(
            "jama_confirm_field_update",
            {
                "confirmation_token": preview.structured_content["confirmation_token"],
                "confirmed": True,
            },
        )
    assert result.is_error
    error = " ".join(content.text for content in result.content if content.type == "text")
    assert "Jama rejected mandatory-field validation for:" in error
    assert message.split("fields: ", 1)[1] in error
    assert "I cannot rewrite this item because Jama's own mandatory-field policies" in error
    assert "No changes were written." in error
    assert "cannot bypass this policy or guess field values" in error
    assert len(patches) == 1


@pytest.mark.parametrize("flag", [False, True])
@pytest.mark.parametrize("release", [115, 0])
async def test_preserve_required_values_in_preview_and_confirmed_patch(flag, release):
    definitions = [
        {"name": name, "label": name, "required": True, "readOnly": False}
        for name in ("release", "derived_requirement$31", "safety_requirement$31")
    ] + [
        {"name": "missing_required", "required": True},
        {"name": "null_required", "required": True},
        {"name": "locked", "required": True, "readOnly": True},
    ]
    client, _, raw, patches = fixture_client(required_fields=definitions)
    values = {"release": release, "derived_requirement$31": flag, "safety_requirement$31": flag}
    raw["fields"].update(values | {"null_required": None, "locked": "read-only"})
    service = JamaWriteService(b"test")
    preview = await service.prepare(client, 12345, {"description": "New"})
    assert len(preview.changes) == 1
    assert {field.field: field.after for field in preview.preserved_fields} == values
    assert all(field.before == field.after for field in preview.preserved_fields)
    assert patches == []
    result = await service.confirm(client, preview.confirmation_token, True)
    assert result.fields == ["description"]
    assert patches[0][1:] == [
        {"op": "replace", "path": f"/fields/{name}", "value": value}
        for name, value in values.items()
    ]
    assert {name: raw["fields"][name] for name in values} == values
    assert raw["fields"]["null_required"] is None
    assert "missing_required" not in raw["fields"]


async def test_invalid_required_metadata_fails_before_patch():
    client, _, _, patches = fixture_client(required_fields=[{"name": "", "required": True}])
    with pytest.raises(ValueError, match="invalid required field name"):
        await JamaWriteService(b"test").prepare(client, 12345, {"description": "New"})
    assert patches == []


async def test_changed_preserved_checkbox_invalidates_confirmation():
    client, _, raw, patches = fixture_client(
        required_fields=[{"name": "safety_requirement$31", "required": True}]
    )
    raw["fields"]["safety_requirement$31"] = False
    service = JamaWriteService(b"test")
    preview = await service.prepare(client, 12345, {"description": "New"})
    raw["fields"]["safety_requirement$31"] = True
    with pytest.raises(ValueError, match="changed"):
        await service.confirm(client, preview.confirmation_token, True)
    assert patches == []


async def test_explicitly_requested_required_value_is_not_replaced_by_preserved_value():
    client, _, raw, patches = fixture_client(
        required_fields=[
            {"name": "customField123", "required": True},
        ]
    )
    service = JamaWriteService(b"test")
    preview = await service.prepare(client, 12345, {"customField123": False})
    assert preview.preserved_fields == []
    await service.confirm(client, preview.confirmation_token, True)
    assert patches == [[{"op": "replace", "path": "/fields/customField123", "value": False}]]
    assert raw["fields"]["customField123"] is False


@pytest.mark.parametrize(
    "status,message",
    [
        (400, "Invalid patch path."),
        (403, "You must set the following required fields. fields: required$31"),
        (500, "Internal server error."),
    ],
)
async def test_other_write_errors_are_not_mislabeled_as_missing_fields(status, message):
    from mcp_radia.connectors.errors import ConnectorError

    client, _, _, patches = fixture_client(patch_status=status, patch_message=message)
    with pytest.raises(ConnectorError) as error:
        await client.patch_fields(
            12345, [{"op": "replace", "path": "/fields/name", "value": "New"}]
        )
    assert "Jama rejected mandatory-field validation for:" not in str(error.value)
    assert error.value.status_code == status
    assert len(patches) == 1
