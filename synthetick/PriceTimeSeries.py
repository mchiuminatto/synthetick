import abc
from abc import ABC


class PriceTimeSeries(ABC):

    @abc.abstractmethod
    def produce(self, *args, **kwargs):
        ...

