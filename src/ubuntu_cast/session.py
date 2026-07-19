"""Drive a cast session: stream server on this side, media receiver on theirs."""

from __future__ import annotations

import contextlib
from uuid import UUID

import pychromecast

from . import audio, stream
from .discovery import CastDevice


class AudioSession:
    """Casts the desktop's audio (default sink monitor) to one device."""

    def __init__(self, device: CastDevice, bitrate: int = 192) -> None:
        self.device = device
        self.bitrate = bitrate
        self.url: str | None = None
        self._server: stream.StreamServer | None = None
        self._cast: pychromecast.Chromecast | None = None

    def start(self) -> str:
        """Start streaming and tell the device to play; returns the stream URL."""
        monitor = audio.default_sink_monitor()
        command = audio.mp3_stream_command(monitor, self.bitrate)
        self._server = stream.start(command)
        ip = stream.local_ip_for(self.device.host)
        self.url = f"http://{ip}:{self._server.server_port}{stream.STREAM_PATH}"

        self._cast = pychromecast.get_chromecast_from_host(
            (
                self.device.host,
                self.device.port,
                UUID(self.device.uuid),
                self.device.model,
                self.device.name,
            )
        )
        self._cast.wait(timeout=10)
        controller = self._cast.media_controller
        controller.play_media(
            self.url,
            "audio/mpeg",
            stream_type="LIVE",
            title="Ubuntu desktop audio",
        )
        controller.block_until_active(timeout=10)
        return self.url

    def stop(self) -> None:
        """Stop playback on the device and tear down the local stream."""
        if self._cast is not None:
            # Best-effort: the device may already be gone when we tear down.
            with contextlib.suppress(Exception):
                self._cast.media_controller.stop()
                self._cast.quit_app()
                self._cast.disconnect()
            self._cast = None
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
