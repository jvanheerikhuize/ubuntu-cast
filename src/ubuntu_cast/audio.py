"""Capture desktop audio: PipeWire default-sink monitor → live MP3 on stdout."""

from __future__ import annotations

import subprocess


def default_sink_monitor() -> str:
    """Name of the monitor source for the current default audio sink."""
    result = subprocess.run(
        ["pactl", "get-default-sink"],
        capture_output=True,
        text=True,
        check=True,
    )
    sink = result.stdout.strip()
    if not sink:
        raise RuntimeError("pactl reported no default audio sink")
    return f"{sink}.monitor"


def mp3_stream_command(monitor: str, bitrate: int = 192) -> list[str]:
    """gst-launch command that writes a live MP3 stream of `monitor` to stdout."""
    return [
        "gst-launch-1.0",
        "-q",
        "pulsesrc",
        f"device={monitor}",
        "!",
        "audioconvert",
        "!",
        "audioresample",
        "!",
        "lamemp3enc",
        "target=bitrate",
        f"bitrate={bitrate}",
        "cbr=true",
        "!",
        "fdsink",
        "fd=1",
    ]
