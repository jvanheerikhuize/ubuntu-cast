# Roadmap — ubuntu-cast

The technical approach lives in [INTENT.md](INTENT.md); why the project exists is
in [PURPOSE.md](PURPOSE.md). This file tracks what is built, what is in flight,
and what comes next.

Status as of 2026-07-25: **~1,600 lines across 14 modules, 11 test files, phases
0–6 shipped.** The tool works end to end on the primary dev machine. What remains
is the gap between "works on my desk" and "safe on someone else's network".

## Shipped

| Phase | What landed |
|---|---|
| 0 — Bootstrap | `uv` layout, ruff, pytest |
| 1 — Discovery | `devices` command, rich table, interactive picker |
| 2 — Audio-only | PipeWire monitor → AAC → HTTP → cast |
| 3 — Screen + audio | XDG portal negotiation, GStreamer pipeline, fMP4 live mux |
| 4 — Polish | Live status UI, `doctor`, error catalog, perf work |
| 5 — Seamless launch | Portal restore token, GNOME `.desktop` launcher |
| 6 — Tray indicator | Top-bar icon, last-device recall, failure notifications |

## In flight

Two branches carry unmerged work. Land or close these before starting anything
below them.

- **`feat/quality-flags-and-stop`** — 3 commits, +690/−59. Implements the
  `--resolution/--fps/--bitrate/--hw` flags, `--quality` presets, and
  `ubuntu-cast stop` (new `quality.py`, session pidfile in `state.py`), with
  tests. This covers the first two items of Phase 8 below.
- **`worktree-roadmap-hardening`** — the roadmap draft this file supersedes.

Note: `worktree-roadmap-hardening` adds its roadmap to `INTENT.md`. Once this
file exists that content is duplicated in two places — fold it into `ROADMAP.md`
and keep `INTENT.md` focused on technical approach.

## Phase 7 — Hardening

The stream server was built for a trusted LAN. Every item below was **verified
against `main` on 2026-07-25**, not inherited from an older draft.

Ordered by value:

1. **Authenticate the stream.** `stream.py:46` binds `0.0.0.0` and `stream.py:21`
   serves a fixed `/stream` path with no auth — on a café or office LAN that is
   an open window onto the user's screen. The Default Media Receiver can't send
   auth headers, so use two cheap layers: an unguessable per-session path
   (`secrets.token_urlsafe(16)`) plus a peer-address check admitting only the
   device we handed the URL to. **Highest-value item in the project.**
2. **Tighten state-file permissions.** `state.py:31` creates the state dir with
   default `0755` and `write_text` leaves the token `0644`. The restore token is
   what makes casting prompt-free — anything that can read it can start a capture
   with no dialog. Create `0700`/`0600`.
3. **Move the pipeline log out of `/tmp`.** `stream.py:27` returns a predictable
   `/tmp/ubuntu-cast-pipeline.log`, opened `"ab"` at `stream.py:91`. On a shared
   machine another user can pre-create it as a symlink and redirect our appends.
   Write under `$XDG_STATE_HOME/ubuntu-cast/` and rotate it.
4. **Cap concurrent pipelines.** Every `GET /stream` spawns an encoder subprocess
   (`stream.py:92`) with no limit. A port scanner or a reconnect loop can spawn
   them without bound, each taking a fresh PipeWire fd. Refuse with 503 past a
   small limit.
5. **Kill a hung encoder.** `stream.py:114-115` runs `terminate()` then
   `wait(timeout=5)` inside `finally` — a pipeline ignoring SIGTERM raises
   `TimeoutExpired` out of the handler and is never killed. Follow with `kill()`
   and a second wait.
6. **Idle auto-stop.** If the device drops off the network the session captures
   and encodes forever. `active_streams` is already tracked (`stream.py:54`); stop
   or notify after ~30 s with no client.
7. **Interface selection.** `local_ip_for` (`stream.py:136`) takes whatever route
   the kernel offers, which on a VPN is often an address the device can't reach.
   Detect the mismatch in `doctor`; add `--bind-address`.
8. **CI that actually runs.** Phase 0 promised a stub and there is still no
   `.github/workflows/` — ubuntu-cast is one of 13 workspace repos with no CI.
   Ruff + pytest on 3.12/3.13 gating PRs.

## Phase 8 — Features

- **Quality flags and `stop`** — implemented on `feat/quality-flags-and-stop`;
  merge rather than rebuild.
- **Keyboard controls.** `INTENT.md` advertises `[q] stop [v] volume [p] pause`;
  the live panel is still read-only.
- **Reconnect on blips.** A Wi-Fi hiccup ends the cast. Retry the media
  controller a few times before giving up, and say so in the status line.
- **Window and region capture.** The portal can return a single window or a
  region, not just a monitor — the obvious ask for presentations. `--window` /
  `--region`, remembered like the monitor is.
- **Monitor selection.** On multi-head setups the portal dialog picks the screen
  once and the restore token freezes that choice. Needs a way to re-pick without
  deleting the token.
- **Cursor toggle.** Portal cursor mode is negotiable; `--no-cursor` is a
  one-line win for recordings and demos.
- **Cast to speaker groups.** pychromecast surfaces multi-device groups; useful
  in audio-only mode and currently invisible in the picker.
- **Config file.** `$XDG_CONFIG_HOME/ubuntu-cast/config.toml` for default device,
  quality, and audio-only preference.
- **`doctor --json`.** Machine-readable diagnostics turn a bug report into a
  paste instead of a screenshot.
- **An end-to-end test.** The suite unit-tests each module but never runs the
  serve-and-cast loop. A fake receiver (HTTP client + stub media controller)
  against a real `StreamServer` would catch wiring regressions unit tests can't.

## Phase 9 — Distribution

- Man page and shell completions (Typer generates them).
- A `.deb` or PPA so the GStreamer/PyGObject system deps come along instead of
  being an `apt install` line in the README.

## Phase 10 — The receiver landscape shifted

This is new strategic ground, not covered by earlier drafts.

Google **discontinued the standalone Chromecast dongle in 2024**, replacing it
with the Google TV Streamer, and rebranded "Chromecast built-in" back to **Google
Cast**. In May 2026 a support-page edit triggered widespread reports that Google
had ended support for nearly every Chromecast model; Google publicly denied it,
but the older dongles are visibly degrading and the 2022 Chromecast with Google
TV (HD) is the model still under a support guarantee — through 2027.

What this means here:

- **The protocol is fine; the hardware assumption isn't.** Cast is being
  actively developed and rebranded, not retired. But "Chromecast" as the mental
  model is now wrong — most receivers in the field are Cast-built-in TVs
  (Sony, Samsung, LG), Nest speakers, and Google TV Streamers.
- **Rename the user-facing vocabulary** from "Chromecast" to "Cast device". The
  code already says `CastDevice`; the docs and CLI help lag.
- **Negotiate capability instead of assuming it.** `video.py` doesn't scale — it
  passes the portal's native resolution through and pins framerate to 30/1
  (`video.py:84`), with a bitrate chosen for 1080p (`video.py:9`). So a 4K
  desktop is already sent at 4K, at a 1080p bitrate, to a device that may not
  decode it. The quality flags on `feat/quality-flags-and-stop` make this
  *controllable*; the next step is making it *automatic* — read the device's
  model and capabilities from pychromecast and pick resolution and bitrate to
  match, rather than leaving the user to discover the mismatch as a black screen.
- **Build a real test matrix.** Currently verified on one dev machine against a
  Chromecast and a Nest Mini. At minimum: a Google TV Streamer, one Cast-built-in
  TV, and one speaker group.
- **Watch Matter Casting.** The emerging cross-vendor alternative, and the reason
  Google is comfortable downsizing Cast's scope. Still a non-goal — but the one
  worth re-examining annually, because it is the plausible successor protocol.

## Known risks

- **Portal UX.** Wayland prompts on every session start without a restore token.
  Mitigated in Phase 5, but revoking and re-granting is still clumsy.
- **Latency expectations.** The 2–5 s delay is inherent to buffered HTTP
  playback. Documented prominently so it isn't filed as a bug.
- **Encoder availability.** VA-API varies by GPU and driver; `doctor` detects it
  and the pipeline falls back to x264.
- **Single-maintainer surface area.** 14 modules spanning D-Bus, GStreamer,
  mDNS, HTTP, and GTK — each an independent breakage source across Ubuntu
  releases. CI (Phase 7) is the cheapest defence.
