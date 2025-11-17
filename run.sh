docker build -t dahua-event-stream .
docker stop dahua-event-stream
docker rm dahua-event-stream

docker run -d --restart=unless-stopped \
  -v "$(pwd)/eventstreamer/settings.json:/app/settings.json:ro" \
  --network=host \
  --name dahua-event-stream \
  dahua-event-stream
