"""Persist the portal restore token across runs (XDG state directory)."""

from __future__ import annotations

import os
from pathlib import Path

_TOKEN_FILE = "restore-token"
_LAST_DEVICE_FILE = "last-device"


def _state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or "~/.local/state"
    return Path(base).expanduser() / "ubuntu-cast"


def load_restore_token() -> str | None:
    """The token saved by the last approved screen cast, if any."""
    try:
        token = (_state_dir() / _TOKEN_FILE).read_text().strip()
    except OSError:
        return None
    return token or None


def save_restore_token(token: str | None) -> None:
    """Persist the token the portal handed back; None leaves the old one."""
    if not token:
        return
    directory = _state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / _TOKEN_FILE).write_text(token + "\n")


def load_last_device() -> tuple[str, bool] | None:
    """The (name, audio_only) of the last device successfully cast to, if any."""
    try:
        lines = (_state_dir() / _LAST_DEVICE_FILE).read_text().splitlines()
    except OSError:
        return None
    if not lines or not lines[0]:
        return None
    audio_only = len(lines) > 1 and lines[1] == "audio"
    return lines[0], audio_only


def save_last_device(name: str, audio_only: bool) -> None:
    """Remember the device (and mode) most recently cast to."""
    directory = _state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    mode = "audio" if audio_only else "video"
    (directory / _LAST_DEVICE_FILE).write_text(f"{name}\n{mode}\n")
