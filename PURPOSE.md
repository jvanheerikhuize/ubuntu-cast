# Purpose

**Problem:** Recording and transcribing podcasts on Linux requires juggling multiple tools (audio capture, speech-to-text, NLP processing), and no single integrated pipeline handles the full flow reliably.

**Audience:** Podcasters, researchers, and content creators who need high-quality transcription and NLP analysis of podcast episodes without vendor lock-in or expensive cloud APIs.

**Key constraints:** Must work on Wayland (modern Linux), support PipeWire for audio capture, use local speech-to-text (no API keys required), and produce structured output (transcript, metadata, analysis).

**Success metric:** A podcaster can record an episode via Wayland, run the pipeline, and get a searchable transcript, speaker diarization markers, and automatic metadata (topics, key moments) without leaving the Linux terminal.
