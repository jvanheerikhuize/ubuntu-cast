# Purpose

**Problem:** Mirroring an Ubuntu desktop to a Chromecast has no good answer on a
modern Linux stack. `mkchromecast` — the tool everyone lands on — last shipped in
2020, is audio-only in practice, and predates Wayland and PipeWire entirely.
`catt` casts files and URLs but never the desktop. Under Wayland there is no
global screen to scrape, so every X11-era screen-grab approach is structurally
dead: capture has to be negotiated through the XDG desktop portal and delivered
over PipeWire.

**Audience:** Ubuntu desktop users who want to put a screen or desktop audio on a
TV or speaker — presentations, photos, a movie — without buying an HDMI cable,
installing a vendor agent, or leaving the terminal.

**Key constraints:**

- **Wayland-first.** Screen capture goes through the XDG portal and
  `pipewiresrc`; ffmpeg has no PipeWire video source, so GStreamer is the capture
  path.
- **Meet the receiver where it is.** The Cast Default Media Receiver plays media
  fetched over HTTP — H.264 + AAC, 1080p on most devices. "Mirroring" is really a
  low-latency live stream served from this machine.
- **Zero-config first run.** Discover, pick, cast. Flags are for power users, not
  prerequisites. A portal restore token makes repeat casts prompt-free.
- **No vendor account, no API key, no cloud.** Everything happens on the LAN.
- **Ubuntu/GNOME Wayland is the target.** Not Windows, not macOS, not X11.

**Success metric:** From a cold start on a fresh Ubuntu 24.04 install, a user
runs `ubuntu-cast`, picks their TV from a list, and sees their screen on it —
with no config file, no manual codec selection, and no more than one permission
dialog ever.

**Explicit non-goals:** Non-Cast protocols (Miracast, AirPlay, DLNA); casting
individual files or YouTube URLs (`catt` does that well); sub-second latency —
the receiver's buffered HTTP playback means 2–5 s of delay, which is fine for
video and presentations and useless for gaming.

See [INTENT.md](INTENT.md) for the technical approach and [ROADMAP.md](ROADMAP.md)
for what's built and what's next.
