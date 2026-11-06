import httpx

from app.main import app


async def test_data_of_unfinished_range_returns_409_not_ready(db, valid_request):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post("/v1/history/tick-range", json=valid_request)
        tick_range_id = created.json()["tick_range_id"]

        response = await client.get(f"/v1/history/tick-range/{tick_range_id}/data")

    assert response.status_code == 409
    assert response.json()["status"] == "REQUESTED"
