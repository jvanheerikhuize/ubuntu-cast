"""Find Google Cast devices on the local network via mDNS."""

from __future__ import annotations

import threading
from dataclasses import dataclass

import zeroconf
from pychromecast.discovery import CastBrowser, SimpleCastListener


@dataclass(frozen=True)
class CastDevice:
    name: str
    model: str
    host: str
    port: int
    uuid: str


def discover(timeout: float = 5.0, wanted: str | None = None) -> list[CastDevice]:
    """Browse mDNS for Cast devices, returning them sorted by name.

    With `wanted`, browsing stops as soon as a device with exactly that
    friendly name announces itself, instead of always waiting out the full
    timeout. Prefix matching still needs the whole window: another device
    appearing later could make the prefix ambiguous.
    """
    done = threading.Event()
    browser: CastBrowser | None = None

    def on_added(_uuid: object, _service: str) -> None:
        assert browser is not None
        if wanted is not None and any(
            info.friendly_name == wanted for info in browser.devices.values()
        ):
            done.set()

    browser = CastBrowser(SimpleCastListener(on_added), zeroconf.Zeroconf())
    browser.start_discovery()
    done.wait(timeout)
    infos = list(browser.devices.values())
    browser.stop_discovery()
    devices = [
        CastDevice(
            name=info.friendly_name or "(unnamed)",
            model=info.model_name or "unknown",
            host=info.host,
            port=info.port,
            uuid=str(info.uuid),
        )
        for info in infos
    ]
    return sorted(devices, key=lambda d: d.name.lower())


def find_device(devices: list[CastDevice], name: str) -> CastDevice | None:
    """Match a device by exact name first, then unique case-insensitive prefix."""
    for device in devices:
        if device.name == name:
            return device
    prefix_matches = [d for d in devices if d.name.lower().startswith(name.lower())]
    if len(prefix_matches) == 1:
        return prefix_matches[0]
    return None
