#!/usr/bin/env bash
echo "=== Starting High-Performance HLS Relay ==="
cd /workspaces/family-stream-relay 2>/dev/null || cd "$(dirname "$0")"

mkdir -p /tmp/hls
pkill -9 -f ffmpeg || true
pkill -9 -f cloudflared || true
pkill -9 -f python3 || true
rm -rf /tmp/hls/*
sleep 1

# 1. Start Python HTTP Server directly from /tmp/hls
(cd /tmp/hls && nohup python3 -m http.server 8888 > /tmp/http.log 2>&1 &)
echo "Web server running on port 8888"

# 2. Start Cloudflare Tunnel
nohup cloudflared tunnel --url http://127.0.0.1:8888 > /tmp/tunnel.log 2>&1 &
echo "Cloudflare Tunnel started"

# 3. Start FFmpeg native HLS packager
nohup ffmpeg -user_agent "VLC/3.0.18" -headers "Host: tv2ip.nl:2095" -i "http://88.135.69.66:2095/live/734824175695/183317487561/1585779.ts" \
  -c copy \
  -f hls \
  -hls_time 2 \
  -hls_list_size 5 \
  -hls_flags delete_segments \
  /tmp/hls/bein1.m3u8 > /tmp/ffmpeg.log 2>&1 &
echo "FFmpeg HLS generator started"

# 4. Wait for tunnel URL and first m3u8
sleep 5
TUNNEL_URL=""
for i in {1..25}; do
  sleep 1
  TUNNEL_URL=$(grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' /tmp/tunnel.log | head -1)
  if [ -n "$TUNNEL_URL" ] && [ -f /tmp/hls/bein1.m3u8 ]; then
    break
  fi
done

echo "Active Tunnel: $TUNNEL_URL"

if [ -n "$TUNNEL_URL" ]; then
  STREAM_URL="$TUNNEL_URL/bein1.m3u8"
  echo "STREAM READY: $STREAM_URL"
  echo "$STREAM_URL" > stream_url.txt
  git config user.name "FamilyStreamBot"
  git config user.email "bot@familystream.local"
  git add stream_url.txt
  git commit -m "Live stream URL: $STREAM_URL" || true
  git push origin main || true
fi
