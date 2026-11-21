import http.server
import socketserver
import os
import sys
import subprocess
import json
import urllib.parse
import threading
import time

PORT = 8888
DIRECTORY = "/tmp/hls"
CHANNELS_FILE = os.path.join(os.path.dirname(__file__), "channels.json")

active_channel = {
    "id": "1178453",
    "name": "beIN SPORTS 1 (4K / UHD)",
    "category": "beIN Sports (Arabe)",
    "url": "http://dinofox.sbs:80/play/live.php?mac=00:1A:79:B5:0D:61&stream=1178453&extension=ts"
}

ffmpeg_proc = None
ffmpeg_lock = threading.Lock()

def load_channels():
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading channels.json: {e}")
    return []

def start_ffmpeg(stream_url):
    global ffmpeg_proc
    with ffmpeg_lock:
        if ffmpeg_proc:
            print("Stopping current FFmpeg process...")
            try:
                ffmpeg_proc.terminate()
                ffmpeg_proc.wait(timeout=3)
            except Exception:
                ffmpeg_proc.kill()
            ffmpeg_proc = None

        os.makedirs(DIRECTORY, exist_ok=True)
        # Clear old segments
        for f in os.listdir(DIRECTORY):
            try:
                os.remove(os.path.join(DIRECTORY, f))
            except Exception:
                pass

        cmd = [
            "ffmpeg",
            "-reconnect", "1",
            "-reconnect_at_eof", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "2",
            "-user_agent", "VLC/3.0.18",
            "-i", stream_url,
            "-c", "copy",
            "-f", "hls",
            "-hls_time", "2",
            "-hls_list_size", "6",
            "-hls_flags", "delete_segments",
            "-hls_segment_type", "mpegts",
            f"{DIRECTORY}/bein1.m3u8"
        ]
        print(f"Starting FFmpeg: {' '.join(cmd)}")
        ffmpeg_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

class RelayHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, HEAD, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/control":
            self.render_control_page()
            return
        elif path == "/api/status":
            self.render_json({
                "status": "online",
                "active_channel": active_channel,
                "ffmpeg_running": ffmpeg_proc is not None and ffmpeg_proc.poll() is None
            })
            return
        elif path == "/api/channels":
            self.render_json(load_channels())
            return
        elif path == "/live.m3u8":
            # Alias for bein1.m3u8
            self.path = "/bein1.m3u8"

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/switch":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            params = urllib.parse.parse_qs(body)
            target_id = params.get("id", [""])[0]
            custom_url = params.get("custom_url", [""])[0]

            channels = load_channels()
            target_ch = next((c for c in channels if c.get("id") == target_id), None)

            if target_ch:
                active_channel.update(target_ch)
                start_ffmpeg(target_ch["url"])
                self.send_response(303)
                self.send_header("Location", "/control")
                self.end_headers()
                return
            elif custom_url.startswith("http"):
                active_channel["id"] = "custom"
                active_channel["name"] = "Flux Personnalisé"
                active_channel["category"] = "Custom"
                active_channel["url"] = custom_url
                start_ffmpeg(custom_url)
                self.send_response(303)
                self.send_header("Location", "/control")
                self.end_headers()
                return

            self.render_json({"error": "Channel not found"}, 400)
            return

        self.send_error(404, "Endpoint not found")

    def render_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def render_control_page(self):
        channels = load_channels()
        categories = {}
        for c in channels:
            categories.setdefault(c.get("category", "Autres"), []).append(c)

        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Family Stream - Centre de Contrôle Relais VIP</title>
    <style>
        body {{
            background: #0f172a;
            color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 760px;
            margin: 0 auto;
        }}
        .header {{
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            border: 1px solid #334155;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
        }}
        .badge {{
            display: inline-block;
            background: #22c55e;
            color: #052e16;
            font-size: 12px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 9999px;
            text-transform: uppercase;
        }}
        .stream-url {{
            background: #090d16;
            padding: 10px 14px;
            border-radius: 8px;
            font-family: monospace;
            color: #38bdf8;
            margin-top: 10px;
            word-break: break-all;
            border: 1px solid #1e293b;
        }}
        h2 {{
            color: #e2e8f0;
            font-size: 18px;
            margin-top: 24px;
            border-bottom: 2px solid #334155;
            padding-bottom: 8px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 12px;
            margin-top: 12px;
        }}
        .channel-card {{
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 12px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: all 0.2s;
        }}
        .channel-card.active {{
            border-color: #38bdf8;
            background: #1e3a5f;
        }}
        .channel-name {{
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 10px;
        }}
        .btn {{
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
        }}
        .btn:hover {{
            background: #2563eb;
        }}
        .btn.active-btn {{
            background: #22c55e;
            cursor: default;
        }}
        .custom-form {{
            background: #1e293b;
            border: 1px solid #334155;
            padding: 16px;
            border-radius: 8px;
            margin-top: 16px;
            display: flex;
            gap: 10px;
        }}
        .custom-input {{
            flex: 1;
            background: #0f172a;
            border: 1px solid #334155;
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="badge">🟢 Relais En Ligne</span>
            <h1 style="margin: 10px 0 5px 0; font-size: 22px;">⚡ Family Stream - Relais VIP</h1>
            <p style="margin: 0; color: #94a3b8; font-size: 14px;">Diffusion haute vitesse 1 Gbps • beIN Sports & France Sports</p>
            <div style="margin-top: 14px;">
                <div style="font-size: 12px; color: #94a3b8;">CHAÎNE ACTUELLEMENT DIFFUSÉE :</div>
                <div style="font-size: 18px; font-weight: 700; color: #f59e0b; margin-top: 2px;">{active_channel.get('name')}</div>
            </div>
            <div class="stream-url">/bein1.m3u8 (ou /live.m3u8)</div>
        </div>
"""
        for cat_name, cat_channels in categories.items():
            html += f"<h2>{cat_name}</h2><div class='grid'>"
            for ch in cat_channels:
                is_active = (ch.get("id") == active_channel.get("id"))
                active_cls = " active" if is_active else ""
                btn_cls = " active-btn" if is_active else ""
                btn_text = "✓ Diffusée" if is_active else "Diffuser ce match"
                disabled = " disabled" if is_active else ""

                html += f"""
                <div class="channel-card{active_cls}">
                    <div class="channel-name">{ch.get('name')}</div>
                    <form method="POST" action="/api/switch">
                        <input type="hidden" name="id" value="{ch.get('id')}">
                        <button type="submit" class="btn{btn_cls}"{disabled}>{btn_text}</button>
                    </form>
                </div>
                """
            html += "</div>"

        html += f"""
        <h2>Lien direct personnalisé</h2>
        <form class="custom-form" method="POST" action="/api/switch">
            <input type="text" name="custom_url" class="custom-input" placeholder="http://... ou lien direct .ts">
            <button type="submit" class="btn" style="width: auto;">Activer</button>
        </form>
    </div>
</body>
</html>
"""
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    os.makedirs(DIRECTORY, exist_ok=True)
    # Start default channel
    channels = load_channels()
    if channels:
        active_channel.update(channels[0])
    start_ffmpeg(active_channel["url"])

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), RelayHandler) as httpd:
        print(f"Server running on port {PORT}", flush=True)
        try:
            httpd.serve_forever()
        finally:
            if ffmpeg_proc:
                ffmpeg_proc.kill()
