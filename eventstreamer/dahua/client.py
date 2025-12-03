import asyncio
import aiohttp
from .digest import DigestAuth
from .parser import MultipartEventParser
from .logger import ColorLogger
from .event_tracker import update_event_time

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
        self._shutting_down = False
        self._reconnect_requested = False

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
            await self.shutdown()
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
                        self._reconnect_requested = True
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

    async def _read_stream(self, resp): # this goes infinite when not running in a container
        parser = MultipartEventParser(self.ignored_events)

        try:
            async for chunk in resp.content.iter_chunked(1024):
                if not self._running:
                    logger.debug("Stop requested; breaking stream read")
                    return

                if not chunk:
                    logger.warning("EOF detected from Dahua stream (empty chunk)")
                    return

                events = parser.feed(chunk)
                for evt in events:
                    if evt.get("code") == "Heartbeat":
                        logger.debug("Heartbeat received")
                    else:
                        await self.on_event(evt)
                    update_event_time()

        except asyncio.CancelledError:
            if self._shutting_down:
                logger.debug("_read_stream() cancelled due to shutdown")
                self.shutdown()
                self._shutting_down = False # probably unreachable

            if self._reconnect_requested:
                logger.debug("_read_stream() reconnecting due to MAX time limit")
                await self.stop()
                self._reconnect_requested = False
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

        finally:
            # 🔥 ALWAYS release the response
            try:
                await resp.release()
            except Exception:
                pass


    async def stop(self):
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        if self.response:
            try:
                await self.response.release()
            except:
                pass
            self.response = None

        if self.session:
            try:
                await self.session.close()
            except:
                pass
            self.session = None

        logger.info("STOP: Dahua client stopped")


    # ----------------------------------------------------------------------

    async def shutdown(self):
        logger.warning("Closing Dahua client...")

        self._running = False

        await self.stop()
        logger.info("Dahua client shut down.")

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
