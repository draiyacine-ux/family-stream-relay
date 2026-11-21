#!/usr/bin/env bash
echo "=== Starting High-Performance HLS Relay ==="
cd /workspaces/family-stream-relay 2>/dev/null || cd "$(dirname "$0")"

mkdir -p /tmp/hls
pkill -9 -f ffmpeg || true
pkill -9 -f cloudflared || true
pkill -9 -f server.py || true
pkill -9 -f "python3.*8888" || true
rm -rf /tmp/hls/*
sleep 1

# 1. Start Python HTTP Server with CORS
nohup python3 server.py > /tmp/http.log 2>&1 &
echo "Web server running on port 8888"

# 2. Start Cloudflare Tunnel
nohup cloudflared tunnel --url http://127.0.0.1:8888 > /tmp/tunnel.log 2>&1 &
echo "Cloudflare Tunnel started"

# 3. Start FFmpeg native HLS packager
nohup ffmpeg -reconnect 1 -reconnect_at_eof 1 -reconnect_streamed 1 -reconnect_delay_max 2 \
  -user_agent "VLC/3.0.18" \
  -i "http://tv2ip.nl:2095/live/734824175695/183317487561/1585779.ts" \
  -c copy \
  -f hls \
  -hls_time 2 \
  -hls_list_size 6 \
  -hls_flags delete_segments \
  -hls_segment_type mpegts \
  /tmp/hls/bein1.m3u8 > /tmp/ffmpeg.log 2>&1 &
echo "FFmpeg HLS generator started"

# 4. Wait for tunnel URL and m3u8 generation
TUNNEL_URL=""
for i in {1..35}; do
  sleep 1
  if [ -z "$TUNNEL_URL" ]; then
    TUNNEL_URL=$(grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' /tmp/tunnel.log 2>/dev/null | head -1)
  fi
  if [ -n "$TUNNEL_URL" ] && [ -f /tmp/hls/bein1.m3u8 ]; then
    echo "Found tunnel: $TUNNEL_URL and playlist exists!"
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
