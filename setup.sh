#!/usr/bin/env bash
set -e
echo "Installing MediaMTX, FFmpeg & Cloudflared..."
sudo apt-get update -y
sudo apt-get install -y ffmpeg curl tar wget git

if [ ! -f mediamtx ]; then
  wget -q https://github.com/bluenviron/mediamtx/releases/download/v1.9.3/mediamtx_v1.9.3_linux_amd64.tar.gz
  tar -xzf mediamtx_v1.9.3_linux_amd64.tar.gz
  chmod +x mediamtx
fi

if ! command -v cloudflared &> /dev/null; then
  wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
  sudo dpkg -i cloudflared-linux-amd64.deb || sudo apt-get install -f -y
fi

echo "Setup completed successfully!"
