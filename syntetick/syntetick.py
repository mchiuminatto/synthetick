from datetime import datetime
import numpy as np
import scipy
import pandas as pd


class Ticks:

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
        self._spread_range: float | None = None
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
                              self._spread_range_pip[0] * self._pip_factor]

    def _compute_date_range(self,
                            date_from: datetime,
                            date_to: datetime,
                            frequency: str,
                            init_value: float):
        date_index: pd.DatetimeIndex = pd.date_range(start=date_from,
                                                     end=date_to,
                                                     freq=frequency)

        delta_p: np.ndarray = np.random.normal(self._trend, self._volatility_range, len(date_index) - 1)
        delta_p = np.append([init_value], delta_p)
        price: np.ndarray = np.zeros(len(delta_p))
        self.price_time_series = pd.DataFrame({"delta_p": delta_p}, index=date_index)
        self.price_time_series["bid"] = self.price_time_series["delta_p"].cumsum()


class OHLC:
    def __init(self,
               trend: float,
               volatility_range: float,
               spread_range: list[float, float],
               pip_position: int,
               remove_weekend: bool,
               time_frame: str):
        self._trend = trend,
        self._volatility_range = volatility_range
        self._spread_range = spread_range
        self._pip_position = pip_position
        self._remove_weekends = remove_weekend

    def compute(self):
        tick = Ticks(self.trend,
                     self.volatility,
                     self.spread_range,
                     self.pip_position,
                     self.remove_weekends)

        tick.compute()

        ohlc = tick["bid"].resample("1h").ohlc()
