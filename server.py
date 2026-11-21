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
HLS_DIR = "/tmp/hls"
CHANNELS_FILE = os.path.join(os.path.dirname(__file__), "channels.json")

MAC = "00:1A:79:B5:0D:61"
PORTAL_HOST = "dinofox.sbs"

# Global state
active_stream_id = None
active_channel_name = "Aucune (En attente)"
ffmpeg_proc = None
ffmpeg_lock = threading.Lock()
last_request_time = time.time()

def load_channels():
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading channels.json: {e}")
    return []

def get_channel_by_id(stream_id):
    channels = load_channels()
    for ch in channels:
        if str(ch.get("id")) == str(stream_id):
            return ch
    return None

def start_stream_for_channel(stream_id):
    global ffmpeg_proc, active_stream_id, active_channel_name, last_request_time
    with ffmpeg_lock:
        last_request_time = time.time()
        
        # If already running this channel and process is alive, nothing to do!
        if active_stream_id == str(stream_id) and ffmpeg_proc is not None and ffmpeg_proc.poll() is None:
            return True

        print(f"[On-Demand] Switching stream to channel ID: {stream_id}")
        
        # Stop existing FFmpeg process
        if ffmpeg_proc:
            print("[On-Demand] Stopping previous FFmpeg process...")
            try:
                ffmpeg_proc.terminate()
                ffmpeg_proc.wait(timeout=2)
            except Exception:
                try:
                    ffmpeg_proc.kill()
                except Exception:
                    pass
            ffmpeg_proc = None

        # Clean HLS directory
        os.makedirs(HLS_DIR, exist_ok=True)
        for f in os.listdir(HLS_DIR):
            try:
                os.remove(os.path.join(HLS_DIR, f))
            except Exception:
                pass

        ch = get_channel_by_id(stream_id)
        if ch:
            stream_url = ch.get("url")
            active_channel_name = ch.get("name", f"Canal {stream_id}")
        else:
            stream_url = f"http://{PORTAL_HOST}:80/play/live.php?mac={MAC}&stream={stream_id}&extension=ts"
            active_channel_name = f"Canal {stream_id}"

        active_stream_id = str(stream_id)
        playlist_path = os.path.join(HLS_DIR, "live.m3u8")

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
            playlist_path
        ]
        
        print(f"[On-Demand] Starting FFmpeg: {stream_url}")
        ffmpeg_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Also create symlink or alias for legacy bein1.m3u8
        # Wait up to 3.5 seconds for playlist creation
        for _ in range(35):
            time.sleep(0.1)
            if os.path.exists(playlist_path) and os.path.getsize(playlist_path) > 0:
                print(f"[On-Demand] Playlist ready for channel {stream_id}!")
                break

        return True

class OnDemandRelayHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HLS_DIR, **kwargs)

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
        global last_request_time
        last_request_time = time.time()

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. Traitement des requêtes On-Demand : /hls/<stream_id>.m3u8
        if path.startswith("/hls/") and path.endswith(".m3u8"):
            stream_id = path.replace("/hls/", "").replace(".m3u8", "").strip()
            if stream_id:
                start_stream_for_channel(stream_id)
                # Servir live.m3u8
                self.path = "/live.m3u8"
                return super().do_GET()

        # 2. Rétro-compatibilité : /bein1.m3u8 ou /live.m3u8
        if path in ["/bein1.m3u8", "/live.m3u8"]:
            if active_stream_id is None:
                # Démarrage par défaut sur beIN Sports 1
                start_stream_for_channel("1178453")
            self.path = "/live.m3u8"
            return super().do_GET()

        # 3. Segments .ts : servis directement depuis HLS_DIR
        if path.endswith(".ts"):
            # Remapper chemin si préfixé par /hls/
            if path.startswith("/hls/"):
                self.path = "/" + os.path.basename(path)
            return super().do_GET()

        # 4. APIs & Statut
        if path == "/api/status":
            self.render_json({
                "status": "online",
                "mode": "on_demand",
                "active_stream_id": active_stream_id,
                "active_channel_name": active_channel_name,
                "ffmpeg_running": ffmpeg_proc is not None and ffmpeg_proc.poll() is None
            })
            return

        if path == "/api/channels":
            self.render_json(load_channels())
            return

        if path == "/control":
            self.render_control_page()
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/switch":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            params = urllib.parse.parse_qs(body)
            target_id = params.get("id", [""])[0]

            if target_id:
                start_stream_for_channel(target_id)
                self.send_response(303)
                self.send_header("Location", "/control")
                self.end_headers()
                return

            self.render_json({"error": "Missing id"}, 400)
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
    <title>Family Stream - Relais On-Demand Automatique</title>
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
        .btn.active-btn {{
            background: #22c55e;
            cursor: default;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="badge">🟢 Mode Automatique (On-Demand)</span>
            <h1 style="margin: 10px 0 5px 0; font-size: 22px;">⚡ Family Stream - Relais VIP</h1>
            <p style="margin: 0; color: #94a3b8; font-size: 14px;">Les chaînes démarrent automatiquement dès qu'un utilisateur clique dans l'application Android.</p>
            <div style="margin-top: 14px;">
                <div style="font-size: 12px; color: #94a3b8;">CHAÎNE ACTUELLEMENT DEMANDÉE :</div>
                <div style="font-size: 18px; font-weight: 700; color: #f59e0b; margin-top: 2px;">{active_channel_name}</div>
            </div>
            <div class="stream-url">Format d'appel direct : /hls/&lt;id&gt;.m3u8</div>
        </div>
"""
        for cat_name, cat_channels in categories.items():
            html += f"<h2>{cat_name}</h2><div class='grid'>"
            for ch in cat_channels:
                is_active = (str(ch.get("id")) == str(active_stream_id))
                active_cls = " active" if is_active else ""
                btn_cls = " active-btn" if is_active else ""
                btn_text = "✓ En cours de diffusion" if is_active else "Tester manuellement"

                html += f"""
                <div class="channel-card{active_cls}">
                    <div class="channel-name">{ch.get('name')}</div>
                    <form method="POST" action="/api/switch">
                        <input type="hidden" name="id" value="{ch.get('id')}">
                        <button type="submit" class="btn{btn_cls}">{btn_text}</button>
                    </form>
                </div>
                """
            html += "</div>"

        html += """
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
    os.makedirs(HLS_DIR, exist_ok=True)
    # Start default stream on boot (beIN Sports 1)
    start_stream_for_channel("1178453")

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), OnDemandRelayHandler) as httpd:
        print(f"[On-Demand] Server running on port {PORT}", flush=True)
        try:
            httpd.serve_forever()
        finally:
            if ffmpeg_proc:
                ffmpeg_proc.kill()
