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
    tick-range/<tick-range-id>/instrument=<instrument>/date=<object-start-date>
    ```

    Example: `tick-range/afdafgbb****/instrument=EURUSD/date=2026-01-01`

    - `<tick-range-id>`: identifier of the tick range.
    - `<instrument>`: instrument symbol, for example `EURUSD`.
    - `<object-start-date>`: start date of the data held in the object, in `YYYY-MM-DD` format.
    - The `key=value` segments follow the Hive partitioning style, so Parquet tools such as `pyarrow` can read them as partition columns.

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
  - Python is already the language of the core library, so the API calls it directly with no extra integration layer.
  - Schema changes are made only through Alembic migrations, never by hand and never by `create_all` outside of tests.

### TS-4: uv for dependency management

- **Decision:** Use uv to manage the Python environment and dependencies.
- **Used for:** Creating the virtual environment, resolving and locking dependencies (`uv.lock`), and running commands in the project environment.
- **Notes:**
  - Dependencies stay declared in `pyproject.toml`; the lock file is committed so installs are reproducible.
  - The current `pyproject.toml` uses Hatch as the build backend. Whether to keep it is not decided here.

## Local environment

The services run with Docker Compose:

| Service | Image | Persistent volume |
|---------|-------|-------------------|
| `postgres` | `postgres:18.6` | Yes |
| `minio` | `docker.io/pgsty/silo:RELEASE.2026-10-26T00-00-00Z` | Yes |

The API runs on the host during development and is containerized later.
