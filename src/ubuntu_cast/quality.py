"""Encoding quality: presets, explicit overrides, and the flags that pick them."""

from __future__ import annotations

from dataclasses import dataclass, replace

# 1080p is the Default Media Receiver's ceiling on most Chromecasts, so even the
# "high" preset stops there and spends its extra budget on frame rate/bitrate.
_NAMED_RESOLUTIONS: dict[str, tuple[int, int]] = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "native": (0, 0),  # sentinel; parse_resolution turns this into None
}


@dataclass(frozen=True)
class Quality:
    """Everything the pipeline needs to know about how good the stream should look."""

    resolution: tuple[int, int] | None = (1920, 1080)
    fps: int = 30
    video_bitrate: int = 8000  # kbit/s
    audio_bitrate: int = 192  # kbit/s
    hardware: bool = True
    show_cursor: bool = True

    @property
    def label(self) -> str:
        """Short human summary, e.g. "1080p · 30 fps · 8.0 Mb/s"."""
        size = "native" if self.resolution is None else f"{self.resolution[1]}p"
        return f"{size} · {self.fps} fps · {self.video_bitrate / 1000:.1f} Mb/s"


PRESETS: dict[str, Quality] = {
    "low": Quality(resolution=(1280, 720), fps=24, video_bitrate=2500, audio_bitrate=128),
    "balanced": Quality(),
    "high": Quality(resolution=(1920, 1080), fps=60, video_bitrate=12000, audio_bitrate=256),
}

DEFAULT = PRESETS["balanced"]


def parse_resolution(value: str) -> tuple[int, int] | None:
    """Accept "720p", "1080p", "native", or an explicit "1600x900"."""
    text = value.strip().lower()
    if text in _NAMED_RESOLUTIONS:
        size = _NAMED_RESOLUTIONS[text]
        return None if size == (0, 0) else size
    if "x" in text:
        width, _, height = text.partition("x")
        try:
            parsed = (int(width), int(height))
        except ValueError:
            parsed = (0, 0)
        if parsed[0] > 0 and parsed[1] > 0:
            return parsed
    choices = ", ".join(_NAMED_RESOLUTIONS)
    raise ValueError(f"unknown resolution {value!r} — use {choices}, or WIDTHxHEIGHT")


def resolve(
    preset: str = "balanced",
    *,
    resolution: str | None = None,
    fps: int | None = None,
    video_bitrate: int | None = None,
    audio_bitrate: int | None = None,
    hardware: bool | None = None,
    show_cursor: bool | None = None,
) -> Quality:
    """Start from a preset; every explicit flag overrides it."""
    if preset not in PRESETS:
        choices = ", ".join(PRESETS)
        raise ValueError(f"unknown quality {preset!r} — use one of: {choices}")
    overrides: dict[str, object] = {}
    if resolution is not None:
        overrides["resolution"] = parse_resolution(resolution)
    if fps is not None:
        if fps < 1:
            raise ValueError(f"fps must be positive, got {fps}")
        overrides["fps"] = fps
    if video_bitrate is not None:
        if video_bitrate < 1:
            raise ValueError(f"bitrate must be positive, got {video_bitrate}")
        overrides["video_bitrate"] = video_bitrate
    if audio_bitrate is not None:
        if audio_bitrate < 1:
            raise ValueError(f"audio bitrate must be positive, got {audio_bitrate}")
        overrides["audio_bitrate"] = audio_bitrate
    if hardware is not None:
        overrides["hardware"] = hardware
    if show_cursor is not None:
        overrides["show_cursor"] = show_cursor
    return replace(PRESETS[preset], **overrides)
