import os

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow import fs

from app.services.tick_generator import Ticks

ROW_GROUP_SIZE = 10_000
SCHEMA = pa.schema(
    [
        pa.field("timestamp", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("bid", pa.decimal128(18, 8), nullable=False),
        pa.field("ask", pa.decimal128(18, 8), nullable=False),
    ]
)


def filesystem() -> fs.S3FileSystem:
    return fs.S3FileSystem(
        access_key=os.environ["MINIO_ROOT_USER"],
        secret_key=os.environ["MINIO_ROOT_PASSWORD"],
        endpoint_override=os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
        scheme="http",
        allow_bucket_creation=True,
    )


def bucket_name() -> str:
    return os.environ.get("MINIO_BUCKET", "synthetick")


def ensure_bucket() -> None:
    filesystem().create_dir(bucket_name())


def _decimal(prices: np.ndarray) -> pa.Array:
    return pa.array(np.round(prices, 8)).cast(pa.decimal128(18, 8), safe=False)


def write_ticks(ticks: Ticks, prefix: str, ticks_per_object: int) -> int:
    """Write the ticks as part-<n>.parquet objects under the prefix; return the object count."""
    s3 = filesystem()
    table = pa.table(
        {
            "timestamp": pa.array(ticks.timestamps, type=pa.timestamp("us", tz="UTC")),
            "bid": _decimal(ticks.bid),
            "ask": _decimal(ticks.ask),
        },
        schema=SCHEMA,
    )
    objects = 0
    for start in range(0, table.num_rows, ticks_per_object):
        objects += 1
        pq.write_table(
            table.slice(start, ticks_per_object),
            f"{bucket_name()}/{prefix}part-{objects:06d}.parquet",
            filesystem=s3,
            row_group_size=ROW_GROUP_SIZE,
        )
    return objects


def read_ticks(bucket: str, prefix: str) -> list[dict[str, str]]:
    """Read the objects under the prefix, in order, as JSON-ready ticks."""
    s3 = filesystem()
    infos = sorted(s3.get_file_info(fs.FileSelector(f"{bucket}/{prefix}")), key=lambda i: i.path)
    ticks = []
    for info in infos:
        for row in pq.read_table(info.path, filesystem=s3).to_pylist():
            ticks.append(
                {
                    "timestamp": row["timestamp"].isoformat().replace("+00:00", "Z"),
                    "bid": str(row["bid"]),
                    "ask": str(row["ask"]),
                }
            )
    return ticks
