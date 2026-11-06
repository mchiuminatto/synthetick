from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.main import app
from app.services.tick_range import process_next_tick_range


async def test_data_of_unfinished_range_returns_409_not_ready(db, valid_request):

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post("/v1/history/tick-range", json=valid_request)
        tick_range_id = created.json()["tick_range_id"]

        response = await client.get(f"/v1/history/tick-range/{tick_range_id}/data")

    assert response.status_code == 409
    assert response.json()["status"] == "REQUESTED"


async def test_data_of_processed_range_returns_ticks_in_time_order_inside_date_range_with_ask_not_below_bid(
    db, bucket, valid_request
):
    valid_request["date_to"] = "2025-01-01T00:01:00Z"
    date_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
    date_to = datetime(2025, 1, 1, 0, 1, tzinfo=timezone.utc)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post("/v1/history/tick-range", json=valid_request)
        tick_range_id = created.json()["tick_range_id"]
        await process_next_tick_range()

        response = await client.get(f"/v1/history/tick-range/{tick_range_id}/data")

    assert response.status_code == 200
    body = response.json()
    ticks = body["ticks"]
    assert len(ticks) > 0
    assert body["records_produced"] == len(ticks)
    timestamps = [datetime.fromisoformat(tick["timestamp"]) for tick in ticks]
    assert timestamps == sorted(timestamps)
    assert date_from <= timestamps[0] and timestamps[-1] <= date_to
    assert all(Decimal(tick["ask"]) >= Decimal(tick["bid"]) for tick in ticks)
