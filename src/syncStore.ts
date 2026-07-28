/**
 * Sync and reset run here, not inside a component.
 *
 * The Decky panel unmounts whenever the user closes the quick access menu. If
 * the sync loop lives in a component, closing the menu mid-sync destroys the
 * progress state while shortcut creation keeps going — the UI comes back idle
 * while work is still happening. Keeping the loop at module scope means the
 * panel is a view onto the sync rather than the thing running it.
 */

import { useEffect, useState } from "react";
import { buildPlan, commit, getArt, listGames, prefetchArt, withTimeout } from "./api";
import {
  addShortcut,
  addToCollection,
  AssetType,
  listShortcuts,
  pruneEmptyCollections,
  clearArtwork,
  removeShortcut,
  setArtwork,
  setShortcutIcon,
  updateShortcut,
} from "./steam";
import { refreshManaged } from "./managed";

export type Phase = "idle" | "scanning" | "applying" | "done" | "error";

export interface SyncState {
  phase: Phase;
  progress: number;
  status: string;
  summary: string[];
  busy: boolean;
}

let state: SyncState = {
  phase: "idle",
  progress: 0,
  status: "",
  summary: [],
  busy: false,
};

const listeners = new Set<() => void>();
let aborted = false;

function set(patch: Partial<SyncState>) {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
}

export function useSyncState(): SyncState {
  const [, bump] = useState(0);
  useEffect(() => {
    const l = () => bump((n) => n + 1);
    listeners.add(l);
    return () => {
      listeners.delete(l);
    };
  }, []);
  return state;
}

/** Clear a finished run's report. The store outlives the panel, so without
 *  this the last sync's summary sits above the system list indefinitely. */
export function dismissSummary() {
  if (state.busy) return;
  set({ phase: "idle", summary: [], status: "", progress: 0 });
}

export function cancel() {
  if (!state.busy) return;
  if (aborted) {
    // Second press: the loop isn't responding, most likely because a backend
    // call is stranded. Let go of it rather than staying stuck forever.
    set({
      phase: "error",
      busy: false,
      status: "Stopped. Anything already added was kept — run Sync again to continue.",
    });
    return;
  }
  aborted = true;
  set({ status: "Finishing the current game, then stopping. Press again to force stop." });
}

const ART_SLOTS: [string, AssetType][] = [
  ["grid", AssetType.Capsule],
  ["hero", AssetType.Hero],
  ["logo", AssetType.Logo],
  ["wide", AssetType.Header],
];

function startDirOf(romPath: string) {
  return romPath.substring(0, romPath.lastIndexOf("/"));
}

export interface SyncOptions {
  /** Called with the removals before any happen; return false to stop. */
  confirmRemovals?: (removals: any[]) => Promise<boolean>;
}

export async function runSync(options: SyncOptions = {}) {
  if (state.busy) return;
  aborted = false;
  set({ phase: "scanning", progress: 0, status: "Looking for ROMs", summary: [], busy: true });

  try {
    const plan = await withTimeout(buildPlan(), 180000, "Scan");

    // Removals are the only destructive part, so they get a look-in first.
    if (plan.remove.length && options.confirmRemovals) {
      set({ status: "Waiting for confirmation" });
      const go = await options.confirmRemovals(plan.remove);
      if (!go) {
        set({ phase: "done", busy: false, status: "",
              summary: ["Cancelled. Nothing was changed."] });
        return;
      }
    }
    const total =
      plan.add.length + plan.update.length + plan.remove.length +
      plan.artwork.length;
    if (total === 0) {
      set({
        phase: "done",
        busy: false,
        summary: [`Nothing to do. ${plan.counts.found} games already in sync.`],
      });
      return;
    }

    // Adoption: shortcuts that already point at one of our ROMs, created by
    // SRM or by hand. Without this every one of them gets a duplicate.
    //
    // Matched on whole arguments, not substrings. A substring test both
    // false-adopts (a shortcut pointing at "Mario.nes.bak" contains the path
    // of "Mario.nes") and costs shortcuts × games comparisons; pulling the
    // quoted arguments out and looking them up is exact and linear.
    set({ phase: "applying", status: "Checking existing shortcuts" });
    const existing = await listShortcuts();
    const wanted = new Map<string, boolean>();
    for (const e of plan.add) wanted.set(e.rom_path, true);

    const byRom = new Map<string, number>();
    const ARG = /'([^']*)'|"([^"]*)"|(\S+)/g;
    for (const sc of existing) {
      for (const m of `${sc.exe} ${sc.launchOptions}`.matchAll(ARG)) {
        const arg = m[1] ?? m[2] ?? m[3];
        if (arg && wanted.has(arg) && !byRom.has(arg)) {
          byRom.set(arg, sc.appid);
        }
      }
    }

    // Warm the artwork cache first, in parallel. Downloading inline per game
    // means paying full network latency 200 times over; this collapses it and
    // makes the per-game calls below cache hits.
    //
    // Chunked rather than one call: a single await over 200 games shows no
    // movement for minutes, which is indistinguishable from a hang. Chunking
    // also keeps Stop responsive during this phase.
    const artNote: string[] = [];
    const needArt = [...plan.add, ...plan.artwork];
    if (needArt.length) {
      const CHUNK = 16;
      let done = 0;
      let found = 0;
      let missing = 0;
      let limited = false;

      for (let i = 0; i < needArt.length; i += CHUNK) {
        if (aborted) break;
        const slice = needArt.slice(i, i + CHUNK);
        set({
          status: `Fetching artwork ${done + 1}-${Math.min(done + slice.length, needArt.length)} of ${needArt.length}`,
          progress: (done / needArt.length) * 100,
        });
        const pre = await withTimeout(
          prefetchArt(
            slice.map((e: any) => ({
              title: e.title,
              sgdb_id: e.sgdb_id ?? null,
              rom_path: e.rom_path,
              system_key: e.system_key,
            })),
          ),
          180000,
          "Artwork fetch",
        );
        found += pre.ok;
        missing += pre.failed;
        if (pre.limited) limited = true;
        for (const r of pre.reasons) {
          if (artNote.length < 8) artNote.push(`• ${r}`);
        }
        done += slice.length;
      }

      if (missing > 0) {
        artNote.unshift(`Artwork: ${found} found, ${missing} without.`);
        if (limited) {
          artNote.push("Hit the SteamGridDB rate limit — rerun Sync later to fill gaps.");
        }
      }
    }

    const added: any[] = [];
    const updated: any[] = [];
    const removedUids: string[] = [];
    const bySystem: Record<string, number[]> = {};
    let step = 0;
    let adoptedCount = 0;

    let artApplied = 0;
    const applyArt = async (appid: number, e: any, isNew: boolean): Promise<string[]> => {
      const { art, icon_path, warning } = await withTimeout(
        getArt(e.rom_path, e.title, e.system_key, e.sgdb_id ?? null),
        60000, "Artwork",
      );
      if (warning && artNote.length < 12) artNote.push(`• ${warning}`);

      // Clear the slots we are about to fill, once, then fill them. A
      // freshly created shortcut has nothing to clear.
      const filling = ART_SLOTS.filter(([name]) => art[name]);
      if (!isNew) await clearArtwork(appid, filling.map(([, type]) => type));

      const landed: string[] = [];
      for (const [name, type] of filling) {
        await setArtwork(appid, art[name], type);
        landed.push(name);
      }
      if (icon_path) {
        await setShortcutIcon(appid, icon_path);
        landed.push("icon");
      }
      if (landed.length) artApplied++;
      return landed;
    };

    for (const e of plan.add) {
      if (aborted) break;
      const spec = {
        title: e.title,
        exe: e.exe,
        startDir: startDirOf(e.rom_path),
        launchOptions: e.launch_options,
      };

      const adopt = byRom.get(e.rom_path);
      let appid: number;
      if (adopt !== undefined) {
        set({ status: `Adopting ${step + 1}/${total} · ${e.title}` });
        await updateShortcut(adopt, spec);
        appid = adopt;
        adoptedCount++;
      } else {
        set({ status: `Adding ${step + 1}/${total} · ${e.title}` });
        appid = await addShortcut(spec);
      }

      const landed = await applyArt(appid, e, adopt === undefined);
      (bySystem[e.system_label] ??= []).push(appid);
      added.push({ ...e, appid, adopted: adopt !== undefined, art: landed });
      set({ progress: (++step / total) * 100 });
    }

    // Artwork-only passes still go through commit so the manifest records
    // which slots landed, but they are not "updates": no shortcut changed.
    let artworkOnly = 0;
    for (const e of plan.artwork) {
      if (aborted) break;
      set({ status: `Artwork ${step + 1}/${total} · ${e.title}` });
      const landed = await applyArt(e.appid, e, false);
      updated.push({ ...e, art: landed });
      artworkOnly++;
      set({ progress: (++step / total) * 100 });
    }

    for (const e of plan.update) {
      if (aborted) break;
      set({ status: `Updating ${step + 1}/${total} · ${e.title}` });
      await updateShortcut(e.appid, {
        title: e.title,
        exe: e.exe,
        startDir: startDirOf(e.rom_path),
        launchOptions: e.launch_options,
      });
      updated.push(e);
      set({ progress: (++step / total) * 100 });
    }

    const touchedCategories = new Set<string>();
    for (const e of plan.remove) {
      if (aborted) break;
      set({ status: `Removing ${step + 1}/${total} · ${e.title}` });
      if (e.appid) await removeShortcut(e.appid);
      if (e.system_label) touchedCategories.add(e.system_label);
      removedUids.push(e.uid);
      set({ progress: (++step / total) * 100 });
    }

    if (!aborted) {
      for (const [label, appids] of Object.entries(bySystem)) {
        set({ status: `Filing into ${label}` });
        await addToCollection(label, appids);
      }
    }

    // Categories emptied by those removals are deleted, so switching a system
    // off doesn't leave a hollow entry behind in the library.
    let prunedCategories: string[] = [];
    if (touchedCategories.size) {
      set({ status: "Tidying categories" });
      prunedCategories = await pruneEmptyCollections([...touchedCategories]);
    }

    // Commit whatever actually landed, cancelled or not, so the manifest
    // always describes reality rather than intent.
    await withTimeout(commit(added, updated, removedUids), 60000, "Save");

    // Menu entries should be right straight after a sync, not after a reload.
    // commit has already landed, so a refresh reads the truth rather than
    // being told it.
    await refreshManaged();

    const lines: string[] = [];
    if (aborted) lines.push("Stopped early. Everything done so far was kept.");
    const realUpdates = updated.length - artworkOnly;
    lines.push(
      `Added ${added.length - adoptedCount}, adopted ${adoptedCount}, ` +
        `updated ${realUpdates}, removed ${removedUids.length}.`,
    );
    if (prunedCategories.length) {
      lines.push(`Removed empty categories: ${prunedCategories.join(", ")}.`);
    }
    const artAttempted = added.length + artworkOnly;
    if (artAttempted > 0) {
      lines.push(`Artwork applied to ${artApplied} of ${artAttempted}.`);
    }
    lines.push(...artNote);
    // Notes explain the non-obvious outcomes — an unreadable root, a folder
    // skipped for want of a system name, a core that moved. Computing them and
    // throwing them away leaves those failures invisible.
    for (const note of (plan.notes ?? []).slice(0, 6)) {
      lines.push(`• ${note}`);
    }
    if ((plan.notes?.length ?? 0) > 6) {
      lines.push(`…and ${plan.notes.length - 6} more notes.`);
    }
    if (plan.counts.excluded > 0) {
      lines.push(`${plan.counts.excluded} excluded by .romsync.txt.`);
    }
    if (plan.counts.unresolved > 0) {
      lines.push(`${plan.counts.unresolved} skipped — no emulator:`);
      for (const u of plan.unresolved.slice(0, 5)) {
        lines.push(`• ${u.title} — ${u.reason}`);
      }
    }
    set({ phase: "done", busy: false, summary: lines, status: "" });
  } catch (err: any) {
    set({ phase: "error", busy: false, status: String(err?.message ?? err) });
  }
}

/**
 * Remove everything this plugin created. Adopted shortcuts are only untracked,
 * never deleted — we did not create them, so deleting them would destroy
 * someone else's work on the way out.
 */
export async function runReset() {
  if (state.busy) return;
  aborted = false;
  set({ phase: "applying", progress: 0, status: "Reading library", summary: [], busy: true });

  try {
    const games = await listGames();
    const uids: string[] = [];
    let deleted = 0;
    let untracked = 0;
    let step = 0;

    for (const g of games) {
      if (aborted) break;
      set({ status: `Removing ${step + 1}/${games.length} · ${g.title}` });
      if (g.appid && !g.adopted) {
        await removeShortcut(g.appid);
        deleted++;
      } else {
        untracked++;
      }
      uids.push(g.uid);
      set({ progress: (++step / Math.max(games.length, 1)) * 100 });
    }

    const categories = [...new Set(
      games.map((g) => (g as any).system_label).filter(Boolean) as string[],
    )];
    if (categories.length) {
      set({ status: "Tidying categories" });
      await pruneEmptyCollections(categories);
    }

    await commit([], [], uids);
    await refreshManaged();
    set({
      phase: "done",
      busy: false,
      status: "",
      summary: [
        `Removed ${deleted} shortcuts.`,
        ...(untracked
          ? [`Left ${untracked} adopted shortcuts alone, just stopped tracking them.`]
          : []),
        "Collections and .romsync.txt files were not touched.",
      ],
    });
  } catch (err: any) {
    set({ phase: "error", busy: false, status: String(err?.message ?? err) });
  }
}
