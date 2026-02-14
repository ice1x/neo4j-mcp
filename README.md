# neo4j-knowledge-mcp

A lightweight [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) server that turns a Neo4j database into a **project knowledge graph** — a persistent, evolving context for LLMs.

## Concept

Traditional documentation is written at the end and quickly becomes stale.
A better approach: **build the documentation incrementally, as a graph, from the very first working session.**

After each session with an LLM (e.g. Claude Code), you generate graph data migrations and schema changes that capture:

- **Entities** — services, models, decisions, components, APIs, concepts
- **Relationships** — dependencies, data flows, ownership, implementation links
- **Observations** — free-text notes attached to entities over time
- **Migrations** — versioned Cypher statements that record every structural change

The graph evolves with the project. By the end you have:

1. A complete, ordered **history of graph migrations**
2. An accurate representation of the **domain and business logic**
3. Documentation that reflects **how the system actually evolved**

The key insight: this living graph becomes a **Knowledge Graph MCP** — a reusable context source that any LLM can query to understand, evolve, and maintain the project.

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
| `get_entity` | Get entity with all relationships (LLM context) |
| `search_knowledge` | Full-text search across entity names and observations |
| `get_project_graph` | Get the complete graph for a project |
| `list_projects` | List all projects in the knowledge graph |
| `add_migration` | Record a versioned graph migration |
| `get_migrations` | Get migration history for a project |
| `apply_migration` | Execute a pending migration |
| `run_cypher` | Run an arbitrary Cypher query |

## Quick Start

### Prerequisites

- Python 3.10+
- A running Neo4j instance (local, Docker, Aura, or Desktop)

### Install

```bash
pip install -e .
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv pip install -e .
```

### Run

```bash
# Using environment variables
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=your-password

neo4j-knowledge-mcp

# Or with CLI arguments
neo4j-knowledge-mcp --db-url bolt://localhost:7687 --username neo4j --password secret

# HTTP transport (for remote / web clients)
neo4j-knowledge-mcp --transport streamable-http
```

### Start Neo4j with Docker (optional)

```bash
docker run -d \
  --name neo4j-knowledge \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:5
```

## Claude Desktop Integration

Yes — this MCP server works with **Claude Desktop**. Add it to your Claude Desktop config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "neo4j-knowledge-mcp",
      "args": [
        "--db-url", "bolt://localhost:7687",
        "--username", "neo4j",
        "--password", "your-password"
      ]
    }
  }
}
```

If you installed with `uv` into a virtual environment, use the full path:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "/path/to/venv/bin/neo4j-knowledge-mcp",
      "args": [
        "--db-url", "bolt://localhost:7687",
        "--username", "neo4j",
        "--password", "your-password"
      ]
    }
  }
}
```

Or use `uvx` to run directly from PyPI (once published):

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "uvx",
      "args": [
        "neo4j-knowledge-mcp",
        "--db-url", "bolt://localhost:7687",
        "--username", "neo4j",
        "--password", "your-password"
      ]
    }
  }
}
```

After editing the config, restart Claude Desktop. The knowledge graph tools will appear in the tool selector.

## Claude Code Integration

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "neo4j-knowledge-mcp",
      "args": ["--db-url", "bolt://localhost:7687", "--username", "neo4j", "--password", "secret"]
    }
  }
}
```

## Workflow Example

A typical session workflow:

```
Session 1 — Project kickoff
  → create_entity("UserService", "Service", "my-app", ["Handles auth and profile"])
  → create_entity("PostgresDB", "Database", "my-app", ["Primary data store"])
  → create_relationship("UserService", "PostgresDB", "READS_FROM", "my-app")
  → add_migration("my-app", "Initial domain model", "CREATE (:Entity {name: 'UserService'}) ...")

Session 2 — Add payments
  → create_entity("PaymentService", "Service", "my-app", ["Stripe integration"])
  → create_relationship("PaymentService", "UserService", "DEPENDS_ON", "my-app")
  → add_migration("my-app", "Add payment domain", "CREATE (:Entity {name: 'PaymentService'}) ...")

Session N — Any future session
  → get_project_graph("my-app")           # Full context for the LLM
  → search_knowledge("authentication")     # Find relevant entities
  → get_migrations("my-app")              # Understand evolution history
```

Each session starts by loading the project graph as context and ends by persisting new knowledge back into it.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USERNAME` | `neo4j` | Database username |
| `NEO4J_PASSWORD` | `password` | Database password |
| `NEO4J_DATABASE` | `neo4j` | Database name |

## License

MIT
