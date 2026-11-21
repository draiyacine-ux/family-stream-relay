#!/usr/bin/env bash
set -e
echo "Installing MediaMTX & FFmpeg..."
sudo apt-get update -y
sudo apt-get install -y ffmpeg curl tar wget
if [ ! -f mediamtx ]; then
  wget -q https://github.com/bluenviron/mediamtx/releases/download/v1.9.3/mediamtx_v1.9.3_linux_amd64.tar.gz
  tar -xzf mediamtx_v1.9.3_linux_amd64.tar.gz
  chmod +x mediamtx
fi
echo "Setup completed successfully!"
