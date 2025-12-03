import sys
import threading
from datetime import datetime


class LoggerConfig:
    level = "INFO"

    LEVELS = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "ERROR": 40,
    }

    @classmethod
    def set_level(cls, level):
        cls.level = level.upper()

    @classmethod
    def enabled(cls, msg_level):
        return cls.LEVELS[msg_level] >= cls.LEVELS[cls.level]


class ColorLogger:
    COLORS = {
        "RESET": "\033[0m",
        "BOLD": "\033[1m",

        "INFO": "\033[94m",
        "DEBUG": "\033[90m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "SUCCESS": "\033[92m",
    }

    def __init__(self, name="LOG", show_time=True):
        self.name = name
        self.show_time = show_time
        self._lock = threading.Lock()

    def _ts(self):
        if not self.show_time:
            return ""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _emit(self, level, msg, color):
        if not LoggerConfig.enabled(level):
            return

        prefix = f"[{self._ts()}] [{self.name}] [{level}]"
        with self._lock:
            print(f"{color}{prefix}{self.COLORS['RESET']} {msg}", flush=True)

    def info(self, msg): self._emit("INFO", msg, self.COLORS["INFO"])
    def debug(self, msg): self._emit("DEBUG", msg, self.COLORS["DEBUG"])
    def warning(self, msg): self._emit("WARNING", msg, self.COLORS["WARNING"])
    def error(self, msg): self._emit("ERROR", msg, self.COLORS["ERROR"])
    def success(self, msg): self._emit("INFO", msg, self.COLORS["SUCCESS"])
