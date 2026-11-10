import math
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime

import numpy as np

# Size of one stored object, in ticks. Part of the dataset definition (ADR-0003):
# changing it changes the ticks generated for every seed.
TICKS_PER_OBJECT = 100_000


@dataclass(frozen=True)
class TickSpec:
    date_from: datetime
    date_to: datetime
    initial_bid: float
    trend_drift: float
    volatility_sigma: float
    spread_mean: float
    spread_stdev: float
    time_unit_seconds: float
    mean_ticks: float
    dispersion: float
    min_ticks: int
    max_ticks: int


@dataclass(frozen=True)
class Ticks:
    timestamps: np.ndarray  # datetime64[us], UTC
    bid: np.ndarray
    ask: np.ndarray


def _ticks_per_unit(spec: TickSpec, units: int, rng: np.random.Generator) -> np.ndarray:
    p = spec.dispersion / (spec.dispersion + spec.mean_ticks)
    counts = rng.negative_binomial(spec.dispersion, p, units)
    outside = (counts < spec.min_ticks) | (counts > spec.max_ticks)
    while outside.any():
        counts[outside] = rng.negative_binomial(spec.dispersion, p, outside.sum())
        outside = (counts < spec.min_ticks) | (counts > spec.max_ticks)
    return counts


def generate_ticks(spec: TickSpec, seed: int) -> Ticks:
    """Arithmetic random walk with negative-binomial tick timing (SYN-41 scope)."""
    rng = np.random.default_rng(seed)
    duration = (spec.date_to - spec.date_from).total_seconds()
    tau = spec.time_unit_seconds
    units = math.ceil(duration / tau)

    counts = _ticks_per_unit(spec, units, rng)
    unit_of_tick = np.repeat(np.arange(units), counts)
    seconds = np.sort(unit_of_tick * tau + rng.random(counts.sum()) * tau)
    seconds = seconds[seconds <= duration]

    gaps = np.diff(seconds, prepend=0.0)
    steps = spec.trend_drift * gaps + spec.volatility_sigma * np.sqrt(gaps) * rng.standard_normal(len(gaps))
    bid = spec.initial_bid + np.cumsum(steps)
    spread = np.maximum(rng.normal(spec.spread_mean, spec.spread_stdev, len(gaps)), 0.0)

    start = np.datetime64(spec.date_from.replace(tzinfo=None), "us")
    timestamps = start + (seconds * 1_000_000).astype("int64").astype("timedelta64[us]")
    return Ticks(timestamps=timestamps, bid=bid, ask=bid + spread)


def generate_blocks(spec: TickSpec, seed: int) -> Iterator[Ticks]:
    """Yield the ticks of the range block by block (ADR-0003)."""
    duration = (spec.date_to - spec.date_from).total_seconds()
    tau = spec.time_unit_seconds
    units = math.ceil(duration / tau)
    units_per_block = max(1, TICKS_PER_OBJECT // spec.max_ticks)
    start = np.datetime64(spec.date_from.replace(tzinfo=None), "us")

    for block_index, first_unit in enumerate(range(0, units, units_per_block)):
        block_units = min(units_per_block, units - first_unit)
        rng = np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(block_index,)))

        counts = _ticks_per_unit(spec, block_units, rng)
        unit_of_tick = np.repeat(np.arange(first_unit, first_unit + block_units), counts)
        seconds = np.sort(unit_of_tick * tau + rng.random(counts.sum()) * tau)
        seconds = seconds[seconds <= duration]

        gaps = np.diff(seconds, prepend=first_unit * tau)
        steps = spec.trend_drift * gaps + spec.volatility_sigma * np.sqrt(gaps) * rng.standard_normal(len(gaps))
        bid = spec.initial_bid + np.cumsum(steps)
        spread = np.maximum(rng.normal(spec.spread_mean, spec.spread_stdev, len(gaps)), 0.0)

        timestamps = start + (seconds * 1_000_000).astype("int64").astype("timedelta64[us]")
        yield Ticks(timestamps=timestamps, bid=bid, ask=bid + spread)
