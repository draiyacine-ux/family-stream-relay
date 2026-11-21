FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

RUN apt-get update && apt-get install -y --no-install-recommends     ffmpeg     curl     wget     ca-certificates     procps     && rm -rf /var/lib/apt/lists/*

RUN wget -q https://github.com/bluenviron/mediamtx/releases/download/v1.9.3/mediamtx_v1.9.3_linux_amd64.tar.gz &&     tar -xzf mediamtx_v1.9.3_linux_amd64.tar.gz -C /usr/local/bin &&     rm mediamtx_v1.9.3_linux_amd64.tar.gz
