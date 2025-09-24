"""
References

https://numpy.org/doc/stable/reference/random/generated/numpy.random.Generator.uniform.html

"""

from synthetick.price_time_series import PriceTimeSeries
from datetime import datetime
import numpy as np
import pandas as pd


class Ticks(PriceTimeSeries):
    """
    Produce tick time series. This is the core Class on top
    of which other price abstractions are calculated upon.

    Toi generate ticks uses a random walk approach

    # TODO: Produce ticks at random intervals
    # TODO: Improve spread calculation to remove skewed towards 1
    # TODO: Remove weekends
    """

    def __init__(self,
                 trend: float,
                 volatility_range: float,
                 spread_min: float,
                 spread_max: float,
                 pip_position: int,
                 remove_weekend: bool
                 ):
        """

        :param trend: mean for tick distribution in pips
        :param volatility_range: standard deviation for tick distribution in pips
        :param spread_min: minimum spread in pips
        :param spread_max: maximum spread in pips
        :param pip_position: Integer positive or negative indicating the pip change decimal position. If less than
        zero, means the position is at the right of the decimal; point (e.g. 0.1: -1, 0.01: -2, 0.001: -3 etc.). If
        greater than zero, means the pip position is at the right of decimal point (10: 1, 100: 2, etc.). If zero, means
        the pip position is right at the decimal point
        :param remove_weekend: True to remove weekend periods, False otherwise
        """

        self._trend_pip: float = trend
        self._volatility_range_pip: float = volatility_range
        self._spread_min: float = spread_min
        self._spread_max: float = spread_max
        self._pip_position: int = pip_position
        self._remove_weekend: bool = remove_weekend
        self._pip_factor: float = 10 ** pip_position

        self._trend: float | None = None
        self._volatility_range: float | None = None
        self._spread: Spread = Spread(pip_position)
        self.price_time_series: pd.DataFrame | None = None

        self._control_stats: dict = {"total-periods": -1,
                                     "weekend-dropped": -1,
                                     "valid-trading-periods": -1}

        self._validate_parameters()
        self._apply_conversions()

    @property
    def control_stats(self):
        return self._control_stats

    def _validate_parameters(self):
        self._validate_spread_range()
        self._validate_volatility_range()

    def _validate_spread_range(self):
        if self._spread_min <= 0:
            raise ValueError(f"Spread min needs to be grater then zero. {self._spread_min} was provided instead")
        if self._spread_min >= self._spread_max:
            raise ValueError(f"spread_max ({self._spread_max}) needs to be "
                             f"greater than spread_min ({self._spread_min})")

    def _validate_volatility_range(self):
        if self._volatility_range_pip <= 0:
            raise ValueError(f"Volatility range must be positive, got {self._volatility_range_pip} "
                             f"instead")

    def _apply_conversions(self):
        # self._convert_spread_range()
        self._convert_volatility_range()
        self._convert_trend()

    def _convert_volatility_range(self):
        self._volatility_range = self._volatility_range_pip * self._pip_factor

    def _convert_trend(self):
        self._trend = self._trend_pip * self._pip_factor

    def produce(self,
                date_from: datetime = None,
                date_to: datetime = None,
                frequency: str = None,
                init_value: float = None):
        """
        Generates tick data time series between date_from and date_to
        :param date_from: Starting date for the time series
        :param date_to: Limit date for the time series
        :param frequency: Periods frequency. More details here:
            https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#offset-aliases
        :param init_value: Initial value for the time series
        :return:
        """

        if date_from is not None and date_to is not None:
            self._compute_date_range(date_from, date_to, frequency, init_value)
        else:
            raise ValueError("Parameter combination not supported")

        if self._remove_weekend:
            self._remove_weekends()

    def _compute_date_range(self,
                            date_from: datetime,
                            date_to: datetime,
                            frequency: str,
                            init_value: float):
        date_index: pd.DatetimeIndex = pd.date_range(start=date_from,
                                                     end=date_to,
                                                     freq=frequency)
        periods = len(date_index)
        delta_p: np.ndarray = np.random.normal(self._trend, self._volatility_range, periods - 1)
        delta_p = np.append([init_value], delta_p)
        self.price_time_series = pd.DataFrame({"delta_p": delta_p}, index=date_index)
        self.price_time_series[self.PRICE_BID] = self.price_time_series["delta_p"].cumsum()

        self._spread.produce(self._spread_min, self._spread_max, periods)
        self.price_time_series[self.PRICE_SPREAD] = self._spread.spread_raw

        self.price_time_series[self.PRICE_ASK] = self.price_time_series[self.PRICE_BID] + self.price_time_series[
            self.PRICE_SPREAD]

        self._control_stats["total-periods"] = len(self.price_time_series)

    def _remove_weekends(self):

        weekend_filter = (self.price_time_series.index.weekday == self.WEEKDAY_SAT) | (
                self.price_time_series.index.weekday == self.WEEKDAY_SUN)

        self._control_stats["weekends-dropped"] = len(self.price_time_series[weekend_filter])
        self.price_time_series.drop(labels=self.price_time_series[weekend_filter].index, inplace=True)
        self._control_stats["valid-trading-periods"] = len(self.price_time_series)


class Spread:

    def __init__(self, pip_position: int):
        self._pip_factor = 10 ** pip_position
        self._spread: np.ndarray | None = None

    @property
    def spread_raw(self) -> np.ndarray:
        return self._spread * self._pip_factor

    @property
    def spread_pip(self) -> np.ndarray:
        return self._spread

    def produce(self, spread_min: float, spread_max: float, periods: int):
        if spread_min >= spread_max:
            raise ValueError(f"lower_limit ({spread_min}) needs to be less than upper_limit ({spread_max})")
        rng = np.random.default_rng()
        self._spread = rng.uniform(spread_min, spread_max, periods)


class OHLC(PriceTimeSeries):

    def __init__(self,
                 trend: float,
                 volatility_range: float,
                 spread_min: float,
                 spread_max: float,
                 pip_position: int,
                 remove_weekend: bool,
                 tick_frequency: str,
                 time_frame: str):
        """

        :param trend: Set the price time series trend: uptrend, range or downtrend. Its value is the mean of the price
        change for the next period, so if the value is greater and far from zero, the time series produced trends
        upwards. In the other hand, if the value is lower and far from zero, the time series produced trends downwards.
        Finally, if the value is close to zero, the time series produced is trendless or range bound.
        :param volatility_range: Sets the standard deviation for the nex period price change. Indirectly sets the
        price volatility.
        :param spread_min: Minimum spread value in pips
        :param spread_max: maximum spread value in pips
        :param pip_position: At which decimal position the minimum meaningful price change (pip change) occurs.
        :param remove_weekend: If true, remove weekends from produced time series
        :param tick_frequency: At which frequency tick data is produced.
        :param time_frame: OHLC time frame. More details here:
            https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#offset-aliases

        """
        self._trend: float = trend
        self._volatility_range: float = volatility_range
        self._spread_min: float = spread_min
        self._spread_max: float = spread_max
        self._pip_position = pip_position
        self._remove_weekends = remove_weekend
        self._tick_frequency: str = tick_frequency
        self._timeframe: str = time_frame

        self.ohlc_time_series: dict = {self.PRICE_BID: None,
                                       self.PRICE_ASK: None}

    def produce(self,
                date_from: datetime = None,
                date_to: datetime = None,
                init_value: float = None):
        """
        Generates OHLC data time series between date_from and date_to
        :param date_from: Starting date for the time series
        :param date_to: Limit date for the time series
        :param init_value: Initial value for the time series
        :return:
        """

        tick = Ticks(self._trend,
                     self._volatility_range,
                     self._spread_min,
                     self._spread_max,
                     self._pip_position,
                     self._remove_weekends)

        tick.produce(date_from=date_from,
                     date_to=date_to,
                     frequency=self._tick_frequency,
                     init_value=init_value)

        self.ohlc_time_series[self.PRICE_BID] = tick.price_time_series[self.PRICE_BID].resample(self._timeframe).ohlc()
        self.ohlc_time_series[self.PRICE_ASK] = tick.price_time_series[self.PRICE_ASK].resample(self._timeframe).ohlc()

        if self._remove_weekends:
            self.ohlc_time_series[self.PRICE_BID] = self._drop_weekends(self.ohlc_time_series[self.PRICE_BID])
            self.ohlc_time_series[self.PRICE_ASK] = self._drop_weekends(self.ohlc_time_series[self.PRICE_ASK])

    def _drop_weekends(self, price: pd.DataFrame) -> pd.DataFrame:

        weekdays_filter = (price.index.weekday == self.WEEKDAY_SAT) | (
                    price.index.weekday == self.WEEKDAY_SUN)
        weekend_labels = price[weekdays_filter].index
        price.drop(labels=weekend_labels, inplace=True)
        return price


