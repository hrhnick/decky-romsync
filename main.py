import asyncio
import base64
import concurrent.futures
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import decky  # noqa: E402
import arcade  # noqa: E402
import romsync as R  # noqa: E402
import sgdb  # noqa: E402

# Local art wins over SteamGridDB. Looked up in this order:
#   <rom_dir>/media/<rom_stem>.<asset>.png
#   <scan_root>/art/<system_key>/<rom_stem>.<asset>.png
ASSETS = ("grid", "hero", "logo", "wide")

# The icon is deliberately not in ASSETS. Steam takes the other four as base64
# through SetCustomArtworkForApp, but a shortcut icon is a *file path* stored on
# the shortcut itself (SetShortcutIcon), so it has to exist on disk somewhere
# stable and is returned as a path rather than bytes.
ICON_EXTS = (".png", ".jpg", ".jpeg", ".ico")

# Decky runs this plugin on a single asyncio event loop. Anything that touches
# the network, the disk at scale, or a subprocess goes through asyncio.to_thread
# — a synchronous call here doesn't just block one request, it freezes every
# endpoint in the plugin until it returns. install_retroarch was the worst
# case: minutes of flatpak inside an async def meant minutes of dead UI.


def _settings_dir() -> Path:
    return Path(decky.DECKY_PLUGIN_SETTINGS_DIR)


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = R.tmp_path(path)
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class Plugin:
    async def _main(self):
        self.settings_path = _settings_dir() / "settings.json"
        self.manifest = R.Manifest(_settings_dir() / "manifest.json")
        self.sgdb = sgdb.SgdbClient(
            cache_dir=Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / "sgdb-cache",
            key_getter=lambda: _read_json(self.settings_path, {}).get("sgdb_key", ""),
        )
        self.icon_dir = Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / "icons"
        self.arcade = arcade.ArcadeNames(
            Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / "arcade")
        # One flight at a time toward SGDB. The client throttles per-call, but
        # the frontend can fire several get_art calls concurrently; without
        # this they'd stack threads all hammering the same rate limit.
        self._sgdb_gate = asyncio.Semaphore(1)
        decky.logger.info("romsync ready")

    async def _unload(self):
        decky.logger.info("romsync unloaded")

    # -- settings -----------------------------------------------------------
    async def get_settings(self) -> dict:
        s = _read_json(self.settings_path, {})

        def probe():
            flatpaks = R.installed_flatpaks()
            return R.survey() | {
                "retroarch_installed": R.RETROARCH_ID in flatpaks,
                "cores": sorted(R.installed_cores().keys()),
                "library_bases": R.removable_bases(),
                # Adopt a key sitting beside the library, once, before
                # reading — after this the config copy is the only source.
                "imported_key": R.import_library_key(),
                "key_file": R.find_key_file(),
                "key_save_target": str(R.key_file_target()),
                "library_file": str(R.library_file()),
                "library_paths": R.read_library_paths(),
            }

        probed = await asyncio.to_thread(probe)

        # A key file on disk beats a typed-in key, and is imported into
        # settings so the rest of the code has one place to look.
        key = s.get("sgdb_key", "")
        key_file = probed.pop("key_file")
        imported = probed.pop("imported_key")
        key_file_path = None
        if key_file:
            file_key, key_file_path = key_file
            if file_key != key:
                s["sgdb_key"] = key = file_key
                # A newly adopted key invalidates anything the old one cached.
                await asyncio.to_thread(self.sgdb.purge_search_cache)
                _write_json(self.settings_path, s)
        if imported:
            probed["imported_from"] = imported[1]

        # Migrate the old enabled_systems list once. It could not express
        # "everything off": an empty list meant "all on", so turning off the
        # last system silently turned them all back on.
        if "enabled_systems" in s and "disabled_systems" not in s:
            enabled = set(s.get("enabled_systems") or [])
            detected = {d["key"] for d in probed["systems"]}
            s["disabled_systems"] = sorted(detected - enabled) if enabled else []
            s.pop("enabled_systems", None)
            _write_json(self.settings_path, s)

        # What a sync would change, so a toggle can be reversible without
        # leaving the user wondering whether it did anything. Cheap: the
        # manifest is already in memory and nothing is scanned again.
        self.manifest.load()
        disabled = set(s.get("disabled_systems") or [])
        tracked: dict[str, int] = {}
        for entry in self.manifest.data.values():
            k = entry.get("system_key", "")
            tracked[k] = tracked.get(k, 0) + 1
        pending_remove = sum(n for k, n in tracked.items() if k in disabled)

        # A changed launch command shows up as an update rather than an add or
        # remove. Detected without rescanning: rebuild what one tracked game's
        # launch options would be under the folder's current command and
        # compare against what was recorded at sync time.
        by_system: dict[str, dict] = {}
        for entry in self.manifest.data.values():
            by_system.setdefault(entry.get("system_key", ""), entry)

        def stale(system: dict) -> int:
            if system["key"] in disabled or not system.get("has_command"):
                return 0
            sample = by_system.get(system["key"])
            if not sample or not sample.get("rom_path"):
                return 0
            # The survey already read this folder's config; re-reading it here
            # would be one extra file read per system on every panel open.
            command = system.get("command") or ""
            core = R.command_core(command) if command else None
            if core:
                found = R.find_core(core)
                if not found:
                    return 0          # unlaunchable; reported elsewhere
                command = command.replace(core, found)
            split = R.split_command(command, sample["rom_path"])
            if not split:
                return 0
            _exe, args = split
            return (tracked.get(system["key"], 0)
                    if args != sample.get("launch_options") else 0)

        pending_update = sum(stale(d) for d in probed["systems"])
        # Systems that can't launch are excluded: counting them would promise
        # an addition that pressing Sync cannot deliver, and it would never
        # clear. The Emulators page reports those instead.
        pending_add = sum(
            max(d["games"] - tracked.get(d["key"], 0), 0)
            for d in probed["systems"]
            if d["key"] not in disabled and d["has_command"]
            and not d["missing_core"])

        return probed | {
            "pending_update": pending_update,
            "pending_remove": pending_remove,
            "pending_add": pending_add,
            "sgdb_key": key,
            "key_file_path": key_file_path,
            "disabled_systems": s.get("disabled_systems", []),
        }

    async def set_settings(self, patch: dict) -> dict:
        s = _read_json(self.settings_path, {})
        s.update(patch)
        _write_json(self.settings_path, s)

        # Mirror the key out to the Emulation folder so it lives with the
        # library rather than in plugin state, and survives a reinstall.
        if "sgdb_key" in patch and patch["sgdb_key"]:
            # A previous bad key may have cached "no results" for the whole
            # library; those are not answers and must not outlive the key.
            await asyncio.to_thread(self.sgdb.purge_search_cache)
            ok, detail = await asyncio.to_thread(R.save_key_file, patch["sgdb_key"])
            s["key_file_path"] = detail if ok else None
            if not ok:
                decky.logger.warning("key file: %s", detail)
        return s

    async def set_library_path(self, path: str) -> dict:
        """Point the plugin at a library auto-detection can't find."""
        raw = (path or "").strip()
        if not raw:
            return {"ok": False, "message": "Enter a folder path."}

        resolved = await asyncio.to_thread(R.resolve_library_path, raw)
        if not resolved:
            return {"ok": False, "message": f"No folder at {raw}."}

        ok, detail = await asyncio.to_thread(R.save_library_paths, [raw])
        if not ok:
            return {"ok": False, "message": detail}
        systems = await asyncio.to_thread(R.detect_systems, [resolved])
        return {
            "ok": True,
            "path": resolved,
            "file": detail,
            "systems": len(systems),
            "message": (f"Using {resolved} — {len(systems)} systems found."
                        if systems else
                        f"Using {resolved}, but no system folders are in it yet."),
        }

    async def create_library(self, base: str) -> dict:
        ok, detail, systems = await asyncio.to_thread(R.create_library, base)
        if not ok:
            return {"ok": False, "message": detail}
        return {
            "ok": True,
            "path": detail,
            "message": (f"Created {detail} with folders: "
                        f"{', '.join(systems)}. Drop ROMs into those."),
        }

    async def set_core(self, system_dir: str, core: str) -> dict:
        """Point a system at a different core, then report what it will cost.

        Nothing is applied to Steam here — the shortcuts still carry the old
        command until the next sync, same as every other setting.
        """
        def work():
            ok, detail = R.set_system_core(Path(system_dir), core)
            if not ok:
                return {"ok": False, "message": detail}
            present = R.find_core(core)
            note = (f"Now using {core}." if present
                    else f"Now using {core}, but that core isn't installed yet.")
            return {"ok": True, "path": detail, "installed": bool(present),
                    "message": note}

        return await asyncio.to_thread(work)

    async def install_cores(self, names: list[str]) -> dict:
        results = await asyncio.to_thread(R.install_cores, names)
        good = [r["core"] for r in results if r["ok"]]
        bad = [r for r in results if not r["ok"]]
        parts = []
        if good:
            parts.append(f"Installed {', '.join(good)}.")
        if bad:
            parts.append(
                f"Couldn't fetch {', '.join(b['core'] for b in bad)} — "
                "install them from RetroArch's Core Downloader instead "
                "(Main Menu, Online Updater, Core Downloader).")
        return {"ok": not bad, "installed": good, "message": " ".join(parts)}

    async def redetect_library(self) -> dict:
        """Forget the configured paths and scan mounted volumes again."""
        def work():
            for name in R.LIBRARY_FILENAMES:
                try:
                    (R.CONFIG_DIR / name).unlink()
                except OSError:
                    pass
            R.invalidate_roots()
            found = R.autodetect_roots()
            if found:
                R.save_library_paths(found)
            return found

        roots = await asyncio.to_thread(work)
        return {
            "ok": bool(roots),
            "roots": roots,
            "message": (f"Found {len(roots)}: {', '.join(roots)}" if roots
                        else "No Emulation folder found on any mounted volume."),
        }

    async def install_retroarch(self) -> dict:
        ok, msg = await asyncio.to_thread(R.install_retroarch)
        return {"ok": ok, "message": msg}

    # -- scan / plan --------------------------------------------------------
    async def build_plan(self) -> dict:
        s = _read_json(self.settings_path, {})
        disabled = set(s.get("disabled_systems") or [])

        def work():
            notes: list[str] = []
            # Fetch the arcade name list on demand, once, and only if there is
            # actually an arcade folder to name.
            if not self.arcade.available:
                probe_roots = R.discover_roots()
                has_arcade = any(
                    d["key"] in arcade.ARCADE_SYSTEMS
                    for d in R.detect_systems(probe_roots))
                if has_arcade:
                    ok, message = self.arcade.refresh()
                    notes.append(message if ok else f"Arcade names: {message}")

            entries, scan_notes, excluded = R.scan(arcade_names=self.arcade)
            notes.extend(scan_notes)
            # A system switched off is an explicit instruction, so its
            # shortcuts are removed rather than merely ignored.
            kept = [e for e in entries if e.system_key not in disabled]

            self.manifest.load()
            plan = self.manifest.plan(kept, excluded, disabled)
            plan["notes"] = notes
            plan["unresolved"] = [
                {"title": e.title, "system": e.system_label, "reason": e.reason}
                for e in kept if not e.resolved
            ]
            plan["counts"] = {
                "found": len(kept),
                "artwork": len(plan["artwork"]),
                "excluded": len(excluded),
                "add": len(plan["add"]),
                "update": len(plan["update"]),
                "remove": len(plan["remove"]),
                "unresolved": len(plan["unresolved"]),
            }
            return plan

        return await asyncio.to_thread(work)

    # -- artwork ------------------------------------------------------------
    async def get_art(self, rom_path: str, title: str, system_key: str,
                      sgdb_id: int | None = None) -> dict:
        """Local files win; SteamGridDB fills the gaps. Values are base64 PNG."""

        system_dir = R.system_dir_for(rom_path)

        def local_pass():
            found: dict[str, str] = {}
            for asset in ASSETS:
                hit = R.find_local_art(rom_path, system_key, asset, system_dir)
                if hit:
                    found[asset] = base64.b64encode(Path(hit).read_bytes()).decode()
            # A local icon needs no copying — point Steam straight at it.
            icon = R.find_local_art(rom_path, system_key, "icon", system_dir)
            return found, icon

        out, icon_path = await asyncio.to_thread(local_pass)
        missing = [a for a in ASSETS if a not in out]
        if not missing and icon_path:
            return {"art": out, "icon_path": icon_path, "source": "local"}

        key = _read_json(self.settings_path, {}).get("sgdb_key", "")
        if not key:
            result = {"art": out, "source": "local",
                      "warning": "Add a SteamGridDB key in settings to fill missing artwork."}
            if icon_path:
                result["icon_path"] = icon_path
            return result

        def sgdb_pass():
            game_id = sgdb_id
            if not game_id:
                best = R.pick_best(title, self.sgdb.search(title))
                game_id = best["id"] if best else None
            if not game_id:
                return out, icon_path, None, f"No SteamGridDB match for {title}."
            for asset in missing:
                blob = self.sgdb.get_asset(game_id, asset)
                if blob:
                    out[asset] = base64.b64encode(blob).decode()

            # Icons live on disk under the plugin runtime dir. The path is
            # written into the shortcut, so it has to be stable — never a temp
            # file, and named by SteamGridDB id so a re-sync reuses it.
            path = icon_path
            if not path:
                blob = self.sgdb.get_asset(game_id, "icon")
                if blob:
                    dest = self.icon_dir / f"{game_id}.png"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    tmp = R.tmp_path(dest)
                    tmp.write_bytes(blob)
                    os.replace(tmp, dest)
                    path = str(dest)
            return out, path, game_id, None

        async with self._sgdb_gate:
            try:
                art, path, game_id, warning = await asyncio.to_thread(sgdb_pass)
            except (sgdb.RateLimited, sgdb.AuthFailed, sgdb.Unavailable) as e:
                result = {"art": out, "source": "local", "warning": str(e)}
                if icon_path:
                    result["icon_path"] = icon_path
                return result

        result = {"art": art, "source": "steamgriddb"}
        if path:
            result["icon_path"] = path
        if game_id:
            result["sgdb_id"] = game_id
        if warning:
            result["warning"] = warning
        return result

    async def prefetch_art(self, entries: list) -> dict:
        """Warm the artwork cache for many games at once.

        Downloads dominate sync time and are almost entirely network latency,
        so they run concurrently. The rate limit is enforced by a shared token
        bucket inside the client, not by these workers, so raising the worker
        count does not raise the request rate.

        Returns counts and reasons rather than images — sending art back here
        would mean tens of megabytes over the websocket. The per-game get_art
        calls that follow hit the cache and return immediately.
        """
        key = _read_json(self.settings_path, {}).get("sgdb_key", "")
        if not key:
            return {"ok": 0, "failed": len(entries), "limited": False,
                    "reasons": ["No SteamGridDB key set — no artwork will be fetched."]}

        def one(entry):
            title = entry.get("title", "")
            try:
                # Local art wins anyway, so fetching it would be wasted
                # bandwidth against a rate limit.
                rom = entry.get("rom_path")
                if rom and self._local_art_complete(rom, entry.get("system_key", "")):
                    return True, None
                game_id = entry.get("sgdb_id")
                if not game_id:
                    best = R.pick_best(title, self.sgdb.search(title))
                    game_id = best["id"] if best else None
                if not game_id:
                    return False, f"No SteamGridDB match for {title}."
                got = 0
                for asset in (*ASSETS, "icon"):
                    if self.sgdb.get_asset(game_id, asset):
                        got += 1
                if got == 0:
                    return False, f"SteamGridDB has no artwork for {title}."
                return True, None
            except (sgdb.RateLimited, sgdb.AuthFailed):
                raise
            except sgdb.Unavailable as e:
                return False, f"{title}: {e}"
            except Exception as e:  # noqa: BLE001
                decky.logger.warning("prefetch %s: %s", title, e)
                return False, f"{title}: {e}"

        def run_all():
            ok = failed = 0
            reasons: list[str] = []
            limited = False
            auth_error = None
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                futures = [pool.submit(one, e) for e in entries]
                for fut in concurrent.futures.as_completed(futures):
                    try:
                        good, reason = fut.result()
                    except sgdb.AuthFailed as e:
                        auth_error = str(e)
                        failed += 1
                        continue
                    except sgdb.RateLimited:
                        limited = True
                        failed += 1
                        continue
                    if good:
                        ok += 1
                    else:
                        failed += 1
                        if reason and len(reasons) < 8:
                            reasons.append(reason)
            if auth_error:
                # One clear cause beats 200 copies of a misleading symptom.
                reasons = [auth_error]
            return {"ok": ok, "failed": failed, "limited": limited,
                    "reasons": reasons}

        return await asyncio.to_thread(run_all)

    async def art_preview(self, sgdb_id: int) -> dict:
        """Base64 cover thumbnail, so a match can be confirmed by eye."""
        if not sgdb_id:
            return {"image": ""}
        try:
            async with self._sgdb_gate:
                blob = await asyncio.to_thread(self.sgdb.get_thumb, int(sgdb_id))
        except Exception:  # noqa: BLE001 - a preview is never worth an error
            return {"image": ""}
        return {"image": base64.b64encode(blob).decode() if blob else ""}

    async def reimport_key(self) -> dict:
        """Force-adopt a key from beside the library.

        The ordinary import only runs when config has no key, so once anything
        has been saved there is otherwise no way to pick up a corrected file.
        Reports where it looked when it finds nothing — a key that isn't being
        seen is almost always a filename or a folder the plugin isn't checking.
        """
        def work():
            found = R.import_library_key(force=True)
            if found:
                return {"ok": True, "path": found[1],
                        "message": f"Imported key from {found[1]}."}
            searched = [str(d) for d in R.key_search_paths()]
            return {
                "ok": False,
                "message": ("No key file found. Looked in: "
                            + (", ".join(searched) or "nowhere — no library set")
                            + ". The file should be named steamgriddb_key.txt "
                              "and contain just the key."),
            }

        result = await asyncio.to_thread(work)
        if result["ok"]:
            # A newly adopted key invalidates anything the old one cached.
            await asyncio.to_thread(self.sgdb.purge_search_cache)
        return result

    async def test_key(self) -> dict:
        key = _read_json(self.settings_path, {}).get("sgdb_key", "")
        if not key:
            return {"ok": False,
                    "message": "No SteamGridDB key set. Add one above."}
        # The cache would otherwise answer for us and hide the real result.
        await asyncio.to_thread(self.sgdb.purge_search_cache)
        ok, message = await asyncio.to_thread(self.sgdb.check_key)
        return {"ok": ok, "message": message}

    def _local_art_complete(self, rom_path: str, system_key: str) -> bool:
        # Resolve the folder once rather than per asset.
        system_dir = R.system_dir_for(rom_path)
        return all(R.find_local_art(rom_path, system_key, asset, system_dir)
                   for asset in ASSETS)

    async def purge_art_cache(self) -> dict:
        n = await asyncio.to_thread(self.sgdb.purge_cache)
        return {"ok": True, "removed": n}

    # -- overrides ----------------------------------------------------------
    async def set_override(self, system_dir: str, filename: str,
                           sgdb_id=None, title=None, exclude=None) -> dict:
        """Write into the system folder's .romsync.txt so the override travels
        with the ROMs and stays hand-editable."""
        ok, detail = await asyncio.to_thread(
            R.save_override, Path(system_dir), filename,
            sgdb_id=sgdb_id, title=title, exclude=exclude)
        if not ok:
            return {"ok": False, "message": detail}
        return {"ok": True, "path": detail}

    async def get_override(self, system_dir: str, filename: str) -> dict:
        ov = R.load_overrides(Path(system_dir)).get(filename.casefold(), {})
        return {
            "sgdb_id": ov.get("sgdb_id"),
            "title": ov.get("title", ""),
            "exclude": bool(ov.get("exclude")),
            "path": str(R.override_path(Path(system_dir))),
        }

    async def list_games(self) -> list:
        """Everything this plugin currently tracks, for the override picker."""
        self.manifest.load()
        out = []
        for uid, e in self.manifest.data.items():
            rom = e.get("rom_path", "")
            out.append({
                "uid": uid,
                "appid": e.get("appid"),
                "title": e.get("title", ""),
                "system_key": e.get("system_key", ""),
                "rom_path": rom,
                # Always derived, never taken from the manifest: entries
                # written before the field existed would otherwise fall back to
                # the ROM's parent, which is a game subfolder on ScummVM.
                "system_dir": R.system_dir_for(rom) if rom else "",
                "art": e.get("art") or [],
                # Taken from the manifest, because for a game whose folder is
                # its identity the filename is the folder, not the file inside
                # it. Deriving it would key the override editor on the launcher
                # script while the scan keys it on the folder, and every
                # override set from Manage ROM would silently do nothing.
                # Derived only as a fallback, for manifests written earlier.
                "filename": e.get("filename") or (Path(rom).name if rom else ""),
                "system_label": e.get("system_label", ""),
                # What Steam will actually execute, for the About readout.
                "exe": e.get("exe", ""),
                "launch_options": e.get("launch_options", ""),
                "emulator": R.emulator_of(e.get("exe", ""),
                                          e.get("launch_options", "")),
                "adopted": bool(e.get("adopted")),
            })
        out.sort(key=lambda g: g["title"].casefold())
        return out

    async def search_sgdb(self, title: str) -> list:
        """Candidate matches, so a wrong cover can be fixed by picking rather
        than by hunting for an id on the website."""
        key = _read_json(self.settings_path, {}).get("sgdb_key", "")
        if not key:
            return []
        async with self._sgdb_gate:
            try:
                items = await asyncio.to_thread(self.sgdb.search, title)
            except (sgdb.RateLimited, sgdb.AuthFailed, sgdb.Unavailable):
                return []
        ranked = R.rank_candidates(title, items)[:10]

        # Years come from a per-game endpoint, so only fetch them for what is
        # actually shown — and fetch them at once. Serially this was ten round
        # trips before the picker could render, which is most of the wait
        # between opening the page and seeing anything. Failures are silent; a
        # missing year is cosmetic.
        def with_years():
            def year_of(candidate):
                try:
                    return candidate, self.sgdb.game_details(candidate["id"])
                except Exception:  # noqa: BLE001
                    return candidate, {}

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                for candidate, details in pool.map(year_of, ranked):
                    if details.get("year"):
                        candidate["year"] = details["year"]
            return ranked

        async with self._sgdb_gate:
            try:
                return await asyncio.to_thread(with_years)
            except Exception:  # noqa: BLE001
                return ranked

    # -- manifest -----------------------------------------------------------
    async def commit(self, added: list, updated: list, removed: list) -> dict:
        """Frontend reports what Steam actually accepted; we record only that.

        Merged into the existing entry rather than replacing it. A plain
        rebuild dropped every field the caller didn't happen to carry: an
        update from a core swap has no `art`, so committing one erased the
        record of which artwork had landed, and the next sync re-applied
        artwork for the entire system for nothing.
        """
        self.manifest.load()
        changes: dict[str, dict] = {}
        for item in added + updated:
            uid = item["uid"]
            entry = dict(self.manifest.data.get(uid) or {})
            for key in ("appid", "rom_path", "title", "system_key", "exe",
                        "launch_options", "system_label", "system_dir",
                        "filename"):
                if item.get(key) is not None:
                    entry[key] = item[key]
            # Only the callers that actually applied artwork report it.
            if item.get("art") is not None:
                entry["art"] = item["art"]
            entry.setdefault("art", [])
            if "adopted" in item:
                entry["adopted"] = bool(item["adopted"])
            entry.setdefault("adopted", False)
            changes[uid] = entry
        tracked = self.manifest.update(changes, removed)
        return {"ok": True, "tracked": tracked}
