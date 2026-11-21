#!/usr/bin/env bash
echo "Starting MediaMTX & Cloudflare Tunnel..."
pkill -f mediamtx || true
pkill -f cloudflared || true

nohup ./mediamtx mediamtx.yml > mediamtx.log 2>&1 &
nohup cloudflared tunnel --url http://localhost:8888 > tunnel.log 2>&1 &

sleep 6
TUNNEL_URL=$(grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' tunnel.log | head -1)
echo "Active Tunnel: $TUNNEL_URL"

if [ -n "$TUNNEL_URL" ]; then
  echo "$TUNNEL_URL" > stream_url.txt
  git config user.name "FamilyStreamBot"
  git config user.email "bot@familystream.local"
  git add stream_url.txt
  git commit -m "Update active stream URL" || true
  git push origin main || true
fi
