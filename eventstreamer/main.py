import asyncio
import json
import sys
from aiohttp import web

from dahua.shutdown import shutdown, install_signal_handlers
from dahua.client import DahuaEventClient
from dahua.mqtt_sender import MqttSender
from dahua.logger import ColorLogger, LoggerConfig

log = ColorLogger("MAIN")

class HealthCheck:
    """Monitors component states for Docker."""
    def __init__(self):
        self.mqtt_ok = False
        self.client_ok = False

    async def handle_request(self, request):
        # Returns 200 if both are true, else 503 Service Unavailable
        is_healthy = self.mqtt_ok and self.client_ok
        status = 200 if is_healthy else 503
        
        return web.json_response({
            "status": "healthy" if is_healthy else "unhealthy",
            "mqtt": "connected" if self.mqtt_ok else "disconnected",
            "dahua": "active" if self.client_ok else "inactive"
        }, status=status)

async def start_health_server(hc: HealthCheck, port: int):
    app = web.Application()
    app.router.add_get('/health', hc.handle_request)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    log.info(f"Healthcheck server live at http://0.0.0.0:{port}/health")
    return runner

async def main():
    loop = asyncio.get_running_loop()
    install_signal_handlers(loop)

    # 1. Configuration
    try:
        with open("settings.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        log.error("settings.json not found.")
        sys.exit(1)

    LoggerConfig.set_level(config.get("log_level", "INFO"))
    health_port = config.get("health_port", 8080)
    
    # 2. Initialization
    hc = HealthCheck()
    
    mqtt = MqttSender(
        host=config.get("mqtt", {}).get("host", "localhost"),
        port=config.get("mqtt", {}).get("port", 1883),
        topic=config.get("mqtt", {}).get("topic", "dahua/events"),
    )
    
    client = DahuaEventClient(
        host=config.get("dahua").get("host"),
        port=config.get("dahua").get("port"),
        username=config.get("dahua").get("username"),
        password=config.get("dahua").get("password"),
        codes=config.get("dahua").get("codes"),
        on_event=mqtt.publish_event,
        ignored_events=config.get("ignored_events", []),
    )

    # 3. Start Health Server
    hc_runner = await start_health_server(hc, health_port)

    # 4. Start Primary Services
    await mqtt.connect()
    hc.mqtt_ok = True 
    
    # Run the client in the background
    task_client = asyncio.create_task(client.run_forever(), name="DahuaRunner")
    hc.client_ok = True 

    log.info("Service operational. Waiting for shutdown signal...")

    try:
        await shutdown.wait()
    except Exception as e:
        log.error(f"Execution error: {e}")
    finally:
        log.warning("Shutdown initiated...")
        
        # Stop Health server
        await hc_runner.cleanup()
        
        # STOP CLIENT FIRST: This must await session.close() inside DahuaEventClient
        await client.shutdown()
        
        # Stop MQTT
        await mqtt.close()

        # Cancel the background task
        if not task_client.done():
            task_client.cancel()
            try:
                await task_client
            except asyncio.CancelledError:
                pass

        # Cleanup any orphaned asyncio tasks
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    log.success("Shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

