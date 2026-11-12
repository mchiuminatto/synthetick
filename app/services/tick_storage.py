import os
from collections.abc import Iterable

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


def write_ticks(ticks: Ticks, prefix: str, ticks_per_object: int, first_part: int = 1) -> int:
    """Write the ticks as part-<n>.parquet objects under the prefix; return the object count.

    The first object is numbered first_part, so a range can be written in several calls.
    """
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
            f"{bucket_name()}/{prefix}part-{first_part + objects - 1:06d}.parquet",
            filesystem=s3,
            row_group_size=ROW_GROUP_SIZE,
        )
    return objects


def _join(pieces: list[Ticks]) -> Ticks:
    return Ticks(
        timestamps=np.concatenate([piece.timestamps for piece in pieces]),
        bid=np.concatenate([piece.bid for piece in pieces]),
        ask=np.concatenate([piece.ask for piece in pieces]),
    )


def _slice(ticks: Ticks, start: int, stop: int) -> Ticks:
    return Ticks(ticks.timestamps[start:stop], ticks.bid[start:stop], ticks.ask[start:stop])


def write_blocks(blocks: Iterable[Ticks], prefix: str, ticks_per_object: int) -> None:
    """Write a stream of blocks as objects of exactly ticks_per_object ticks (the last may be shorter)."""
    pending: list[Ticks] = []
    pending_rows = 0
    part = 1
    for block in blocks:
        pending.append(block)
        pending_rows += len(block.timestamps)
        while pending_rows >= ticks_per_object:
            joined = _join(pending)
            part += write_ticks(_slice(joined, 0, ticks_per_object), prefix, ticks_per_object, first_part=part)
            rest = _slice(joined, ticks_per_object, pending_rows)
            pending = [rest]
            pending_rows = len(rest.timestamps)
    if pending_rows > 0:
        write_ticks(_join(pending), prefix, ticks_per_object, first_part=part)


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
