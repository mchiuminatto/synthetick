import asyncio
import os

from app.services import tick_storage
from app.services.tick_range import process_next_tick_range


async def main() -> None:
    """Process REQUESTED tick ranges for ever. An unexpected error ends the process.

    The container restart policy (on-failure) restarts it, see ADR-0002.
    """
    tick_storage.ensure_bucket()
    poll_seconds = float(os.environ.get("WORKER_POLL_SECONDS", "5"))
    while True:
        if not await process_next_tick_range():
            await asyncio.sleep(poll_seconds)


if __name__ == "__main__":
    asyncio.run(main())
