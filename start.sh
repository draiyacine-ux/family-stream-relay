#!/usr/bin/env bash
echo "Starting MediaMTX Relay..."
pkill -f mediamtx || true
nohup ./mediamtx mediamtx.yml > mediamtx.log 2>&1 &
sleep 2
if pgrep -f mediamtx > /dev/null; then
  echo "MediaMTX is running on port 8888!"
else
  echo "Failed to start MediaMTX, checking log:"
  cat mediamtx.log
fi
