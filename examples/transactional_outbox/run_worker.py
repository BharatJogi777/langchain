"""Standalone worker entry point with a safe no-op graph adapter."""
import asyncio
import os
import signal

from repository import OutboxRepository
from worker import OutboxWorker

class NoopResumer:
    async def resume(self, **kwargs):
        print("DEMO: would resume LangGraph thread", kwargs["thread_id"])

async def main():
    repository = OutboxRepository(os.environ["DATABASE_URL"])
    await repository.open()
    worker = OutboxWorker(
        repository, NoopResumer(),
        worker_id=os.getenv("WORKER_ID", "local-worker"),
    )
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.stop)
    try:
        await worker.run()
    finally:
        await repository.close()

if __name__ == "__main__":
    asyncio.run(main())
