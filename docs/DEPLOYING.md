# Deploying and debugging

## On the device, once

Decky's loader runs as root, so a sudo password must exist, and SSH is needed
to push from a dev machine:

```bash
passwd                          # in Konsole, Desktop Mode, if not already set
sudo systemctl enable --now sshd
```

Point the plugin directory at a folder you own, so nothing after this needs
root except restarting the loader:

```bash
DECK=deck@steamdeck.local
ssh -t $DECK 'sudo rm -rf "/home/deck/homebrew/plugins/ROM Sync" && \
  mkdir -p ~/dev-plugins/romsync/dist && \
  sudo ln -s ~/dev-plugins/romsync "/home/deck/homebrew/plugins/ROM Sync"'
```

## Every push

```bash
pnpm run build
grep -c prefetch_art dist/index.js    # must print 1

rsync -av plugin.json package.json main.py romsync.py sgdb.py arcade.py \
  "$DECK:~/dev-plugins/romsync/"
rsync -av dist/index.js "$DECK:~/dev-plugins/romsync/dist/"
ssh -t $DECK 'sudo systemctl restart plugin_loader'
```

Verify it landed:

```bash
ssh $DECK 'cd ~/dev-plugins/romsync && ls -la && grep -c prefetch_art dist/index.js && \
  python3 -c "import sys; sys.path.insert(0,\".\"); import romsync, sgdb, arcade; print(\"imports OK\")"'
```

Want `1` and `imports OK`, and every file owned by `deck`.

## Rules learned the hard way

**Never `sudo cp` into the plugin directory.** Root-owned files the plugin
cannot read take the whole backend down — `main.py` imports `romsync`, `sgdb`
and `arcade`, so one unreadable file means every method call fails and the panel
renders blank. If it happens:

```bash
ssh -t $DECK 'sudo chown -R deck:deck ~/dev-plugins && sudo chmod -R u+rwX,go+rX ~/dev-plugins'
```

**Check the bundle before pushing.** A build that compiles stale sources
succeeds silently. If the frontend seems not to change, grep `dist/index.js`
for a string you just added.

**Restarting `plugin_loader` mid-sync strands the frontend.** The backend call
never settles. Every call now has a timeout so it rejects rather than hangs, and
pressing Stop twice force-clears — but stopping the sync first is cleaner. Note
that restarting the loader does not reload the injected frontend; a full Steam
restart does.

## Diagnosing

| Symptom | Look at |
|---|---|
| Panel blank, all fields empty | Backend is dead — check imports and file ownership |
| Plugin absent from Decky menu | `sudo journalctl -u plugin_loader -n 50` |
| `ReferenceError` on load | Wrong rollup config; must use `@decky/rollup` |
| Every method fails, `api_version` in log | `plugin.json` missing `"api_version": 1` |
| Frontend errors | CEF debugger, `localhost:8081`, after enabling Remote Debugging |
| Backend logs | `~/homebrew/logs/ROM Sync/` once the plugin loads |

A useful one-shot health check:

```bash
ssh -t $DECK 'bash -s' <<'EOF'
P="/home/deck/dev-plugins/romsync"
ls -la "$P" "$P/dist"
grep -c prefetch_art "$P/dist/index.js"
cd "$P" && python3 -c "
import sys; sys.path.insert(0,'.')
for m in ['arcade','sgdb','romsync']:
    try: __import__(m); print(f'  {m}: OK')
    except Exception as e: print(f'  {m}: FAILED -> {type(e).__name__}: {e}')
"
cat "$P/plugin.json"
EOF
```

Note that a heredoc consumes stdin, so `ssh -t` cannot allocate a terminal for
sudo inside one — run any sudo command separately.

## Releasing

```bash
# repo
git add -A && git commit -m "ROM Sync X.Y.Z" && git push

# installable artifact for a GitHub Release
mkdir -p "out/ROM Sync/dist"
cp plugin.json package.json main.py romsync.py sgdb.py arcade.py "out/ROM Sync/"
cp dist/index.js "out/ROM Sync/dist/"
(cd out && zip -r "../ROM-Sync-$(node -p "require('../package.json').version").zip" "ROM Sync")
```

Bump `package.json` first — the plugin store keys on the version.

For the official store: PR against `SteamDeckHomebrew/decky-plugin-database`
adding the plugin as a submodule. Instructions at
`wiki.deckbrew.xyz/en/plugin-dev/submitting-plugins`. Needs
`assets/thumbnail.png` committed and the repo public.
