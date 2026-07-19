"""Find Google Cast devices on the local network via mDNS."""

from __future__ import annotations

from dataclasses import dataclass

import pychromecast


@dataclass(frozen=True)
class CastDevice:
    name: str
    model: str
    host: str
    port: int
    uuid: str


def discover(timeout: float = 5.0) -> list[CastDevice]:
    """Browse mDNS for Cast devices, returning them sorted by name."""
    infos, browser = pychromecast.discovery.discover_chromecasts(timeout=timeout)
    pychromecast.discovery.stop_discovery(browser)
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
