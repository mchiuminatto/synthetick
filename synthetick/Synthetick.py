"""
References

https://numpy.org/doc/stable/reference/random/generated/numpy.random.Generator.uniform.html

"""

from synthetick.PriceTimeSeries import PriceTimeSeries
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

        self._validate_parameters()
        self._apply_conversions()

    def _validate_parameters(self):
        self._validate_spread_range()
        self._validate_volatility_range()

    def _validate_volatility_range(self):
        if self._volatility_range_pip <= 0:
            raise ValueError(f"Volatility range must be positive, got {self._volatility_range_pip} "
                             f"instead")

    def _validate_spread_range(self):
        if self._spread_min <= 0:
            raise ValueError(f"Spread min needs to be grater then zero. {self._spread_min} was provided instead")
        if self._spread_min >= self._spread_max:
            raise ValueError(f"spread_max ({self._spread_max}) needs to be "
                             f"greater than spread_min ({self._spread_min})")

    def _apply_conversions(self):
        # self._convert_spread_range()
        self._convert_volatility_range()
        self._convert_trend()

    def _convert_trend(self):
        self._trend = self._trend_pip * self._pip_factor

    def _convert_volatility_range(self):
        self._volatility_range = self._volatility_range_pip * self._pip_factor

    # def _convert_spread_range(self):
    #     self._spread_range = [self._spread_range_pip[0] * self._pip_factor,
    #                           self._spread_range_pip[1] * self._pip_factor]
    #     self._spread_lower_bound: float = self._spread_range[0]
    #     self._spread_upper_bound: float = self._spread_range[1]

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
        self.price_time_series["bid"] = self.price_time_series["delta_p"].cumsum()

        self._spread.produce(self._spread_min, self._spread_max, periods)
        self.price_time_series["spread"] = self._spread.spread_raw

        self.price_time_series["ask"] = self.price_time_series["bid"] + self.price_time_series["spread"]

    def _calculate_spread(self, lower_limit: float, upper_limit: float, periods: int):

        spread_mean = (lower_limit + upper_limit)/2
        spread_std = spread_mean - lower_limit
        spread = np.random.normal(spread_mean, spread_std, periods)
        self._spread = np.clip(spread, lower_limit, upper_limit)

    def produce(self,
                date_from: datetime = None,
                date_to: datetime = None,
                frequency: str = None,
                init_value: float = None):
        """
        Generates tick data time series between date_from and date_to
        :param date_from: Starting date for the time series
        :param date_to: Limit date for the time series
        :param frequency: Periods frequency
        :param init_value: Initial value for the time series
        :return:
        """

        if date_from is not None and date_to is not None:
            self._compute_date_range(date_from, date_to, frequency, init_value)
        else:
            raise ValueError("Parameter combination not supported")


class Spread:

    def __init__(self, pip_position: int):
        self._pip_factor = 10**pip_position
        self._spread: np.ndarray | None = None

    @property
    def spread_raw(self) -> np.ndarray:
        return self._spread*self._pip_factor

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
        self._trend: float = trend
        self._volatility_range: float = volatility_range
        self._spread_min: float = spread_min
        self._spread_max: float = spread_max
        self._pip_position = pip_position
        self._remove_weekends = remove_weekend
        self._tick_frequency: str = tick_frequency
        self._timeframe: str = time_frame
        self.ohlc_time_series: dict = {"bid": None,
                                       "ask": None}

    def produce(self,
                date_from: datetime = None,
                date_to: datetime = None,
                init_value: float = None):
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

        self.ohlc_time_series["bid"] = tick.price_time_series["bid"].resample(self._timeframe).ohlc()
