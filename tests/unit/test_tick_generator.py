from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.services.tick_generator import TICKS_PER_OBJECT, TickSpec, generate_blocks, generate_ticks


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


def test_different_seeds_give_different_ticks():
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

    bid_seed_1 = np.concatenate([block.bid for block in generate_blocks(spec, seed=1)])
    bid_seed_2 = np.concatenate([block.bid for block in generate_blocks(spec, seed=2)])

    assert not (len(bid_seed_1) == len(bid_seed_2) and np.array_equal(bid_seed_1, bid_seed_2))


def test_no_block_has_more_ticks_than_ticks_per_object():
    date_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
    spec = TickSpec(
        date_from=date_from,
        date_to=date_from + timedelta(hours=1),
        initial_bid=110.0,
        trend_drift=0.0,
        volatility_sigma=0.002,
        spread_mean=0.02,
        spread_stdev=0.005,
        time_unit_seconds=1.0,
        mean_ticks=50.0,
        dispersion=4.0,
        min_ticks=0,
        max_ticks=200,
    )

    block_sizes = [len(block.timestamps) for block in generate_blocks(spec, seed=42)]

    assert sum(block_sizes) > TICKS_PER_OBJECT
    assert all(size <= TICKS_PER_OBJECT for size in block_sizes)


def test_price_carries_over_block_boundaries_without_a_jump():
    date_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
    spec = TickSpec(
        date_from=date_from,
        date_to=date_from + timedelta(hours=1),
        initial_bid=110.0,
        trend_drift=0.001,
        volatility_sigma=0.0,
        spread_mean=0.02,
        spread_stdev=0.005,
        time_unit_seconds=1.0,
        mean_ticks=50.0,
        dispersion=4.0,
        min_ticks=0,
        max_ticks=200,
    )

    blocks = list(generate_blocks(spec, seed=42))
    timestamps = np.concatenate([block.timestamps for block in blocks])
    bid = np.concatenate([block.bid for block in blocks])

    assert len(blocks) > 1
    assert np.all(np.diff(bid) >= 0)
    elapsed_seconds = (timestamps[-1] - np.datetime64("2025-01-01T00:00:00", "us")) / np.timedelta64(1, "s")
    assert bid[-1] == pytest.approx(110.0 + 0.001 * elapsed_seconds, abs=1e-6)


def test_blocks_are_one_time_unit_when_max_ticks_is_bigger_than_ticks_per_object():
    date_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
    spec = TickSpec(
        date_from=date_from,
        date_to=date_from + timedelta(seconds=5),
        initial_bid=110.0,
        trend_drift=0.0,
        volatility_sigma=0.002,
        spread_mean=0.02,
        spread_stdev=0.005,
        time_unit_seconds=1.0,
        mean_ticks=10.0,
        dispersion=4.0,
        min_ticks=0,
        max_ticks=TICKS_PER_OBJECT + 1,
    )

    blocks = list(generate_blocks(spec, seed=42))

    assert len(blocks) == 5


def test_ticks_stay_in_order_inside_date_range_with_ask_not_below_bid_across_block_boundaries():
    date_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
    spec = TickSpec(
        date_from=date_from,
        date_to=date_from + timedelta(hours=1),
        initial_bid=110.0,
        trend_drift=0.0,
        volatility_sigma=0.002,
        spread_mean=0.02,
        spread_stdev=0.005,
        time_unit_seconds=1.0,
        mean_ticks=50.0,
        dispersion=4.0,
        min_ticks=0,
        max_ticks=200,
    )

    blocks = list(generate_blocks(spec, seed=42))
    timestamps = np.concatenate([block.timestamps for block in blocks])
    bid = np.concatenate([block.bid for block in blocks])
    ask = np.concatenate([block.ask for block in blocks])

    assert len(blocks) > 1
    assert np.all(np.diff(timestamps) >= np.timedelta64(0, "us"))
    assert timestamps[0] >= np.datetime64("2025-01-01T00:00:00", "us")
    assert timestamps[-1] <= np.datetime64("2025-01-01T01:00:00", "us")
    assert np.all(ask >= bid)


def test_a_range_shorter_than_one_block_gives_a_single_block_inside_the_range():
    date_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
    spec = TickSpec(
        date_from=date_from,
        date_to=date_from + timedelta(seconds=5),
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

    blocks = list(generate_blocks(spec, seed=42))

    assert len(blocks) == 1
    assert len(blocks[0].timestamps) > 0
    assert blocks[0].timestamps[0] >= np.datetime64("2025-01-01T00:00:00", "us")
    assert blocks[0].timestamps[-1] <= np.datetime64("2025-01-01T00:00:05", "us")


def test_ticks_after_date_to_in_the_last_partial_time_unit_are_dropped():
    date_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
    spec = TickSpec(
        date_from=date_from,
        date_to=date_from + timedelta(seconds=2.5),
        initial_bid=110.0,
        trend_drift=0.0,
        volatility_sigma=0.002,
        spread_mean=0.02,
        spread_stdev=0.005,
        time_unit_seconds=1.0,
        mean_ticks=200.0,
        dispersion=4.0,
        min_ticks=0,
        max_ticks=1000,
    )

    blocks = list(generate_blocks(spec, seed=42))
    timestamps = np.concatenate([block.timestamps for block in blocks])

    assert timestamps[-1] <= np.datetime64("2025-01-01T00:00:02.500000", "us")
    assert timestamps[-1] > np.datetime64("2025-01-01T00:00:02.000000", "us")


def test_a_fixed_seed_gives_known_first_ticks():
    # Golden values recorded once from the ADR-0003 scheme (seed 42, one block).
    # If this fails, the dataset changed for every seed: only update it on purpose.
    date_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
    spec = TickSpec(
        date_from=date_from,
        date_to=date_from + timedelta(seconds=5),
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

    blocks = list(generate_blocks(spec, seed=42))
    first = blocks[0]

    assert len(blocks) == 1
    assert len(first.timestamps) == 43
    assert [str(t) for t in first.timestamps[:3]] == [
        "2025-01-01T00:00:00.017881",
        "2025-01-01T00:00:00.037252",
        "2025-01-01T00:00:00.058150",
    ]
    assert first.bid[:3] == pytest.approx([109.99963580768191, 109.99971301635375, 109.99980167871371], abs=1e-9)
    assert first.ask[:3] == pytest.approx([110.0189382280061, 110.02075256155533, 110.01715608750946], abs=1e-9)
