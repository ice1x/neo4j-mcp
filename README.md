# neo4j-knowledge-mcp

A lightweight [MCP](https://modelcontextprotocol.io/) server that turns a Neo4j database into a **project knowledge graph** — a persistent, evolving context source for LLMs.

## Why Use a Knowledge Graph MCP?

- **Living documentation** — documentation is built incrementally as a graph from the first session, not bolted on at the end when it's already stale.
- **Persistent LLM memory** — the graph survives between sessions; every new chat starts with full project context instead of a blank slate.
- **Structured over flat** — entities and typed relationships capture architecture far better than free-text notes or scattered markdown files.
- **Migration history** — every structural change is a versioned Cypher migration, giving you a complete, replayable audit trail of how the project evolved.
- **Cross-tool reuse** — any MCP-compatible client (Claude Desktop, Claude Code, Cursor, custom agents) can read and write the same graph.
- **Onboarding in seconds** — new team members (or new LLM sessions) call `get_project_graph` and instantly see the full domain map with all relationships and decisions.

## Architecture

```
┌──────────────────────┐       MCP (stdio / http)       ┌────────────────────┐
│  Claude Desktop /    │◄───────────────────────────────►│  neo4j-knowledge-  │
│  Claude Code /       │   tools: create_entity,         │  mcp server        │
│  any MCP client      │   search_knowledge,             │                    │
└──────────────────────┘   get_project_graph, ...        └────────┬───────────┘
                                                                  │ Bolt
                                                                  ▼
                                                         ┌────────────────────┐
                                                         │     Neo4j          │
                                                         │  Knowledge Graph   │
                                                         └────────────────────┘
```

## Tools

| Tool | Description |
|---|---|
| `create_entity` | Create or update a knowledge entity (service, model, decision, etc.) |
| `add_observations` | Append observations to an existing entity |
| `delete_entity` | Remove an entity and its relationships |
| `create_relationship` | Connect two entities with a typed relationship |
| `delete_relationship` | Remove a specific relationship |
| `get_entity` | Get entity with all relationships |
| `search_knowledge` | Full-text search across entity names and observations |
| `get_project_graph` | Get the complete graph for a project |
| `list_projects` | List all projects in the knowledge graph |
| `add_migration` | Record a versioned graph migration |
| `get_migrations` | Get migration history for a project |
| `apply_migration` | Execute a pending migration |
| `run_cypher` | Run an arbitrary read-only Cypher query |

---

## Quick Start

### 1. Start Neo4j (Docker)

A ready-made Dockerfile with APOC plugin and tuned memory settings lives in `docker/`.

```bash
# Build & run in one step
./docker/start.sh
```

This will:
- build the image from `docker/Dockerfile` (Neo4j 5.18 + APOC)
- start a container named `neo4j-kg`
- expose the browser at `http://localhost:7474` and Bolt at `bolt://localhost:7687`
- persist data in `neo4j/kgdata`, logs in `neo4j/kglogs`, imports in `neo4j/kgimport`

Default credentials: `neo4j` / `password`.

<details>
<summary>What's inside the Dockerfile</summary>

```dockerfile
FROM neo4j:5.18

ENV NEO4J_AUTH=neo4j/password \
    NEO4J_dbms_memory_heap_initial__size=1G \
    NEO4J_dbms_memory_heap_max__size=1G \
    NEO4J_dbms_memory_pagecache_size=512M \
    NEO4J_PLUGINS='["apoc"]' \
    NEO4J_dbms_security_procedures_unrestricted=apoc.* \
    NEO4J_dbms_security_procedures_allowlist=apoc.*

EXPOSE 7474 7687
WORKDIR /data
CMD ["neo4j"]
```
</details>

### 2. Install the MCP Server

```bash
pip install -e .
# or with uv
uv pip install -e .
```

### 3. Run

```bash
# Environment variables (defaults shown)
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=password

neo4j-knowledge-mcp

# Or pass arguments directly
neo4j-knowledge-mcp --db-url bolt://localhost:7687 --username neo4j --password password

# HTTP transport (for remote / web clients)
neo4j-knowledge-mcp --transport streamable-http
```

---

## MCP Configuration

### Claude Code (`.mcp.json`)

Create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "neo4j-knowledge-mcp",
      "args": [
        "--db-url", "bolt://localhost:7687",
        "--username", "neo4j",
        "--password", "password"
      ]
    }
  }
}
```

If you installed into a virtualenv, use the full path:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "/path/to/venv/bin/neo4j-knowledge-mcp",
      "args": [
        "--db-url", "bolt://localhost:7687",
        "--username", "neo4j",
        "--password", "password"
      ]
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)

Edit the config file:

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

If `neo4j-knowledge-mcp` is on your `PATH`:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "neo4j-knowledge-mcp",
      "args": [
        "--db-url", "bolt://localhost:7687",
        "--username", "neo4j",
        "--password", "password"
      ]
    }
  }
}
```

If installed into a conda / virtualenv, use the full path to the binary:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "/Users/you/miniconda/envs/localkg/bin/neo4j-knowledge-mcp",
      "args": [
        "--db-url", "bolt://localhost:7687",
        "--username", "neo4j",
        "--password", "password"
      ]
    }
  }
}
```

Or run via `uvx` (no local install needed):

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "uvx",
      "args": [
        "neo4j-knowledge-mcp",
        "--db-url", "bolt://localhost:7687",
        "--username", "neo4j",
        "--password", "password"
      ]
    }
  }
}
```

After saving, **restart Claude Desktop**.

---

## Testing in Claude Desktop

Once the config is saved and Claude Desktop is restarted:

1. **Check the tool icon** — open a new chat; you should see a hammer icon (tools) in the input area. Click it and verify that `knowledge-graph` tools are listed (e.g. `create_entity`, `search_knowledge`, etc.).

2. **Smoke test** — type in Claude Desktop:

   > Create an entity called "TestService" of type "Service" in project "demo" with observation "smoke test".

   Claude should call `create_entity` and return a confirmation.

3. **Read it back** — ask:

   > Show me the full graph for project "demo".

   Claude calls `get_project_graph` and returns the entity you just created.

4. **Search** — ask:

   > Search the knowledge graph for "smoke".

   Claude calls `search_knowledge` and finds the observation.

5. **Clean up** — ask:

   > Delete entity "TestService" from project "demo".

If all five steps succeed, the MCP server is fully operational.

---

## Workflow Example

```
Session 1 — Project kickoff
  → create_entity("UserService", "Service", "my-app", ["Handles auth and profile"])
  → create_entity("PostgresDB", "Database", "my-app", ["Primary data store"])
  → create_relationship("UserService", "PostgresDB", "READS_FROM", "my-app")
  → add_migration("my-app", "Initial domain model", "CREATE (:Entity {name:'UserService'}) ...")

Session 2 — Add payments
  → create_entity("PaymentService", "Service", "my-app", ["Stripe integration"])
  → create_relationship("PaymentService", "UserService", "DEPENDS_ON", "my-app")
  → add_migration("my-app", "Add payment domain", "...")

Session N — Any future session
  → get_project_graph("my-app")           # Full context
  → search_knowledge("authentication")     # Find relevant entities
  → get_migrations("my-app")              # Understand evolution
```

Each session starts by loading the project graph and ends by persisting new knowledge back into it.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USERNAME` | `neo4j` | Database username |
| `NEO4J_PASSWORD` | `password` | Database password |
| `NEO4J_DATABASE` | `neo4j` | Database name |

## License

MIT
