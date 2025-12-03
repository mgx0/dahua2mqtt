#!/bin/sh

LAST_EVENT_FILE="/tmp/dahua_last_event.tmp"
NOW=$(date +%s)

if [ ! -f "$LAST_EVENT_FILE" ]; then
  echo "no-event-file"
  exit 1
fi

LAST=$(cat "$LAST_EVENT_FILE")

DIFF=$((NOW - LAST))

if [ "$DIFF" -gt 60 ]; then
  echo "no recent event ($DIFF seconds ago)"
  exit 1
fi

echo "healthy ($DIFF seconds since last event)"
exit 0
