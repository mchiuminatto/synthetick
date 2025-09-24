from synthetick.price_feed import Worker


class TestWorker:

    def test_worker_basic_path(self):

        instrument = "EURUSD"
        volatility = 4  # pips
        first_value = 1.1300
        frequency_mean = 10  # ticks per second
        frequency_std = 3  # ticks per second
        buffer = 1000   # ticks

        worker = Worker(instrument, volatility, first_value, frequency_mean, frequency_std, buffer=buffer)
        worker.start(for_period=15)

        assert len(worker.buffer) >= 15*(frequency_mean - frequency_std)


class TestServer:

    pass