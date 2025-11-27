import asyncio
import aiohttp
from .digest import DigestAuth
from .parser import MultipartEventParser
from .logger import ColorLogger

logger = ColorLogger(name="DAHUA_Client", show_time=True)


class DahuaEventClient:
    def __init__(
        self,
        host,
        port,
        username,
        password,
        codes,
        on_event,
        ignored_events=None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.codes = codes
        self.on_event = on_event  # async callback

        # keepalive + heartbeat improves long stability
        self.url = (
            f"http://{host}:{port}/cgi-bin/eventManager.cgi"
            f"?action=attach&codes={codes}&heartbeat=10"
        )

        self.session: aiohttp.ClientSession | None = None
        self.response = None
        self._read_task: asyncio.Task | None = None

        self.ignored_events = ignored_events or []
        self.auth = DigestAuth(username, password)
        self._running = True

    # ----------------------------------------------------------------------

    async def connect(self):
        """Perform Digest Auth handshake manually."""
        tcp_keepalive = aiohttp.TCPConnector(
            keepalive_timeout=30,
            force_close=False,
        )

        self.session = aiohttp.ClientSession(connector=tcp_keepalive)
        logger.debug(
            f"Connecting to Dahua event stream at {self.host}:{self.port} "
            f"using username '{self.username}'"
        )
        logger.debug("Ignored events: " + ", ".join(self.ignored_events))

        try:
            # First 401 challenge
            r1 = await self.session.get(self.url)
            if r1.status != 401:
                raise Exception(
                    f"Expected HTTP 401 challenge from {self.host}:{self.port}"
                )

            logger.debug("Received 401 challenge for Digest Auth")
            auth_header = self.auth.auth_header("GET", self.url, r1)

            # Second request with digest response
            logger.debug("Sending authenticated request to Dahua")
            r2 = await self.session.get(self.url, headers={"Authorization": auth_header})
            r2.raise_for_status()

            logger.info(
                f"Authenticated successfully against {self.host}:{self.port} "
                f"using username '{self.username}'"
            )

            self.response = r2
            return r2

        except Exception:
            await self.close()
            raise

    # ----------------------------------------------------------------------

    async def run_forever(self):
        """Main reconnect loop. Stops cleanly when .close() is called."""
        RECONNECT_MAX = 240  # Forced reconnect interval

        while self._running:
            if not self._running:
                break   # 🔥 Prevent hang
            try:
                logger.debug("Connecting to Dahua event stream...")
                resp = await self.connect()
                if not self._running:
                    break

                # Launch _read_stream as task
                self._read_task = asyncio.create_task(self._read_stream(resp))

                # Wait until timeout or until stream ends
                try:
                    await asyncio.wait_for(self._read_task, timeout=RECONNECT_MAX)
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Forcing reconnect after {RECONNECT_MAX} seconds (timeout refresh)."
                    )
                    # Cancel the task safely
                    if self._read_task:
                        self._read_task.cancel()
                        try:
                            await self._read_task
                        except asyncio.CancelledError:
                            pass

                except asyncio.CancelledError:
                    if not self._running:
                        logger.debug("run_forever exiting after cancellation")
                        break   # 🔥 stop loop immediately

            except asyncio.CancelledError:
                logger.debug("run_forever() was cancelled")
                break

            except Exception as e:
                if not self._running:
                    break
                logger.info(f"[ERROR] {e}, reconnecting shortly")
                await asyncio.sleep(1)

            await asyncio.sleep(0.2)
            if not self._running:
                break

    # ----------------------------------------------------------------------

    async def _read_stream(self, resp):
        """Read the multipart stream safely."""
        parser = MultipartEventParser(self.ignored_events)

        try:
            async for chunk in resp.content.iter_chunked(1024):

                # Shutdown requested
                if not self._running:
                    logger.debug("Stop requested; breaking stream read")
                    return

                # Silent EOF (VERY common in Docker NAT layer)
                if not chunk:
                    logger.warning("EOF detected from Dahua stream (empty chunk)")
                    return

                events = parser.feed(chunk)
                for evt in events:
                    await self.on_event(evt)

        except asyncio.CancelledError:
            logger.debug("_read_stream() was cancelled (forced reconnect)")
            return

        except (
            aiohttp.ClientConnectionError,
            aiohttp.ServerDisconnectedError,
            aiohttp.ClientPayloadError,
            asyncio.IncompleteReadError,
        ) as e:
            logger.warning(f"Dahua stream disconnected unexpectedly: {e}")
            return

        except Exception as e:
            logger.error(f"Unhandled exception in _read_stream(): {e}")
            return

        logger.debug("Stream ended naturally in _read_stream()")

    # ----------------------------------------------------------------------

    async def close(self):
        """Gracefully stop the streaming and close HTTP session."""
        logger.warning("Closing Dahua client...")

        self._running = False

        # Cancel the read task if it exists
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        # Release response cleanly
        if self.response:
            try:
                await self.response.release()
            except Exception:
                pass

        # Close session last (never before read task ends)
        if self.session and not self.session.closed:
            try:
                await self.session.close()
            except Exception:
                pass

        logger.info("Dahua client closed")

    # ----------------------------------------------------------------------

    def get_config(self):
        """Return the configuration as a dictionary."""
        return {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "codes": self.codes,
            "ignored_events": self.ignored_events,
        }
