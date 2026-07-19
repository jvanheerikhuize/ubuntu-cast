"""Drive a cast session: stream server on this side, media receiver on theirs."""

from __future__ import annotations

import contextlib
import os
from uuid import UUID

import pychromecast

from . import audio, portal, stream, video
from .discovery import CastDevice


def _connect(device: CastDevice) -> pychromecast.Chromecast:
    cast = pychromecast.get_chromecast_from_host(
        (device.host, device.port, UUID(device.uuid), device.model, device.name)
    )
    cast.wait(timeout=10)
    return cast


def _play(cast: pychromecast.Chromecast, url: str, content_type: str, title: str) -> None:
    controller = cast.media_controller
    controller.play_media(url, content_type, stream_type="LIVE", title=title)
    controller.block_until_active(timeout=10)


def _disconnect(cast: pychromecast.Chromecast) -> None:
    # Best-effort: the device may already be gone when we tear down.
    with contextlib.suppress(Exception):
        cast.media_controller.stop()
        cast.quit_app()
        cast.disconnect()


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

        self._cast = _connect(self.device)
        _play(self._cast, self.url, "audio/mpeg", "Ubuntu desktop audio")
        return self.url

    def stop(self) -> None:
        """Stop playback on the device and tear down the local stream."""
        if self._cast is not None:
            _disconnect(self._cast)
            self._cast = None
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


class ScreenSession:
    """Casts the desktop's screen, with its audio, to one device."""

    def __init__(self, device: CastDevice, audio_bitrate: int = 192) -> None:
        self.device = device
        self.audio_bitrate = audio_bitrate
        self.url: str | None = None
        self._server: stream.StreamServer | None = None
        self._cast: pychromecast.Chromecast | None = None
        self._portal: portal.ScreenCastSession | None = None
        self._pipewire_fd: int | None = None

    def start(self) -> str:
        """Negotiate capture, start streaming, tell the device to play.

        Shows the system screen-share dialog; raises portal.PortalError if the
        user cancels it. Encoders are checked first so a missing one fails fast
        without popping the dialog.
        """
        h264_encoder = video.pick_h264_encoder()
        aac_encoder = video.pick_aac_encoder(self.audio_bitrate)
        monitor = audio.default_sink_monitor()

        self._portal = portal.ScreenCastSession()
        capture = self._portal.open()
        self._pipewire_fd = capture.pipewire_fd

        command = video.fmp4_stream_command(
            capture.pipewire_fd, capture.node_id, monitor, h264_encoder, aac_encoder
        )
        self._server = stream.start(
            command, content_type="video/mp4", pass_fds=(capture.pipewire_fd,)
        )
        ip = stream.local_ip_for(self.device.host)
        self.url = f"http://{ip}:{self._server.server_port}{stream.STREAM_PATH}"

        self._cast = _connect(self.device)
        _play(self._cast, self.url, "video/mp4", "Ubuntu desktop")
        return self.url

    def stop(self) -> None:
        """Stop playback, tear down the stream, and end the portal capture."""
        if self._cast is not None:
            _disconnect(self._cast)
            self._cast = None
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._portal is not None:
            self._portal.close()
            self._portal = None
        if self._pipewire_fd is not None:
            with contextlib.suppress(OSError):
                os.close(self._pipewire_fd)
            self._pipewire_fd = None
