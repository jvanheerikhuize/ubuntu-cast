"""Environment checks: is this machine ready to cast?"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum

from .gstenv import sanitized_env


class Status(Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class CheckResult:
    label: str
    status: Status
    detail: str
    hint: str = ""


def _have_gst_plugin(plugin: str) -> bool:
    if shutil.which("gst-inspect-1.0") is None:
        return False
    result = subprocess.run(
        ["gst-inspect-1.0", "--exists", plugin],
        capture_output=True,
        check=False,
        env=sanitized_env(),
    )
    return result.returncode == 0


def _process_running(name: str) -> bool:
    # pgrep matches the kernel comm name, which is truncated to 15 characters
    result = subprocess.run(["pgrep", "-x", name[:15]], capture_output=True, check=False)
    return result.returncode == 0


def check_session() -> CheckResult:
    session = os.environ.get("XDG_SESSION_TYPE", "unknown")
    if session == "wayland":
        return CheckResult("Display session", Status.OK, "Wayland")
    if session == "x11":
        return CheckResult(
            "Display session",
            Status.WARN,
            "X11",
            "Screen capture will use x11grab instead of the portal (untested path).",
        )
    return CheckResult(
        "Display session",
        Status.FAIL,
        f"unknown ({session})",
        "Run from a desktop session; XDG_SESSION_TYPE is not set.",
    )


def check_pipewire() -> CheckResult:
    if _process_running("pipewire"):
        return CheckResult("PipeWire", Status.OK, "running")
    return CheckResult(
        "PipeWire",
        Status.FAIL,
        "not running",
        "Audio and Wayland screen capture need PipeWire. Try: systemctl --user start pipewire",
    )


def check_portal() -> CheckResult:
    if _process_running("xdg-desktop-portal"):
        return CheckResult("Desktop portal", Status.OK, "running")
    return CheckResult(
        "Desktop portal",
        Status.FAIL,
        "not running",
        "Wayland screen capture needs xdg-desktop-portal. Install/start it and retry.",
    )


def check_gstreamer() -> CheckResult:
    if shutil.which("gst-launch-1.0") is None:
        return CheckResult(
            "GStreamer",
            Status.FAIL,
            "gst-launch-1.0 not found",
            "Install with: sudo apt install gstreamer1.0-tools gstreamer1.0-plugins-good",
        )
    return CheckResult("GStreamer", Status.OK, "installed")


def check_pipewiresrc() -> CheckResult:
    if _have_gst_plugin("pipewiresrc"):
        return CheckResult("GStreamer PipeWire plugin", Status.OK, "pipewiresrc available")
    return CheckResult(
        "GStreamer PipeWire plugin",
        Status.FAIL,
        "pipewiresrc missing",
        "Needed for Wayland screen capture. Install with: sudo apt install gstreamer1.0-pipewire",
    )


def check_h264_encoder() -> CheckResult:
    if _have_gst_plugin("vah264enc") or _have_gst_plugin("vaapih264enc"):
        return CheckResult("H.264 encoder", Status.OK, "hardware (VA-API)")
    if _have_gst_plugin("x264enc"):
        return CheckResult(
            "H.264 encoder",
            Status.WARN,
            "software (x264) only",
            "Works, but costs CPU. For hardware encoding: sudo apt install gstreamer1.0-vaapi",
        )
    return CheckResult(
        "H.264 encoder",
        Status.FAIL,
        "none found",
        "Chromecast needs H.264. Install with: sudo apt install gstreamer1.0-plugins-ugly",
    )


def check_mp3_encoder() -> CheckResult:
    if _have_gst_plugin("lamemp3enc"):
        return CheckResult("MP3 encoder", Status.OK, "lamemp3enc available")
    return CheckResult(
        "MP3 encoder",
        Status.FAIL,
        "lamemp3enc missing",
        "Needed for audio casting. Install with: sudo apt install gstreamer1.0-plugins-good",
    )


def check_aac_encoder() -> CheckResult:
    if _have_gst_plugin("avenc_aac") or _have_gst_plugin("voaacenc"):
        return CheckResult("AAC encoder", Status.OK, "available")
    return CheckResult(
        "AAC encoder",
        Status.FAIL,
        "none found",
        "Needed for screen casting audio. Install with: sudo apt install gstreamer1.0-libav",
    )


def check_appindicator() -> CheckResult:
    from . import tray

    try:
        namespace = tray.find_appindicator_namespace()
    except RuntimeError as error:
        return CheckResult(
            "Tray indicator (optional)",
            Status.WARN,
            str(error),
            "sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1",
        )
    if namespace is None:
        return CheckResult(
            "Tray indicator (optional)",
            Status.WARN,
            "AppIndicator typelib missing",
            "Needed for `ubuntu-cast tray`. Install with: "
            "sudo apt install gir1.2-ayatanaappindicator3-0.1",
        )
    return CheckResult("Tray indicator (optional)", Status.OK, f"{namespace} available")


def run_all_checks() -> list[CheckResult]:
    return [
        check_session(),
        check_pipewire(),
        check_portal(),
        check_gstreamer(),
        check_pipewiresrc(),
        check_h264_encoder(),
        check_aac_encoder(),
        check_mp3_encoder(),
        check_appindicator(),
    ]
