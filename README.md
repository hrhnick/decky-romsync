# ROM Sync

A Decky Loader plugin that turns a ROM folder into Steam shortcuts with artwork
and per-system collections. Runs inside Game Mode, uses Valve's own React
components, and never touches `shortcuts.vdf`.

## Why this shape

Steam Big Picture is a React app. Building against `@decky/ui` means the UI is
Valve's actual components — controller focus, D-pad navigation, and styling all
come for free and stay correct across Steam updates.

More importantly, running inside Steam's frontend means shortcuts are created
through `SteamClient.Apps.*` rather than by editing the binary `shortcuts.vdf`.
That removes the two worst properties of file-based tools: binary VDF surgery,
and the mandatory Steam restart before changes appear. Games show up live.

## Adoption

`SteamClient.Apps` can add, remove and mutate a shortcut by appid but has no way
to list shortcuts, so enumeration goes through `collectionStore` (untyped, and
its collection names have moved between releases — `listShortcuts` tries several
shapes). Exe and launch options are not on the app overview; they live on
AppDetails as `strShortcutExe` / `strShortcutLaunchOptions`, which loads lazily.

On sync, any existing shortcut whose command line contains one of our ROM paths
is adopted rather than duplicated. Without this, a library already imported with
Steam ROM Manager gets a second copy of every game.

Adopted shortcuts are flagged in the manifest, because adoption grants delete
authority over something we did not create. Reset therefore deletes only what
this plugin made and merely forgets the adopted ones.

## Artwork throughput

Fetching art inline per game pays full network latency 200 times over. Sync
instead warms the cache up front via `prefetch_art`, which fans out across 8
threads; the token bucket keeps the request rate constant regardless of worker
count, so concurrency buys latency hiding rather than a higher rate. Measured
roughly 8x against a serial baseline.

Prefetch is issued in chunks of 16 rather than one call for the whole library.
A single await over 200 games shows no movement for minutes, which is
indistinguishable from a hang; chunking gives real progress and keeps Stop
responsive during the phase.

Expect roughly 5 minutes for a first sync of 200 games. That is the rate limit,
not a stall: about 11 requests per game at 8 per second is a ~4.6 minute floor
before download time. Later syncs are near-instant because the cache holds.

Prefetch returns counts and reasons, not images — shipping artwork back through
that call would mean tens of megabytes over the websocket. The per-game
`get_art` calls that follow are cache hits.

Art failures are reported in the sync summary rather than swallowed. "No key
set", "no SteamGridDB match for X", and rate-limit hits each say so, and the
summary always states how many games actually received artwork.

## User-Agent

Every outbound request sends an explicit `User-Agent`. urllib's default is
`Python-urllib/3.x`, which Cloudflare — which fronts SteamGridDB — answers with
a 403 before the request reaches the API. That is indistinguishable from a
rejected key unless you look at the response body, so a 403 whose body carries
Cloudflare's markers is reported as a blocked request rather than a key problem.

## TLS

Decky runs plugins with a trimmed environment, and Python's default certificate
verification can end up with no CA bundle at all — every HTTPS request then
fails with CERTIFICATE_VERIFY_FAILED, which surfaces as "couldn't reach
SteamGridDB". `sgdb.ssl_context()` finds a bundle explicitly, checking
`SSL_CERT_FILE`, then certifi, then the usual distribution paths, then
`/etc/ssl/certs` as a directory. `describe_tls()` reports which one was used and
is included in the Test key result, so a TLS failure names its own cause.

A wrong system clock produces the same error with a valid trust store, so check
`date` on the device before going further.

## System toggles

Each row is name, game count, toggle — nothing else. A per-system sync button
used to sit here, but it was the rarest action in the panel occupying the most
prominent spot in every row, and it appeared and disappeared with the toggle so
rows changed shape as you used them.

Toggling defers, like every other setting: nothing is added or removed until
the next sync. That matters more than consistency alone, because removal
destroys Steam playtime and cannot be undone — deferring means a mis-tap costs
nothing and can be reversed for free. What is queued shows under the Sync
button ("12 to add, 40 to remove"), since a change with no visible effect
otherwise reads as a broken toggle.

Systems that cannot launch are left out of the queued count. Promising an
addition that pressing Sync cannot deliver would never clear; the Emulators
page in settings reports those instead.

The panel lists only folders that actually hold ROMs. A folder holding files that the plugin can't
place — an unknown name with no `.romsync.txt` — is named as unrecognised
rather than skipped in silence, since from outside that looks like the plugin
lost your games. A freshly created library
or a folder kept for later is named separately as "waiting for ROMs" rather than
appearing as a toggle, and a missing core is only reported for systems with
games in them.

Switching a system off also deletes its Steam category once nothing is left in
it, so the library isn't littered with hollow entries. Only empty categories
matching a name the plugin manages are touched — one you filled yourself would
not be empty. `collectionStore`'s delete method has moved between releases, so
the call tries the shapes that have existed and gives up quietly: a leftover
category is cosmetic, and failing a sync over it would not be.

Settings store `disabled_systems`, not enabled ones. The earlier list could not
express "everything off" — an empty list meant "all on", so switching off the
last system silently switched them all back on. Old settings are migrated once
on load.

Full-page routes use `SidebarNavigation`, Steam's own settings component.
Both split the same way: Settings into Library / SteamGridDB / Emulators /
Danger zone, Manage ROM into About / Artwork / Danger zone.

About is read-only and exists to answer "why won't this launch" for one game —
system, emulator, ROM file, and the exact command Steam runs, read back off the
shortcut rather than off the folder template. Exclusion sits in its own pane
because it is the one action here the plugin cannot walk back, and it should
not be reachable by a stray press while adjusting a cover.

Excluding is framed against Steam's own Manage > Hide: hide for temporary and
reversible, exclude for keeping a game out for good. Neither deletes the ROM,
and the copy says so, because "exclude" is the kind of word people reasonably
worry about.

This is not a cosmetic choice. Three attempts at a hand-rolled scroll
container — a plain div with `overflow-y: scroll`, then a `Focusable` with
`flow-children="column"`, then page-native section components — all left the
D-pad unable to reach the bottom of a long page. Touch dragging worked
throughout, which made it present as a scrolling bug when it was a focus one:
Steam's gamepad navigation drives scrolling through its own page components and
cannot be told about an arbitrary overflow div. `PageShell` now only reserves
space below the top bar and hands the rest to Steam.

Actions are grouped into rows rather than stacked full-width, which keeps the
important controls on screen instead of pushing them past the fold. No page has
a Back button — B does that, and duplicating a platform control in the UI only
adds something to navigate past. Manage ROM has one Save, which always applies:
a save that deliberately doesn't take effect was a distinction with no use
behind it.

Progress uses a bare `ProgressBar` with the status rendered separately, not
`ProgressBarWithInfo`. That component draws the status inside its own markup,
where a long game title has nothing to truncate against and drags the bar off
the panel. Split apart, the text clips with an ellipsis and the bar is pinned
to the row width. Statuses lead with position (`Adding 12/200 · …`) so the part
that survives truncation is the part worth reading.

All three screens draw from one scale in `PageShell`: two type sizes, two
secondary opacities, two button heights. Values used to be picked locally,
which had produced four font sizes and five button heights across two screens —
differences too small to notice individually and collectively the thing that
makes an interface look assembled rather than designed.

Long paths, notes and error messages wrap rather than trailing off the edge.
Row labels truncate with `flex-basis: 0` and `min-width: 0`, without which a
long system name keeps its natural width and pushes the toggle off-panel.

A finished sync's report can be dismissed. The store outlives the panel, so
otherwise the last run's summary sits above the system list indefinitely.

Manage ROM shows the cover for the selected match beside the list. Reading
names that differ by a subtitle is slow; seeing the artwork is instant. The
thumbnail comes from the grids endpoint's own `thumb` — 20-50KB rather than
several hundred — and is cached per game.

The match list is capped and scrolls. Ten full-height
buttons pushed every other control off the page. Each row shows the release
year where available — the autocomplete endpoint returns only id, name, types
and verified, so the year costs one extra request per shown candidate, fetched
only for what is displayed and cached permanently.

## Panel layout

The panel is Sync, progress and system toggles. Library path, API key and the
destructive reset live behind the cog in the title, as a route — they are
touched once during setup, and keeping them out of the way leaves Sync as the
obvious thing to press. A route rather than a modal for the same reason as
Manage ROM: modals raised from the panel render behind the quick access menu.

## Artwork backfill

The manifest records which artwork slots actually landed per game. A tracked
game with none gets picked up on the next sync as an artwork-only pass — no
shortcut is touched, only the missing slots are fetched. That is what makes a
library synced before the SteamGridDB key worked recoverable without deleting
and recreating everything, which would discard playtime.

Prefetch skips any game whose artwork is already complete locally: local files
win regardless, so fetching them would spend rate limit on results that get
thrown away.

## Removals

Nothing is removed without showing what and why first — title, reason, and a
note that playtime is lost. Switching a system off makes removals easy to
trigger by accident, so the confirmation matters more than it used to.

## The manifest

`commit` merges into the existing entry rather than rebuilding it. A rebuild
dropped every field the caller did not happen to carry — an update from a core
swap has no `art`, so committing one erased the record of which artwork had
landed, and the next sync re-applied artwork for the whole system for nothing.

All mutation goes through `Manifest.update`, which loads, applies and saves
under one lock. It is reached from the event loop and from worker threads, so
an unguarded reload could rebind the data between another caller's mutation and
its save, silently reverting the write.

## Concurrency

Every temp file is named per thread, not derived from its target. The artwork
prefetch runs eight workers, and two games routinely resolve to the same
SteamGridDB id — regional variants of one game always do — so a shared `.tmp`
name meant two writers interleaving into it and `os.replace` publishing a
half-written image into a permanent cache.

`listShortcuts` fetches shortcut details concurrently. Each miss waits on a
callback with a timeout, so serially a library with fifty unloaded shortcuts
would sit at "Checking existing shortcuts" for over a minute.

Artwork slots are cleared in a batch, then filled. `ClearCustomArtworkForApp`
resolves before the clear actually happens, so it needs a fixed wait after it;
one wait per game rather than one per slot is minutes of difference across a
library.

Components are never declared inside a render. A component defined there gets a
new function identity each time, so React sees a different type and remounts the
subtree — which on a gamepad UI drops focus on every keystroke.

## Hot paths

`discover_roots` reads the library file and stats every configured path, and it
sits under both `find_local_art` and `system_dir_for` — each of which runs per
game, per artwork slot. A 200-game prefetch was calling it roughly 1,600 times,
much of it against an SD card. It is cached for five seconds and invalidated
outright whenever the library changes: a sync finishes well inside the window,
and a card plugged in mid-session is picked up shortly after.

Adoption matches whole quoted arguments rather than substrings. A substring
test both costs shortcuts × games comparisons and false-adopts — a shortcut
pointing at `Mario.nes.bak` contains the path of `Mario.nes`.

## Panel cost

`get_settings` runs one library survey and derives systems, empty folders,
missing cores and unrecognised folders from it. It previously asked each
question separately, which meant five full walks of every system folder — and
fifteen ROM counts for three folders — every time the panel opened.

## Long operations

Sync and reset run in `syncStore.ts` at module scope, not inside a component.
The Decky panel unmounts every time the quick access menu closes; a loop living
in component state would lose its progress mid-run while shortcut creation
carried on in the background. The panel is a view onto the operation, not the
thing running it. Cancelling stops at the next game boundary and still commits
what landed.

## Documentation

- `CLAUDE.md` — working context: build and deploy commands, non-obvious
  platform constraints, fragile surfaces, conventions, open items
- `docs/DECISIONS.md` — why things are the way they are, including what was
  deliberately not built and why
- `docs/DEPLOYING.md` — hardware deploy and debugging runbook

## Layout it expects

```
<home or any mounted volume>/Emulation/roms/<system>/
```

Folder names use the short lowercase convention shared by EmuDeck, RetroDECK
and RetroPie — `nes`, `snes`, `n64`, `gba`, `psx`, `ps2`, `gc`, `segacd`,
`tg16`, `arcade`. Alternate spellings are accepted on scan, so `gamecube`,
`pcengine`, `megadrive` and `playstation` folders are recognised too.

Mount points are read from `/proc/mounts` rather than matched against a fixed
pattern — SteamOS has used both `/run/media/<label>` and
`/run/media/deck/<label>`, and a hand-mounted card can be anywhere. Home is
always checked.

**Every path component is case-insensitive**, including `Emulation` and `roms`
themselves. A card formatted on another machine may hold `emulation/roms` or
`Emulation/ROMs`; a literal glob would silently find nothing on a case-sensitive
filesystem. If there is no `roms` level, the `Emulation` folder is scanned
directly.

System folder names and file extensions are matched casefolded, in code rather
than by the filesystem — the internal drive is case-sensitive but an exFAT SD
card is not, so neither can be relied on.

**Duplicates and same-named games.** The same *filename* under two roots is one
game on two drives: internal wins, the other is skipped. Different filenames
that merely clean to the same title are different games — regional releases,
usually — so instead of dropping one, both get back the tags that tell them
apart:

```
Chrono Trigger (USA).sfc     ->  Chrono Trigger (USA)
Chrono Trigger (Japan).sfc   ->  Chrono Trigger (Japan)
Earthbound (USA).sfc         ->  Earthbound
```

Only tags that differ are restored, so two files sharing `(Rev 1)` don't both
get it. If nothing in the names separates them, the filename is used rather
than silently losing a game.

## Conventions

**How a system launches** lives in that system's folder, in `.romsync.txt`:

```
system = Nintendo 64
command = /usr/bin/flatpak run org.libretro.RetroArch -L "/home/deck/.var/app/…/mupen64plus_next_libretro.so" "{rom}"
extensions = .z64 .n64 .v64 .ndd .zip .7z
```

Every folder gets all three lines, known systems included, so each file looks
the same and every part of a system's behaviour is visible and editable in one
place.

Folder names follow the EmuDeck/ES-DE convention — lowercase short keys such as
`nes`, `snes`, `n64`, `gba`, `psx`, `gc`, `segacd`, `tg16`, `arcade`. `system`
inside the file is the human-readable Steam category, which is why it reads
"PlayStation" while the folder is `psx`.

`system` is the Steam category the games appear under. `command` is how each
ROM launches, with `{rom}` replaced by the file path — splitting happens before
substitution, so paths with spaces stay one argument.

The plugin only *seeds* this file. Once it exists it is authoritative, so
pointing a system at a different core, or a different emulator entirely, is a
one-line edit. A folder carrying a valid `system` and `command` is a system even
if its name matches nothing the plugin knows, which is how an unsupported
console is added — including one whose emulator does not exist yet. The command
is an ordinary command line: native binary, AppImage, wrapper script or
flatpak, with flags in any order around `{rom}`.

```
system = Nintendo Switch
command = /usr/bin/flatpak run org.yuzu_emu.yuzu -f -g "{rom}"
extensions = .nsp .xci
```

`extensions` decides which files in the folder count as games.

Two things are refused rather than synced. A command with no `{rom}` would
build an identical shortcut for every file in the folder, launching the
emulator with nothing loaded — never intended, and it fails at launch rather
than at sync. And a program that is not installed is reported the same way a
missing core is, since it is the same failure: absolute paths are checked
directly, a bare name is looked up on PATH.

Core paths are written literally, so they are readable and editable. If a path
stops resolving — a Flatpak update, or a switch between user and system install
— the same core filename is looked up in the known core directories and used,
with a note in the sync log. The file is never rewritten, so a hand edit cannot
be clobbered.

**Default cores.** RetroArch-first: NES nestopia, SNES bsnes, N64
mupen64plus_next, GB/GBC gambatte, GBA mgba, DS melondsds, GameCube/Wii dolphin,
Genesis/Master System/Game Gear/Sega CD genesis_plus_gx, Saturn kronos,
Dreamcast flycast, PlayStation mednafen_psx_hw, PSP ppsspp, PC Engine
mednafen_pce, Arcade/Neo Geo fbneo, Atari 2600 stella, 3DO opera, C64
vice_x64sc, MSX bluemsx. PS2, PS3, Wii U and Switch have no core worth
defaulting to, so their file is written with the command commented out and a
note to fill it in.

**Show launch commands** on the Emulators page reveals what each system
actually runs and which file that line lives in. Read-only and off by default:
"why won't this launch" is answered by reading the command far more often than
by rewriting it, and the path says where to go if it does need changing. One
toggle for the page rather than an expander per row, which would have tripled
the focus stops there for something read once a year.

Editing the command in the UI was considered and dropped. It is the
highest-consequence field in the plugin — a malformed line silently breaks
every game in a system, and you only find out on launch — and typing 100+
characters of quoted paths on an on-screen keyboard is worse than opening the
file, which anyone willing to type that could do anyway.

**Changing a core** is a picker on the Emulators page, offering the cores worth
running for that system. Every row gets the same control even when there is
only one core, so a 3DO row doesn't sit in a differently shaped box beside a
SNES row with four options; re-picking the current core is a no-op, so nothing
is risked by leaving it live. A system running something other than RetroArch
keeps the same box but inert, since there is no core to pick and a flatpak id
must never end up in a `-L` argument. Uninstalled ones are offered too and marked as such:
on a fresh setup only one core exists per system, so an installed-only list
would leave nothing to choose between. Picking a missing core flags it, and the
Install button on the same page fetches it.

The write is deliberately narrow. `set_system_core` edits the raw file line by
line and replaces only the `-L` argument — not a regeneration from parsed
values. Flags someone added by hand (`--fullscreen`, `--appendconfig=…`), their
comments, and their per-ROM blocks all survive untouched. A system pointed at
something other than RetroArch has no core to swap, so it shows read-only text
rather than a picker that could overwrite a hand-written command.

Nothing reaches Steam until the next sync, like every other setting. The change
appears in the panel's pending line as "40 to update", detected without
rescanning: rebuild what one tracked game's launch options would be under the
folder's current command and compare against what was recorded at sync time.

Missing cores are fetched from RetroArch's own buildbot
(`buildbot.libretro.com/nightly/linux/x86_64/latest/`). Those are nightlies
built against current RetroArch, so one can fail to load against an older
Flatpak — when a download fails the UI points at RetroArch's Core Downloader
instead.

**Titles.** `Super Mario 64 (USA) [!].z64` becomes `Super Mario 64`. Parenthetical
and bracketed tags are stripped, underscores become spaces, and trailing articles
flip: `Legend of Zelda, The - Ocarina of Time` becomes
`The Legend of Zelda - Ocarina of Time`. Dots are only treated as separators when
the name has no spaces, so `Super Mario Bros. 3` survives intact.

**Arcade.** MAME and Neo Geo ROMs are named by set short-name — `sf2ce.zip`,
`mslug.zip` — so there is no title in the filename to clean up. Titles come
from libretro-database's consolidated MAME DAT, downloaded once on the first
sync that finds an arcade folder and reduced to a ~0.8MB lookup (about 16,000
sets). `sf2ce.zip` becomes "Street Fighter II': Champion Edition". Unknown sets
keep their filename, and a failed download degrades to the same.

Note the DAT maps the opposite way to what its field names suggest: `name` is
the title and the zip appears inside the `rom` line.

Title precedence for every system: `.romsync.txt` override, then the arcade
DAT, then the cleaned filename.

**Folder games.** Not every system stores a game as one file. Two forms are
supported, because matching on extension otherwise finds `SETUP.EXE` and
`EBOOT.BIN` rather than the game:

- a directory whose name ends in a configured extension is a game, which is how
  Daphne works (`lair.daphne/`)
- `folders = yes` in `.romsync.txt` makes every immediate subdirectory one game,
  named after the folder — PlayStation 3 and Wii U default to this

Either way the directory itself is passed to the emulator, which is what the
formats that work this way expect. ScummVM is the exception that does not need
it: its `.scummvm` stub is a real file.

MS-DOS deliberately does **not** list `.exe`, `.com` or `.bat`. Those match the
helper executables sitting in every game folder, so one game produced separate
shortcuts for SETUP and INSTALL. Archives are what DOSBox Pure expects anyway;
a folder-per-game DOS library wants `folders = yes`.

**Multi-disc.** If an `.m3u` exists, the files it references are skipped and only
the `.m3u` is imported. Members are resolved relative to the playlist.

**Artwork.** Local files always win, checked in this order:

```
<system>/media/<asset>/<rom name>.png      <- written by Export
<rom_dir>/media/<rom name>.<asset>.png
<scan_root>/art/<system>/<rom name>.<asset>.png
```

`<asset>` is grid, hero, logo, wide or icon. `.jpg` and `.jpeg` also work.

The per-asset layout is checked first because it is the one worth curating by
hand. Dropping a PNG into `<system>/media/grid/` replaces that game's cover on
the next sync — no plugin involvement, no SteamGridDB ID to find, and it
travels with the ROMs like the launch config and the key. The plugin only ever
reads these; nothing writes them.

Anything missing is filled from SteamGridDB through `sgdb.py`, which owns
throttling (a token bucket, 8 requests/second sustained with a burst of 16,
shared across every worker),
retry with backoff on 429/5xx honouring Retry-After, and a disk cache under the
plugin runtime dir. Both hits and misses are cached — images are keyed on
`game_id + asset` so a re-sync or reset-then-resync refetches nothing, and
"SGDB has no hero for this game" is remembered for a week so obscure ROMs don't
re-ask the same unanswerable questions every sync. A failed request is never treated as an empty result. A rejected key, a
network error and "this game genuinely has no artwork" are distinct outcomes,
and only the last one is cached — otherwise one bad key silently poisons the
cache for the whole library and keeps answering "no match" long after the key
is fixed. Changing the key clears the search cache for the same reason. If the
rate limit is hit anyway, the sync degrades to art-less shortcuts with a
warning rather than failing; the next sync fills the gaps from cache plus whatever fetches succeed.

**Overrides.** Each system folder gets a hidden `.romsync.txt`. It travels with
the ROMs — move a folder to another card or another machine and the corrections
go with it — and it is meant to be hand-edited:

```
# ROM Sync overrides - edit freely, one block per ROM.

file = GoldenEye 007 (USA).z64
sgdb_id = 5297

file = Super Mario 64 (USA).z64
title = Mario 64

file = Bad Dump (USA).z64
exclude = yes
```

Plain text rather than JSON because these are edited by hand, often on a Deck:
no braces to balance, no quoting rules, and a typo costs one line instead of the
whole file. Parsing is forgiving — keys are case-insensitive, whitespace is
ignored, `exclude` accepts yes/true/on/1, unknown keys are skipped, and only the
first `=` splits so filenames containing `=` survive. Filenames are matched
casefolded, so hand-typed casing needn't be exact.

Existing `.romsync.json` files are still read, and are converted to
`.romsync.txt` the next time that folder's overrides are written.

The system folder a ROM belongs to is *derived* — the direct child of a scan
root — never taken from the ROM's parent directory. Those differ whenever games
live in subfolders, as ScummVM's do, and the parent would put a game's
overrides in its own folder where nothing reads them.

The same file is written by the Manage ROM page, which searches SteamGridDB by
title and lets you pick the right entry rather than hunting for an ID on the
website. If a folder is read-only the write fails loudly rather than silently
falling back to plugin state — the file is the source of truth.

**Arcade.** MAME and Neo Geo ROMs are named by set short-name — `sf2ce.zip`,
`mslug.zip` — so there is no title in the filename to clean up. Titles come
from libretro-database's consolidated MAME DAT, downloaded once on the first
sync that finds an arcade folder and reduced to a ~0.8MB lookup (about 16,000
sets). `sf2ce.zip` becomes "Street Fighter II': Champion Edition". Unknown sets
keep their filename, and a failed download degrades to the same.

Note the DAT maps the opposite way to what its field names suggest: `name` is
the title and the zip appears inside the `rom` line.

Title precedence for every system: `.romsync.txt` override, then the arcade
DAT, then the cleaned filename.

**Folder games.** Not every system stores a game as one file. Two forms are
supported, because matching on extension otherwise finds `SETUP.EXE` and
`EBOOT.BIN` rather than the game:

- a directory whose name ends in a configured extension is a game, which is how
  Daphne works (`lair.daphne/`)
- `folders = yes` in `.romsync.txt` makes every immediate subdirectory one game,
  named after the folder — PlayStation 3 and Wii U default to this

Either way the directory itself is passed to the emulator, which is what the
formats that work this way expect. ScummVM is the exception that does not need
it: its `.scummvm` stub is a real file.

MS-DOS deliberately does **not** list `.exe`, `.com` or `.bat`. Those match the
helper executables sitting in every game folder, so one game produced separate
shortcuts for SETUP and INSTALL. Archives are what DOSBox Pure expects anyway;
a folder-per-game DOS library wants `folders = yes`.

**Multi-disc.** If an `.m3u` exists, the files it references are skipped and only
the `.m3u` is imported. Members are resolved relative to the playlist.

**Artwork.** Local files always win, checked in this order:

```
<system>/media/<asset>/<rom name>.png      <- written by Export
<rom_dir>/media/<rom name>.<asset>.png
<scan_root>/art/<system>/<rom name>.<asset>.png
```

`<asset>` is grid, hero, logo, wide or icon. `.jpg` and `.jpeg` also work.

The per-asset layout is checked first because it is the one worth curating by
hand. Dropping a PNG into `<system>/media/grid/` replaces that game's cover on
the next sync — no plugin involvement, no SteamGridDB ID to find, and it
travels with the ROMs like the launch config and the key. The plugin only ever
reads these; nothing writes them.

Anything missing is filled from SteamGridDB through `sgdb.py`, which owns
throttling (a token bucket, 8 requests/second sustained with a burst of 16,
shared across every worker),
retry with backoff on 429/5xx honouring Retry-After, and a disk cache under the
plugin runtime dir. Both hits and misses are cached — images are keyed on
`game_id + asset` so a re-sync or reset-then-resync refetches nothing, and
"SGDB has no hero for this game" is remembered for a week so obscure ROMs don't
re-ask the same unanswerable questions every sync. A failed request is never treated as an empty result. A rejected key, a
network error and "this game genuinely has no artwork" are distinct outcomes,
and only the last one is cached — otherwise one bad key silently poisons the
cache for the whole library and keeps answering "no match" long after the key
is fixed. Changing the key clears the search cache for the same reason. If the
rate limit is hit anyway, the sync degrades to art-less shortcuts with a
warning rather than failing; the next sync fills the gaps from cache plus whatever fetches succeed.

**Overrides.** Each system folder gets a hidden `.romsync.txt`. It travels with
the ROMs — move a folder to another card or another machine and the corrections
go with it — and it is meant to be hand-edited:

```
# ROM Sync overrides — edit freely, one block per ROM.

file = GoldenEye 007 (USA).z64
sgdb_id = 5297

file = Super Mario 64 (USA).z64
title = Mario 64

file = Bad Dump (USA).z64
exclude = yes
```

Plain text rather than JSON because these are edited by hand, often on a Deck:
no braces to balance, no quoting rules, and a typo costs one line instead of the
whole file. Parsing is deliberately forgiving — keys are case-insensitive,
whitespace is ignored, `exclude` accepts yes/true/on/1, unknown keys are
skipped, and only the first `=` splits so values containing `=` survive.
Filenames are matched casefolded, so hand-typed casing needn't be exact.

Existing `.romsync.json` files are still read and are converted to `.romsync.txt`
the next time that folder's overrides are written.

The system folder a ROM belongs to is *derived* — the direct child of a scan
root — never taken from the ROM's parent directory. Those differ whenever games
live in subfolders, as ScummVM's do, and the parent would put a game's
overrides in its own folder where nothing reads them.

The same file is written by the Manage ROM page, which searches SteamGridDB by
title and lets you pick the right entry rather than hunting for an ID on the
website. If a folder is read-only, the write fails loudly rather than silently
falling back to plugin state — the file is the source of truth.

**Arcade.** MAME and Neo Geo ROMs are named by set short-name — `sf2ce.zip`,
`mslug.zip` — so there is no title in the filename to clean up. Titles come
from libretro-database's consolidated MAME DAT, downloaded once on the first
sync that finds an arcade folder and reduced to a ~0.8MB lookup (about 16,000
sets). `sf2ce.zip` becomes "Street Fighter II': Champion Edition". Unknown sets
keep their filename, and a failed download degrades to the same.

Note the DAT maps the opposite way to what its field names suggest: `name` is
the title and the zip appears inside the `rom` line.

Title precedence for every system: `.romsync.txt` override, then the arcade
DAT, then the cleaned filename.

**Folder games.** Not every system stores a game as one file. Two forms are
supported, because matching on extension otherwise finds `SETUP.EXE` and
`EBOOT.BIN` rather than the game:

- a directory whose name ends in a configured extension is a game, which is how
  Daphne works (`lair.daphne/`)
- `folders = yes` in `.romsync.txt` makes every immediate subdirectory one game,
  named after the folder — PlayStation 3 and Wii U default to this

Either way the directory itself is passed to the emulator, which is what the
formats that work this way expect. ScummVM is the exception that does not need
it: its `.scummvm` stub is a real file.

MS-DOS deliberately does **not** list `.exe`, `.com` or `.bat`. Those match the
helper executables sitting in every game folder, so one game produced separate
shortcuts for SETUP and INSTALL. Archives are what DOSBox Pure expects anyway;
a folder-per-game DOS library wants `folders = yes`.

**Multi-disc.** If an `.m3u` exists, the files it references are skipped and only
the `.m3u` is imported. Members are resolved relative to the playlist.

**Artwork.** Local files always win, checked in this order:

```
<system>/media/<asset>/<rom name>.png      <- written by Export
<rom_dir>/media/<rom name>.<asset>.png
<scan_root>/art/<system>/<rom name>.<asset>.png
```

`<asset>` is grid, hero, logo, wide or icon. `.jpg` and `.jpeg` also work.

The per-asset layout is checked first because it is the one worth curating by
hand. Dropping a PNG into `<system>/media/grid/` replaces that game's cover on
the next sync — no plugin involvement, no SteamGridDB ID to find, and it
travels with the ROMs like the launch config and the key. The plugin only ever
reads these; nothing writes them.

Anything missing is filled from SteamGridDB through `sgdb.py`, which owns
throttling (a token bucket, 8 requests/second sustained with a burst of 16,
shared across every worker),
retry with backoff on 429/5xx honouring Retry-After, and a disk cache under the
plugin runtime dir. Both hits and misses are cached — images are keyed on
`game_id + asset` so a re-sync or reset-then-resync refetches nothing, and
"SGDB has no hero for this game" is remembered for a week so obscure ROMs don't
re-ask the same unanswerable questions every sync. A failed request is never treated as an empty result. A rejected key, a
network error and "this game genuinely has no artwork" are distinct outcomes,
and only the last one is cached — otherwise one bad key silently poisons the
cache for the whole library and keeps answering "no match" long after the key
is fixed. Changing the key clears the search cache for the same reason. If the
rate limit is hit anyway, the sync degrades to art-less shortcuts with a
warning rather than failing; the next sync fills the gaps from cache plus whatever fetches succeed.

**Overrides.** Each system folder gets a hidden `.romsync.json`. It travels with
the ROMs — move a folder to another card or another machine and the corrections
go with it — and it is meant to be hand-edited:

```json
{
  "_help": "...",
  "games": {
    "GoldenEye 007 (USA).z64": { "sgdb_id": 5297 },
    "Super Mario 64 (USA).z64": { "title": "Mario 64" },
    "Bad Dump (USA).z64": { "exclude": true }
  }
}
```

Filename keys are matched casefolded, so hand-typed casing doesn't have to be
exact. `sgdb_id` pins a SteamGridDB match, `title` replaces the cleaned name,
and `exclude` keeps a ROM out of Steam.

The system folder a ROM belongs to is *derived* — the direct child of a scan
root — never taken from the ROM's parent directory. Those differ whenever games
live in subfolders, as ScummVM's do, and the parent would put a game's
overrides in its own folder where nothing reads them.

The same file is written by the Manage ROM page, which searches SteamGridDB by
title and lets you pick the right entry rather than hunting for an ID on the
website. If a folder is read-only, the write fails loudly rather than silently
falling back to plugin state — the file is the source of truth.

**Library folders** come from `~/.config/romsync/.library_path.txt`. Auto-detection
seeds it on first run by scanning mounted volumes; after that the file is
authoritative, so the way to point at a library auto-detection can't reach is to
edit the file or use the Library folder panel. Either an Emulation folder or the
roms folder inside it is accepted. Re-detect deletes the file and scans again.

Entries that no longer resolve are skipped rather than rewritten out, so
unplugging a card doesn't silently discard a configured path.

**The SteamGridDB key** lives in one place:

```
~/.config/romsync/steamgriddb_key.txt
~/.config/romsync/library_path.txt
```

Neither is hidden: the config folder already is, and a dotfile inside a
dotfolder is only harder to find. Dotted spellings written by earlier versions
are still read, and the library file is rewritten under the visible name the
next time it is saved.

That file is canonical. The GUI writes it, and it is the only location read.

A key found beside the library is **imported** into config when config has
none, and left exactly where it is. Reading matches by pattern rather than an
exact filename — `steamgriddb_key.txt`, `.steamgriddb_key`,
`.steamgriddb_key.txt`, `sgdb-key.txt` and similar all work, in either the
Emulation folder or the roms folder. This file gets written by hand across
several machines and every spelling obviously means the same thing; enumerating
them guarantees missing one.

**Import file** in settings forces a re-import regardless of what config
holds — without it there is no way to pick up a corrected file once anything
has been saved. When it finds nothing it lists the folders it searched, because
a key that isn't being seen is nearly always a filename or a folder the plugin
wasn't checking. A library synced across several devices carries its key
with it, and every device imports from that same file, so nothing may move or
rename it. Import is already one-time by construction: it only runs when the
config copy is empty.

The config copy is canonical rather than the library copy for two reasons.
`chmod 600` is meaningless on exFAT, so a key on a card is readable by anything
that mounts it. And the config path exists before any library has been found, so
a key can be set on a machine with no card plugged in.

Adopting a key also purges the search cache, since results cached under a
rejected key are not answers.

**Emulators.** Resolved per system by scanning installed Flatpaks and RetroArch
cores — nothing is assumed to exist. Detection reads the Flatpak app
directories directly rather than trusting `flatpak list`: the plugin runs with a
minimal environment where `flatpak` may not be on PATH, and a failed subprocess
looks identical to nothing being installed. RetroArch is preferred when a core for the
system is present; otherwise a known standalone (Dolphin, PCSX2, RPCS3, PPSSPP,
melonDS, Cemu, Flycast) is used. If RetroArch is missing, the plugin offers to
install it with `flatpak install --user`. User scope is deliberate: a
system-scope install won't survive a SteamOS update, and user scope needs no
password, which matters in Game Mode where there's nowhere to type one.

## Mirror sync

`manifest.json` records only the shortcuts this plugin created. A shortcut you
added by hand is never touched.

A tracked shortcut is removed for exactly three reasons: the ROM file is gone,
you excluded it in `.romsync.txt`, or its system was switched off in the panel.
A missing emulator core is none of those — that downgrades a game to "skipped"
and leaves the shortcut alone, so a botched RetroArch update can't wipe the
library. The other three are explicit instructions and do delete.

Removing a shortcut discards its Steam playtime; re-enabling a system rebuilds
the shortcut but not the history.

The frontend applies the plan and reports back what Steam accepted; the manifest
is written from that, not from what was intended. A sync interrupted halfway
leaves a manifest that matches reality.

## Adoption

`SteamClient.Apps` can add, remove and mutate a shortcut by appid but has no way
to list shortcuts, so enumeration goes through `collectionStore` (untyped, and
its collection names have moved between releases — `listShortcuts` tries several
shapes). Exe and launch options are not on the app overview; they live on
AppDetails as `strShortcutExe` / `strShortcutLaunchOptions`, which loads lazily.

On sync, any existing shortcut whose command line contains one of our ROM paths
is adopted rather than duplicated. Without this, a library already imported with
Steam ROM Manager gets a second copy of every game.

Adopted shortcuts are flagged in the manifest, because adoption grants delete
authority over something we did not create. Reset therefore deletes only what
this plugin made and merely forgets the adopted ones.

## Artwork throughput

Fetching art inline per game pays full network latency 200 times over. Sync
instead warms the cache up front via `prefetch_art`, which fans out across 8
threads; the token bucket keeps the request rate constant regardless of worker
count, so concurrency buys latency hiding rather than a higher rate. Measured
roughly 8x against a serial baseline.

Prefetch is issued in chunks of 16 rather than one call for the whole library.
A single await over 200 games shows no movement for minutes, which is
indistinguishable from a hang; chunking gives real progress and keeps Stop
responsive during the phase.

Expect roughly 5 minutes for a first sync of 200 games. That is the rate limit,
not a stall: about 11 requests per game at 8 per second is a ~4.6 minute floor
before download time. Later syncs are near-instant because the cache holds.

Prefetch returns counts and reasons, not images — shipping artwork back through
that call would mean tens of megabytes over the websocket. The per-game
`get_art` calls that follow are cache hits.

Art failures are reported in the sync summary rather than swallowed. "No key
set", "no SteamGridDB match for X", and rate-limit hits each say so, and the
summary always states how many games actually received artwork.

## User-Agent

Every outbound request sends an explicit `User-Agent`. urllib's default is
`Python-urllib/3.x`, which Cloudflare — which fronts SteamGridDB — answers with
a 403 before the request reaches the API. That is indistinguishable from a
rejected key unless you look at the response body, so a 403 whose body carries
Cloudflare's markers is reported as a blocked request rather than a key problem.

## TLS

Decky runs plugins with a trimmed environment, and Python's default certificate
verification can end up with no CA bundle at all — every HTTPS request then
fails with CERTIFICATE_VERIFY_FAILED, which surfaces as "couldn't reach
SteamGridDB". `sgdb.ssl_context()` finds a bundle explicitly, checking
`SSL_CERT_FILE`, then certifi, then the usual distribution paths, then
`/etc/ssl/certs` as a directory. `describe_tls()` reports which one was used and
is included in the Test key result, so a TLS failure names its own cause.

A wrong system clock produces the same error with a valid trust store, so check
`date` on the device before going further.

## System toggles

Each row is name, game count, toggle — nothing else. A per-system sync button
used to sit here, but it was the rarest action in the panel occupying the most
prominent spot in every row, and it appeared and disappeared with the toggle so
rows changed shape as you used them.

Toggling defers, like every other setting: nothing is added or removed until
the next sync. That matters more than consistency alone, because removal
destroys Steam playtime and cannot be undone — deferring means a mis-tap costs
nothing and can be reversed for free. What is queued shows under the Sync
button ("12 to add, 40 to remove"), since a change with no visible effect
otherwise reads as a broken toggle.

Systems that cannot launch are left out of the queued count. Promising an
addition that pressing Sync cannot deliver would never clear; the Emulators
page in settings reports those instead.

The panel lists only folders that actually hold ROMs. A folder holding files that the plugin can't
place — an unknown name with no `.romsync.txt` — is named as unrecognised
rather than skipped in silence, since from outside that looks like the plugin
lost your games. A freshly created library
or a folder kept for later is named separately as "waiting for ROMs" rather than
appearing as a toggle, and a missing core is only reported for systems with
games in them.

Switching a system off also deletes its Steam category once nothing is left in
it, so the library isn't littered with hollow entries. Only empty categories
matching a name the plugin manages are touched — one you filled yourself would
not be empty. `collectionStore`'s delete method has moved between releases, so
the call tries the shapes that have existed and gives up quietly: a leftover
category is cosmetic, and failing a sync over it would not be.

Settings store `disabled_systems`, not enabled ones. The earlier list could not
express "everything off" — an empty list meant "all on", so switching off the
last system silently switched them all back on. Old settings are migrated once
on load.

Full-page routes share `PageShell`, a `Focusable` with `flow-children="column"`
rather than a plain div. A plain scroll container sits outside Steam's focus
tree, so the D-pad has no traversal order to follow and stops at whatever
control it happens to reach, with nothing scrolling to reveal the rest.
Dragging still works, which makes it present as a scrolling bug rather than a
focus one. Sections on those pages are `Section`, not `PanelSection` — the latter is a
quick-access-menu component whose focus behaviour in a route is not something
to depend on. The focus tree is PageShell → Section → ActionRow → button, every
level declaring its own direction, with nothing in between that navigation has
to guess about.

`PageShell` sets an explicit height,
`overflow-y: scroll` and generous fixed padding — 56px top for clearance under
Steam's header, 140px bottom so the last control isn't flush against the edge
when scrolled down. Without the height and overflow the content simply
overflows: the controller can still move focus, but there is nothing for a
finger to drag.

Actions are grouped into rows rather than stacked full-width, which keeps the
important controls on screen instead of pushing them past the fold. No page has
a Back button — B does that, and duplicating a platform control in the UI only
adds something to navigate past. Manage ROM has one Save, which always applies:
a save that deliberately doesn't take effect was a distinction with no use
behind it.

Progress uses a bare `ProgressBar` with the status rendered separately, not
`ProgressBarWithInfo`. That component draws the status inside its own markup,
where a long game title has nothing to truncate against and drags the bar off
the panel. Split apart, the text clips with an ellipsis and the bar is pinned
to the row width. Statuses lead with position (`Adding 12/200 · …`) so the part
that survives truncation is the part worth reading.

All three screens draw from one scale in `PageShell`: two type sizes, two
secondary opacities, two button heights. Values used to be picked locally,
which had produced four font sizes and five button heights across two screens —
differences too small to notice individually and collectively the thing that
makes an interface look assembled rather than designed.

Long paths, notes and error messages wrap rather than trailing off the edge.
Row labels truncate with `flex-basis: 0` and `min-width: 0`, without which a
long system name keeps its natural width and pushes the toggle off-panel.

A finished sync's report can be dismissed. The store outlives the panel, so
otherwise the last run's summary sits above the system list indefinitely.

Manage ROM shows the cover for the selected match beside the list. Reading
names that differ by a subtitle is slow; seeing the artwork is instant. The
thumbnail comes from the grids endpoint's own `thumb` — 20-50KB rather than
several hundred — and is cached per game.

The match list is capped and scrolls. Ten full-height
buttons pushed every other control off the page. Each row shows the release
year where available — the autocomplete endpoint returns only id, name, types
and verified, so the year costs one extra request per shown candidate, fetched
only for what is displayed and cached permanently.

## Panel layout

The panel is Sync, progress and system toggles. Library path, API key and the
destructive reset live behind the cog in the title, as a route — they are
touched once during setup, and keeping them out of the way leaves Sync as the
obvious thing to press. A route rather than a modal for the same reason as
Manage ROM: modals raised from the panel render behind the quick access menu.

## Artwork backfill

The manifest records which artwork slots actually landed per game. A tracked
game with none gets picked up on the next sync as an artwork-only pass — no
shortcut is touched, only the missing slots are fetched. That is what makes a
library synced before the SteamGridDB key worked recoverable without deleting
and recreating everything, which would discard playtime.

Prefetch skips any game whose artwork is already complete locally: local files
win regardless, so fetching them would spend rate limit on results that get
thrown away.

## Removals

Nothing is removed without showing what and why first — title, reason, and a
note that playtime is lost. Switching a system off makes removals easy to
trigger by accident, so the confirmation matters more than it used to.

## The manifest

`commit` merges into the existing entry rather than rebuilding it. A rebuild
dropped every field the caller did not happen to carry — an update from a core
swap has no `art`, so committing one erased the record of which artwork had
landed, and the next sync re-applied artwork for the whole system for nothing.

All mutation goes through `Manifest.update`, which loads, applies and saves
under one lock. It is reached from the event loop and from worker threads, so
an unguarded reload could rebind the data between another caller's mutation and
its save, silently reverting the write.

## Concurrency

Every temp file is named per thread, not derived from its target. The artwork
prefetch runs eight workers, and two games routinely resolve to the same
SteamGridDB id — regional variants of one game always do — so a shared `.tmp`
name meant two writers interleaving into it and `os.replace` publishing a
half-written image into a permanent cache.

`listShortcuts` fetches shortcut details concurrently. Each miss waits on a
callback with a timeout, so serially a library with fifty unloaded shortcuts
would sit at "Checking existing shortcuts" for over a minute.

Artwork slots are cleared in a batch, then filled. `ClearCustomArtworkForApp`
resolves before the clear actually happens, so it needs a fixed wait after it;
one wait per game rather than one per slot is minutes of difference across a
library.

Components are never declared inside a render. A component defined there gets a
new function identity each time, so React sees a different type and remounts the
subtree — which on a gamepad UI drops focus on every keystroke.

## Hot paths

`discover_roots` reads the library file and stats every configured path, and it
sits under both `find_local_art` and `system_dir_for` — each of which runs per
game, per artwork slot. A 200-game prefetch was calling it roughly 1,600 times,
much of it against an SD card. It is cached for five seconds and invalidated
outright whenever the library changes: a sync finishes well inside the window,
and a card plugged in mid-session is picked up shortly after.

Adoption matches whole quoted arguments rather than substrings. A substring
test both costs shortcuts × games comparisons and false-adopts — a shortcut
pointing at `Mario.nes.bak` contains the path of `Mario.nes`.

## Panel cost

`get_settings` runs one library survey and derives systems, empty folders,
missing cores and unrecognised folders from it. It previously asked each
question separately, which meant five full walks of every system folder — and
fifteen ROM counts for three folders — every time the panel opened.

## Long operations

Sync and reset run in `syncStore.ts` at module scope, not inside a component.
The Decky panel unmounts every time the quick access menu closes; a loop living
in component state would lose its progress mid-run while shortcut creation
carried on in the background. The panel is a view onto the operation, not the
thing running it. Cancelling stops at the next game boundary and still commits
what landed.

## Layout

Everything blocking in `main.py` — network, subprocess, scanning — runs
through `asyncio.to_thread`. Decky drives the backend on one event loop, so a
synchronous call doesn't slow one endpoint down, it freezes all of them;
`install_retroarch` alone could hold the loop for minutes.

```
main.py          Decky plugin class: async endpoints, thread dispatch
sgdb.py          SteamGridDB client: throttle, retry, disk cache — no decky
                 import, testable off-device
romsync.py       Scanning, title cleaning, emulator resolution, match ranking —
                 no decky import, so it is testable off-device
src/steam.ts     Every Steam internal, isolated
src/syncStore.ts Sync and reset loops, module scope so they survive unmount
src/api.ts       Backend bindings
src/index.tsx    Panel: sync, progress, system toggles
src/Settings.tsx Settings route behind the title cog
src/managed.ts       which appids the plugin owns, cached for the menu patch
src/contextMenu.tsx  "Manage ROM..." patched into Steam's game menu
src/ManageRom.tsx    the page that entry opens
```

A modal raised from the Decky panel renders *behind* the quick access menu, so
per-game editing is a real route reached from the game's gear menu instead.

The entry only appears on ROMs this plugin manages — Steam games and shortcuts
created by anything else are left alone. The menu renders synchronously and
cannot await the backend, so `managed.ts` keeps the appid set in memory,
refreshed on mount and after every sync. Before that first load resolves it
claims nothing, on the grounds that a briefly missing entry beats one appearing
across someone's entire Steam library.
Patching Steam's own React tree is inherently fragile, so the patch is wrapped:
if it fails, the menu entry is simply absent and the panel still works. It logs
to the CEF console at each step, because a silently missing entry is otherwise
impossible to tell apart from a working one that declined to show.

The module export is a function component that *returns* the menu; the class
whose prototype gets patched only exists once rendered, so
`fakeRenderComponent(...).type` is required. Skipping it yields something with
no `prototype.render`, the patch attaches to nothing, and the entry never
appears.

## Known-fragile

`src/steam.ts` is the whole risk surface. `SteamClient.Apps.*`,
`collectionStore`, `appStore`, and `appDetailsStore` are undocumented internals
that Valve reshapes without notice. When a Steam update breaks the plugin, this
is the only file to fix.

Artwork slots use `ELibraryAssetType` from @decky/ui rather than a local copy
(`Capsule 0, Hero 1, Logo 2, Header 3, Icon 4, HeroBlur 5`). The library defines
it but never re-exports it from the package root, so `steam.ts` deep-imports it
from `@decky/ui/dist/globals/steam-client/App`. It is a real emitted enum and
rollup inlines it. If a future release moves that path, this is the import to
fix.

**Icons are not like the other four.** Capsule, hero, logo and header are sent
as base64 through `SetCustomArtworkForApp`. A shortcut icon is a *file path*
stored on the shortcut record and set with `SetShortcutIcon`, so it has to live
somewhere stable: a local icon is pointed at in place, and a SteamGridDB icon is
written to `<runtime>/icons/<sgdb_id>.png` and reused on later syncs. Never a
temp file — the path outlives the sync that created it.

Verified on hardware: `SetShortcutIcon` applies live, no Steam restart needed.

Worth recording because the evidence pointed the other way. SteamGridDB's own
Decky plugin does not use this API — it edits `shortcuts.vdf` directly and then
prompts for a restart, which suggested the clean path didn't work. It does. Do
not "fix" this by reintroducing binary VDF editing on the strength of that
plugin's approach.

Two artwork behaviours are not obvious and are both handled:

- `ClearCustomArtworkForApp` resolves before the clear has actually happened, so
  it needs a fixed wait after it. We skip the clear entirely for a
  freshly-created shortcut, which has no custom art to clear — otherwise the
  wait dominates the runtime of a large sync at four slots per game.
- A logo on a non-Steam shortcut renders blank unless a custom logo position
  record exists, so one is forced via `appDetailsStore.SaveCustomLogoPosition`.

## Build

```
pnpm i
pnpm run build
```

### Source files (14)

```
plugin.json          package.json         rollup.config.js     tsconfig.json
main.py              romsync.py           sgdb.py              arcade.py
src/index.tsx        src/api.ts           src/steam.ts
src/syncStore.ts     src/overrides.tsx    README.md
```

### Deploying (7)

Only these go onto the device — the build config and TypeScript sources stay
behind, since `dist/index.js` is the compiled bundle of all of them:

```
plugin.json  package.json  main.py  romsync.py  sgdb.py  dist/index.js
```

The Rollup config is `@decky/rollup`, the official preset. Use it rather than a
hand-rolled config: Steam injects React as globals (`SP_REACT`, `SP_JSX`,
`SP_REACTDOM`, `DFL`) and the exact set of externals, the ESM output format and
the sourcemap URL rewriting all have to match what the loader expects. A config
that misses `react/jsx-runtime` builds cleanly and then throws
`ReferenceError: jsxRuntime is not defined` at load.

```bash
pnpm i && pnpm run build
grep -c prefetch_art dist/index.js    # sanity: must print 1
```

Deploy over SSH without root. Point the plugin directory at a folder you own,
once:

```bash
DECK=deck@steamdeck.local
ssh -t $DECK 'mkdir -p ~/dev-plugins/romsync/dist && \
  sudo rm -rf "/home/deck/homebrew/plugins/ROM Sync" && \
  sudo ln -s ~/dev-plugins/romsync "/home/deck/homebrew/plugins/ROM Sync"'
```

Then every push is:

```bash
rsync -av plugin.json package.json main.py romsync.py sgdb.py arcade.py \
  "$DECK:~/dev-plugins/romsync/"
rsync -av dist/index.js dist/index.js.map "$DECK:~/dev-plugins/romsync/dist/"
ssh -t $DECK 'sudo systemctl restart plugin_loader'
```

Do not `sudo cp` into the plugin directory. It creates root-owned files the
plugin's own user cannot read, and an unreadable `arcade.py` takes the whole
backend down with a PermissionError on import — every method call then fails
and the panel renders blank.

All four Python files are required at runtime: `main.py` imports `romsync`,
`sgdb` and `arcade` as siblings.
