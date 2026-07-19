# Intent & Plan — ubuntu-cast

## Purpose

A single, friendly CLI command that mirrors an Ubuntu desktop (screen + audio) to a
Chromecast device on the local network. It replaces mkchromecast, which is
unmaintained (last release 2020), audio-only in practice on modern systems, and
predates the Wayland/PipeWire desktop stack that current Ubuntu ships.

The experience we want:

```
$ ubuntu-cast
✔ Found 2 devices
❯ Living Room TV   (Chromecast Ultra)
  Bedroom speaker  (Google Home Mini)

⠹ Casting screen + audio to Living Room TV   1080p · 30 fps · 4.2 Mb/s · 00:12:31
  [q] stop   [v] volume   [p] pause
```

Guiding principles:

- **Zero-config first run.** Discover devices, pick one, casting starts. Flags exist
  for power users, not as prerequisites.
- **Look good, be informative.** Live status (device, resolution, bitrate, elapsed
  time), clear spinners/progress, and actionable error messages ("Chromecast needs
  H.264 ≤1080p — falling back to 1080p") instead of stack traces.
- **Fail helpfully.** Every failure mode (no devices found, portal permission
  denied, port in use) gets a human explanation and a suggested fix.

## Non-goals (for now)

- Casting to non-Google protocols (Miracast, AirPlay, DLNA).
- Casting individual files or YouTube URLs — `catt` already does that well.
- Sub-second latency. Chromecast's buffered HTTP playback means ~2–5 s of delay;
  fine for movies/photos/presentations, not for gaming.
- Windows/macOS support. Ubuntu (and Wayland-era Linux generally) is the target.

## Target environment

Verified on the primary dev machine:

- Ubuntu 24.04, **Wayland** session (GNOME) — so no `x11grab`; capture must go
  through the XDG desktop portal + PipeWire.
- Audio: PipeWire 1.0 with PulseAudio compat layer — desktop audio is captured
  from a sink's monitor source.
- ffmpeg 6.1 available; GStreamer is the likely capture path (see below).

## Technical approach

Chromecast's Default Media Receiver plays media fetched over HTTP: H.264 + AAC,
max 1080p on most devices. So "mirroring" is really a low-latency live stream:

```
┌──────────────────────┐   ┌──────────────────────┐
│ Screen (XDG portal → │   │ Audio (PipeWire      │
│ PipeWire video node) │   │ monitor source)      │
└──────────┬───────────┘   └──────────┬───────────┘
           └──────────┬───────────────┘
                      ▼
        GStreamer pipeline: encode H.264 (VA-API when
        available, x264 fallback) + AAC, mux to fMP4/HLS
                      ▼
        Local HTTP server (aiohttp) serving the live stream
                      ▼
        pychromecast: mDNS discovery + tell the device
        to play http://<this-machine>:<port>/stream
```

Key decisions:

- **Python 3.12+** — pychromecast is the mature Cast library, PyGObject gives
  first-class GStreamer bindings, and rich/typer make a polished CLI cheap.
- **GStreamer over ffmpeg for capture** — ffmpeg has no PipeWire video source, so
  the portal-negotiated screen node is only reachable via `pipewiresrc`. ffmpeg
  stays a fallback for X11 sessions (`x11grab`) if we ever need it.
- **Typer + Rich** for the CLI: subcommands, `--help` that reads well, live status
  tables, interactive device picker.
- **fMP4 first, HLS if needed.** A single fragmented-MP4 HTTP response is the
  simplest live container the Default Media Receiver accepts; switch to LL-HLS
  only if buffering proves problematic.
- **uv** for project/deps management; installable via `uv tool install` / pipx.

## CLI surface (planned)

| Command | Behavior |
|---|---|
| `ubuntu-cast` | Interactive: discover, pick device, start mirroring |
| `ubuntu-cast devices` | List Cast devices found on the network |
| `ubuntu-cast start -d "Living Room TV"` | Non-interactive start (scriptable) |
| `ubuntu-cast start --audio-only` | Cast desktop audio without video |
| `ubuntu-cast stop` | Stop casting and restore the device |
| `ubuntu-cast doctor` | Check portal, PipeWire, codecs, network reachability |

Quality flags on `start`: `--resolution 1080p|720p`, `--fps 30|60`,
`--bitrate`, `--hw/--no-hw` (VA-API toggle).

## Roadmap

- **Phase 0 — Bootstrap.** Repo, `uv` project layout, ruff + pytest, CI stub. ✅ (this PR)
- **Phase 1 — Discovery.** `devices` command with a rich table (name, model, IP);
  interactive picker component.
- **Phase 2 — Audio-only casting.** Simplest end-to-end slice: PipeWire monitor →
  AAC → HTTP → cast. Proves the serve-and-cast plumbing without portal complexity.
- **Phase 3 — Screen + audio.** XDG portal ScreenCast negotiation, combined
  GStreamer pipeline, fMP4 live mux. The core deliverable.
- **Phase 4 — Polish.** Live status UI, keyboard controls (stop/volume/pause),
  `doctor` command, friendly error catalog, quality presets.
- **Phase 5 — Packaging.** pipx/uv install docs, man page, maybe a .deb.

## Known risks

- **Portal UX:** Wayland shows a screen-picker dialog on every session start; a
  restore-token can make repeat casts prompt-free — worth doing early.
- **Latency expectations:** document the ~2–5 s delay prominently so it isn't
  reported as a bug.
- **Encoder availability:** VA-API varies by GPU/driver; `doctor` must detect and
  the pipeline must fall back to x264 cleanly.
