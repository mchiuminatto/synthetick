import asyncio
from multiprocessing import Process
from tests.test_utils import socket_server
import logging


def start_socket_server():
    asyncio.run(socket_server.main())


class TestWorker:

    def test_one_worker(self):
        server_process = Process(target=start_socket_server)
        server_process.start()
        logging.info("Server started")

        # throw worker here

        server_process.join()
        server_process.kill()

