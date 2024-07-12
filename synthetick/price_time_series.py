import abc
from abc import ABC


class PriceTimeSeries(ABC):

    WEEKDAY_MON: int = 0
    WEEKDAY_TUE: int = 1
    WEEKDAY_WED: int = 2
    WEEKDAY_THU: int = 3
    WEEKDAY_FRI: int = 4
    WEEKDAY_SAT: int = 5
    WEEKDAY_SUN: int = 6

    PRICE_BID: str = "bid"
    PRICE_ASK: str = "ask"
    PRICE_SPREAD: str = "spread"

    @abc.abstractmethod
    def produce(self, *args, **kwargs):
        ...

