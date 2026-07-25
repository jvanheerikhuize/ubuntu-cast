# ubuntu-cast

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)

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
| `ubuntu-cast` | Shows the tray icon (falls back to the terminal picker if the tray isn't installed) |
| `ubuntu-cast pick` | Interactive: discover devices, pick one, start casting |
| `ubuntu-cast devices` | List Cast devices on the local network |
| `ubuntu-cast start -d "woonkamer TV"` | Non-interactive start (device name or unique prefix) |
| `ubuntu-cast start -d TV --audio-only` | Cast desktop audio without the screen |
| `ubuntu-cast start -d TV -q high` | Quality preset: `low`, `balanced` (default), or `high` |
| `ubuntu-cast stop` | Stop the cast running in another terminal or in the tray |
| `ubuntu-cast doctor` | Check that this machine is ready to cast |
| `ubuntu-cast install-launcher` | Add an "Ubuntu Cast" launcher to the GNOME app grid |
| `ubuntu-cast tray` | Show a GNOME top-bar icon to start/stop casting, no terminal needed |
| `ubuntu-cast install-autostart` | Start the tray icon automatically at login |

The first screen cast pops the system screen-share dialog — pick the monitor to
mirror and approve. Your choice is remembered (a portal restore token in
`~/.local/state/ubuntu-cast/`), so later casts start with **no dialog at all**.
Revoke it any time under GNOME Settings → Apps → Screen Sharing, or delete the
token file. Stop casting with **Ctrl+C**, or `ubuntu-cast stop` from any
other terminal; the Chromecast returns to its idle screen.

Expect **2–5 seconds of delay**: the Chromecast buffers its HTTP stream. That's
fine for movies, photos, and presentations — not for gaming.

## Install

Requires Ubuntu 24.04 (or similar), a GNOME Wayland session, and
[uv](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:jvanheerikhuize/ubuntu-cast.git
uv tool install --editable ./ubuntu-cast
```

`uv tool install` puts `ubuntu-cast` on your PATH so it works from any
terminal; `--editable` makes the installed command track the checkout, so a
`git pull` in `./ubuntu-cast` is all an upgrade takes.

Install the system packages the pipeline needs:

```bash
sudo apt install gstreamer1.0-tools gstreamer1.0-pipewire \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly \
  gstreamer1.0-vaapi gstreamer1.0-libav
```

`gstreamer1.0-vaapi` enables hardware H.264 encoding (Intel/AMD); without it
the pipeline falls back to software x264.

Then verify everything is wired up:

```bash
ubuntu-cast doctor
```

Every requirement is checked and each failure comes with the exact command
that fixes it.

### Optional: app launcher

```bash
ubuntu-cast install-launcher
```

Adds **Ubuntu Cast** to the GNOME Activities overview (right-click the icon
for audio-only). It opens in a terminal window — that's where the device
picker and the live status panel run; Ctrl+C there stops the cast. For
one-keystroke casting, bind a custom shortcut in GNOME Settings → Keyboard to
`gtk-launch ubuntu-cast` (it opens that same terminal launcher).

### Optional: top-bar tray icon

Prefer no window at all? `ubuntu-cast tray` puts an icon in the GNOME top bar
with a menu to pick a device (or audio-only) and stop casting — no terminal,
no dialog after the first approved cast. The icon itself shows at a glance
whether you're casting, and the menu leads with a one-click "Cast to \<device\>
again" entry for whichever device (and mode) you used last. If a cast fails to
start or stop, the tray reports it with a desktop notification instead of
failing silently. It needs PyGObject and an AppIndicator typelib that aren't
part of the Python packaging story:

```bash
sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1
```

`ubuntu-cast doctor` reports this as an optional check, since the terminal
launcher works without it. Run `ubuntu-cast install-autostart` to have the
tray icon start automatically every time you log in — after that, the bare
`ubuntu-cast` command (and your session login) both just open the tray, no
manual `tray` subcommand needed.

### For development

Run from the checkout instead of a `uv tool install`: `uv sync`, then
`uv run ubuntu-cast`.

## Run

| Command | What it does |
|---|---|
| `ubuntu-cast` | Shows the tray icon (falls back to the terminal picker if the tray isn't installed) |
| `ubuntu-cast pick` | Interactive: discover devices, pick one, start casting |
| `ubuntu-cast devices` | List Cast devices on the local network |
| `ubuntu-cast start -d "woonkamer TV"` | Non-interactive start (device name or unique prefix) |
| `ubuntu-cast start -d TV --audio-only` | Cast desktop audio without the screen |
| `ubuntu-cast start -d TV -q high` | Quality preset: `low`, `balanced` (default), or `high` |
| `ubuntu-cast stop` | Stop the cast running in another terminal or in the tray |
| `ubuntu-cast doctor` | Check that this machine is ready to cast |
| `ubuntu-cast install-launcher` | Add an "Ubuntu Cast" launcher to the GNOME app grid |
| `ubuntu-cast tray` | Show a GNOME top-bar icon to start/stop casting, no terminal needed |
| `ubuntu-cast install-autostart` | Start the tray icon automatically at login |

The first screen cast pops the system screen-share dialog — pick the monitor to
mirror and approve. Your choice is remembered (a portal restore token in
`~/.local/state/ubuntu-cast/`), so later casts start with **no dialog at all**.
Revoke it any time under GNOME Settings → Apps → Screen Sharing, or delete the
token file. Stop casting with **Ctrl+C**, or `ubuntu-cast stop` from any
other terminal; the Chromecast returns to its idle screen.

Expect **2–5 seconds of delay**: the Chromecast buffers its HTTP stream. That's
fine for movies, photos, and presentations — not for gaming.

## Uninstall

To remove ubuntu-cast completely:

```bash
# Stop any running cast/tray first (Ctrl+C, or close the tray icon).

# Remove the CLI itself
uv tool uninstall ubuntu-cast

# Remove the app launcher, if you installed one
rm -f ~/.local/share/applications/ubuntu-cast.desktop

# Remove the saved portal restore token and any other state
rm -rf ~/.local/state/ubuntu-cast

# Revoke the screen-share permission (optional, matches the deleted token)
# GNOME Settings → Apps → Screen Sharing → remove ubuntu-cast's entry

# Remove the cloned repo, if you no longer need the editable checkout
rm -rf ./ubuntu-cast

# Optional: remove the system packages installed for ubuntu-cast, if nothing
# else on your machine depends on them
sudo apt remove gstreamer1.0-vaapi python3-gi gir1.2-ayatanaappindicator3-0.1
```

`uv tool uninstall` only removes the installed command — it doesn't touch the
git checkout, the desktop launcher, or the saved restore token, so those are
separate steps above. The `apt remove` step is optional and only worth it if
you don't use GStreamer/VA-API/PyGObject for anything else.

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

See [INTENT.md](INTENT.md) for the full plan. Phases 1–6 (discovery, audio-only
casting, screen + audio casting, performance + live status UI, seamless launch,
tray indicator) are done; Phases 7–9 there cover what's next — stream
authentication and other hardening, quality flags, `stop`, window capture, and
deb packaging.

## License

[MIT](LICENSE)

## Roadmap

See [branch: roadmap-hardening](https://github.com/jvanheerikhuize/ubunutu-cast/tree/roadmap-hardening) for 6-phase rollout: quality flags, auth improvements, tray hardening.

---
