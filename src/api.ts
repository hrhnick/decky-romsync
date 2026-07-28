import { callable } from "@decky/api";

/**
 * Backend calls can hang indefinitely — restarting plugin_loader while a call
 * is in flight leaves the promise unsettled forever, which strands the sync
 * store in a permanently busy state with no way back. A rejection is
 * recoverable; a hang is not.
 */
export function withTimeout<T>(p: Promise<T>, ms: number, label: string): Promise<T> {
  return Promise.race([
    p,
    new Promise<T>((_, reject) =>
      setTimeout(
        () => reject(new Error(`${label} did not respond after ${Math.round(ms / 1000)}s`)),
        ms,
      ),
    ),
  ]);
}

export interface Game {
  uid: string;
  appid: number | null;
  title: string;
  system_key: string;
  system_label?: string;
  rom_path: string;
  system_dir: string;
  filename: string;
  /** What Steam actually runs, straight off the shortcut. */
  exe?: string;
  launch_options?: string;
  emulator?: string;
  adopted?: boolean;
}

export interface Override {
  sgdb_id: number | null;
  title: string;
  exclude: boolean;
  path: string;
}

export interface Candidate {
  id: number;
  name: string;
  score?: number;
  year?: number;
}

export const getSettings = callable<[], any>("get_settings");
export const setSettings = callable<[patch: any], any>("set_settings");
export const installRetroArch =
  callable<[], { ok: boolean; message: string }>("install_retroarch");
export const buildPlan = callable<[], any>("build_plan");
export const getArt = callable<
  [rom_path: string, title: string, system_key: string, sgdb_id: number | null],
  { art: Record<string, string>; icon_path?: string; warning?: string }
>("get_art");
export const commit = callable<
  [added: any[], updated: any[], removed: string[]],
  any
>("commit");
export const listGames = callable<[], Game[]>("list_games");
export const getOverride =
  callable<[system_dir: string, filename: string], Override>("get_override");
export const setOverride = callable<
  [system_dir: string, filename: string, sgdb_id: any, title: any, exclude: any],
  { ok: boolean; message?: string; path?: string }
>("set_override");
export const prefetchArt = callable<
  [entries: any[]],
  { ok: number; failed: number; limited: boolean; reasons: string[] }
>("prefetch_art");
export const setLibraryPath = callable<
  [path: string],
  { ok: boolean; message: string; path?: string }
>("set_library_path");
export const redetectLibrary =
  callable<[], { ok: boolean; message: string; roots: string[] }>("redetect_library");
export const createLibrary = callable<
  [base: string],
  { ok: boolean; message: string; path?: string }
>("create_library");
export const setCore = callable<
  [system_dir: string, core: string],
  { ok: boolean; message: string; installed?: boolean }
>("set_core");
export const installCores = callable<
  [names: string[]],
  { ok: boolean; message: string; installed: string[] }
>("install_cores");
export const purgeArtCache =
  callable<[], { ok: boolean; removed: number }>("purge_art_cache");
export const artPreview =
  callable<[sgdb_id: number], { image: string }>("art_preview");
export const reimportKey =
  callable<[], { ok: boolean; message: string; path?: string }>("reimport_key");
export const testKey =
  callable<[], { ok: boolean; message: string }>("test_key");
export const searchSgdb = callable<[title: string], Candidate[]>("search_sgdb");
