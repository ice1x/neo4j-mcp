"""MCP server exposing a project knowledge graph backed by Neo4j."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from neo4j_knowledge_mcp.graph import KnowledgeGraph

# ── Configuration ─────────────────────────────────────────────────────

_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
_NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "password")
_NEO4J_DB = os.getenv("NEO4J_DATABASE", "neo4j")

mcp = FastMCP(
    "neo4j-knowledge-graph",
    description=(
        "Knowledge Graph MCP — store and query project knowledge, "
        "domain models, and schema migrations in Neo4j."
    ),
)

kg = KnowledgeGraph(uri=_NEO4J_URI, username=_NEO4J_USER, password=_NEO4J_PASS, database=_NEO4J_DB)


def _json(obj: Any) -> str:
    """Serialise arbitrary Neo4j results to JSON."""
    def default(o: Any) -> Any:
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return str(o)
    return json.dumps(obj, indent=2, default=default, ensure_ascii=False)


# ── Lifecycle ─────────────────────────────────────────────────────────

@mcp.lifecycle("startup")
async def startup() -> None:
    await kg.connect()


@mcp.lifecycle("shutdown")
async def shutdown() -> None:
    await kg.close()


# ── Tools: Entities ───────────────────────────────────────────────────

@mcp.tool()
async def create_entity(
    name: str,
    entity_type: str,
    project: str,
    observations: list[str] | None = None,
    properties: dict[str, Any] | None = None,
) -> str:
    """Create or update a knowledge entity in the graph.

    Args:
        name: Unique name of the entity within the project.
        entity_type: Type label, e.g. "Service", "Model", "Decision", "Component".
        project: Project this entity belongs to.
        observations: Free-text observations about the entity.
        properties: Arbitrary key-value properties.
    """
    result = await kg.create_entity(name, entity_type, project, observations, properties)
    return _json(result)


@mcp.tool()
async def add_observations(name: str, project: str, observations: list[str]) -> str:
    """Append new observations to an existing entity.

    Args:
        name: Name of the entity.
        project: Project the entity belongs to.
        observations: New observations to add.
    """
    result = await kg.add_observations(name, project, observations)
    return _json(result)


@mcp.tool()
async def delete_entity(name: str, project: str) -> str:
    """Delete an entity and all its relationships.

    Args:
        name: Name of the entity.
        project: Project the entity belongs to.
    """
    deleted = await kg.delete_entity(name, project)
    return _json({"deleted": deleted})


# ── Tools: Relationships ─────────────────────────────────────────────

@mcp.tool()
async def create_relationship(
    from_entity: str,
    to_entity: str,
    relation_type: str,
    project: str,
    properties: dict[str, Any] | None = None,
) -> str:
    """Create a typed relationship between two entities.

    Args:
        from_entity: Source entity name.
        to_entity: Target entity name.
        relation_type: Relationship type, e.g. "DEPENDS_ON", "USES", "IMPLEMENTS".
        project: Project scope.
        properties: Optional relationship properties.
    """
    result = await kg.create_relationship(
        from_entity, to_entity, relation_type, project, properties
    )
    return _json(result)


@mcp.tool()
async def delete_relationship(
    from_entity: str, to_entity: str, relation_type: str, project: str
) -> str:
    """Delete a relationship between two entities.

    Args:
        from_entity: Source entity name.
        to_entity: Target entity name.
        relation_type: Relationship type.
        project: Project scope.
    """
    deleted = await kg.delete_relationship(from_entity, to_entity, relation_type, project)
    return _json({"deleted": deleted})


# ── Tools: Queries ────────────────────────────────────────────────────

@mcp.tool()
async def get_entity(name: str, project: str) -> str:
    """Get an entity with all its incoming and outgoing relationships.

    Useful as context for an LLM to understand a specific concept
    and how it relates to the rest of the project.

    Args:
        name: Entity name.
        project: Project scope.
    """
    result = await kg.get_entity(name, project)
    return _json(result)


@mcp.tool()
async def search_knowledge(query: str, project: str | None = None) -> str:
    """Search the knowledge graph by text (entity names and observations).

    Args:
        query: Text to search for (case-insensitive contains).
        project: Optional project filter.
    """
    results = await kg.search(query, project)
    return _json(results)


@mcp.tool()
async def get_project_graph(project: str) -> str:
    """Get the complete knowledge graph for a project.

    Returns all entities and relationships — useful as full project
    context for an LLM session.

    Args:
        project: Project name.
    """
    result = await kg.get_project_graph(project)
    return _json(result)


@mcp.tool()
async def list_projects() -> str:
    """List all projects stored in the knowledge graph."""
    projects = await kg.list_projects()
    return _json(projects)


# ── Tools: Migrations ────────────────────────────────────────────────

@mcp.tool()
async def add_migration(
    project: str,
    description: str,
    cypher_up: str,
    cypher_down: str | None = None,
    version: str | None = None,
) -> str:
    """Record a graph schema/data migration for a project.

    Migrations are stored as nodes so the full evolution history
    is preserved inside the knowledge graph itself.

    Args:
        project: Project name.
        description: Human-readable description of the migration.
        cypher_up: Cypher statement to apply the migration.
        cypher_down: Optional Cypher statement to revert.
        version: Optional version label (auto-incremented if omitted).
    """
    result = await kg.add_migration(project, description, cypher_up, cypher_down, version)
    return _json(result)


@mcp.tool()
async def get_migrations(project: str) -> str:
    """Get the full migration history for a project.

    Args:
        project: Project name.
    """
    results = await kg.get_migrations(project)
    return _json(results)


@mcp.tool()
async def apply_migration(project: str, seq: int) -> str:
    """Execute a pending migration and mark it as applied.

    Args:
        project: Project name.
        seq: Migration sequence number.
    """
    result = await kg.apply_migration(project, seq)
    return _json(result)


# ── Tools: Raw Cypher ─────────────────────────────────────────────────

@mcp.tool()
async def run_cypher(query: str, params: dict[str, Any] | None = None) -> str:
    """Execute a read-only Cypher query against the knowledge graph.

    For advanced exploration when the built-in tools are not enough.

    Args:
        query: Cypher query string.
        params: Optional query parameters.
    """
    results = await kg.run_cypher(query, params)
    return _json(results)


# ── Entrypoint ────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Neo4j Knowledge Graph MCP Server")
    parser.add_argument("--db-url", default=_NEO4J_URI, help="Neo4j connection URI")
    parser.add_argument("--username", default=_NEO4J_USER)
    parser.add_argument("--password", default=_NEO4J_PASS)
    parser.add_argument("--database", default=_NEO4J_DB)
    parser.add_argument(
        "--transport", default="stdio", choices=["stdio", "sse", "streamable-http"]
    )
    args = parser.parse_args()

    kg.uri = args.db_url
    kg.username = args.username
    kg.password = args.password
    kg.database = args.database

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
