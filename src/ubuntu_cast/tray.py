"""GNOME top-bar tray indicator: start/stop casting without a terminal."""

from __future__ import annotations

import contextlib
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from . import discovery, session, state
from .discovery import CastDevice

# uv venvs (and `uv tool install`) don't see system site-packages, but
# PyGObject and the AppIndicator typelib are apt-only — no wheel ships them.
# Both environments run the same CPython minor version here, so the system
# extension modules load fine once their directory is on sys.path.
SYSTEM_DIST_PACKAGES = Path("/usr/lib/python3/dist-packages")

APPINDICATOR_NAMESPACES = ("AyatanaAppIndicator3", "AppIndicator3")


def _ensure_gi() -> None:
    try:
        import gi  # noqa: F401

        return
    except ImportError:
        pass
    if str(SYSTEM_DIST_PACKAGES) not in sys.path:
        sys.path.insert(0, str(SYSTEM_DIST_PACKAGES))
    try:
        import gi  # noqa: F401
    except ImportError as error:
        raise RuntimeError(
            "PyGObject not found; install it with: sudo apt install python3-gi"
        ) from error


def find_appindicator_namespace() -> str | None:
    """Which AppIndicator GI namespace is usable, if any."""
    _ensure_gi()
    import gi

    for namespace in APPINDICATOR_NAMESPACES:
        try:
            gi.require_version(namespace, "0.1")
            __import__(f"gi.repository.{namespace}")
        except (ValueError, ImportError):
            continue
        else:
            return namespace
    return None


def _import_indicator() -> tuple[Any, Any, Any]:
    """Import Gtk, GLib, and whichever AppIndicator binding is available."""
    namespace = find_appindicator_namespace()
    if namespace is None:
        raise RuntimeError(
            "No AppIndicator GI typelib found; install it with: "
            "sudo apt install gir1.2-ayatanaappindicator3-0.1"
        )
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    indicator_module = __import__(f"gi.repository.{namespace}", fromlist=[namespace])
    from gi.repository import GLib

    return indicator_module, Gtk, GLib


class TrayApp:
    """Owns the indicator icon/menu and the (at most one) active cast session."""

    IDLE_ICON = "video-display"
    ACTIVE_ICON = "network-transmit-receive-symbolic"

    def __init__(
        self, indicator_module: Any, gtk: Any, glib: Any, devices: list[CastDevice]
    ) -> None:
        self._indicator_module = indicator_module
        self._gtk = gtk
        self._glib = glib
        self.devices = devices
        self._session: session.AudioSession | session.ScreenSession | None = None
        self._active_device: CastDevice | None = None

        self.indicator = indicator_module.Indicator.new(
            "ubuntu-cast",
            "video-display",
            indicator_module.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(indicator_module.IndicatorStatus.ACTIVE)
        self.menu = gtk.Menu()
        self.indicator.set_menu(self.menu)
        self._rebuild_menu()

    def _rebuild_menu(self) -> None:
        for child in self.menu.get_children():
            self.menu.remove(child)

        if self._session is None:
            last_item = self._build_last_device_item()
            if last_item is not None:
                self.menu.append(last_item)
                self.menu.append(self._gtk.SeparatorMenuItem())
            if not self.devices:
                empty = self._gtk.MenuItem(label="No devices found")
                empty.set_sensitive(False)
                self.menu.append(empty)
            for device in self.devices:
                cast_item = self._gtk.MenuItem(label=f"Cast to {device.name}")
                cast_item.connect("activate", self._on_start, device, False)
                self.menu.append(cast_item)
                audio_item = self._gtk.MenuItem(label=f"  Audio only → {device.name}")
                audio_item.connect("activate", self._on_start, device, True)
                self.menu.append(audio_item)
            self.menu.append(self._gtk.SeparatorMenuItem())
            refresh_item = self._gtk.MenuItem(label="Refresh devices")
            refresh_item.connect("activate", self._on_refresh)
            self.menu.append(refresh_item)
        else:
            assert self._active_device is not None
            status_item = self._gtk.MenuItem(label=f"Casting to {self._active_device.name}")
            status_item.set_sensitive(False)
            self.menu.append(status_item)
            stop_item = self._gtk.MenuItem(label="Stop casting")
            stop_item.connect("activate", self._on_stop)
            self.menu.append(stop_item)

        self.menu.append(self._gtk.SeparatorMenuItem())
        quit_item = self._gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit)
        self.menu.append(quit_item)
        self.menu.show_all()
        self._update_icon()

    def _build_last_device_item(self) -> Any | None:
        last = state.load_last_device()
        if last is None:
            return None
        last_name, audio_only = last
        device = discovery.find_device(self.devices, last_name)
        if device is None:
            return None
        mode = " (audio only)" if audio_only else ""
        item = self._gtk.MenuItem(label=f"Cast to {device.name} again{mode}")
        item.connect("activate", self._on_start, device, audio_only)
        return item

    def _update_icon(self) -> None:
        if self._session is None:
            self.indicator.set_icon_full(self.IDLE_ICON, "Ubuntu Cast (idle)")
        else:
            self.indicator.set_icon_full(self.ACTIVE_ICON, "Ubuntu Cast (casting)")

    def _on_start(self, _widget: Any, device: CastDevice, audio_only: bool) -> None:
        if self._session is not None:
            return
        cast_session: session.AudioSession | session.ScreenSession = (
            session.AudioSession(device) if audio_only else session.ScreenSession(device)
        )
        # Mark busy immediately so a second click can't start a race.
        self._session = cast_session
        self._active_device = device
        self._rebuild_menu()
        threading.Thread(
            target=self._start_worker, args=(cast_session, device, audio_only), daemon=True
        ).start()

    def _start_worker(
        self,
        cast_session: session.AudioSession | session.ScreenSession,
        device: CastDevice,
        audio_only: bool,
    ) -> None:
        try:
            cast_session.start()
        except Exception as error:
            self._glib.idle_add(self._on_start_failed, str(error))
            return
        state.save_last_device(device.name, audio_only)
        self._glib.idle_add(self._rebuild_menu)

    def _on_start_failed(self, message: str) -> bool:
        self._session = None
        self._active_device = None
        self._rebuild_menu()
        self._notify_error("Ubuntu Cast", f"Could not start casting: {message}")
        return False

    def _on_stop(self, _widget: Any = None) -> None:
        cast_session = self._session
        if cast_session is None:
            return
        self._session = None
        self._active_device = None
        self._rebuild_menu()
        threading.Thread(target=self._stop_worker, args=(cast_session,), daemon=True).start()

    def _stop_worker(self, cast_session: session.AudioSession | session.ScreenSession) -> None:
        try:
            cast_session.stop()
        except Exception as error:
            self._glib.idle_add(self._notify_error, "Ubuntu Cast", f"Error stopping cast: {error}")

    def _notify_error(self, title: str, message: str) -> bool:
        with contextlib.suppress(FileNotFoundError):
            subprocess.run(["notify-send", "--icon=dialog-error", title, message], check=False)
        return False

    def _on_refresh(self, _widget: Any) -> None:
        self.devices = discovery.discover(timeout=5.0)
        self._rebuild_menu()

    def _on_quit(self, _widget: Any) -> None:
        self._on_stop()
        self._gtk.main_quit()


def run(timeout: float = 5.0) -> None:
    """Discover devices, show the tray icon, and block on the GTK main loop."""
    indicator_module, gtk, glib = _import_indicator()
    devices = discovery.discover(timeout=timeout)
    app = TrayApp(indicator_module, gtk, glib, devices)
    del app  # kept alive by the GTK menu's signal connections
    gtk.main()
