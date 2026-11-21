import http.server
import socketserver
import os
import sys

PORT = 8888
DIRECTORY = "/tmp/hls"

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

if __name__ == "__main__":
    os.makedirs(DIRECTORY, exist_ok=True)
    socketserver.TCPServer.allow_reuse_address = True
    print(f"Serving {DIRECTORY} on port {PORT} with CORS enabled", flush=True)
    with socketserver.TCPServer(("", PORT), CORSRequestHandler) as httpd:
        httpd.serve_forever()
