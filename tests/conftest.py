import os
from pathlib import Path

import psycopg
import pytest
from pyarrow import fs
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parent.parent


def _connect(dbname: str) -> psycopg.Connection:
    return psycopg.connect(
        dbname=dbname,
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        autocommit=True,
    )


@pytest.fixture(scope="session")
def test_database() -> str:
    """Recreate <POSTGRES_DB>_test, migrate it, and point the app at it."""
    name = f"{os.environ['POSTGRES_DB']}_test"
    assert name.endswith("_test")
    with _connect("postgres") as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.execute(f'CREATE DATABASE "{name}"')
    os.environ["POSTGRES_DB"] = name
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    return name


@pytest.fixture
def db(test_database: str):
    """A connection to the test database, with the tables empty before each test."""
    with _connect(test_database) as connection:
        connection.execute("TRUNCATE tick_range, domain_event")
        yield connection


@pytest.fixture
def valid_request() -> dict:
    return {
        "instrument": "USDJPY",
        "date_from": "2025-01-01T00:00:00Z",
        "date_to": "2025-01-02T00:00:00Z",
        "min_price": "100",
        "max_price": "200",
        "initial_bid": "110",
        "volatility_sigma": 0.002,
        "spread_mean": 0.02,
        "spread_stdev": 0.005,
        "time_unit_seconds": 1,
        "mean_ticks": 10,
        "dispersion": 4,
        "min_ticks": 0,
        "max_ticks": 50,
    }


@pytest.fixture
def invalid_request(valid_request: dict):
    """Build a request that is valid except for the given fields, e.g. invalid_request(max_ticks=-1)."""

    def build(**overrides) -> dict:
        unknown = set(overrides) - set(valid_request)
        assert not unknown, f"not request fields: {unknown}"
        return {**valid_request, **overrides}

    return build


@pytest.fixture(scope="session")
def s3() -> fs.S3FileSystem:
    """The MinIO test bucket (created if missing), reached with the Compose credentials."""
    os.environ["MINIO_BUCKET"] = "synthetick-test"
    filesystem = fs.S3FileSystem(
        access_key=os.environ["MINIO_ROOT_USER"],
        secret_key=os.environ["MINIO_ROOT_PASSWORD"],
        endpoint_override=os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
        scheme="http",
        allow_bucket_creation=True,
    )
    filesystem.create_dir("synthetick-test")
    return filesystem


@pytest.fixture
def bucket(s3: fs.S3FileSystem) -> str:
    """The test bucket name, with no objects in it before each test."""
    s3.delete_dir_contents("synthetick-test", accept_root_dir=True)
    return "synthetick-test"
