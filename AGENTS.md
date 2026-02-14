# AGENTS.md

## Knowledge Persistence Rule

After every session that changes the project's architecture, data model, or business logic, **persist your findings as a numbered Python data migration**.

### Migration file format

Create files in `migrations/` with the naming convention:

```
migrations/
  001_initial_domain_model.py
  002_add_payment_service.py
  003_refactor_auth_flow.py
  ...
```

Each migration file must:

1. Be a standalone Python script.
2. Write a record to `migrations/migration.log` with the version number and UTC timestamp.
3. Contain the Cypher queries (via the Neo4j driver) that apply the knowledge to the graph.

### Template

```python
"""003 — Refactor auth flow."""

import datetime
from pathlib import Path

VERSION = "003"
DESCRIPTION = "Refactor auth flow"

CYPHER_UP = """
MERGE (e:Entity {name: 'AuthService', project: 'my-app'})
SET e.type = 'Service',
    e.observations = coalesce(e.observations, []) + ['Extracted from UserService in session 3']
"""

CYPHER_DOWN = """
MATCH (e:Entity {name: 'AuthService', project: 'my-app'}) DETACH DELETE e
"""


def log(version: str, description: str) -> None:
    log_path = Path(__file__).resolve().parent / "migration.log"
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(log_path, "a") as f:
        f.write(f"{ts}  v{version}  {description}\n")


def run(tx) -> None:
    tx.run(CYPHER_UP)


if __name__ == "__main__":
    log(VERSION, DESCRIPTION)
    print(f"Logged migration v{VERSION}: {DESCRIPTION}")
    print("Run with Neo4j session.execute_write(run) to apply.")
```

### Rules for the agent

- **Always** increment the migration number.
- **Always** call `log()` so `migration.log` has a continuous audit trail.
- Keep `CYPHER_UP` idempotent (`MERGE` over `CREATE`).
- Provide `CYPHER_DOWN` for reversibility when practical.
- One migration per logical change — do not bundle unrelated changes.
- Commit the migration file together with the code it documents.

### Example `migration.log`

```
2025-06-01T14:23:00+00:00  v001  Initial domain model
2025-06-02T09:15:44+00:00  v002  Add payment service
2025-06-03T17:42:11+00:00  v003  Refactor auth flow
```
