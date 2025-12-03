import asyncio
import json
import paho.mqtt.client as mqtt
from .logger import ColorLogger


logger = ColorLogger(name="DAHUA_MQTT_Sender", show_time=True)

class MqttSender:
    def __init__(self, host, port, topic):
        self.host = host
        self.port = port
        self.topic = topic
        self.client = mqtt.Client()

    async def connect(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.client.connect, self.host, self.port)
        self.client.loop_start()
        logger.info(f"MQTT connected -> {self.host}:{self.port}")

    async def publish_event(self, event: dict):
        logger.info(f"Publishing event to MQTT: {event['code']}")
        payload = json.dumps(event, ensure_ascii=False)
        self.client.publish(self.topic, payload)

    async def close(self):
        self.client.loop_stop()
        self.client.disconnect()

    def get_config(self):
        """Return the MQTT configuration as a dictionary."""
        return {
            'host': self.host,
            'port': self.port,
            'topic': self.topic
        }