"""Build the screen+audio capture pipeline: PipeWire → H.264/AAC → live fMP4."""

from __future__ import annotations

import subprocess

from .gstenv import sanitized_env
from .quality import DEFAULT, Quality

_AAC_ENCODERS: tuple[str, ...] = ("avenc_aac", "voaacenc")


def _h264_candidates(quality: Quality) -> tuple[tuple[str, list[str]], ...]:
    """Encoder elements in preference order, tuned for this quality.

    Keyframes every two seconds keep the Chromecast's buffer seekable without
    spending too much of the bitrate budget on I-frames.

    No rate-control on vaapih264enc: Intel's iHD driver rejects caps negotiation
    in cbr/vbr modes, so it must stay on its default (cqp).
    """
    bitrate = quality.video_bitrate
    gop = max(1, quality.fps * 2)
    hardware: tuple[tuple[str, list[str]], ...] = (
        ("vaapih264enc", ["vaapih264enc", f"bitrate={bitrate}", f"keyframe-period={gop}"]),
        ("vah264enc", ["vah264enc", f"bitrate={bitrate}", f"key-int-max={gop}"]),
    )
    software: tuple[tuple[str, list[str]], ...] = (
        (
            "x264enc",
            [
                "x264enc",
                "tune=zerolatency",
                "speed-preset=veryfast",
                f"bitrate={bitrate}",
                f"key-int-max={gop}",
            ],
        ),
    )
    return (*hardware, *software) if quality.hardware else software


def _have_element(name: str) -> bool:
    result = subprocess.run(
        ["gst-inspect-1.0", "--exists", name],
        capture_output=True,
        env=sanitized_env(),
        check=False,
    )
    return result.returncode == 0


def pick_h264_encoder(quality: Quality = DEFAULT) -> list[str]:
    """Encoder element + tuning for the pipeline, hardware first."""
    for name, args in _h264_candidates(quality):
        if _have_element(name):
            return args
    if not quality.hardware:
        raise RuntimeError(
            "no software H.264 encoder found — install gstreamer1.0-plugins-ugly, "
            "or drop --no-hw to allow gstreamer1.0-vaapi"
        )
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


def _raw_caps(quality: Quality) -> str:
    caps = f"video/x-raw,format=NV12,framerate={quality.fps}/1"
    if quality.resolution is not None:
        width, height = quality.resolution
        caps += f",width={width},height={height}"
    return caps


def fmp4_stream_command(
    pipewire_fd: int,
    node_id: int,
    monitor: str,
    h264_encoder: list[str],
    aac_encoder: list[str],
    quality: Quality = DEFAULT,
) -> list[str]:
    """gst-launch command muxing screen video and desktop audio to fMP4 on stdout.

    The mux must be defined in the first branch so the audio branch can link to
    it by name; queues on both live branches keep the muxer from deadlocking.
    """
    # add-borders letterboxes rather than distorting when the monitor's aspect
    # ratio doesn't match the requested resolution.
    scaling = ["videoscale", "add-borders=true", "!"] if quality.resolution is not None else []
    return [
        "gst-launch-1.0",
        "-q",
        "pipewiresrc",
        f"fd={pipewire_fd}",
        f"path={node_id}",
        "do-timestamp=true",
        "!",
        # Decouple capture from encoding: a slow encoder must never
        # back-pressure pipewiresrc into dropping portal frames.
        "queue",
        "!",
        "videoconvert",
        "n-threads=0",
        "!",
        *scaling,
        "videorate",
        "!",
        # The portal stream is variable-rate (framerate=0/1); pin a constant
        # frame rate so the encoder and Chromecast see a steady cadence.
        _raw_caps(quality),
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
