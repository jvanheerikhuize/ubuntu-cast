"""Persist the portal restore token across runs (XDG state directory)."""

from __future__ import annotations

import os
from pathlib import Path

_TOKEN_FILE = "restore-token"


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
