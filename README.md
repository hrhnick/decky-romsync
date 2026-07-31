# ROM Sync

A Decky Loader plugin that turns a ROM folder into Steam shortcuts with artwork
and per-system collections. Runs inside Game Mode, uses Valve's own React
components, and never touches `shortcuts.vdf`.

## Installing

ROM Sync is not in the Decky plugin store yet, so installation is manual. It
takes about two minutes.

### 1. Install Decky Loader

If you do not already have it, follow the installer at
[decky.xyz](https://decky.xyz). Everything below assumes Decky is working and
its plug icon appears in the Quick Access Menu (the **·· ·** button).

### 2. Turn on Developer Mode

Developer Mode is what exposes the "install from a file" option; without it
Decky only installs from its own store.

1. Press the **·· ·** (Quick Access) button and open the **Decky** tab — the
   plug icon in the QAM's top row.
2. Press the **gear** icon in Decky's header to open its settings.
3. On the **General** page, scroll to **Developer Mode** and switch it on.
4. A new **Developer** entry appears in the settings sidebar. Open it.

### 3. Download the release

Grab `ROM-Sync-<version>.zip` from the
[Releases page](https://github.com/hrhnick/decky-romsync/releases). It has to
end up on the Deck itself, so either download it in Desktop Mode with a browser
or fetch it from Konsole:

```bash
# In Desktop Mode, Konsole. Set VERSION to the release you want.
VERSION=1.8.0
cd ~/Downloads
curl -LO "https://github.com/hrhnick/decky-romsync/releases/download/v$VERSION/ROM-Sync-$VERSION.zip"
```

Do not unzip it. Decky wants the archive.

### 4. Install the zip

Back in Game Mode, in **Decky → settings → Developer**, choose **Install Plugin
from ZIP File**. A file browser opens; navigate to the zip (`~/Downloads` if you
followed the step above) and select it.

Decky unpacks it, restarts its loader, and **ROM Sync** appears in the plugin
list in the QAM. Open it and press **Sync** to get started — the plugin will
walk you through pointing it at a ROM folder on first run.

### Updating

Same steps with the newer zip. Decky replaces the existing install; your
`.romsync.txt` overrides, launch commands and SteamGridDB key live in the
library and in `~/.config/romsync`, not in the plugin folder, so nothing you
have customised is lost.

### If the zip install option is missing

The **Developer** sidebar entry only appears after Developer Mode is toggled on,
and the settings page does not always redraw immediately — back out of Decky's
settings and reopen them.

### Manual install, as a fallback

If the file picker will not cooperate, unpack the zip into Decky's plugin
directory from Desktop Mode:

```bash
cd ~/Downloads
unzip "ROM-Sync-$VERSION.zip" -d ~/homebrew/plugins/
sudo systemctl restart plugin_loader
```

The zip contains a single `ROM Sync/` folder, so this lands at
`~/homebrew/plugins/ROM Sync/`. Unpack as your normal user — do **not**
`sudo unzip` or `sudo cp`. Root-owned files inside the plugin folder cannot be
read by the account the plugin runs as, and a single unreadable file takes the
whole backend down: every call fails and the panel renders blank with no error
pointing at the cause. If you hit that, `sudo chown -R deck:deck
"$HOME/homebrew/plugins/ROM Sync"` fixes it.

Only the `systemctl restart` needs sudo.

## Romhacks, decompilations and recompilations

Not everything is a ROM. Decomps and native recompilations ship as a folder
with a launcher script and no emulator at all. Put them in a `comps` folder,
one folder per game, with the script named after its folder:

```
roms/comps/Sonic 3 A.I.R/Sonic 3 A.I.R.sh
roms/comps/Ship of Harkinian/Ship of Harkinian.sh
```

Sync picks these up as games named after their folders, and they get artwork
and a Steam category like anything else. Two rules keep it unambiguous: the
launcher is the script named after the folder, or the only script in it — a
release that ships an uninstaller beside the real launcher would otherwise be
a coin flip, and the panel tells you which folders it could not decide about.

Scripts are run with `sh`, so they never need the executable bit — which
matters, because a copy off a FAT or exFAT drive does not have one. The
trade-off is that the script's `#!` line is ignored; if a launcher genuinely
needs bash, change the command in `comps/.romsync.txt` to
`/bin/bash "{rom}"`.

Any folder name works, not just `comps` — write `system` and `launcher = .sh`
into its `.romsync.txt` and it becomes its own Steam category. That is how you
keep `ports` and `romhacks` separate.

## Why?

Steam ROM Manager, the inspiration for this plugin, can be overwhelming for new users. In addition it requires desktop mode, and closing Steam. Decky ROM Sync allows managing almost everything from Gamescope/Big Picture, in addition to having an easy to modify text file based configuration for advanced power users.

