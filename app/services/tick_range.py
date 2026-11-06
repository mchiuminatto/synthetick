import json
import os
import secrets
import uuid
from datetime import datetime
from typing import Any, Mapping

from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


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
