/**
 * Every undocumented Steam internal we touch lives here.
 *
 * These are not a public API. Valve renames and reshapes them without notice,
 * so keep this file small and keep the rest of the plugin free of them — when
 * a Steam update breaks the plugin, this is the only file to fix.
 */

// @decky/ui defines ELibraryAssetType but never re-exports it from the package
// root (globals/index only re-exports SteamClient and stores), so this is a deep
// import by necessity. It is a real emitted enum, not a type-only declaration.
// Values: Capsule 0, Hero 1, Logo 2, Header 3, Icon 4, HeroBlur 5.
import { ELibraryAssetType } from "@decky/ui/dist/globals/steam-client/App";

// SteamClient, appStore and appDetailsStore are typed by @decky/ui.
// collectionStore is not, so it is the only one declared here.
declare global {
  // eslint-disable-next-line no-var
  var collectionStore: any;
}

export { ELibraryAssetType as AssetType };

export interface ShortcutSpec {
  title: string;
  exe: string;
  startDir: string;
  launchOptions: string;
}

export async function addShortcut(spec: ShortcutSpec): Promise<number> {
  const appid: number = await SteamClient.Apps.AddShortcut(
    spec.title,
    spec.exe,
    spec.startDir,
    spec.launchOptions,
  );
  // AddShortcut is inconsistent about honouring every field, so set explicitly.
  await SteamClient.Apps.SetShortcutName(appid, spec.title);
  await SteamClient.Apps.SetShortcutStartDir(appid, spec.startDir);
  await SteamClient.Apps.SetShortcutLaunchOptions(appid, spec.launchOptions);
  return appid;
}

export async function updateShortcut(appid: number, spec: ShortcutSpec) {
  await SteamClient.Apps.SetShortcutName(appid, spec.title);
  await SteamClient.Apps.SetShortcutExe(appid, spec.exe);
  await SteamClient.Apps.SetShortcutStartDir(appid, spec.startDir);
  await SteamClient.Apps.SetShortcutLaunchOptions(appid, spec.launchOptions);
}

export async function removeShortcut(appid: number) {
  await SteamClient.Apps.RemoveShortcut(appid);
}

/**
 * Set a shortcut's icon.
 *
 * Icons are the one asset that does NOT go through SetCustomArtworkForApp —
 * that call takes base64 for the capsule/hero/logo/header slots, but a
 * shortcut icon is a file path stored on the shortcut record itself. The path
 * must stay valid for as long as the shortcut does, so it points at the plugin
 * runtime dir (or the user's own art folder), never a temp file.
 *
 * Caveat: SteamGridDB's own Decky plugin does not use this API. It edits
 * shortcuts.vdf directly and then prompts for a Steam restart, which suggests
 * SetShortcutIcon may not take effect live. Verify on device; if the icon only
 * appears after restarting Steam, that is expected rather than a bug here.
 */
export async function setShortcutIcon(appid: number, path: string) {
  await SteamClient.Apps.SetShortcutIcon(appid, path);
}

export interface ExistingShortcut {
  appid: number;
  name: string;
  exe: string;
  launchOptions: string;
}

/**
 * Every non-Steam shortcut currently in the library.
 *
 * `SteamClient.Apps` has no enumeration method — it can add, remove and mutate
 * a shortcut by appid, but not list them. So this goes through the app stores
 * instead, which is why it is defensive about their shape: `collectionStore`
 * is not in the @decky/ui typings and its collection names have moved around.
 *
 * Exe and launch options are not on the overview; they live on AppDetails as
 * strShortcutExe / strShortcutLaunchOptions, which loads lazily, hence the
 * RegisterForAppDetails fallback.
 */
export async function listShortcuts(): Promise<ExistingShortcut[]> {
  const cs: any = collectionStore;
  const apps: any[] =
    cs?.deckDesktopApps?.allApps ??
    cs?.localGamesCollection?.allApps ??
    cs?.allAppsCollection?.allApps ??
    [];

  const shortcuts = apps.filter((a) => {
    try {
      return a?.BIsShortcut?.();
    } catch {
      return false;
    }
  });

  // Concurrently, not one at a time. Each miss waits on a callback with a
  // timeout, so serially a library with fifty unloaded shortcuts would sit at
  // "Checking existing shortcuts" for over a minute before the sync appeared
  // to do anything. Fired together, the wait is the timeout once.
  return Promise.all(
    shortcuts.map(async (app): Promise<ExistingShortcut> => {
      const appid = app.appid;
      let details = window.appDetailsStore.GetAppDetails(appid);
      if (!details) {
        details = await new Promise<any>((resolve) => {
          const timer = setTimeout(() => resolve(null), 2000);
          const reg = SteamClient.Apps.RegisterForAppDetails(appid, (d: any) => {
            clearTimeout(timer);
            reg?.unregister?.();
            resolve(d);
          });
        });
      }
      return {
        appid,
        name: app.display_name ?? "",
        exe: details?.strShortcutExe ?? "",
        launchOptions: details?.strShortcutLaunchOptions ?? "",
      };
    }),
  );
}

/**
 * Clear existing custom art from slots before replacing them.
 *
 * ClearCustomArtworkForApp resolves before the clear has actually happened, so
 * it needs a wait afterwards. Clearing every slot first and waiting once costs
 * one delay per game rather than one per slot — on a 200-game artwork backfill
 * that is the difference between two seconds and half a second each, which is
 * minutes over a library.
 */
export async function clearArtwork(appid: number, types: ELibraryAssetType[]) {
  if (!types.length) return;
  for (const type of types) {
    await SteamClient.Apps.ClearCustomArtworkForApp(appid, type);
  }
  await new Promise((r) => setTimeout(r, 500));
}

/** Write one artwork slot. Clearing, when needed, happens beforehand. */
export async function setArtwork(
  appid: number,
  base64Png: string,
  type: ELibraryAssetType,
) {
  await SteamClient.Apps.SetCustomArtworkForApp(appid, base64Png, "png", type);

  // A logo on a non-Steam shortcut renders blank unless a position record
  // exists, so force one if the game doesn't already have it.
  if (type === ELibraryAssetType.Logo) {
    const overview: any = window.appStore.GetAppOverviewByAppID(appid);
    if (overview?.BIsShortcut?.()) {
      const existing = await window.appDetailsStore.GetCustomLogoPosition?.(overview);
      if (!existing) {
        await window.appDetailsStore.SaveCustomLogoPosition(overview, {
          pinnedPosition: "BottomLeft",
          nWidthPct: 50,
          nHeightPct: 50,
        });
      }
    }
  }
}

/** Put appids into a named collection, creating it if needed. */
export async function addToCollection(name: string, appids: number[]) {
  if (!appids.length) return;

  const existing = collectionStore.userCollections.find(
    (c: any) => c.displayName === name,
  );
  const collection = existing ?? collectionStore.NewUnsavedCollection(name, undefined, []);

  for (const appid of appids) {
    collection.AsDragDropCollection().AddApps([{ appid }]);
  }
  await collection.Save();
}

/**
 * Delete collections we created that no longer contain anything.
 *
 * Removing a system leaves its category behind as an empty entry in the
 * library, which looks like a bug. Only empty ones are touched, and only those
 * matching a name we manage — a category the user filled themselves is never
 * at risk, because it would not be empty.
 *
 * collectionStore is untyped and its delete method has moved around, so this
 * tries the shapes that have existed and gives up quietly rather than throwing
 * mid-sync.
 */
export async function pruneEmptyCollections(names: string[]): Promise<string[]> {
  const removed: string[] = [];
  for (const name of names) {
    try {
      const collection = collectionStore.userCollections.find(
        (c: any) => c.displayName === name,
      );
      if (!collection) continue;

      const count =
        collection.visibleApps?.length ??
        collection.allApps?.length ??
        collection.apps?.size ??
        0;
      if (count > 0) continue;

      if (typeof collection.Delete === "function") {
        await collection.Delete();
      } else if (typeof collectionStore.DeleteCollection === "function") {
        await collectionStore.DeleteCollection(collection);
      } else if (typeof collectionStore.RemoveCollection === "function") {
        await collectionStore.RemoveCollection(collection);
      } else {
        continue;
      }
      removed.push(name);
    } catch {
      // A category left behind is cosmetic; failing the sync over it is not.
    }
  }
  return removed;
}
