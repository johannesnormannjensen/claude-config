# Crew config — Driftwood

## Project
Driftwood, a Rust + Bevy voxel adventure game, multiplayer-first (solo runs a hidden local
server). Co-op ships over the internet, so assume 80–150 ms latency and some packet loss.

## Rules
- The server owns outcomes; clients send intents and predict only their own player.
- Content (items, creatures, biomes) is data under `assets/`, not code.
- If the network format changes, bump `PROTOCOL_VERSION`.
- Automated runs stay silent: test and screenshot runs set `GAME_MUTE=1`.
- Everything must also work on a gamepad.

## Gates
- gate: `cargo fmt --check && cargo clippy --all-targets -- -D warnings`
- test: `cargo test -q`
- evidence: `scripts/smoke.sh` (two clients over a lossy link) when net or sim changes;
  `scripts/screenshot.sh <scene>` when anything visible changes; LOOK at every shot.

## Implement
- Kept-in-sync docs: `docs/design.md` when a rule of play changes; the module README of every
  module you change.

## References
- Cube World, Veloren and Valheim; GDC talks and dev blogs as primary sources.
- For networking: Gaffer on Games, the Overwatch netcode GDC talk.

## Verify before merge
- `cargo test -q`, `scripts/smoke.sh`, `scripts/screenshot.sh all` and look at every changed shot.
