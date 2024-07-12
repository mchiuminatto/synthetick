from synthetick.synthetick import Spread


class TestSpreadHappyPath:

    SPREAD_LOWER_BOUND_PIP: float = 0.5
    SPREAD_UPPER_BOUND_PIP: float = 3
    PIP_POSITION: float = -4

    def test_basic_path(self):

        spread = Spread(-4)
        spread.produce(self.SPREAD_LOWER_BOUND_PIP, self.SPREAD_UPPER_BOUND_PIP, 1000)
        assert spread.spread_raw.max() <= self.SPREAD_UPPER_BOUND_PIP*10**self.PIP_POSITION
        assert spread.spread_raw.min() >= self.SPREAD_LOWER_BOUND_PIP*10**self.PIP_POSITION

