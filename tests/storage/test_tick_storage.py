from datetime import datetime, timedelta, timezone
from decimal import Decimal

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow import fs

from app.services.tick_generator import Ticks
from app.services.tick_storage import write_blocks, write_ticks

PREFIX = "tick-range/5b0f3c1e-9d7a-4c55-8a53-0d6d2f1c7e11/"

DOCUMENTED_SCHEMA = pa.schema(
    [
        pa.field("timestamp", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("bid", pa.decimal128(18, 8), nullable=False),
        pa.field("ask", pa.decimal128(18, 8), nullable=False),
    ]
)


def test_written_ticks_are_parquet_objects_under_the_range_prefix_with_the_documented_schema(
    s3, bucket
):
    start = np.datetime64("2025-01-01T00:00:00", "us")
    ticks = Ticks(
        timestamps=start + np.arange(25).astype("timedelta64[ms]"),
        bid=np.full(25, 110.5),
        ask=np.full(25, 110.52),
    )

    objects = write_ticks(ticks, prefix=PREFIX, ticks_per_object=10)

    assert objects == 3
    names = sorted(
        info.base_name for info in s3.get_file_info(fs.FileSelector(bucket + "/" + PREFIX))
    )
    assert names == ["part-000001.parquet", "part-000002.parquet", "part-000003.parquet"]
    tables = [pq.read_table(f"{bucket}/{PREFIX}{name}", filesystem=s3) for name in names]
    assert [table.num_rows for table in tables] == [10, 10, 5]
    assert all(table.schema.equals(DOCUMENTED_SCHEMA) for table in tables)
    first = tables[0].to_pylist()[0]
    assert first["bid"] == Decimal("110.5")
    assert first["ask"] == Decimal("110.52")


def test_blocks_of_uneven_sizes_are_cut_into_objects_of_exactly_ticks_per_object_rows(s3, bucket):
    start = np.datetime64("2025-01-01T00:00:00", "us")

    def block(first: int, count: int) -> Ticks:
        numbers = np.arange(first, first + count)
        return Ticks(
            timestamps=start + numbers.astype("timedelta64[ms]"),
            bid=np.full(count, 110.5),
            ask=np.full(count, 110.52),
        )

    blocks = [block(0, 4), block(4, 7), block(11, 5)]

    write_blocks(blocks, prefix=PREFIX, ticks_per_object=10)

    names = sorted(
        info.base_name for info in s3.get_file_info(fs.FileSelector(bucket + "/" + PREFIX))
    )
    assert names == ["part-000001.parquet", "part-000002.parquet"]
    tables = [pq.read_table(f"{bucket}/{PREFIX}{name}", filesystem=s3) for name in names]
    assert [table.num_rows for table in tables] == [10, 6]
    written = [value for table in tables for value in table.column("timestamp").to_pylist()]
    first_instant = datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert written == [first_instant + timedelta(milliseconds=i) for i in range(16)]


def test_an_exact_multiple_of_ticks_per_object_leaves_no_empty_trailing_object(s3, bucket):
    start = np.datetime64("2025-01-01T00:00:00", "us")

    def block(first: int, count: int) -> Ticks:
        numbers = np.arange(first, first + count)
        return Ticks(
            timestamps=start + numbers.astype("timedelta64[ms]"),
            bid=np.full(count, 110.5),
            ask=np.full(count, 110.52),
        )

    blocks = [block(0, 6), block(6, 6), block(12, 8)]

    write_blocks(blocks, prefix=PREFIX, ticks_per_object=10)

    names = sorted(
        info.base_name for info in s3.get_file_info(fs.FileSelector(bucket + "/" + PREFIX))
    )
    assert names == ["part-000001.parquet", "part-000002.parquet"]
    tables = [pq.read_table(f"{bucket}/{PREFIX}{name}", filesystem=s3) for name in names]
    assert [table.num_rows for table in tables] == [10, 10]


def test_an_empty_stream_writes_no_objects(s3, bucket):
    start = np.datetime64("2025-01-01T00:00:00", "us")
    empty_block = Ticks(
        timestamps=start + np.arange(0).astype("timedelta64[ms]"),
        bid=np.empty(0),
        ask=np.empty(0),
    )
    selector = fs.FileSelector(bucket + "/" + PREFIX, allow_not_found=True)

    write_blocks([], prefix=PREFIX, ticks_per_object=10)
    assert s3.get_file_info(selector) == []

    write_blocks([empty_block, empty_block], prefix=PREFIX, ticks_per_object=10)
    assert s3.get_file_info(selector) == []


def test_blocks_are_written_as_parquet_objects_under_the_range_prefix_with_the_documented_schema(
    s3, bucket
):
    start = np.datetime64("2025-01-01T00:00:00", "us")

    def block(first: int, count: int) -> Ticks:
        numbers = np.arange(first, first + count)
        return Ticks(
            timestamps=start + numbers.astype("timedelta64[ms]"),
            bid=np.full(count, 110.5),
            ask=np.full(count, 110.52),
        )

    write_blocks([block(0, 7), block(7, 5)], prefix=PREFIX, ticks_per_object=10)

    names = sorted(
        info.base_name for info in s3.get_file_info(fs.FileSelector(bucket + "/" + PREFIX))
    )
    assert names == ["part-000001.parquet", "part-000002.parquet"]
    tables = [pq.read_table(f"{bucket}/{PREFIX}{name}", filesystem=s3) for name in names]
    assert all(table.schema.equals(DOCUMENTED_SCHEMA) for table in tables)
    first = tables[0].to_pylist()[0]
    assert first["bid"] == Decimal("110.5")
    assert first["ask"] == Decimal("110.52")


def test_write_blocks_returns_the_object_count_and_the_record_count_it_wrote(s3, bucket):
    start = np.datetime64("2025-01-01T00:00:00", "us")

    def block(first: int, count: int) -> Ticks:
        numbers = np.arange(first, first + count)
        return Ticks(
            timestamps=start + numbers.astype("timedelta64[ms]"),
            bid=np.full(count, 110.5),
            ask=np.full(count, 110.52),
        )

    blocks = [block(0, 4), block(4, 7), block(11, 5)]

    objects, records = write_blocks(blocks, prefix=PREFIX, ticks_per_object=10)

    assert objects == 2
    assert records == 16
