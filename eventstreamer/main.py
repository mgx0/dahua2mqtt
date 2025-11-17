import asyncio
import json
import os

from dahua.shutdown import shutdown, install_signal_handlers
from dahua.client import DahuaEventClient
from dahua.mqtt_sender import MqttSender
from dahua.logger import ColorLogger, LoggerConfig


log = ColorLogger("MAIN")



async def main():
    # Install signal handlers using the *running* loop
    loop = asyncio.get_running_loop()
    install_signal_handlers(loop)

    with open("settings.json") as f:
        config = json.load(f)

    LoggerConfig.set_level(config.get("log_level", "INFO"))
    # --- Initialize MQTT ---
    mqtt = MqttSender(
        host=config.get("mqtt", {}).get("host", "localhost"),
        port=config.get("mqtt", {}).get("port", 1883),
        topic=config.get("mqtt", {}).get("topic", "dahua/events"),
    )

    # --- Initialize Dahua Client ---
    client = DahuaEventClient(
        host=config.get("dahua").get("host"),
        port=config.get("dahua").get("port"),
        username=config.get("dahua").get("username"),
        password=config.get("dahua").get("password"),
        codes=config.get("dahua").get("codes"),
        on_event=mqtt.publish_event,
        ignored_events=config.get("ignored_events", []),
    )

    log.debug(f"Dahua Client Config: {json.dumps(client.get_config(), indent=4)}")
    log.debug(f"MQTT Config: {json.dumps(mqtt.get_config(), indent=4)}")

    await mqtt.connect()

    # Run Dahua event client in background
    task_client = asyncio.create_task(client.run_forever())

    log.info("Service started. Waiting for shutdown signal…")

    # Wait for SIGTERM / SIGINT
    await shutdown.wait()

    log.warning("Shutdown signal received. Stopping…")

    # Cancel event stream task
    task_client.cancel()
    try:
        await task_client
    except asyncio.CancelledError:
        pass

    # Close clients
    await client.close()
    await mqtt.close()

    log.success("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
