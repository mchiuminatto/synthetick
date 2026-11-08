import uuid

import httpx
import pytest

from app.main import app

INVALID_FIELDS = {
    "date_from_not_before_date_to": {"date_from": "2025-01-02T00:00:00Z", "date_to": "2025-01-01T00:00:00Z"},
    "date_from_equal_to_date_to": {"date_from": "2025-01-01T00:00:00Z", "date_to": "2025-01-01T00:00:00Z"},
    "min_price_not_below_max_price": {"min_price": "200", "max_price": "100"},
    "initial_bid_below_min_price": {"initial_bid": "99"},
    "initial_bid_above_max_price": {"initial_bid": "201"},
    "min_price_not_positive": {"min_price": "0"},
    "volatility_sigma_negative": {"volatility_sigma": -0.1},
    "spread_mean_negative": {"spread_mean": -0.01},
    "spread_stdev_negative": {"spread_stdev": -0.01},
    "time_unit_seconds_zero": {"time_unit_seconds": 0},
    "time_unit_seconds_negative": {"time_unit_seconds": -1},
    "mean_ticks_not_positive": {"mean_ticks": 0},
    "dispersion_not_positive": {"dispersion": 0},
    "min_ticks_negative": {"min_ticks": -1},
    "min_ticks_above_max_ticks": {"min_ticks": 60, "max_ticks": 50},
    "instrument_empty": {"instrument": ""},
}


@pytest.mark.parametrize("overrides", INVALID_FIELDS.values(), ids=INVALID_FIELDS.keys())
async def test_post_invalid_request_returns_422_and_records_nothing(db, invalid_request, overrides):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/history/tick-range", json=invalid_request(**overrides))

    assert response.status_code == 422
    assert db.execute("SELECT count(*) FROM tick_range").fetchone() == (0,)
    assert db.execute("SELECT count(*) FROM domain_event").fetchone() == (0,)


async def test_post_valid_request_returns_202_with_id_and_requested_status(db, valid_request):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/history/tick-range", json=valid_request)

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "REQUESTED"
    tick_range_id = uuid.UUID(body["tick_range_id"])

    row = db.execute(
        "SELECT status FROM tick_range WHERE tick_range_id = %s", (tick_range_id,)
    ).fetchone()
    assert row == ("REQUESTED",)
    events = db.execute(
        "SELECT count(*) FROM domain_event WHERE aggregate_id = %s", (tick_range_id,)
    ).fetchone()
    assert events == (1,)
