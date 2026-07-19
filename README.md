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

Screen casting pops the system screen-share dialog once per session — pick the
monitor to mirror and approve. Stop any time with **Ctrl+C**; the Chromecast is
returned to its idle screen.

Expect **2–5 seconds of delay**: the Chromecast buffers its HTTP stream. That's
fine for movies, photos, and presentations — not for gaming.

## Installation

From a checkout, with [uv](https://docs.astral.sh/uv/):

```bash
git clone git@github.com:jvanheerikhuize/ubuntu-cast.git
cd ubuntu-cast
uv sync
uv run ubuntu-cast doctor
```

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

See [INTENT.md](INTENT.md) for the full plan. Phases 1–3 (discovery, audio-only
casting, screen + audio casting) are done; next up is polish (live status UI,
keyboard controls, quality presets) and packaging.
