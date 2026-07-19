"""Install a desktop launcher so casting starts from the GNOME app grid."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

LAUNCHER_NAME = "ubuntu-cast.desktop"
AUTOSTART_NAME = "ubuntu-cast-tray.desktop"


def find_executable() -> str:
    """Absolute path of the ubuntu-cast command this process was started as."""
    argv0 = Path(sys.argv[0])
    if argv0.name == "ubuntu-cast" and argv0.is_file():
        return str(argv0.resolve())
    found = shutil.which("ubuntu-cast")
    if found:
        return found
    raise RuntimeError(
        "could not find an installed ubuntu-cast executable; "
        "install one first: uv tool install <path-to-repo>"
    )


def desktop_entry(executable: str) -> str:
    """A .desktop entry that opens the CLI in a terminal window.

    Terminal=true because the interactive picker and the live status panel
    need one; Ctrl+C in that window stops the cast.
    """
    return f"""\
[Desktop Entry]
Type=Application
Name=Ubuntu Cast
GenericName=Screen casting
Comment=Cast your Ubuntu desktop — screen and audio — to a Chromecast
Exec={executable}
Terminal=true
Icon=video-display
Categories=AudioVideo;
Keywords=chromecast;cast;screen;mirror;audio;
Actions=audio-only;

[Desktop Action audio-only]
Name=Cast audio only
Exec={executable} --audio-only
"""


def install(directory: Path | None = None) -> Path:
    """Write the launcher into the user's applications directory."""
    directory = directory or Path("~/.local/share/applications").expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / LAUNCHER_NAME
    path.write_text(desktop_entry(find_executable()))
    return path


def autostart_entry(executable: str) -> str:
    """A .desktop entry that starts the tray icon automatically at login.

    Terminal=false and NoDisplay=true because this runs unattended in the
    background; it shouldn't show up as a launchable app or open a window.
    """
    return f"""\
[Desktop Entry]
Type=Application
Name=Ubuntu Cast Tray
Comment=Cast your Ubuntu desktop — screen and audio — to a Chromecast
Exec={executable} tray
Terminal=false
Icon=video-display
NoDisplay=true
X-GNOME-Autostart-enabled=true
"""


def install_autostart(directory: Path | None = None) -> Path:
    """Write the tray autostart entry so it launches automatically at login."""
    directory = directory or Path("~/.config/autostart").expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / AUTOSTART_NAME
    path.write_text(autostart_entry(find_executable()))
    return path
