from datetime import datetime
import numpy as np
import pandas as pd


class Ticks:
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
                 spread_range: list[float, float],
                 pip_position: int,
                 remove_weekend: bool
                 ):
        """

        :param trend: mean for tick distribution [pips]
        :param volatility_range: standard deviation for tick distribution [pips]
        :param spread_range: spread variation used to calculate bid price [pips]
        :param pip_position: decimal position for pip calculation
        :param remove_weekend: True to remove weekend periods, False otherwise
        """

        self._trend_pip: float = trend
        self._volatility_range_pip: float = volatility_range
        self._spread_range_pip: list[float, float] = spread_range
        self._pip_position: int = pip_position
        self._remove_weekend: bool = remove_weekend
        self._pip_factor: float = 10 ** (-pip_position)

        self._trend: float | None = None
        self._volatility_range: float | None = None
        self._spread_range: list | None = None
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
        if self._spread_range_pip[0] <= 0:
            raise ValueError(f"Spread range must be positive, got {self._spread_range_pip} instead")

    def _apply_conversions(self):
        self._convert_spread_range()
        self._convert_volatility_range()
        self._convert_trend()

    def _convert_trend(self):
        self._trend = self._trend_pip * self._pip_factor

    def _convert_volatility_range(self):
        self._volatility_range = self._volatility_range_pip * self._pip_factor

    def _convert_spread_range(self):
        self._spread_range = [self._spread_range_pip[0] * self._pip_factor,
                              self._spread_range_pip[1] * self._pip_factor]

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
        spread: np.ndarray = np.random.rand(periods)*self._pip_factor*self._spread_range_pip[1]
        spread[spread > self._spread_range[1]] = self._spread_range[1]
        spread[spread < self._spread_range[0]] = self._spread_range[0]
        self.price_time_series["spread"] = spread
        self.price_time_series["ask"] = self.price_time_series["bid"] + spread

    def compute(self,
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


class OHLC:

    def __init__(self,
                 trend: float,
                 volatility_range: float,
                 spread_range: list[float, float],
                 pip_position: int,
                 remove_weekend: bool,
                 tick_frequency: str,
                 time_frame: str):
        self._trend: float = trend
        self._volatility_range: float = volatility_range
        self._spread_range: list[float, float] = spread_range
        self._pip_position = pip_position
        self._remove_weekends = remove_weekend
        self._tick_frequency: str = tick_frequency
        self._timeframe: str = time_frame
        self.ohlc_time_series: dict = {"bid": None,
                                       "ask": None}

    def compute(self,
                date_from: datetime = None,
                date_to: datetime = None,
                init_value: float = None):
        tick = Ticks(self._trend,
                     self._volatility_range,
                     self._spread_range,
                     self._pip_position,
                     self._remove_weekends)

        tick.compute(date_from=date_from,
                     date_to=date_to,
                     frequency=self._tick_frequency,
                     init_value=init_value)

        self.ohlc_time_series["bid"] = tick.price_time_series["bid"].resample(self._timeframe).ohlc()
