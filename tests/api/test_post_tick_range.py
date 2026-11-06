import uuid

import httpx

from app.main import app


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
