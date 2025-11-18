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
        self.on_event = on_event   # async callback
        self.url = (
            f"http://{host}:{port}/cgi-bin/eventManager.cgi"
            f"?action=attach&codes={codes}&heartbeat=10"
        )

        self.session: aiohttp.ClientSession | None = None
        self.response = None
        self.ignored_events = ignored_events or []
        self.auth = DigestAuth(username, password)
        self._running = True

    async def connect(self):
        """Perform Digest Auth handshake manually."""
        tcp_keepalive = aiohttp.TCPConnector(
            keepalive_timeout=30,
            force_close=False,
        )

        self.session = aiohttp.ClientSession(connector=tcp_keepalive)
        logger.debug(f"Connecting to Dahua event stream at {self.host}:{self.port} with username {self.username} and password {self.password}")
        logger.debug("Ignoring events: " + ", ".join(self.ignored_events))
        try:
            # FIRST REQUEST -> expected 401 challenge
            r1 = await self.session.get(self.url)
            if r1.status != 401:
                raise Exception(f"Expected HTTP 401 for Digest challenge from {self.host}:{self.port} using username {self.username}")

            logger.debug("Received 401 challenge for Digest Auth")

            # SECOND REQUEST -> with Authorization header
            auth_header = self.auth.auth_header("GET", self.url, r1)
            logger.debug(f"Sending authenticated request with Digest Auth to {self.host}:{self.port} using username {self.username}")

            r2 = await self.session.get(self.url, headers={"Authorization": auth_header})
            r2.raise_for_status()

            logger.info(f"Authenticated successfully against {self.host}:{self.port} using username {self.username}")

            self.response = r2
            return r2

        except Exception:
            await self.close()
            raise

    async def run_forever(self):
        """Main reconnect loop. Stops cleanly when .close() is called."""

        RECONNECT_MAX = 240  # seconds until forced reconnect

        while self._running:
            try:
                logger.debug("Connecting to Dahua event stream...")
                resp = await self.connect()

                # Limit _read_stream to RECONNECT_MAX seconds
                try:
                    await asyncio.wait_for(
                        self._read_stream(resp),
                        timeout=RECONNECT_MAX
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Forcing reconnect after {RECONNECT_MAX} seconds (timeout refresh)."
                    )

            except asyncio.CancelledError:
                logger.debug("run_forever() was cancelled")
                break

            except Exception as e:
                if not self._running:
                    break
                logger.info(f"[ERROR] {e}, reconnecting shortly")
                await asyncio.sleep(1)

            # small delay to avoid hammering if disconnect loop is too fast
            await asyncio.sleep(0.2)


    async def _read_stream(self, resp):
        parser = MultipartEventParser(self.ignored_events)

        async for chunk in resp.content.iter_chunked(1024):
            if not self._running:
                break

            events = parser.feed(chunk)
            for evt in events:
                await self.on_event(evt)

        logger.debug("Stream ended or stop requested in _read_stream()")

    async def close(self):
        """Gracefully stop the streaming and close HTTP session."""
        logger.warning("Closing Dahua client...")

        self._running = False

        # Cancel ongoing response stream
        if self.response:
            try:
                await self.response.release()
            except Exception:
                pass

        # Close session if it exists
        if self.session and not self.session.closed:
            try:
                await self.session.close()
            except Exception:
                pass

        logger.success("Dahua client closed")

    def get_config(self):
        """Return the MQTT configuration as a dictionary."""
        return {
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'password': self.password,
            'codes': self.codes,
            'ignored_events': self.ignored_events
        }
