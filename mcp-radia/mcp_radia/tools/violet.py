"""Read-only Violet tools backed by the remote MCP connector."""

import json
import time
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from mcp_radia.connectors.violet import VioletMCPClient
from mcp_radia.logging import get_logger
from mcp_radia.tools._guard import READ_ONLY, guard

logger = get_logger(__name__)


async def _call(
    client: VioletMCPClient,
    tool_name: str,
    remote_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = await guard(tool_name, lambda: client.call_tool(remote_name, arguments))
    except ToolError as exc:
        logger.info(
            "violet_tool_call_complete",
            tool=tool_name,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            success=False,
            error_type=type(exc).__name__,
        )
        raise
    logger.info(
        "violet_tool_call_complete",
        tool=tool_name,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
        success=True,
    )
    return result


def register_violet_tools(server: MCPServer, client: VioletMCPClient) -> list[str]:
    """Register the curated, read-only Violet tools."""

    @server.tool(
        name="violet_get_instructions",
        title="Get Violet query instructions",
        description=(
            "Return Violet's query guidance for interpreting Violet data and building "
            "structured Explore queries. This tool is read-only."
        ),
        annotations=READ_ONLY,
    )
    async def violet_get_instructions() -> dict[str, Any]:
        return await _call(client, "violet_get_instructions", "getInstructions", {})

    @server.tool(
        name="violet_explore_entities",
        title="Search Violet entities",
        description=(
            "Search accessible Violet entities using structured filters. Use "
            "violet_get_instructions first for query syntax and violet_get_explore_column_values "
            "when a set filter needs canonical values. Read-only."
        ),
        annotations=READ_ONLY,
    )
    async def violet_explore_entities(
        keyword: Annotated[
            str | None, Field(default=None, description="Optional text search.")
        ] = None,
        filter_model: Annotated[
            dict[str, Any] | None,
            Field(default=None, description="Violet Explore filter model, keyed by column id."),
        ] = None,
        sort: Annotated[
            list[dict[str, Any]] | None,
            Field(default=None, description="Sort specs, each with a field and asc/desc order."),
        ] = None,
        page: Annotated[int, Field(default=1, ge=1, description="One-based result page.")] = 1,
        limit: Annotated[int, Field(default=100, ge=1, le=1000, description="Page size.")] = 100,
        include_parameters: Annotated[
            bool, Field(default=False, description="Include entity parameters.")
        ] = False,
        include_sub_entities: Annotated[
            bool, Field(default=False, description="Include sub-entities.")
        ] = False,
        include_schemas: Annotated[
            bool, Field(default=False, description="Include entity schemas.")
        ] = False,
        is_count_query: Annotated[
            bool, Field(default=False, description="Optimize for a count-only query.")
        ] = False,
        aggregation_intent: Annotated[
            dict[str, Any] | None,
            Field(
                default=None, description="Optional sum or average aggregation over one property."
            ),
        ] = None,
    ) -> dict[str, Any]:
        arguments = {
            key: value
            for key, value in {
                "keyword": keyword,
                "filterModel": filter_model,
                "sort": sort,
                "page": page,
                "limit": limit,
                "includeParameters": include_parameters,
                "includeSubEntities": include_sub_entities,
                "includeSchemas": include_schemas,
                "isCountQuery": is_count_query,
                "aggregationIntent": aggregation_intent,
            }.items()
            if value is not None
        }
        return await _call(client, "violet_explore_entities", "exploreEntities", arguments)

    @server.tool(
        name="violet_get_explore_column_values",
        title="Get Violet filter values",
        description=(
            "Return distinct values for a Violet Explore column. Use these canonical values "
            "for set filters. Read-only."
        ),
        annotations=READ_ONLY,
    )
    async def violet_get_explore_column_values(
        column: Annotated[str, Field(description="Explore column/property id.", min_length=1)],
        size: Annotated[
            int | None, Field(default=None, ge=1, le=10000, description="Maximum values.")
        ] = None,
    ) -> dict[str, Any]:
        return await _call(
            client,
            "violet_get_explore_column_values",
            "getExploreColumnValues",
            {"column": column, **({"size": size} if size is not None else {})},
        )

    @server.tool(
        name="violet_get_schema_model",
        title="Get Violet data model",
        description=(
            "Inspect Violet's accessible entity schemas and property names. Use application "
            "and schema filters to keep results focused. Returns one bounded section, "
            "default entitySchemas. Follow next_offset until null before claiming a schema "
            "is absent. Use section=applications to discover application names. Read-only."
        ),
        annotations=READ_ONLY,
    )
    async def violet_get_schema_model(
        application: Annotated[
            str | None, Field(default=None, description="Application name.")
        ] = None,
        schema_name: Annotated[
            str | None, Field(default=None, description="Entity schema name filter.")
        ] = None,
        include_properties: Annotated[
            bool | None, Field(default=None, description="Include property names.")
        ] = None,
        section: Literal[
            "entitySchemas", "applications", "relationshipSpecifications", "allRelationshipTypes"
        ] = "entitySchemas",
        offset: Annotated[int, Field(default=0, ge=0, description="Section item offset.")] = 0,
        limit: Annotated[int, Field(default=5, ge=1, le=20, description="Maximum page items.")] = 5,
    ) -> dict[str, Any]:
        arguments = {
            key: value
            for key, value in {
                "application": application,
                "schemaName": schema_name,
                "includeProperties": include_properties,
            }.items()
            if value is not None
        }
        result = await _call(client, "violet_get_schema_model", "getSchemaModel", arguments)
        data = result.get("data")
        if not isinstance(data, dict) or not isinstance(data.get(section), list):
            raise ToolError(
                "Violet returned an unexpected schema section shape; no absence inferred."
            )
        entries = data[section]
        page: dict[str, Any] = {
            "section": section,
            "items": [],
            "total": len(entries),
            "offset": offset,
            "next_offset": None,
            "notice": "Only this section/page is shown. Follow next_offset until null.",
        }
        for entry in entries[offset : offset + limit]:
            candidate = {**page, "items": [*page["items"], entry]}
            # Leave room for pagination metadata within the normal chat context budget.
            if len(json.dumps(candidate, ensure_ascii=True)) > 4000:
                if not page["items"]:
                    raise ToolError(
                        "A Violet schema item exceeds the page budget. Retry with "
                        "include_properties=false and application/schema_name filters. "
                        "No absence can be inferred from this error."
                    )
                break
            page = candidate
        end = offset + len(page["items"])
        if end < len(entries):
            page["next_offset"] = end
        return page

    @server.tool(
        name="violet_get_relationship_model",
        title="Get Violet relationship types",
        description=(
            "Return relationship types and their entity-type examples for planning a "
            "Violet relationship query. Read-only."
        ),
        annotations=READ_ONLY,
    )
    async def violet_get_relationship_model(
        suggest_path: Annotated[
            str | None,
            Field(default=None, description="Comma-separated entity types for path suggestions."),
        ] = None,
    ) -> dict[str, Any]:
        arguments = {"suggestPath": suggest_path} if suggest_path is not None else {}
        return await _call(
            client, "violet_get_relationship_model", "getRelationshipModel", arguments
        )

    @server.tool(
        name="violet_get_entity_relationships",
        title="Get Violet entity relationships",
        description=(
            "Read the relationship graph for one Violet entity. Resolve the entity UUID first "
            "with Violet search tools; relationship type names come from "
            "violet_get_relationship_model."
        ),
        annotations=READ_ONLY,
    )
    async def violet_get_entity_relationships(
        source_id: Annotated[str, Field(description="Violet entity UUID.", min_length=1)],
        recursive_relationship_types: Annotated[
            str | None,
            Field(default=None, description="Comma-separated recursive relationship types."),
        ] = None,
        non_recursive_relationship_types: Annotated[
            str | None,
            Field(default=None, description="Comma-separated one-level relationship types."),
        ] = None,
    ) -> dict[str, Any]:
        arguments = {
            key: value
            for key, value in {
                "sourceId": source_id,
                "recursiveRelationshipTypes": recursive_relationship_types,
                "nonRecursiveRelationshipTypes": non_recursive_relationship_types,
            }.items()
            if value is not None
        }
        return await _call(
            client, "violet_get_entity_relationships", "getEntityRelationships", arguments
        )

    @server.tool(
        name="violet_get_entities_by_ids",
        title="Get Violet entity details",
        description=(
            "Read compact details for Violet entity UUIDs, typically returned in a relationship "
            "graph. Up to 100 UUIDs per call."
        ),
        annotations=READ_ONLY,
    )
    async def violet_get_entities_by_ids(
        ids: Annotated[
            list[str],
            Field(description="One to 100 Violet entity UUIDs.", min_length=1, max_length=100),
        ],
    ) -> dict[str, Any]:
        return await _call(
            client, "violet_get_entities_by_ids", "getVioletEntitiesByIds", {"ids": ids}
        )

    @server.tool(
        name="violet_list_programs",
        title="List Violet programs",
        description="List programs visible to the authenticated Violet user. Read-only.",
        annotations=READ_ONLY,
    )
    async def violet_list_programs() -> dict[str, Any]:
        return await _call(client, "violet_list_programs", "listPrograms", {})

    @server.tool(
        name="violet_list_requirements",
        title="List Violet requirements",
        description=(
            "List accessible Violet requirements in a program. Supports simple folder, status, "
            "name, and pagination filters. Use violet_get_requirement for full details."
        ),
        annotations=READ_ONLY,
    )
    async def violet_list_requirements(
        program_id: Annotated[str, Field(description="Violet program UUID.", min_length=1)],
        folder_id: Annotated[
            str | None, Field(default=None, description="Requirement folder UUID.")
        ] = None,
        status_id: Annotated[
            str | None, Field(default=None, description="Current-revision status UUID.")
        ] = None,
        name_contains: Annotated[
            str | None, Field(default=None, description="Case-insensitive name substring.")
        ] = None,
        limit: Annotated[int | None, Field(default=None, ge=1, le=2000)] = None,
        offset: Annotated[int | None, Field(default=None, ge=0)] = None,
    ) -> dict[str, Any]:
        arguments = {
            key: value
            for key, value in {
                "programId": program_id,
                "folderId": folder_id,
                "statusId": status_id,
                "nameContains": name_contains,
                "limit": limit,
                "offset": offset,
            }.items()
            if value is not None
        }
        return await _call(client, "violet_list_requirements", "listRequirements", arguments)

    @server.tool(
        name="violet_get_requirement",
        title="Get Violet requirement",
        description="Read full details and revision history for one Violet requirement UUID.",
        annotations=READ_ONLY,
    )
    async def violet_get_requirement(
        requirement_id: Annotated[str, Field(description="Violet requirement UUID.", min_length=1)],
    ) -> dict[str, Any]:
        return await _call(
            client, "violet_get_requirement", "getRequirement", {"id": requirement_id}
        )

    registered = [
        "violet_get_instructions",
        "violet_explore_entities",
        "violet_get_explore_column_values",
        "violet_get_schema_model",
        "violet_get_relationship_model",
        "violet_get_entity_relationships",
        "violet_get_entities_by_ids",
        "violet_list_programs",
        "violet_list_requirements",
        "violet_get_requirement",
    ]
    return registered
