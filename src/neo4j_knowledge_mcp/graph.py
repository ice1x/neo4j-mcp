"""Neo4j graph operations for the knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver


@dataclass
class KnowledgeGraph:
    """Manages knowledge graph operations against Neo4j."""

    uri: str
    username: str
    password: str
    database: str = "neo4j"
    _driver: AsyncDriver | None = field(default=None, repr=False)

    async def connect(self) -> None:
        self._driver = AsyncGraphDatabase.driver(self.uri, auth=(self.username, self.password))
        await self._driver.verify_connectivity()
        await self._ensure_indexes()

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()

    async def _ensure_indexes(self) -> None:
        """Create indexes for efficient lookups."""
        async with self._driver.session(database=self.database) as session:
            await session.run(
                "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)"
            )
            await session.run(
                "CREATE INDEX entity_project IF NOT EXISTS FOR (e:Entity) ON (e.project)"
            )
            await session.run(
                "CREATE INDEX migration_project IF NOT EXISTS "
                "FOR (m:Migration) ON (m.project)"
            )

    # ── Entities ──────────────────────────────────────────────────────

    async def create_entity(
        self,
        name: str,
        entity_type: str,
        project: str,
        observations: list[str] | None = None,
        properties: dict[str, Any] | None = None,
    ) -> dict:
        """Create or merge an entity node in the knowledge graph."""
        props = properties or {}
        obs = observations or []
        query = """
        MERGE (e:Entity {name: $name, project: $project})
        ON CREATE SET
            e.type = $entity_type,
            e.observations = $observations,
            e.created_at = datetime(),
            e.updated_at = datetime()
        ON MATCH SET
            e.type = $entity_type,
            e.observations = e.observations + $observations,
            e.updated_at = datetime()
        SET e += $properties
        RETURN e{.*, labels: labels(e)} AS entity
        """
        async with self._driver.session(database=self.database) as session:
            result = await session.run(
                query,
                name=name,
                project=project,
                entity_type=entity_type,
                observations=obs,
                properties=props,
            )
            record = await result.single()
            return record["entity"] if record else {}

    async def add_observations(
        self, name: str, project: str, observations: list[str]
    ) -> dict:
        """Append observations to an existing entity."""
        query = """
        MATCH (e:Entity {name: $name, project: $project})
        SET e.observations = e.observations + $observations,
            e.updated_at = datetime()
        RETURN e{.*, labels: labels(e)} AS entity
        """
        async with self._driver.session(database=self.database) as session:
            result = await session.run(
                query, name=name, project=project, observations=observations
            )
            record = await result.single()
            return record["entity"] if record else {}

    async def delete_entity(self, name: str, project: str) -> bool:
        """Delete an entity and all its relationships."""
        query = """
        MATCH (e:Entity {name: $name, project: $project})
        DETACH DELETE e
        RETURN count(e) AS deleted
        """
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, name=name, project=project)
            record = await result.single()
            return record["deleted"] > 0

    # ── Relationships ─────────────────────────────────────────────────

    async def create_relationship(
        self,
        from_entity: str,
        to_entity: str,
        relation_type: str,
        project: str,
        properties: dict[str, Any] | None = None,
    ) -> dict:
        """Create a typed relationship between two entities."""
        props = properties or {}
        # Cypher doesn't support parameterised relationship types,
        # so we sanitise and interpolate the type name.
        safe_type = "".join(c if c.isalnum() or c == "_" else "_" for c in relation_type.upper())
        query = f"""
        MATCH (a:Entity {{name: $from_name, project: $project}})
        MATCH (b:Entity {{name: $to_name, project: $project}})
        MERGE (a)-[r:{safe_type}]->(b)
        SET r += $properties, r.created_at = coalesce(r.created_at, datetime())
        RETURN type(r) AS type,
               a.name AS from, b.name AS to,
               properties(r) AS properties
        """
        async with self._driver.session(database=self.database) as session:
            result = await session.run(
                query,
                from_name=from_entity,
                to_name=to_entity,
                project=project,
                properties=props,
            )
            record = await result.single()
            if not record:
                return {}
            return dict(record)

    async def delete_relationship(
        self, from_entity: str, to_entity: str, relation_type: str, project: str
    ) -> bool:
        """Delete a specific relationship between two entities."""
        safe_type = "".join(c if c.isalnum() or c == "_" else "_" for c in relation_type.upper())
        query = f"""
        MATCH (a:Entity {{name: $from_name, project: $project}})
              -[r:{safe_type}]->
              (b:Entity {{name: $to_name, project: $project}})
        DELETE r
        RETURN count(r) AS deleted
        """
        async with self._driver.session(database=self.database) as session:
            result = await session.run(
                query, from_name=from_entity, to_name=to_entity, project=project
            )
            record = await result.single()
            return record["deleted"] > 0

    # ── Queries ───────────────────────────────────────────────────────

    async def get_entity(self, name: str, project: str) -> dict:
        """Get an entity with all its relationships (context for LLM)."""
        query = """
        MATCH (e:Entity {name: $name, project: $project})
        OPTIONAL MATCH (e)-[r]->(target:Entity)
        OPTIONAL MATCH (source:Entity)-[ri]->(e)
        WITH e,
             collect(DISTINCT {type: type(r), target: target.name, target_type: target.type}) AS outgoing,
             collect(DISTINCT {type: type(ri), source: source.name, source_type: source.type}) AS incoming
        RETURN e{.*, labels: labels(e)} AS entity,
               [x IN outgoing WHERE x.target IS NOT NULL] AS outgoing_relations,
               [x IN incoming WHERE x.source IS NOT NULL] AS incoming_relations
        """
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, name=name, project=project)
            record = await result.single()
            if not record:
                return {}
            return {
                "entity": record["entity"],
                "outgoing_relations": record["outgoing_relations"],
                "incoming_relations": record["incoming_relations"],
            }

    async def search(self, query_text: str, project: str | None = None) -> list[dict]:
        """Search entities by name or observations (case-insensitive contains)."""
        project_filter = "AND e.project = $project" if project else ""
        query = f"""
        MATCH (e:Entity)
        WHERE (e.name CONTAINS $query OR
               any(obs IN e.observations WHERE obs CONTAINS $query))
              {project_filter}
        RETURN e{{.*, labels: labels(e)}} AS entity
        ORDER BY e.updated_at DESC
        LIMIT 25
        """
        params: dict[str, Any] = {"query": query_text}
        if project:
            params["project"] = project
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, **params)
            return [record["entity"] async for record in result]

    async def get_project_graph(self, project: str) -> dict:
        """Get the full knowledge graph for a project."""
        query = """
        MATCH (e:Entity {project: $project})
        OPTIONAL MATCH (e)-[r]->(t:Entity {project: $project})
        RETURN collect(DISTINCT e{.name, .type, .observations}) AS entities,
               collect(DISTINCT {
                   from: e.name, to: t.name, type: type(r)
               }) AS relationships
        """
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, project=project)
            record = await result.single()
            rels = [r for r in record["relationships"] if r["to"] is not None]
            return {
                "project": project,
                "entities": record["entities"],
                "relationships": rels,
            }

    async def list_projects(self) -> list[str]:
        """List all projects in the knowledge graph."""
        query = """
        MATCH (e:Entity)
        RETURN DISTINCT e.project AS project
        ORDER BY project
        """
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query)
            return [record["project"] async for record in result]

    # ── Migrations ────────────────────────────────────────────────────

    async def add_migration(
        self,
        project: str,
        description: str,
        cypher_up: str,
        cypher_down: str | None = None,
        version: str | None = None,
    ) -> dict:
        """Record a schema/data migration for a project."""
        query = """
        MATCH (latest:Migration {project: $project})
        WITH max(latest.seq) AS max_seq
        WITH coalesce(max_seq, 0) + 1 AS next_seq
        CREATE (m:Migration {
            project: $project,
            seq: next_seq,
            version: coalesce($version, toString(next_seq)),
            description: $description,
            cypher_up: $cypher_up,
            cypher_down: $cypher_down,
            created_at: datetime(),
            applied: false
        })
        RETURN m{.*} AS migration
        """
        async with self._driver.session(database=self.database) as session:
            result = await session.run(
                query,
                project=project,
                description=description,
                cypher_up=cypher_up,
                cypher_down=cypher_down,
                version=version,
            )
            record = await result.single()
            return record["migration"] if record else {}

    async def get_migrations(self, project: str) -> list[dict]:
        """Get migration history for a project."""
        query = """
        MATCH (m:Migration {project: $project})
        RETURN m{.*} AS migration
        ORDER BY m.seq
        """
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, project=project)
            return [record["migration"] async for record in result]

    async def apply_migration(self, project: str, seq: int) -> dict:
        """Execute a migration's cypher_up and mark it as applied."""
        get_query = """
        MATCH (m:Migration {project: $project, seq: $seq, applied: false})
        RETURN m{.*} AS migration
        """
        async with self._driver.session(database=self.database) as session:
            result = await session.run(get_query, project=project, seq=seq)
            record = await result.single()
            if not record:
                return {"error": "Migration not found or already applied"}

            migration = record["migration"]
            # Execute the migration
            await session.run(migration["cypher_up"])
            # Mark as applied
            await session.run(
                "MATCH (m:Migration {project: $project, seq: $seq}) "
                "SET m.applied = true, m.applied_at = datetime()",
                project=project,
                seq=seq,
            )
            migration["applied"] = True
            return migration

    # ── Raw Cypher ────────────────────────────────────────────────────

    async def run_cypher(self, query: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Execute an arbitrary read-only Cypher query."""
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, **(params or {}))
            return [dict(record) async for record in result]
