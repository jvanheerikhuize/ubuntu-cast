# ubuntu-cast

Cast your Ubuntu desktop — screen **and** audio — to a Chromecast from the terminal.

A modern replacement for mkchromecast, built for today's Ubuntu desktop stack:
Wayland screen capture through the XDG desktop portal, PipeWire audio, hardware
H.264 encoding via VA-API, and a clean Typer/Rich CLI.

```
$ ubuntu-cast
✔ Found 2 devices
❯ woonkamer TV       (Chromecast)
  woonkamer speaker  (Nest Mini)

⛶ Casting your screen to woonkamer TV
  http://192.168.178.x:PORT/stream
  Press Ctrl+C to stop.
```

## Usage

| Command | What it does |
|---|---|
| `ubuntu-cast` | Interactive: discover devices, pick one, start casting |
| `ubuntu-cast devices` | List Cast devices on the local network |
| `ubuntu-cast start -d "woonkamer TV"` | Non-interactive start (device name or unique prefix) |
| `ubuntu-cast start -d TV --audio-only` | Cast desktop audio without the screen |
| `ubuntu-cast doctor` | Check that this machine is ready to cast |
| `ubuntu-cast install-launcher` | Add an "Ubuntu Cast" launcher to the GNOME app grid |

The first screen cast pops the system screen-share dialog — pick the monitor to
mirror and approve. Your choice is remembered (a portal restore token in
`~/.local/state/ubuntu-cast/`), so later casts start with **no dialog at all**.
Revoke it any time under GNOME Settings → Apps → Screen Sharing, or delete the
token file. Stop casting with **Ctrl+C**; the Chromecast returns to its idle
screen.

Expect **2–5 seconds of delay**: the Chromecast buffers its HTTP stream. That's
fine for movies, photos, and presentations — not for gaming.

## Installation

With [uv](https://docs.astral.sh/uv/):

```bash
git clone git@github.com:jvanheerikhuize/ubuntu-cast.git
uv tool install --editable ./ubuntu-cast
ubuntu-cast doctor
```

`uv tool install` puts `ubuntu-cast` on your PATH so it works from any
terminal; `--editable` makes the installed command track the checkout, so a
`git pull` is all an upgrade takes. Then make it feel like an app:

```bash
ubuntu-cast install-launcher
```

That adds **Ubuntu Cast** to the GNOME Activities overview (right-click the
icon for audio-only). It opens in a terminal window — that's where the device
picker and the live status panel run; Ctrl+C there stops the cast. For
one-keystroke casting, bind a custom shortcut in GNOME Settings → Keyboard to
`gtk-launch ubuntu-cast` (it opens that same terminal launcher).

For development, run from the checkout instead: `uv sync`, then
`uv run ubuntu-cast`.

System requirements (Ubuntu 24.04, GNOME Wayland session):

```bash
sudo apt install gstreamer1.0-tools gstreamer1.0-pipewire \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly \
  gstreamer1.0-vaapi gstreamer1.0-libav
```

`gstreamer1.0-vaapi` enables hardware H.264 encoding (Intel/AMD); without it the
pipeline falls back to software x264. Run `ubuntu-cast doctor` — every
requirement is checked and each failure comes with the command that fixes it.

## How it works

```
screen: XDG portal ─▶ PipeWire node ─▶ pipewiresrc ─▶ H.264 (VA-API / x264) ─┐
                                                                             ├─▶ fMP4 ─▶ local HTTP ─▶ Chromecast
audio:  PipeWire default-sink monitor ─▶ pulsesrc ─▶ AAC ────────────────────┘
```

The Chromecast's Default Media Receiver simply plays a live fragmented-MP4
stream served from your machine. Discovery and playback control go through
[pychromecast](https://github.com/home-assistant-libs/pychromecast); the portal
handshake is plain D-Bus via [jeepney](https://gitlab.com/takluyver/jeepney).
Audio-only mode skips the portal entirely and streams live MP3.

## Development

```bash
uv run pytest        # test suite
uv run ruff check .  # lint
uv run ruff format . # format
```

See [INTENT.md](INTENT.md) for the full plan. Phases 1–5 (discovery, audio-only
casting, screen + audio casting, performance + live status UI, seamless launch)
are done; remaining ideas: quality presets, a tray indicator, deb packaging.
