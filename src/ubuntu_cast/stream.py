"""A tiny HTTP server the Chromecast pulls the live stream from.

The capture pipeline is spawned per connection, so a reconnecting Chromecast
always gets a fresh stream from "now" rather than a stale buffer. Pipelines
that read a single-consumer resource (a PipeWire connection fd) supply a
command_factory so every connection gets its own fresh copy.
"""

from __future__ import annotations

import os
import socket
import subprocess
import tempfile
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .gstenv import sanitized_env

STREAM_PATH = "/stream"
_CHUNK_SIZE = 8192


def pipeline_log_path() -> str:
    """Where pipeline stderr is appended, so failures are diagnosable after the fact."""
    return os.path.join(tempfile.gettempdir(), "ubuntu-cast-pipeline.log")


# Returns (command, fds): the pipeline argv and the fds it inherits. The
# server passes the fds to the child and closes its own copies afterwards.
CommandFactory = Callable[[], tuple[list[str], tuple[int, ...]]]


class StreamServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        command: list[str] | None = None,
        content_type: str = "audio/mpeg",
        command_factory: CommandFactory | None = None,
    ) -> None:
        if (command is None) == (command_factory is None):
            raise ValueError("provide exactly one of command or command_factory")
        super().__init__(("0.0.0.0", 0), _StreamHandler)
        self.command = command
        self.content_type = content_type
        self.command_factory = command_factory


class _StreamHandler(BaseHTTPRequestHandler):
    server: StreamServer

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != STREAM_PATH:
            self.send_error(404)
            return
        if self.server.command_factory is not None:
            try:
                command, fds = self.server.command_factory()
            except Exception:
                self.send_error(503)
                return
        else:
            assert self.server.command is not None
            command, fds = self.server.command, ()
        self.send_response(200)
        self.send_header("Content-Type", self.server.content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with open(pipeline_log_path(), "ab") as log:
            pipeline = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=log,
                env=sanitized_env(),
                pass_fds=fds,
            )
        # The child holds its own dups now; keeping ours would leak one fd
        # per connection and hold PipeWire sockets open forever.
        for fd in fds:
            os.close(fd)
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


def start(
    command: list[str] | None = None,
    content_type: str = "audio/mpeg",
    command_factory: CommandFactory | None = None,
) -> StreamServer:
    """Serve a pipeline's stdout on an ephemeral port; returns the running server.

    Pass a static `command`, or a `command_factory` called once per connection
    when each pipeline needs fresh resources (e.g. its own PipeWire fd).
    """
    server = StreamServer(command, content_type=content_type, command_factory=command_factory)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def local_ip_for(host: str) -> str:
    """The local address this machine uses to reach `host`."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect((host, 9))
        return probe.getsockname()[0]
