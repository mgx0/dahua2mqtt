# event_tracker.py
import time
import threading
from .logger import ColorLogger

LAST_EVENT_FILE = "/tmp/dahua_last_event.tmp"

logger = ColorLogger(name="EventTracker", show_time=True)
_lock = threading.Lock()


def update_event_time():
    with _lock:
        _last_event_time = str(int(time.time()))
    # persist for healthcheck script
    with open(LAST_EVENT_FILE, "w") as f:
        f.write(_last_event_time)
        logger.debug(f"Updated last event time to {_last_event_time}")
