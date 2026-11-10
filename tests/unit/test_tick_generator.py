from datetime import datetime, timedelta, timezone

import numpy as np

from app.services.tick_generator import TickSpec, generate_blocks, generate_ticks


def test_generated_ticks_are_in_time_order_inside_date_range_with_ask_not_below_bid():
    date_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
    date_to = date_from + timedelta(minutes=1)
    spec = TickSpec(
        date_from=date_from,
        date_to=date_to,
        initial_bid=110.0,
        trend_drift=0.0,
        volatility_sigma=0.002,
        spread_mean=0.02,
        spread_stdev=0.005,
        time_unit_seconds=1.0,
        mean_ticks=10.0,
        dispersion=4.0,
        min_ticks=0,
        max_ticks=50,
    )

    ticks = generate_ticks(spec, seed=42)

    assert len(ticks.timestamps) > 0
    assert np.all(np.diff(ticks.timestamps) >= np.timedelta64(0, "us"))
    assert ticks.timestamps[0] >= np.datetime64("2025-01-01T00:00:00", "us")
    assert ticks.timestamps[-1] <= np.datetime64("2025-01-01T00:01:00", "us")
    assert np.all(ticks.ask >= ticks.bid)


def test_same_seed_and_spec_give_identical_ticks_on_repeated_runs():
    date_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
    spec = TickSpec(
        date_from=date_from,
        date_to=date_from + timedelta(minutes=1),
        initial_bid=110.0,
        trend_drift=0.0,
        volatility_sigma=0.002,
        spread_mean=0.02,
        spread_stdev=0.005,
        time_unit_seconds=1.0,
        mean_ticks=10.0,
        dispersion=4.0,
        min_ticks=0,
        max_ticks=50,
    )

    first = list(generate_blocks(spec, seed=42))
    second = list(generate_blocks(spec, seed=42))

    assert len(first) > 0
    assert len(first) == len(second)
    for block_a, block_b in zip(first, second):
        assert np.array_equal(block_a.timestamps, block_b.timestamps)
        assert np.array_equal(block_a.bid, block_b.bid)
        assert np.array_equal(block_a.ask, block_b.ask)
