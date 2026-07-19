"""Negotiate Wayland screen capture through the XDG Desktop Portal.

The portal handshake (CreateSession → SelectSources → Start) pops the system
"share your screen" dialog; Start's response carries the PipeWire node id and
OpenPipeWireRemote hands us a connection fd that GStreamer's pipewiresrc can
use. The D-Bus session — and therefore the capture — stays alive until close().
"""

from __future__ import annotations

import contextlib
import secrets
import threading

from jeepney import DBusAddress, MatchRule, new_method_call
from jeepney.bus_messages import message_bus
from jeepney.io.blocking import DBusConnection, Proxy, open_dbus_connection
from jeepney.wrappers import unwrap_msg

_DESKTOP_BUS = "org.freedesktop.portal.Desktop"
_PORTAL_PATH = "/org/freedesktop/portal/desktop"

_SCREENCAST = DBusAddress(
    _PORTAL_PATH, bus_name=_DESKTOP_BUS, interface="org.freedesktop.portal.ScreenCast"
)

SOURCE_MONITOR = 1
CURSOR_EMBEDDED = 2
# persist_mode: keep the user's screen selection until they revoke it, so a
# restore_token can skip the share dialog on later runs.
PERSIST_UNTIL_REVOKED = 2

_REPLY_TIMEOUT = 30.0
# Start() blocks on the human answering the share dialog — give them time.
_DIALOG_TIMEOUT = 300.0


class PortalError(RuntimeError):
    pass


def request_path(unique_name: str, token: str) -> str:
    """Predictable Request object path, per the portal spec."""
    sender = unique_name.lstrip(":").replace(".", "_")
    return f"{_PORTAL_PATH}/request/{sender}/{token}"


def select_sources_options(restore_token: str | None) -> dict:
    """SelectSources options; a valid restore token skips the share dialog."""
    options = {
        "types": ("u", SOURCE_MONITOR),
        "cursor_mode": ("u", CURSOR_EMBEDDED),
        "persist_mode": ("u", PERSIST_UNTIL_REVOKED),
    }
    if restore_token:
        # The portal ignores unknown/revoked tokens and shows the dialog.
        options["restore_token"] = ("s", restore_token)
    return options


class ScreenCastSession:
    """One portal ScreenCast session; keep it open for the capture's lifetime."""

    def __init__(self) -> None:
        self._conn: DBusConnection | None = None
        self._session_handle: str | None = None
        # Set by open(); persist it to skip the share dialog next run.
        self.restore_token: str | None = None
        # jeepney's blocking connection is not thread-safe; HTTP handler
        # threads call open_pipewire_fd() while the main thread may close().
        self._lock = threading.Lock()

    def open(self, restore_token: str | None = None) -> int:
        """Run the portal handshake; shows the system share dialog.

        A restore_token from an earlier approved run skips the dialog. Returns
        the PipeWire node id of the approved stream; self.restore_token then
        holds the (possibly renewed) token to persist for the next run. Call
        open_pipewire_fd() for a connection fd to read the stream with.
        """
        self._conn = open_dbus_connection(bus="SESSION", enable_fds=True)
        session_token = "ubuntu_cast_" + secrets.token_hex(4)
        results = self._request(
            "CreateSession",
            "a{sv}",
            ({"session_handle_token": ("s", session_token)},),
        )
        self._session_handle = results["session_handle"][1]
        self._request(
            "SelectSources",
            "oa{sv}",
            (self._session_handle, select_sources_options(restore_token)),
        )
        results = self._request(
            "Start", "osa{sv}", (self._session_handle, "", {}), timeout=_DIALOG_TIMEOUT
        )
        self.restore_token = results.get("restore_token", (None, None))[1]
        streams = results["streams"][1]
        if not streams:
            raise PortalError("the portal approved the session but returned no streams")
        return streams[0][0]

    def open_pipewire_fd(self) -> int:
        """A fresh PipeWire connection fd. Each fd is a single-consumer socket,
        so every pipeline needs its own; the caller owns closing it."""
        remote = new_method_call(
            _SCREENCAST, "OpenPipeWireRemote", "oa{sv}", (self._session_handle, {})
        )
        with self._lock:
            if self._conn is None:
                raise PortalError("the portal session is closed")
            reply = unwrap_msg(self._conn.send_and_get_reply(remote, timeout=_REPLY_TIMEOUT))
        return reply[0].to_raw_fd()

    def _request(
        self, method: str, signature: str, body: tuple, timeout: float = _REPLY_TIMEOUT
    ) -> dict:
        """Call a portal method and wait for its Request's Response signal."""
        assert self._conn is not None
        token = "ubuntu_cast_" + secrets.token_hex(4)
        options = body[-1]
        options["handle_token"] = ("s", token)
        rule = MatchRule(
            type="signal",
            interface="org.freedesktop.portal.Request",
            member="Response",
            path=request_path(self._conn.unique_name, token),
        )
        Proxy(message_bus, self._conn).AddMatch(rule)
        with self._conn.filter(rule) as responses:
            call = new_method_call(_SCREENCAST, method, signature, body)
            unwrap_msg(self._conn.send_and_get_reply(call, timeout=_REPLY_TIMEOUT))
            signal = self._conn.recv_until_filtered(responses, timeout=timeout)
        code, results = signal.body
        if code == 1:
            raise PortalError("screen sharing was cancelled in the system dialog")
        if code != 0:
            raise PortalError(f"portal request {method} failed (response code {code})")
        return results

    def close(self) -> None:
        """End the portal session and drop the D-Bus connection."""
        with self._lock:
            if self._conn is None:
                return
            if self._session_handle is not None:
                session = DBusAddress(
                    self._session_handle,
                    bus_name=_DESKTOP_BUS,
                    interface="org.freedesktop.portal.Session",
                )
                with contextlib.suppress(Exception):
                    self._conn.send_and_get_reply(
                        new_method_call(session, "Close"), timeout=_REPLY_TIMEOUT
                    )
                self._session_handle = None
            self._conn.close()
            self._conn = None
