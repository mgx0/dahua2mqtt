# Dahua Event Stream (dahua2mqtt)

A Python service that connects to Dahua security cameras and NVRs to stream events and forward them to an MQTT broker. This service monitors Dahua camera events in real-time and publishes them to MQTT topics for integration with home automation systems or other applications.

## What it does

- **Event Monitoring**: Connects to Dahua devices and listens for security events (motion detection, intrusion alerts, etc.)
- **Event Filtering**: Allows filtering of specific event codes and ignoring unwanted events
- **MQTT Publishing**: Forwards filtered events to an MQTT broker in JSON format
- **Graceful Shutdown**: Handles SIGTERM/SIGINT signals for clean shutdown (Docker-friendly)
- **Configurable Logging**: Supports different log levels with colored output

## Features

- Asynchronous operation using `asyncio`
- Real-time event streaming from Dahua cameras
- Configurable event filtering
- MQTT integration for IoT/home automation
- Docker-ready with proper signal handling
- Structured logging with colors

## Requirements

- Python 3.7+
- Dahua camera with event streaming capability
- MQTT broker (e.g., Mosquitto)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd dahua-event-stream
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Create a `settings.json` file in the `eventstreamer` directory:

```json
{
  "log_level": "INFO",
  "dahua": {
    "host": "192.168.1.100",
    "port": 80,
    "username": "admin",
    "password": "your_password",
    "codes": ["VideoMotion", "CrossLineDetection", "CrossRegionDetection"]
  },
  "mqtt": {
    "host": "localhost",
    "port": 1883,
    "topic": "dahua/events"
  },
  "ignored_events": ["SomeUnwantedEvent"]
}
```

### Configuration Options

- **log_level**: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- **dahua**: Camera connection settings
  - **host**: Camera IP address
  - **port**: Camera port (usually 80)
  - **username/password**: Camera credentials
  - **codes**: Array of event codes to monitor. [All] can be used for all events
- **mqtt**: MQTT broker settings
  - **host**: MQTT broker IP/hostname
  - **port**: MQTT broker port (usually 1883)
  - **topic**: MQTT topic to publish events
- **ignored_events**: Array of event codes to ignore

## Usage

### Running locally

```bash
cd eventstreamer
python main.py
```

### Running with Docker

```bash
# Build the image
docker build -t dahua-event-stream .

# Run the container
docker run -d \
  --name dahua-events \
  -v /path/to/settings.json:/app/settings.json \
  dahua-event-stream
```

## Event Format

Events are published to MQTT in JSON format:

```json
{
  "code": "VideoMotion",
  "action": "Start",
  "index": "0",
  "timestamp": "2025-11-20T10:30:45Z",
  "data": {
    "channel": 0,
    "name": "Motion Detection"
  }
}
```

## Logging

The service provides colored console logging with timestamps. Log levels can be configured in `settings.json`. Example output:

```
[2025-11-20 10:30:45] [INFO] MAIN: Service started. Waiting for shutdown signal…
[2025-11-20 10:30:46] [INFO] DAHUA_MQTT_Sender: MQTT connected -> localhost:1883
[2025-11-20 10:30:47] [INFO] DAHUA_Client: Connected to Dahua camera at 192.168.1.100
```

## Caveats

- Due the connection to Dahua device is a HTTP (not a TCP tunnel), it times out eventually. Script is configured to close and reopen the connection after 240 seconds. Small delay (200ms) is used to prevent hammering the device REST API. Some events can be lost during reconnection.
- Dahua can produce a really long message, which will not fit into MQTT maximum message length. Consider bumping the value in your MQTT broker config
- developed on VTO2311, NVR4216 and NVR5216-EI

## Signal Handling

The service handles SIGTERM and SIGINT signals gracefully:
- Stops event monitoring
- Closes camera connection
- Disconnects from MQTT broker
- Exits cleanly

This makes it suitable for use in Docker containers and systemd services.

NOTE: This repository and it's content is provided as-is. It has been build for my own purposes and I cannot guarantee new feature additions due to time pressure or unavailable hardware.
[![Buy me a coffee](https://www.paypalobjects.com/en_US/i/btn/btn_donate_LG.gif)](https://www.paypal.com/donate/?hosted_button_id=MPFQRSJMWJXXE)
