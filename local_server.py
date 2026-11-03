#!/usr/bin/env python3
"""Serve local UI with no-cache response headers to avoid stale V2.x assets."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os

os.chdir(Path(__file__).resolve().parent / 'docs')
class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control','no-store, max-age=0')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        super().end_headers()
ThreadingHTTPServer(('127.0.0.1',5173),Handler).serve_forever()
