Turns a ROM folder into Steam shortcuts with artwork and per-system
collections. Runs inside Game Mode, uses Valve's own React components, and
never touches `shortcuts.vdf`.

## Installing

ROM Sync is not in the Decky plugin store yet, so install is manual:

1. Install [Decky Loader](https://decky.xyz) if you do not have it.
2. QAM → **Decky** → gear icon → **General** → turn on **Developer Mode**.
3. Download the `ROM-Sync-*.zip` attached below, onto the Deck itself.
4. Decky settings → **Developer** → **Install Plugin from ZIP File**, and pick
   the archive.

Full instructions, including a Desktop Mode fallback, are in the
[README](https://github.com/hrhnick/decky-romsync#installing).

## What is in the archive

The seven files that run on device — `plugin.json`, `package.json`, the four
Python modules and the compiled `dist/index.js` — inside a single `ROM Sync/`
folder. TypeScript sources and build config are not included; build them with
`pnpm install --frozen-lockfile && pnpm run build`.

## Notes

- Everything defers to the next Sync. Toggling a system, excluding a ROM or
  changing a core takes effect then, not immediately — removing a shortcut
  discards its Steam playtime and cannot be undone, so a mis-tap costs nothing.
- Shortcuts already imported by Steam ROM Manager are adopted rather than
  duplicated.
- Artwork needs a SteamGridDB key, set on the Settings page. Without one the
  sync still runs; art is filled in on a later sync once a key is present.
