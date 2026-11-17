import httpx
import pyarrow.parquet as pq
from pyarrow import fs

from app.main import app
from app.services.tick_generator import TICKS_PER_OBJECT
from app.services.tick_range import process_next_tick_range


async def test_process_next_marks_requested_range_processed_and_records_result(
    db, s3, bucket, valid_request
):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post("/v1/history/tick-range", json=valid_request)
    tick_range_id = created.json()["tick_range_id"]

    await process_next_tick_range()

    status, records, storage_bucket, prefix, objects, per_object = db.execute(
        """
        SELECT status, records_produced, storage_bucket, storage_prefix,
               objects_produced, ticks_per_object
        FROM tick_range WHERE tick_range_id = %s
        """,
        (tick_range_id,),
    ).fetchone()
    assert status == "PROCESSED"
    assert storage_bucket == bucket
    assert per_object == TICKS_PER_OBJECT
    files = s3.get_file_info(fs.FileSelector(f"{bucket}/{prefix}"))
    assert objects == len(files) > 1
    assert records == sum(pq.read_table(info.path, filesystem=s3).num_rows for info in files)


async def test_process_next_returns_without_error_when_no_range_is_requested(db):
    assert await process_next_tick_range() is False


async def test_process_next_uses_the_code_constant_and_ignores_the_environment_value(
    db, s3, bucket, valid_request, monkeypatch
):
    monkeypatch.setenv("TICKS_PER_OBJECT", "100")
    valid_request["date_to"] = "2025-01-01T00:01:00Z"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post("/v1/history/tick-range", json=valid_request)
    tick_range_id = created.json()["tick_range_id"]

    await process_next_tick_range()

    per_object, objects = db.execute(
        "SELECT ticks_per_object, objects_produced FROM tick_range WHERE tick_range_id = %s",
        (tick_range_id,),
    ).fetchone()
    assert per_object == TICKS_PER_OBJECT
    assert objects == 1


def _read_objects(s3, bucket, prefix):
    infos = s3.get_file_info(fs.FileSelector(f"{bucket}/{prefix}"))
    return {info.base_name: pq.read_table(info.path, filesystem=s3) for info in infos}


async def test_processing_the_same_range_twice_writes_identical_objects(
    db, s3, bucket, valid_request
):
    valid_request["date_to"] = "2025-01-01T06:00:00Z"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post("/v1/history/tick-range", json=valid_request)
    tick_range_id = created.json()["tick_range_id"]

    await process_next_tick_range()
    (prefix,) = db.execute(
        "SELECT storage_prefix FROM tick_range WHERE tick_range_id = %s", (tick_range_id,)
    ).fetchone()
    first_run = _read_objects(s3, bucket, prefix)

    db.execute("UPDATE tick_range SET status = 'REQUESTED' WHERE tick_range_id = %s", (tick_range_id,))
    await process_next_tick_range()
    second_run = _read_objects(s3, bucket, prefix)

    assert len(first_run) > 1
    assert second_run.keys() == first_run.keys()
    assert all(second_run[name].equals(first_run[name]) for name in first_run)
