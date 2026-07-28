/**
 * Which appids ROM Sync manages.
 *
 * The context menu patch runs inside a synchronous React render, so it cannot
 * await the backend to decide whether to show its entry. The answer has to be
 * in memory already — hence this small cache, refreshed on mount and after any
 * operation that changes the library.
 */

import { listGames } from "./api";

let managed = new Set<number>();
let loaded = false;

export function isManaged(appid: number): boolean {
  // Before the first load completes, claim nothing. A missing entry for a few
  // seconds is better than showing "Manage ROM..." on someone's Steam library.
  return loaded && managed.has(appid);
}

export async function refreshManaged(): Promise<number> {
  try {
    const games = await listGames();
    managed = new Set(
      games.map((g) => g.appid).filter((a): a is number => typeof a === "number"),
    );
    loaded = true;
    return managed.size;
  } catch {
    return managed.size;
  }
}
