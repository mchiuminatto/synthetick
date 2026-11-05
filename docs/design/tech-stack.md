# Tech Stack

This document lists the technologies chosen for Synthetick and the role each one plays. Each decision is a short record: what was chosen, where it runs, and what it is used for. Decisions that need a full trade-off analysis get their own ADR in [`docs/ADR`](../ADR/template.md) and are linked from here.

## Summary

| Layer | Technology | Version | Runtime | Role |
|-------|------------|---------|---------|------|
| Object storage | MinIO (pgsty/silo image) | RELEASE.2026-10-26T00-00-00Z | Docker | Stores generated tick datasets for download |
| Database | PostgreSQL | 18.6 | Docker | Relational data: instrument catalog, request and job metadata |
| Language | Python | >= 3.11 | Host / container | Core library and API |
| Dependency management | uv | latest stable | Host / container | Python environments, dependency resolution and lock file |
| API framework | FastAPI | latest stable | Host / container | HTTP API for requesting and downloading tick ranges |
| ORM | SQLAlchemy | 2.x | n/a | Database access from the API |
| Migrations | Alembic | latest stable | n/a | Versioned schema migrations |
| Job queue | PostgreSQL (`FOR UPDATE SKIP LOCKED`) | 18.6 | Docker | Persistent queue between the API and the worker that runs the core |
| Worker | Python (core library) | >= 3.11 | Container | Takes tick range requests from the queue and produces them |

## Decisions

### TS-1: MinIO for object storage

- **Decision:** Use MinIO as the object store, running the `pgsty/silo` image.
- **Image:** `docker.io/pgsty/silo:RELEASE.2026-10-26T00-00-00Z`
- **Runs on:** Docker.
- **Used for:** Storing the generated tick datasets as Parquet files so that the API can serve them for download.
- **Notes:**
  - MinIO exposes an S3-compatible API, so the application code can use a standard S3 client and be moved to another S3-compatible store later.
  - Datasets are stored in Apache Parquet format. The project already depends on `pyarrow`, which reads and writes it.
  - Object naming convention:

    ```text
    tick-range/<tick-range-id>/part-<n>.parquet
    ```

    Example: `tick-range/5b0f3c1e-9d7a-4c55-8a53-0d6d2f1c7e11/part-000001.parquet`

    - `<tick-range-id>`: identifier of the tick range (UUID).
    - `<n>`: sequence number of the object inside the tick range, zero-padded. Objects follow each other in time order and each holds `ticks_per_object` ticks (the last one holds the remainder).
    - The prefix `tick-range/<tick-range-id>/` is stored in `tick_range.storage_prefix`. The API maps a tick position to its object by sequence number, see "Aggregate data model" in [domain-analysis.md](domain-analysis.md).

  - Data lives in a Docker volume; the bucket name and credentials come from environment variables, never from the code.

### TS-2: PostgreSQL as database engine

- **Decision:** Use PostgreSQL, latest stable version (18.6), as the database engine.
- **Runs on:** Docker.
- **Used for:** Relational data of the API, such as the instrument catalog and the metadata of tick range requests.
- **Notes:**
  - The Docker image tag pins the version (`postgres:18.6`), not `latest`, so environments stay reproducible. The tag is upgraded deliberately.
  - Data lives in a Docker volume; credentials come from environment variables.

### TS-3: Python and FastAPI for the API

- **Decision:** Use Python with FastAPI as the API framework, SQLAlchemy as the ORM, and Alembic for schema migrations.
- **Used for:**
  - **FastAPI**: HTTP endpoints, request validation and the OpenAPI documentation.
  - **SQLAlchemy**: Mapping and querying PostgreSQL, using the async API (`AsyncSession` and `create_async_engine`).
  - **Alembic**: Schema changes as versioned migration scripts, applied in order on every environment. It runs synchronously.
- **Notes:**
  - Database access in the API is async, so the endpoints do not block the event loop. The API uses the `asyncpg` driver (`postgresql+asyncpg://`).
  - Alembic runs migrations synchronously as a separate one-off step, using the default Alembic setup and a sync driver, `psycopg` (`postgresql+psycopg://`). Migrations do not benefit from async, and this keeps `env.py` simple.
  - Both connection URLs are built from the same database settings, so there is a single source of configuration.
  - Python is already the language of the core library, so the API and the worker use it directly with no extra integration layer. The API does not run the core itself: it hands the request to the worker through the queue, see TS-5.
  - Schema changes are made only through Alembic migrations, never by hand and never by `create_all` outside of tests.

### TS-4: uv for dependency management

- **Decision:** Use uv to manage the Python environment and dependencies.
- **Used for:** Creating the virtual environment, resolving and locking dependencies (`uv.lock`), and running commands in the project environment.
- **Notes:**
  - Dependencies stay declared in `pyproject.toml`; the lock file is committed so installs are reproducible.
  - The current `pyproject.toml` uses Hatch as the build backend. Whether to keep it is not decided here.

### TS-5: Worker and PostgreSQL as the job queue

- **Decision:** The core (the `TickRange` aggregate) runs in its own container, the worker. The API does not produce tick ranges; it records the request and the worker takes it from a persistent queue implemented on PostgreSQL. No message broker is added.
- **Runs on:** Docker (worker container), using the existing `postgres` service.
- **Used for:** Running the production of a tick range in the background, so that `POST /v1/history/tick-range` returns `202 Accepted` immediately and the API event loop is never blocked by generation.
- **How it works:**
  - The API validates the request, then in one transaction inserts the `tick_range` row with status `REQUESTED` and the `TickRangeRequested` event (transactional outbox, see "Domain event storage" in [domain-analysis.md](domain-analysis.md)). A request is therefore never saved without being queued, or queued without being saved.
  - The worker claims pending work with `SELECT … FOR UPDATE SKIP LOCKED`, so several workers can run in parallel without taking the same request twice. It moves the range to `STARTED`, produces the ticks, writes the objects to MinIO and marks the range `PROCESSED` or `FAILED`, as described in the domain analysis.
  - The queue is persistent: requests survive restarts of the API, the worker and the database.
- **Notes:**
  - Delivery is at-least-once. Producing a range must be safe to repeat: the seed is stored in the spec, so the same range gives the same series, and the objects are written to a fixed prefix, so a rerun overwrites them.
  - Worker crashes: the worker container runs with the Docker restart policy `on-failure`, so Docker starts it again if it exits with an error (including a crash or an out-of-memory kill). The policy only restarts the process. It does not change the database, so a range that was `STARTED` when the worker died stays `STARTED` until something handles it.
  - Stuck-job recovery (decided): when the worker starts, it puts every range in `STARTED` back to `REQUESTED`, and then produces it again from the start, like any other pending range. This is safe because producing a range is repeatable (stored seed, fixed MinIO prefix). It assumes a single worker: with several workers, one starting up could requeue a range another worker is still processing. Running several workers needs a different mechanism (a heartbeat or a timeout) and a new decision.
  - Retry limit (decided): a range can be started at most `max_attempts` times, a configuration value (suggested default: 3). Each start counts as an attempt. At startup, a range in `STARTED` that has already used all its attempts is not requeued: it is marked `FAILED`, with a `failure_reason` that says the attempts were exhausted, and `TickRangeFailed` is recorded. This stops a range that crashes the worker every time from restarting forever. The attempt count must be stored with the range (for example an `attempts` column on `tick_range`); that column is not in `domain-analysis.md` yet.
  - The requeue is recorded as a new lifecycle event; its name and how it fits the status flow `REQUESTED` → `STARTED` → `PROCESSED` / `FAILED` are not decided here, and `domain-analysis.md` does not describe this transition yet.
  - The API and the worker share one codebase and the same core library, with two entrypoints and two container images.
  - Why not a broker (RabbitMQ, Redis): the load is a few long-running jobs, not a high message rate, and the outbox and the `REQUESTED` status already exist. A broker adds a service and a technology for no current need. If the load grows, a broker can replace the polling because the domain only depends on "a request was made". That change gets its own ADR.

## Local environment

The services run with Docker Compose:

| Service | Image | Persistent volume |
|---------|-------|-------------------|
| `postgres` | `postgres:18.6` | Yes |
| `minio` | `docker.io/pgsty/silo:RELEASE.2026-10-26T00-00-00Z` | Yes |

The API and the worker (TS-5) run on the host during development and are containerized later. The queue is the `postgres` service, so no extra service is needed.
