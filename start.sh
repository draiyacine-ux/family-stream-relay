#!/usr/bin/env bash
echo "=== Starting MediaMTX & Cloudflare Tunnel ==="
cd /workspaces/family-stream-relay 2>/dev/null || cd "$(dirname "$0")"

pkill -9 -f mediamtx || true
pkill -9 -f cloudflared || true
sleep 1

# Find mediamtx binary
MTX_BIN="mediamtx"
if [ -f "/usr/local/bin/mediamtx" ]; then
  MTX_BIN="/usr/local/bin/mediamtx"
elif [ -f "./mediamtx" ]; then
  MTX_BIN="./mediamtx"
fi

echo "Using MediaMTX: $MTX_BIN"
nohup $MTX_BIN mediamtx.yml > mediamtx.log 2>&1 &
echo "MediaMTX started (PID: $!)"

echo "Starting Cloudflare Tunnel..."
nohup cloudflared tunnel --url http://127.0.0.1:8888 > tunnel.log 2>&1 &
echo "Cloudflared started (PID: $!)"

# Wait for tunnel URL
echo "Waiting for Cloudflare Tunnel URL..."
TUNNEL_URL=""
for i in {1..20}; do
  sleep 1
  TUNNEL_URL=$(grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' tunnel.log | head -1)
  if [ -n "$TUNNEL_URL" ]; then
    break
  fi
done

echo "Active Tunnel: $TUNNEL_URL"

if [ -n "$TUNNEL_URL" ]; then
  STREAM_URL="$TUNNEL_URL/bein1/index.m3u8"
  echo "Stream URL: $STREAM_URL"
  echo "$STREAM_URL" > stream_url.txt
  
  git config user.name "FamilyStreamBot"
  git config user.email "bot@familystream.local"
  git add stream_url.txt
  git commit -m "Live stream URL: $STREAM_URL" || true
  git push origin main || true
fi
