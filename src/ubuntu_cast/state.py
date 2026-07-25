"""Persist the portal restore token across runs (XDG state directory)."""

from __future__ import annotations

import json
import os
import signal
from pathlib import Path

_TOKEN_FILE = "restore-token"
_LAST_DEVICE_FILE = "last-device"
_SESSION_FILE = "session.json"


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


def save_session(
    device: str,
    audio_only: bool,
    url: str | None = None,
    stop_signal: int = signal.SIGINT,
    pid: int | None = None,
) -> None:
    """Record the running cast so `ubuntu-cast stop` can find and signal it.

    stop_signal differs by owner: a terminal cast dies on SIGINT (the same path
    as Ctrl+C), while the tray takes SIGUSR1 so only the cast stops, not the
    tray itself.
    """
    directory = _state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    owner = os.getpid() if pid is None else pid
    record = {
        "pid": owner,
        # Fingerprint the process so a recycled pid can't be mistaken for it.
        "cmdline": _cmdline(owner),
        "device": device,
        "audio_only": audio_only,
        "url": url,
        "stop_signal": int(stop_signal),
    }
    (directory / _SESSION_FILE).write_text(json.dumps(record) + "\n")


def _cmdline(pid: int) -> str | None:
    """A process's argv, or None where /proc isn't readable (non-Linux)."""
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", "replace")
    except OSError:
        return None


def _process_alive(pid: int, cmdline: str | None = None) -> bool:
    """Is this pid still around, and still the process that saved the record?"""
    try:
        os.kill(pid, 0)
    except OSError:
        # Gone, or owned by another user — either way, not ours to signal.
        return False
    if cmdline is None:
        return True  # nothing to compare against; liveness is all we have
    current = _cmdline(pid)
    return current is None or current == cmdline


def load_session() -> dict | None:
    """The running cast's record, or None (clearing it if the process is gone)."""
    try:
        record = json.loads((_state_dir() / _SESSION_FILE).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or not isinstance(record.get("pid"), int):
        return None
    if not _process_alive(record["pid"], record.get("cmdline")):
        clear_session()
        return None
    return record


def clear_session() -> None:
    """Forget the running cast; safe to call when nothing was recorded."""
    (_state_dir() / _SESSION_FILE).unlink(missing_ok=True)
