"""Neutralise snap-injected environment variables before spawning GStreamer.

Terminals packaged as snaps (Alacritty, kitty, ...) export GST_PLUGIN_PATH,
GST_PLUGIN_SCANNER, LD_LIBRARY_PATH and friends pointing inside the snap's
own read-only tree. Any child process inheriting them sees only the snap's
bundled GStreamer plugins — not the ones installed with apt — so pipelines
and `gst-inspect-1.0` mysteriously miss elements that are installed.
"""

from __future__ import annotations

import os

_PATH_LIST_VARS = (
    "GST_PLUGIN_PATH",
    "GST_PLUGIN_SYSTEM_PATH",
    "LD_LIBRARY_PATH",
    "LIBVA_DRIVERS_PATH",
    "LIBGL_DRIVERS_PATH",
)

_SINGLE_PATH_VARS = (
    "GST_PLUGIN_SCANNER",
    "GST_REGISTRY",
    "XDG_CACHE_HOME",
)


def _is_snap_path(path: str) -> bool:
    return path.startswith("/snap/") or "/snap/" in path


def sanitized_env() -> dict[str, str]:
    """A copy of the environment safe for GStreamer/libva subprocesses.

    Snap components are stripped from path-list variables (the variable is
    dropped if nothing survives); single-path variables pointing into a snap
    are dropped entirely. Everything else passes through untouched.
    """
    env = dict(os.environ)
    for var in _PATH_LIST_VARS:
        if var in env:
            kept = [p for p in env[var].split(os.pathsep) if p and not _is_snap_path(p)]
            if kept:
                env[var] = os.pathsep.join(kept)
            else:
                del env[var]
    for var in _SINGLE_PATH_VARS:
        if var in env and _is_snap_path(env[var]):
            del env[var]
    return env
