import json
import os
import secrets
import uuid
from datetime import datetime
from typing import Any, Mapping

from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.services import tick_storage
from app.services.tick_generator import TickSpec, generate_ticks


def _engine():
    url = URL.create(
        "postgresql+asyncpg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ["POSTGRES_DB"],
    )
    return create_async_engine(url, poolclass=NullPool)


def _json_default(value: Any) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value)


async def get_status(tick_range_id: uuid.UUID) -> str:
    engine = _engine()
    async with engine.connect() as connection:
        result = await connection.execute(
            text("SELECT status FROM tick_range WHERE tick_range_id = :id"),
            {"id": tick_range_id},
        )
        status = result.scalar_one()
    await engine.dispose()
    return str(status)


async def request_tick_range(spec: Mapping[str, Any]) -> uuid.UUID:
    """Record a tick range as REQUESTED, with its event, in one transaction."""
    tick_range_id = uuid.uuid4()
    engine = _engine()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO tick_range (tick_range_id, instrument, date_from, date_to,
                    min_price, max_price, initial_bid, trend_drift, volatility_sigma,
                    spread_mean, spread_stdev, time_unit_seconds, mean_ticks, dispersion,
                    min_ticks, max_ticks, seed)
                VALUES (:tick_range_id, :instrument, :date_from, :date_to,
                    :min_price, :max_price, :initial_bid, 0, :volatility_sigma,
                    :spread_mean, :spread_stdev, :time_unit_seconds, :mean_ticks, :dispersion,
                    :min_ticks, :max_ticks, :seed)
                """
            ),
            {**spec, "tick_range_id": tick_range_id, "seed": secrets.randbits(62)},
        )
        await connection.execute(
            text(
                """
                INSERT INTO domain_event (event_id, event_type, aggregate_type,
                    aggregate_id, aggregate_version, payload)
                VALUES (:event_id, 'TickRangeRequested', 'TickRange',
                    :tick_range_id, 1, CAST(:payload AS jsonb))
                """
            ),
            {
                "event_id": uuid.uuid4(),
                "tick_range_id": tick_range_id,
                "payload": json.dumps(dict(spec), default=_json_default),
            },
        )
    await engine.dispose()
    return tick_range_id


async def process_next_tick_range() -> None:
    """Take a REQUESTED range, generate and store its ticks, mark it PROCESSED.

    The row lock is held until PROCESSED is written (ADR-0002).
    """
    engine = _engine()
    async with engine.begin() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    SELECT * FROM tick_range WHERE status = 'REQUESTED'
                    ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED
                    """
                )
            )
        ).mappings().one()
        spec = TickSpec(
            date_from=row["date_from"],
            date_to=row["date_to"],
            initial_bid=float(row["initial_bid"]),
            trend_drift=row["trend_drift"],
            volatility_sigma=row["volatility_sigma"],
            spread_mean=row["spread_mean"],
            spread_stdev=row["spread_stdev"],
            time_unit_seconds=row["time_unit_seconds"],
            mean_ticks=row["mean_ticks"],
            dispersion=row["dispersion"],
            min_ticks=row["min_ticks"],
            max_ticks=row["max_ticks"],
        )
        ticks = generate_ticks(spec, seed=row["seed"])
        prefix = f"tick-range/{row['tick_range_id']}/"
        ticks_per_object = int(os.environ.get("TICKS_PER_OBJECT", "100000"))
        objects = tick_storage.write_ticks(ticks, prefix, ticks_per_object)
        await connection.execute(
            text(
                """
                UPDATE tick_range SET status = 'PROCESSED', records_produced = :records,
                    storage_bucket = :bucket, storage_prefix = :prefix,
                    objects_produced = :objects, ticks_per_object = :per_object,
                    updated_at = now()
                WHERE tick_range_id = :id
                """
            ),
            {
                "records": len(ticks.timestamps),
                "bucket": tick_storage.bucket_name(),
                "prefix": prefix,
                "objects": objects,
                "per_object": ticks_per_object,
                "id": row["tick_range_id"],
            },
        )
    await engine.dispose()
