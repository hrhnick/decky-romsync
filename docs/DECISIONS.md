# Decisions

Why things are the way they are. Each of these was a real fork with a real
reason; several look like obvious gaps until you know what they cost.

---

## Architecture

### A Decky plugin, not a standalone app

Steam's Game Mode UI is React. Building against `@decky/ui` means the interface
uses Valve's own components — controller focus, D-pad navigation and styling
come free and stay correct across Steam updates.

More importantly, running inside Steam's frontend means shortcuts are created
through `SteamClient.Apps.*` rather than by editing the binary `shortcuts.vdf`.
That removes the two worst properties of file-based tools: binary VDF surgery,
and the mandatory Steam restart before changes appear. Games show up live.

### The library is the source of truth

Launch commands, per-ROM corrections and the API key live in plain text next to
the ROMs or in `~/.config/romsync`. The plugin seeds those files and then reads
them. A user who edits a file wins; nothing is silently overwritten.

This is why `set_system_core` edits the raw file line by line and replaces only
the `-L` argument instead of regenerating from parsed values — hand-added flags
and comments survive.

### Everything defers to the next sync

Toggling a system, excluding a ROM, changing a core: none take effect until
Sync. Consistency is part of it, but the real reason is that **removal destroys
Steam playtime and cannot be undone.** Deferring means a mis-tap costs nothing.

The counterpart is that queued changes must be visible, or a toggle that
appears to do nothing reads as broken. Hence the pending line under Sync.

---

## Rejected, with reasons

### Editing launch commands in the UI

It is the highest-consequence field in the plugin: a malformed line silently
breaks every game in a system and you only find out on launch. And typing 100+
characters of quoted paths on an on-screen keyboard is worse than opening the
file — which anyone willing to type that could do anyway.

What shipped instead: a **read-only** view (Show launch commands on the
Emulators page, and the About pane per game). "Why won't this launch" is
answered by reading the command far more often than by rewriting it.

### RetroAchievements as native Steam achievements

Not achievable. Steam achievements are server-backed per appid; a non-Steam
shortcut has no server-side record, so there is no panel to populate. Two mature
plugins (Emuchievements, Achievement Companion) both stop at a custom badge and
their own view — if it were possible they would have done it.

The hard part is also identification: RetroAchievements hashes ROMs with
console-specific rules (skip the iNES header, hash the executable inside a disc
image). Achievement Companion hedges with hashing "where supported" and falls
back to title matching.

Better path if wanted: make our shortcuts recognisable to those plugins, which
match on ROM paths in launch options. Ours already look like SRM's.

### IGDB metadata in the game details panel

Feasible — MetaDeck proves it. But it needs Twitch/IGDB credentials on top of
the SteamGridDB key, and MetaDeck's own reviews report metadata not loading
without leaving and re-entering the page, graphical glitches in the library, and
conflicts with the SteamGridDB plugin over the same store.

### Exporting artwork into the library

Built, then removed on request. The lookup precedence remains: a file in
`<system>/media/<asset>/` beats SteamGridDB. The plugin only ever *reads* those
paths now — nothing writes them, so curated artwork cannot be half-populated or
overwritten.

### An "excluded games" list

Excluding is a UI one-way door: exclude, sync, the shortcut is gone, and Manage
ROM is reached from a shortcut's context menu. Recovery means editing
`.romsync.txt`.

Accepted deliberately. Steam's own Manage → Hide covers the temporary case and
is reversible from the library; exclude is for keeping a game out for good. The
toggle's copy says so, and that the ROM file is never deleted.

---

## Smaller calls

**Region variants keep their tags.** Three files cleaning to "Chrono Trigger"
are three different games, not duplicates. Only the tags that *differ* are
restored, so two files sharing `(Rev 1)` do not both get it. True duplicates —
the same filename under two roots — still collapse, internal winning.

**Artwork is only fetched for slots a game lacks.** The manifest records which
landed. This is what made a library synced before the API key worked
recoverable without deleting and recreating everything.

**Adoption matches whole quoted arguments, not substrings.** A substring test
false-adopts: a shortcut pointing at `Mario.nes.bak` contains the path of
`Mario.nes`.

**A command with no `{rom}` is refused.** It would build an identical shortcut
for every file in the folder, launching the emulator with nothing loaded, and
fail at launch rather than at sync.

**MS-DOS does not list `.exe`, `.com` or `.bat`.** They match `SETUP.EXE` and
`INSTALL.EXE` in every game folder, so one game produced four shortcuts.

**Uninstalled cores are still offered in the picker.** On a fresh setup only one
core exists per system, so an installed-only list would leave nothing to choose
between. Picking a missing one flags it and the Install button fetches it.

**Every system gets the same picker**, even with one core. Re-picking the
current core is a no-op, so a single-option picker is harmless, and uniform
rows beat a differently-shaped box for 3DO next to SNES.

**No Back buttons.** B does that. Duplicating a platform control only adds
something to navigate past.

**"Sync", not "Sync All".** It is not all — disabled systems are actively
removed, not skipped.
