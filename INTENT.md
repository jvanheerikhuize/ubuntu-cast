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

- **Phase 0 — Bootstrap.** Repo, `uv` project layout, ruff + pytest, CI stub. ✅
- **Phase 1 — Discovery.** `devices` command with a rich table (name, model, IP);
  interactive picker component. ✅
- **Phase 2 — Audio-only casting.** Simplest end-to-end slice: PipeWire monitor →
  AAC → HTTP → cast. Proves the serve-and-cast plumbing without portal complexity. ✅
- **Phase 3 — Screen + audio.** XDG portal ScreenCast negotiation, combined
  GStreamer pipeline, fMP4 live mux. The core deliverable. ✅
- **Phase 4 — Polish.** Live status UI, `doctor` command, friendly error catalog. ✅
- **Phase 5 — Seamless launch.** Portal restore token, GNOME `.desktop` launcher. ✅
- **Phase 6 — Tray indicator.** GNOME top-bar icon, last-device recall, failure
  notifications. ✅

### Phase 7 — Hardening

The stream server was built for "it works on my desk"; these are the gaps that
matter once it runs on someone else's network.

- **Authenticate the stream.** `StreamServer` binds `0.0.0.0` and serves
  `/stream` to anyone who asks — on a café or office LAN that is an open window
  onto the user's screen. The Default Media Receiver can't send auth headers, so
  the fix is two cheap layers: an unguessable per-session path
  (`/stream/<secrets.token_urlsafe(16)>`) plus a peer-address check that only
  admits the Chromecast we handed the URL to. Highest-value item on this list.
- **Cap concurrent pipelines.** Every `GET /stream` spawns an encoder
  subprocess. A port scanner (or a stuck client reconnect loop) can spawn them
  without bound, each one pulling a fresh PipeWire fd. Refuse with 503 past a
  small limit.
- **Don't hand a hung encoder a free pass.** In `stream.py` the teardown runs
  `pipeline.terminate(); pipeline.wait(timeout=5)` inside `finally` — a pipeline
  that ignores SIGTERM raises `TimeoutExpired` out of the handler and is never
  killed. Follow up with `kill()` and a second wait.
- **Move the pipeline log out of `/tmp`.** `ubuntu-cast-pipeline.log` is a
  predictable path opened with `"ab"`; on a shared machine another user can
  pre-create it as a symlink and redirect our appends. Write it under
  `$XDG_STATE_HOME/ubuntu-cast/` instead, and truncate or rotate it so a long
  cast can't fill the disk.
- **Tighten state-file permissions.** The restore token is what makes casting
  prompt-free — anything that can read it can start a capture without the user
  seeing a dialog. Create the state dir `0700` and the token file `0600`.
- **Idle auto-stop.** If the Chromecast drops off the network the session stays
  up, capturing and encoding forever. Stop (or notify) after the stream has had
  no active client for ~30 s.
- **Interface selection.** `local_ip_for` picks whatever route the kernel offers,
  which on a VPN is often an address the Chromecast can't reach. Detect the
  mismatch in `doctor` and allow `--bind-address`.
- **CI that actually runs.** Phase 0 promised a stub, but there's no
  `.github/workflows/` — add ruff + pytest on 3.12/3.13 so the suite gates PRs.

### Phase 8 — Features

- **Quality flags.** `--resolution`, `--fps`, `--bitrate`, `--hw/--no-hw` from the
  CLI table above are still unimplemented: `video.py` hardcodes 8000 kb/s and
  pins 30 fps, with no scaling. Presets (`--quality low|balanced|high`) on top.
- **`ubuntu-cast stop`.** The CLI table lists it and nothing implements it —
  today the only ways to stop are Ctrl+C in the owning terminal or the tray menu.
  Needs a session pidfile/socket in the state dir, which also unlocks scripting.
- **Keyboard controls.** The mockup at the top of this file advertises
  `[q] stop  [v] volume  [p] pause`; the live status panel is read-only so far.
- **Reconnect on blips.** A Wi-Fi hiccup ends the cast. Retry the media
  controller a few times before giving up, and say so in the status line.
- **Window and region capture.** The portal can hand back a single window or a
  chosen region, not just a whole monitor — the obvious ask for presentations.
  `--window` / `--region`, with the choice remembered like the monitor is.
- **Cursor toggle.** The portal's cursor mode is negotiable; `--no-cursor` is a
  one-line win for screen recordings and demos.
- **Cast to speaker groups.** pychromecast surfaces multi-device groups; useful
  in audio-only mode and currently invisible in the picker.
- **Config file.** `$XDG_CONFIG_HOME/ubuntu-cast/config.toml` for default device,
  quality, and audio-only preference, so the flags don't have to be retyped.
- **`doctor --json`.** Machine-readable diagnostics make bug reports a paste
  instead of a screenshot.
- **An end-to-end test.** The suite unit-tests each module but never runs the
  serve-and-cast loop. A fake Chromecast (HTTP client + stub media controller)
  against a real `StreamServer` would catch the wiring regressions unit tests
  can't see.

### Phase 9 — Distribution

- pipx/uv install docs ✅, man page, shell completions (Typer generates them).
- A `.deb` or PPA so the GStreamer/PyGObject system deps come along instead of
  being an `apt install` line in the README.

## Known risks

- **Portal UX:** Wayland shows a screen-picker dialog on every session start; a
  restore-token can make repeat casts prompt-free — worth doing early.
- **Latency expectations:** document the ~2–5 s delay prominently so it isn't
  reported as a bug.
- **Encoder availability:** VA-API varies by GPU/driver; `doctor` must detect and
  the pipeline must fall back to x264 cleanly.
