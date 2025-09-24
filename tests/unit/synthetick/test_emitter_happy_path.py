from datetime import timedelta

import pandas as pd

from synthetick.emitter import EmitterFactory, Emitter, TickEmissionSpecification

FIRST_VALUE: float = 1.13000
TREND: float = 0.0001
VOLATILITY: float = 0.0005
TICKS_TO_EMIT: int = 1000
TICK_FREQUENCY_MEAN: int = 100
TICK_FREQUENCY_STD: int = 10
INSTRUMENT: str = "EURUSD"
SPREAD_MIN: float = 0.0001
SPREAD_MAX: float = 0.0005
MIN_CHANGE_DEC_POSITION: int = 4


class TestEmitter:

    def test_generate_tick_first_tick(self):

        tick_emission_spec = TickEmissionSpecification(instrument=INSTRUMENT,
                                                       volatility=VOLATILITY,
                                                       min_change_dec_position=MIN_CHANGE_DEC_POSITION,
                                                       trend=TREND,
                                                       first_value=FIRST_VALUE,
                                                       tick_frequency_mean=TICK_FREQUENCY_MEAN,
                                                       tick_frequency_std=TICK_FREQUENCY_STD,
                                                       spread_min=SPREAD_MIN,
                                                       spread_max=SPREAD_MAX,
                                                       ticks_to_emit=TICKS_TO_EMIT)
        emitter = EmitterFactory()(tick_emission_spec)
        emitter.gen_tick()
        tick = emitter.buffer[-1]

        assert tick["bid"] == FIRST_VALUE

    def test_generate_tick_two_ticks(self):

        tick_emission_spec = TickEmissionSpecification(instrument=INSTRUMENT,
                                                       volatility=VOLATILITY,
                                                       min_change_dec_position=MIN_CHANGE_DEC_POSITION,
                                                       trend=TREND,
                                                       first_value=FIRST_VALUE,
                                                       tick_frequency_mean=TICK_FREQUENCY_MEAN,
                                                       tick_frequency_std=TICK_FREQUENCY_STD,
                                                       spread_min=SPREAD_MIN,
                                                       spread_max=SPREAD_MAX,
                                                       ticks_to_emit=TICKS_TO_EMIT)
        emitter = EmitterFactory()(tick_emission_spec)
        emitter.gen_tick()
        emitter.gen_tick()
        tick_i = emitter.buffer[-1]
        tick_i_1 = emitter.buffer[-2]

        new_bid = tick_i_1["bid"] + tick_i["price-change"]
        assert tick_i["bid"] == new_bid

    def test_emmit_n_ticks(self):

        tick_emission_spec = TickEmissionSpecification(instrument=INSTRUMENT,
                                                       volatility=VOLATILITY,
                                                       min_change_dec_position=MIN_CHANGE_DEC_POSITION,
                                                       trend=TREND,
                                                       first_value=FIRST_VALUE,
                                                       tick_frequency_mean=TICK_FREQUENCY_MEAN,
                                                       tick_frequency_std=TICK_FREQUENCY_STD,
                                                       spread_min=SPREAD_MIN,
                                                       spread_max=SPREAD_MAX,
                                                       ticks_to_emit=TICKS_TO_EMIT)
        emitter = EmitterFactory()(tick_emission_spec)

        emitter.emit()

        df = pd.DataFrame(emitter.buffer)
        df.to_csv("test_tick_emit_1000.csv")

        assert len(emitter.buffer) == TICKS_TO_EMIT
        assert df["price-change"].mean() - TREND <= 0.0001
        assert df["price-change"].std() - VOLATILITY <= 0.0001

        # TODO: Add check for tick frequency

    def test_emmit_during_time(self):

        emission_period = timedelta(seconds=10)
        tick_emission_spec = TickEmissionSpecification(instrument=INSTRUMENT,
                                                       volatility=VOLATILITY,
                                                       min_change_dec_position=MIN_CHANGE_DEC_POSITION,
                                                       trend=TREND,
                                                       first_value=FIRST_VALUE,
                                                       tick_frequency_mean=TICK_FREQUENCY_MEAN,
                                                       tick_frequency_std=TICK_FREQUENCY_STD,
                                                       spread_min=SPREAD_MIN,
                                                       spread_max=SPREAD_MAX,
                                                       emit_for_period=emission_period)

        emitter = EmitterFactory()(tick_emission_spec)

        emitter.emit()

        df = pd.DataFrame(emitter.buffer)
        df.to_csv("test_tick_emit_20_seconds.csv")

        start_time = emitter.buffer[0]["date-time"]
        end_time = emitter.buffer[-1]["date-time"]
        time_delta = end_time - start_time

        assert time_delta.seconds >= 10
        assert df["bid"].mean() - VOLATILITY <= 0.0001

        # TODO: Add check for tick frequency
