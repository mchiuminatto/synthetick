from decimal import Decimal

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow import fs

from app.services.tick_generator import Ticks
from app.services.tick_storage import write_ticks

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
