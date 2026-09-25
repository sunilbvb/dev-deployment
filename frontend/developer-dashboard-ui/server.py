#!/usr/bin/env python3
"""
Lightweight Python HTTP Server for Developer Dashboard UI Component Library Showcase.
Serves the showcase documentation and static component assets.
"""

import http.server
import socketserver
import urllib.parse
from pathlib import Path

PORT = 8088
PROJECT_ROOT = Path(__file__).parent.resolve()

class ComponentLibraryHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Redirect root '/' or '/showcase' to '/showcase/index.html'
        if path in ("/", "/showcase", "/showcase/"):
            self.send_response(302)
            self.send_header("Location", "/showcase/index.html")
            self.end_headers()
            return

        super().do_GET()

if __name__ == "__main__":
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", PORT), ComponentLibraryHandler) as httpd:
        print(f"===========================================================")
        print(f"⚡ Developer Dashboard UI Component Library Showcase")
        print(f"🌐 Showcase URL: http://localhost:{PORT}/showcase/")
        print(f"📁 Root Path: {PROJECT_ROOT}")
        print(f"🛑 Press Ctrl+C to stop server")
        print(f"===========================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down showcase server.")
