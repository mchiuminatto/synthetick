import pandas as pd
from syntetick.syntetick import Ticks


class TestSynteticHappyPath:

    def test_gen_tick_date_range(self):
        tick_data_generator = Ticks(trend=0.01,
                                    volatility_range=10,
                                    spread_range=[1, 2],
                                    pip_position=4,
                                    remove_weekend=True)

        tick_data_generator._compute_date_range(date_from="2023-01-01 00:00:00",
                                                date_to="2023-02-01 00:00:00",
                                                frequency="1s",
                                                init_value=1.1300)
        tick_data_generator.price_time_series.to_csv("test_price_time_series.csv", index_label="date-time")

        assert tick_data_generator.price_time_series.index[0] == pd.to_datetime("2023-01-01 00:00:00")
        assert tick_data_generator.price_time_series.index[-1] == pd.to_datetime("2023-02-01 00:00:00")
        assert pd.infer_freq(tick_data_generator.price_time_series.index) == "S"
