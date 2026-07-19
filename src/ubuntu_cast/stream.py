"""A tiny HTTP server the Chromecast pulls the live stream from.

The capture pipeline is spawned per connection, so a reconnecting Chromecast
always gets a fresh stream from "now" rather than a stale buffer.
"""

from __future__ import annotations

import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .gstenv import sanitized_env

STREAM_PATH = "/stream.mp3"
_CHUNK_SIZE = 8192


class StreamServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, command: list[str]) -> None:
        super().__init__(("0.0.0.0", 0), _StreamHandler)
        self.command = command


class _StreamHandler(BaseHTTPRequestHandler):
    server: StreamServer

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != STREAM_PATH:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        pipeline = subprocess.Popen(
            self.server.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=sanitized_env(),
        )
        assert pipeline.stdout is not None
        try:
            while chunk := pipeline.stdout.read(_CHUNK_SIZE):
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            pipeline.terminate()
            pipeline.wait(timeout=5)

    def log_message(self, format: str, *args: object) -> None:
        """Keep request chatter out of the user's terminal."""


def start(command: list[str]) -> StreamServer:
    """Serve `command`'s stdout on an ephemeral port; returns the running server."""
    server = StreamServer(command)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def local_ip_for(host: str) -> str:
    """The local address this machine uses to reach `host`."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect((host, 9))
        return probe.getsockname()[0]
