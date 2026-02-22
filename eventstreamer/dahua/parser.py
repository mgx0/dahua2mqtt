import json
import re
from .logger import ColorLogger


class MultipartEventParser:
    BOUNDARY = b"--myboundary"

    def __init__(self, ignored_events=[]):
        self.buffer = b""
        self.logger = ColorLogger(name="DAHUA_Parser", show_time=True)
        self.ignored_events = ignored_events

    def feed(self, chunk: bytes):
        self.buffer += chunk
        events = []

        while True:
            start = self.buffer.find(self.BOUNDARY)
            if start == -1:
                break

            end = self.buffer.find(self.BOUNDARY, start + len(self.BOUNDARY))
            if end == -1:
                break

            part = self.buffer[start:end]
            self.buffer = self.buffer[end:]

            event = self._parse_part(part)
            if event:
                events.append(event)

        return events

    def _parse_part(self, part: bytes):
        try:
            self.logger.debug(f"Parsing part: {part}")
            text = part.decode(errors="ignore")

            heartbeat = re.search(r"Heartbeat\r\n\r\n", text)
            if heartbeat:
                return {"code": "Heartbeat"}

            # Extract Code
            m_code = re.search(r"Code=([^;]+)", text)
            if not m_code:
                return None
            code = m_code.group(1)

            # Extract action
            m_action = re.search(r"action=([^;]+)", text)
            action = m_action.group(1) if m_action else None

            # Extract index
            m_index = re.search(r"index=([0-9]+)", text)
            index = int(m_index.group(1)) if m_index else None

            # Extract JSON block
            m_json = re.search(r"data=\{(.+)\}\s*$", text, re.S)
            if not m_json:
                return {
                    "code": code,
                    "action": action,
                    "index": index,
                    "raw": text
                }

            json_str = "{" + m_json.group(1) + "}"
            data = json.loads(json_str)

            object = {
                "code": code,
                "action": action,
                "index": index,
                "data": data
            }

            if code in self.ignored_events:
                self.logger.debug(f"Ignored event {code}: {json.dumps(object, indent=4)}")
                return None

            return object

        except Exception:
            return None
