"""Build the screen+audio capture pipeline: PipeWire → H.264/AAC → live fMP4."""

from __future__ import annotations

import subprocess

from .gstenv import sanitized_env

# Preferred first: hardware VA-API, then software x264. 8 Mbit/s suits 1080p desktop.
# No rate-control on vaapih264enc: Intel's iHD driver rejects caps negotiation
# in cbr/vbr modes, so it must stay on its default (cqp).
_H264_ENCODERS: tuple[tuple[str, list[str]], ...] = (
    ("vaapih264enc", ["vaapih264enc", "bitrate=8000", "keyframe-period=60"]),
    ("vah264enc", ["vah264enc", "bitrate=8000", "key-int-max=60"]),
    (
        "x264enc",
        ["x264enc", "tune=zerolatency", "speed-preset=veryfast", "bitrate=8000", "key-int-max=60"],
    ),
)

_AAC_ENCODERS: tuple[str, ...] = ("avenc_aac", "voaacenc")


def _have_element(name: str) -> bool:
    result = subprocess.run(
        ["gst-inspect-1.0", "--exists", name],
        capture_output=True,
        env=sanitized_env(),
        check=False,
    )
    return result.returncode == 0


def pick_h264_encoder() -> list[str]:
    """Encoder element + tuning for the pipeline, hardware first."""
    for name, args in _H264_ENCODERS:
        if _have_element(name):
            return args
    raise RuntimeError(
        "no H.264 encoder found — install gstreamer1.0-vaapi (hardware) "
        "or gstreamer1.0-plugins-ugly (software)"
    )


def pick_aac_encoder(bitrate: int = 192) -> list[str]:
    """AAC encoder element + bitrate, or a hint about what to install."""
    for name in _AAC_ENCODERS:
        if _have_element(name):
            return [name, f"bitrate={bitrate * 1000}"]
    raise RuntimeError("no AAC encoder found — install gstreamer1.0-libav")


def fmp4_stream_command(
    pipewire_fd: int,
    node_id: int,
    monitor: str,
    h264_encoder: list[str],
    aac_encoder: list[str],
) -> list[str]:
    """gst-launch command muxing screen video and desktop audio to fMP4 on stdout.

    The mux must be defined in the first branch so the audio branch can link to
    it by name; queues on both live branches keep the muxer from deadlocking.
    """
    return [
        "gst-launch-1.0",
        "-q",
        "pipewiresrc",
        f"fd={pipewire_fd}",
        f"path={node_id}",
        "do-timestamp=true",
        "!",
        "videoconvert",
        "!",
        "videorate",
        "!",
        # The portal stream is variable-rate (framerate=0/1); pin a constant
        # 30 fps so the encoder and Chromecast see a steady cadence.
        "video/x-raw,format=NV12,framerate=30/1",
        "!",
        *h264_encoder,
        "!",
        "h264parse",
        "config-interval=-1",
        "!",
        "queue",
        "!",
        "mp4mux",
        "name=mux",
        "streamable=true",
        "fragment-duration=500",
        "!",
        "fdsink",
        "fd=1",
        "pulsesrc",
        f"device={monitor}",
        "!",
        "audioconvert",
        "!",
        "audioresample",
        "!",
        *aac_encoder,
        "!",
        "aacparse",
        "!",
        "queue",
        "!",
        "mux.",
    ]
