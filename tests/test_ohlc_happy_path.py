
from datetime import datetime
import pandas as pd
from synthetick.synthetick import OHLC


DATE_FROM: datetime = pd.to_datetime("2023-01-01 00:00:00")
DATE_TO: datetime = pd.to_datetime("2023-02-01 00:00:00")


class TestOHLCHappyPath:

    """
    Test OHLC Class
    """
    def test_ohlc_basic(self):
        ohlc: OHLC = OHLC(trend=0.001,
                          volatility_range=10,
                          spread_range=[1, 2],
                          pip_position=4,
                          remove_weekend=True,
                          tick_frequency="1s",
                          time_frame="H")

        ohlc.compute(date_from=DATE_FROM, date_to=DATE_TO, init_value=1.1300)
        assert pd.infer_freq(ohlc.ohlc_time_series["bid"].index) == "H"
        assert ohlc.ohlc_time_series["bid"].index[0] == DATE_FROM
        assert ohlc.ohlc_time_series["bid"].index[-1] == DATE_TO

        ohlc.ohlc_time_series["bid"].to_csv("ohlc_bid_1h.csv", index_label="date-time")



