# CLAUDE.md

Working context for ROM Sync, a Decky Loader plugin for SteamOS. Read this
before changing anything; most of it is knowledge that cost real debugging on
hardware and is not discoverable from the code alone.

Target: Steam Deck / Steam Machine, SteamOS. Current version lives in
`package.json` — it is not repeated here, because a version in prose goes stale
on the next commit.

---

## What it does

Scans a ROM library, creates Steam shortcuts with SteamGridDB artwork, and
files them into per-system Steam categories. RetroArch-first, but every
system's launch command lives in a plain-text file the user can point at any
emulator.

The design principle behind almost every decision: **the files in the library
are the source of truth, not plugin state.** Launch commands, per-ROM
overrides and the API key all live next to the ROMs or in a config folder, in
hand-editable text. The plugin seeds those files and then reads them.

---

## Build and deploy

```bash
pnpm i
pnpm run build                        # produces dist/index.js
grep -c prefetch_art dist/index.js    # sanity: must print 1, not 0
```

`dist/` is gitignored — the plugin store builds from source and releases attach
the built artifact, so the bundle is never committed even though it is one of
the files that ships to the device.

**Full deploy, debugging and release steps are in `docs/DEPLOYING.md`.** It has
the one-time symlink setup, the rsync pair, an import health-check and a
symptom→cause table. Do not duplicate those commands here; they will drift.

Three rules from that file are repeated here because they are the ones that
cost days:

**The stale-bundle trap.** A build that silently compiles old sources succeeds
and deploys with no error. Always grep the bundle for a string you just added
before pushing.

**Never `sudo cp` into the plugin directory.** It creates root-owned files the
plugin's own user cannot read, and an unreadable `arcade.py` takes the entire
backend down with a PermissionError on import — every method call then fails
and the panel renders blank with no obvious cause. Only the restart needs sudo.

**Restarting `plugin_loader` does not reload the injected frontend.** It
reloads the Python backend only; picking up a new `dist/index.js` needs a full
Steam restart. Restarting mid-sync also strands the frontend — the backend call
never settles. Stop the sync first.

Diagnostics: `sudo journalctl -u plugin_loader -n 80 --no-pager` for backend,
CEF debugger at `localhost:8081` for frontend, `~/homebrew/logs/ROM Sync/` once
the plugin loads successfully.

---

## Testing

`romsync.py`, `sgdb.py` and `arcade.py` deliberately import nothing from
`decky`, so they run off-device. `main.py` is tested by injecting a fake module
— these three attributes are the entire `decky` surface it touches:

```python
import sys, types, tempfile, logging
fake = types.ModuleType("decky")
fake.DECKY_PLUGIN_SETTINGS_DIR = tempfile.mkdtemp()
fake.DECKY_PLUGIN_RUNTIME_DIR = tempfile.mkdtemp()
fake.logger = logging.getLogger("d")
sys.modules["decky"] = fake
import main
```

Point `romsync.CORE_SEARCH_DIRS`, `romsync.CORE_DIR` and
`romsync._candidate_bases` at temp directories to simulate a library.

There is no test suite in the repo — testing has been ad-hoc scripts. Adding
one is a reasonable next step; the modules are structured for it.

---

## Architecture

```
main.py            Decky Plugin class. Async endpoints only; every blocking
                   call goes through asyncio.to_thread.
romsync.py         Scanning, titles, per-folder config, cores, manifest.
sgdb.py            SteamGridDB client: throttle, retry, disk cache, TLS.
arcade.py          MAME DAT lookup for arcade set names.

src/index.tsx      QAM panel: Sync, progress, system toggles.
src/Settings.tsx   Settings route (Library / SteamGridDB / Emulators / Danger).
src/ManageRom.tsx  Per-game route (About / Artwork / Danger zone).
src/syncStore.ts   Sync and reset loops, at module scope.
src/steam.ts       Every Steam internal, isolated.
src/contextMenu.tsx "Manage ROM..." patched into Steam's game menu.
src/managed.ts     Which appids the plugin owns, for the menu filter.
src/PageShell.tsx  Shared page layout, visual scale, Progress.
src/api.ts         Backend bindings and shared types.
```

**Deploy set is 7 files:** `plugin.json`, `package.json`, the four `.py` files,
and `dist/index.js`. The TypeScript sources and build config stay behind. All
four Python files are required at runtime — `main.py` imports the other three
as siblings.

---

## Safety invariants

**Removing a shortcut destroys its Steam playtime and cannot be undone.** This
is the reason nothing takes effect immediately: toggling a system, excluding a
ROM and changing a core all defer to the next Sync, so a mis-tap costs nothing.
The counterpart is that queued changes must stay visible, or a toggle that
appears to do nothing reads as broken — hence the pending line under Sync.

**A tracked shortcut is removed for exactly three reasons:** the ROM file is
gone, the user excluded it, or its system was switched off. A missing emulator
core is none of those — it downgrades the game to "skipped" and leaves the
shortcut alone, so a botched RetroArch update cannot wipe a library.

**Adoption grants delete authority over something the plugin did not create,**
so adopted shortcuts are flagged in the manifest. Reset deletes only what the
plugin made and merely forgets the adopted ones.

**The manifest is written from what Steam accepted, not what was planned.** The
frontend applies the plan and reports back. A sync interrupted halfway leaves a
manifest that matches reality.

---

## Non-obvious constraints

These are the things that will waste a day if rediscovered from scratch.

**`plugin.json` must contain `"api_version": 1`.** Without it Decky rejects
every method called with positional arguments — which is all of them — and each
fails with `api_version 1 or newer is required to call methods with index-based
arguments`.

**Use `@decky/rollup`, not a hand-rolled config.** Steam injects React as
globals; a config that misses `react/jsx-runtime` → `SP_JSX` builds cleanly and
then throws `ReferenceError` at load. A hand-rolled config also emitted `iife`
where Decky expects `esm`.

**Long operations must not live in a component.** The Decky panel unmounts when
the quick access menu closes. Sync and reset run at module scope in
`syncStore.ts`; the panel is a view onto them.

**Never declare a component inside a render.** It gets a new function identity
each render, so React sees a different type and remounts the subtree — which on
a gamepad UI drops focus on every keystroke. `Footer` and `Fact` in
`ManageRom.tsx` were originally inline and did exactly this.

**Full-page routes must use `SidebarNavigation`.** Three attempts at a
hand-rolled scroll container — plain div, `Focusable` with `flow-children`,
page-native sections — all left the D-pad unable to reach the bottom of a long
page. Touch dragging worked throughout, which made it present as a scrolling
bug when it was a focus one. Steam's gamepad navigation drives scrolling
through its own page components and cannot be told about an arbitrary overflow
div. `PageShell` only reserves 40px below the top bar.

**Outbound HTTP needs a real User-Agent.** urllib's default `Python-urllib/3.x`
gets a Cloudflare 403 before the request reaches SteamGridDB, which is
indistinguishable from a rejected key. See `sgdb.DEFAULT_HEADERS`.

**Decky's Python may have no CA bundle.** `sgdb.ssl_context()` locates one
explicitly. A wrong system clock produces the same symptom.

**`SetShortcutIcon` works live** — verified on hardware, no Steam restart
needed. The SteamGridDB plugin edits `shortcuts.vdf` and prompts for a restart,
which strongly implies otherwise. Do not "fix" this by reintroducing binary VDF
editing on the strength of their approach.

**The context menu patch needs `fakeRenderComponent(...).type`.** The module
export is a function component that *returns* the menu; the class whose
prototype gets patched only exists once rendered. Patching the raw export
attaches to nothing and the entry silently never appears.

**`ELibraryAssetType` is deep-imported** from
`@decky/ui/dist/globals/steam-client/App` — the library defines it but never
re-exports it from the package root. Values: Capsule 0, Hero 1, Logo 2,
Header 3, Icon 4, HeroBlur 5.

**A logo on a shortcut renders blank** unless a custom logo position record
exists. `setArtwork` forces one.

**`ClearCustomArtworkForApp` resolves before the clear happens.** It needs a
fixed wait afterwards. Clear all slots for a game in one batch and wait once —
per-slot waits cost minutes across a library.

**`listShortcuts` fires its detail lookups concurrently on purpose.** Each miss
waits on a callback with a 2s timeout, so serially a library with fifty
unloaded shortcuts sits at "Checking existing shortcuts" for over a minute.
Fired together, the wait is the timeout once. This is not a gratuitous
`Promise.all`.

**`set_system_core` edits the config file line by line** and replaces only the
`-L` argument, rather than regenerating the file from parsed values. Hand-added
flags and comments have to survive. Do not refactor it into parse-and-rebuild.

---

## Fragile surfaces

`src/steam.ts` and `src/contextMenu.tsx` are the entire risk surface.
`SteamClient.Apps.*`, `collectionStore`, `appStore` and `appDetailsStore` are
undocumented internals Valve reshapes without notice.

- `collectionStore` has no typings and its collection names have moved between
  releases; `listShortcuts` tries several shapes.
- `SteamClient.Apps` can add, remove and mutate a shortcut by appid but **cannot
  list them** — enumeration goes through the stores.
- Shortcut exe and launch options are on `AppDetails`, not the app overview,
  and load lazily.
- The context menu patch is wrapped so a failure leaves the entry absent rather
  than taking the plugin down. It logs to the CEF console at each step.

When a Steam update breaks the plugin, look here first.

---

## Conventions

- Every temp file is named per thread (`tmp_path`, `_tmp_for`). Deriving it from
  the target races: the artwork prefetch runs eight workers and two games
  routinely resolve to the same SteamGridDB id.
- All manifest mutation goes through `Manifest.update`, which loads, applies and
  saves under one lock. It is reached from the event loop and worker threads.
- `Plugin.commit` in `main.py` **merges** field-by-field into the existing entry
  before handing the batch to `Manifest.update` — `update` itself replaces whole
  entries. A rebuild dropped fields the caller did not carry: an update from a
  core swap has no `art`, so committing one erased the artwork record and the
  next sync re-applied everything.
- Anything that changes the library invalidates the roots cache
  (`invalidate_roots`).
- Two type sizes and two secondary opacities live in `PageShell.ui`; the shared
  button height is `PageShell.compactButton`. Do not pick these values locally —
  that is how the UI drifted to four font sizes and five button heights.
- Bump `package.json` version on every change; the plugin store keys on it.

---

## Open items

- **Unverified:** whether the D-pad now reaches the bottom of Settings after the
  `SidebarNavigation` change. This is the one behavioural fix from late in
  development never confirmed on hardware.
- `assets/thumbnail.png` is referenced by `plugin.json` but not committed. The
  store listing needs it and the URL only resolves once the repo is public.
- `README.md` is ~1200 lines and its second half duplicates the first —
  `## Adoption`, `## Artwork throughput`, `## TLS`, `## The manifest` and about
  a dozen more each appear twice, and the trailing `## Build` section is stale
  (it lists a `src/overrides.tsx` that does not exist, and its "Deploying (7)"
  block names only six files, omitting `arcade.py`). Needs a cut, not a patch.
- Consider dropping `"debug"` from `plugin.json` flags before store submission.
- Store submission: PR against `SteamDeckHomebrew/decky-plugin-database` adding
  the plugin as a submodule. See `wiki.deckbrew.xyz/en/plugin-dev/submitting-plugins`.

## Deliberately not built

Do not re-litigate these without new information; each was considered and
rejected for a stated reason. Full rationale in `docs/DECISIONS.md`.

- Editing launch commands in the UI
- RetroAchievements as native Steam achievements
- IGDB metadata in the game details panel
- Exporting artwork into the library
- An "excluded games" list to undo exclusions
