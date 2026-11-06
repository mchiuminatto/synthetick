# ADR-0001: Organise the application under `app/` with FastAPI routers and a services layer

- **Status:** Accepted
- **Date:** 2026-11-06
- **Deciders:** Marcello Chiuminatto
- **Consulted:** n/a
- **Informed:** n/a
- **Tags:** structure, api, code-organisation

## Context

SYN-41 is the first story with application code. It started with a single module, `synthetick/api.py`, that holds the FastAPI app, the request model, the database access and the insert of the `tick_range` row and its event. The `synthetick/` package is otherwise empty: the earlier pandas-based library was removed, so nothing there needs to be preserved.

The stack (see [tech-stack.md](../design/tech-stack.md)) has an API that records requests and a worker that runs the core (the `TickRange` aggregate). The backlog adds many endpoints (status, data, paging, errors, expiry, instrument catalog loading, events: SYN-42 to SYN-55). The files and the places where code goes need to be settled before they multiply.

The Alembic migrations live at the repository root in `migrations/`.

## Decision Drivers

- Keep HTTP concerns (routes, request and response models, status codes) apart from the domain logic (the aggregates and their rules), so the core can be tested without HTTP and reused by the worker.
- Follow FastAPI's own convention for growing applications: one `APIRouter` per resource, assembled in a main module.
- One obvious root folder for everything that is the application, separate from `docs/`, `tests/` and the project files.
- A structure that does not need to change as SYN-42 to SYN-55 are added.

## Considered Options

1. **Single module** (`synthetick/api.py`, as today)
2. **`app/` with `main.py`, `routers/` and `services/`**
3. **Full layered or hexagonal layout** (`api/`, `domain/`, `application/`, `infrastructure/`)

## Decision

We will **create an `app/` folder at the repository root as the root of the application, with `main.py`, a `routers/` sub-folder and a `services/` sub-folder**, because it separates HTTP from the core logic with the least structure and follows the FastAPI convention.

Layout:

```text
app/
  main.py           # creates the FastAPI app and includes the routers
  routers/
    tick_range.py   # APIRouter for /v1/history/tick-range
  services/         # core logic: the aggregates (TickRange) and their rules
  migrations/       # Alembic migrations, moved here from the repository root
```

Rules:

- `main.py` only creates the application and includes the routers. It holds no route and no business logic.
- There is one router module per resource. For now there is one: `tick_range`. A router translates HTTP into calls to the services and the result back into HTTP. It does not hold domain rules.
- `services/` holds the core logic, in particular the aggregates (`TickRange`). It does not import FastAPI. The API and the worker both use it.
- `migrations/` moves inside `app/`. Schema changes still go only through Alembic.

Scope: this decision covers where the application code lives and the dependency direction (`main` → `routers` → `services`). It does not cover the worker's entry point, the internal design of the aggregates, the persistence layer inside `services/`, or the test layout.

## Options Analysis

### Option 1 — Single module
- ✅ Pro: nothing to do now.
- ❌ Con: HTTP, database access and domain logic already share one function, and 15 stories are still to come.
- ❌ Con: the core logic cannot be reused by the worker without importing the API.

### Option 2 — `app/` with `main.py`, `routers/`, `services/`
- ✅ Pro: standard FastAPI layout, easy for newcomers to find things.
- ✅ Pro: the core in `services/` is independent of FastAPI, so the worker and the tests can use it directly.
- ✅ Pro: adding a resource means adding one router module.
- ❌ Con: "services" is a broad name; without discipline it can collect unrelated code.
- ❌ Con: the repository-root `migrations/` has to move, with the config that points at it.

### Option 3 — Full layered or hexagonal layout
- ✅ Pro: strongest separation, ports and adapters for PostgreSQL and MinIO.
- ❌ Con: more folders and indirection than a single-resource API needs today.
- ❌ Con: not justified by the current scope (see the "Expensive-to-change decisions: none" note in `CLAUDE.md`).

## Consequences

### Positive
- A single place for application code, and a clear dependency direction.
- The aggregates can be unit-tested without HTTP, and the worker can import them.
- New endpoints follow an existing pattern.

### Negative / Trade-offs accepted
- A one-off restructuring now, with the files that refer to the old paths changed together.
- The `app/` folder name is generic; the Python package is no longer called `synthetick`.

### Risks and Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Moving `migrations/` breaks Alembic or the Compose and Make commands | Med | Med | Update `alembic.ini` (`script_location`) in the same change, then run `alembic upgrade head` and the existing test before anything else |
| Domain logic leaks into routers over time | Med | Med | Rule above: routers only translate; review for it in `/code-review` |
| `services/` turns into a catch-all | Low | Low | Only aggregates and their rules go there; revisit if it grows (see below) |

## Implementation Notes

- The restructuring is done as its own change, separate from new functionality, with the tests green before and after.
- Things that change with the move: `synthetick/api.py` is split into `app/main.py`, `app/routers/tick_range.py` and a first piece of `app/services/`; `alembic.ini` (`script_location`); the imports and `pythonpath` in `tests/` and `pyproject.toml`; `CLAUDE.md` and the design documents that mention paths.
- Open points, to settle in the refactor or later: where the worker's entry point lives (inside `app/` is the natural place), what happens to the empty `synthetick/` package, and how the tests are laid out.
- Rollback: revert the commit; the change is mechanical.

## Validation

- The existing test (`post_valid_request_returns_202_with_id_and_requested_status`) passes unchanged in behaviour after the move.
- `alembic upgrade head` runs from the new location.
- `app/services/` imports nothing from FastAPI.

**Revisit when:** `services/` holds unrelated concerns, or a second consumer needs the persistence layer separated (then consider Option 3).

## References

- [tech-stack.md](../design/tech-stack.md)
- [domain-analysis.md](../design/domain-analysis.md)
- FastAPI, "Bigger Applications - Multiple Files"
- Jira SYN-41
