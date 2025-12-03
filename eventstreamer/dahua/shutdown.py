import asyncio
import signal


class Shutdown:
    def __init__(self):
        self._event = asyncio.Event()

    def trigger(self):
        self._event.set()

    async def wait(self):
        await self._event.wait()


shutdown = Shutdown()


def install_signal_handlers(loop):
    """Enable graceful shutdown for Docker."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown.trigger)
        except NotImplementedError:
            # Windows does not support this
            pass
