import abc
import logging
from dataclasses import dataclass
from datetime import timedelta, datetime
from time import sleep
import numpy as np


@dataclass
class TickEmissionSpecification:
    instrument: str
    min_change_dec_position: int
    volatility: float
    trend: float
    first_value: float
    tick_frequency_mean: int  # ticks per second
    tick_frequency_std: int  # ticks per second
    spread_min: float
    spread_max: float
    ticks_to_emit: int | None = None
    emit_for_period: timedelta | None = None


class Emitter(abc.ABC):

    def __init__(self, emission_spec: TickEmissionSpecification,
                 dry_run: bool = True):
        self._buffer: list = []
        self._emission_spec = emission_spec
        self._dry_run: bool = dry_run

    @abc.abstractmethod
    def emit(self):
        ...

    @property
    def buffer(self):
        return self._buffer

    def gen_tick(self):

        # generate spread
        rng = np.random.default_rng()
        spread = rng.uniform(self._emission_spec.spread_min,
                             self._emission_spec.spread_max,
                             1).round(self._emission_spec.min_change_dec_position + 1)[0]

        price_change: float = 0

        if len(self._buffer) == 0:
            new_bid = self._emission_spec.first_value
        else:
            price_change = np.random.normal(self._emission_spec.trend,
                                            self._emission_spec.volatility,
                                            1).round(self._emission_spec.min_change_dec_position + 1)[0]
            new_bid = round((self.buffer[-1]["bid"] + price_change), self._emission_spec.min_change_dec_position + 1)

        new_ask = new_bid + spread

        tick = {
            "date-time": datetime.now(),
            "bid": new_bid,
            "ask": new_ask,
            "price-change": price_change,
            "spread": spread
        }

        self._buffer.append(tick)


class TickAmountEmitter(Emitter):

    def __init__(self,
                 emission_spec: TickEmissionSpecification,
                 dry_run: bool = True):

        super().__init__(emission_spec,
                         dry_run=dry_run)

    def emit(self):

        for _ in range(self._emission_spec.ticks_to_emit):
            self.gen_tick()

            if not self._dry_run:
                # send ticks to socket server
                pass

            frequency: float = np.random.normal(self._emission_spec.tick_frequency_mean,
                                                self._emission_spec.tick_frequency_std,
                                                1)[0]
            period: float = 1 / frequency
            sleep(period)


# TODO: Todo next
class TimePeriodEmitter(Emitter):
    def __init__(self, emission_spec: TickEmissionSpecification,
                 dry_run: bool = True):
        super().__init__(emission_spec,
                         dry_run=dry_run)

    def emit(self):
        start_time = datetime.now()
        while datetime.now() - start_time <= self._emission_spec.emit_for_period:
            # TODO: refactor repeated code
            self.gen_tick()
            if not self._dry_run:
                # send tick to socket server
                pass
            frequency: float = np.random.normal(self._emission_spec.tick_frequency_mean,
                                                self._emission_spec.tick_frequency_std,
                                                1)[0]
            period: float = 1 / frequency
            sleep(period)


class EmitterFactory:
    def __call__(self, emission_spec: TickEmissionSpecification,
                 dry_run: bool = True):

        if emission_spec.ticks_to_emit and emission_spec.emit_for_period:
            logging.warning("ticks_to_emit and emmit_for_time were specified, will ticks_to_emit will be assumed")
        if not emission_spec.ticks_to_emit and not emission_spec.emit_for_period:
            logging.error("Neither ticks_to_emit nor emmit_for_period were specified. One MUST be passed")
            raise ValueError("Neither ticks_to_emit nor emmit_for_time were specified. One MUST be passed")

        if emission_spec.ticks_to_emit is not None:
            return TickAmountEmitter(emission_spec,
                                     dry_run=dry_run)

        if emission_spec.emit_for_period is not None:
            return TimePeriodEmitter(emission_spec,
                                     dry_run=dry_run)
