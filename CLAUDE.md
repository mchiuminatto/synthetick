# Synthetick

## Context

Synthetick generates synthetic historic tick data (timestamp, bid, ask) for an instrument and a date range. This iteration is API only; its consumers are algo-trading developers and quants. A client requests a tick range, polls its status, and downloads the ticks page by page.

Out of scope for now: OHLC, real-time tick and OHLC feeds, the library as a direct consumer, authentication and authorization, and market calendars (the series runs continuously, with no weekends or holidays removed).

Expensive-to-change decisions: none apply (no multi-tenant, no roles, no offline/sync, no multi-language or multi-currency).

Design documents:
- `docs/design/domain-analysis.md`: domain model, rules, endpoints, data model.
- `docs/design/tech-stack.md`: technology decisions (TS-1 to TS-5).
- `docs/design/synthetic-price-generation.md`: random walk reference.

Backlog: Jira project SYN, epic SYN-25 "Implement tick range" (stories SYN-41 to SYN-55). Stories are kept as one-liners and refined later.

## Stack

- Python >= 3.11, managed with uv (`uv.lock` committed).
- FastAPI for the API, SQLAlchemy 2 async (`asyncpg`) for database access, Alembic for migrations (sync, `psycopg`). Schema changes only through Alembic.
- PostgreSQL 18.6 in Docker (`postgres:18.6`): instrument catalog, `tick_range`, `domain_event`, and the job queue.
- MinIO (`docker.io/pgsty/silo:RELEASE.2026-10-26T00-00-00Z`) in Docker: tick datasets as Parquet, `tick-range/<tick-range-id>/part-<n>.parquet`.
- Worker: the core (`TickRange` aggregate) runs in its own container. The API records the request (`REQUESTED` plus the event, in one transaction) and the worker takes it from PostgreSQL with `FOR UPDATE SKIP LOCKED`. No message broker. Container restart policy `on-failure`.
- Docker Compose for the local services. Credentials and settings come from environment variables, never from code.
