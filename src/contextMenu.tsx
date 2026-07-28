/**
 * Adds "Manage ROM..." to a game's context menu (the gear icon).
 *
 * A modal opened from the Decky panel renders behind the quick access menu,
 * which is why the fix flow felt awkward. Routing to a real page instead puts
 * the UI where Steam expects it and matches how the SteamGridDB plugin does the
 * same job.
 *
 * This reaches deep into Steam's own React tree, so it is written defensively:
 * every step is wrapped, and a failure here must never take the plugin down —
 * worst case the menu entry is absent and the panel still works.
 */

import { isManaged } from "./managed";
import {
  afterPatch,
  fakeRenderComponent,
  findInReactTree,
  findInTree,
  findModuleByExport,
  MenuItem,
  Navigation,
  Patch,
} from "@decky/ui";

export const MANAGE_ROUTE = "/romsync-manage";
const MENU_KEY = "romsync-manage";

/**
 * The appid the menu was opened on. Handed over directly rather than through a
 * route parameter: react-router is available at runtime but not as a typed
 * dependency here, and a module variable is both simpler and one less thing to
 * break when Steam moves its router.
 */
let selected = 0;
export const getSelectedAppId = () => selected;

function insertItem(children: any[], appid: number) {
  // Only for ROMs this plugin created. Steam games and other people's
  // shortcuts get their menu left alone.
  // No logging here: this runs on every context menu open for every game in
  // the library, and the common case is correctly declining.
  if (!isManaged(appid)) return;

  // Sit just above "Properties...", the same slot Steam uses for app actions.
  const idx = children.findIndex((item) =>
    findInReactTree(
      item,
      (x: any) => x?.onSelected && x.onSelected.toString().includes("AppProperties"),
    ),
  );
  const entry = (
    <MenuItem
      key={MENU_KEY}
      onSelected={() => {
        selected = appid;
        Navigation.Navigate(MANAGE_ROUTE);
      }}
    >
      Manage ROM...
    </MenuItem>
  );
  children.splice(idx >= 0 ? idx : children.length, 0, entry);
}

/** Only the app context menu, not the screenshot or media menus. */
function isAppContextMenu(items: any[]): boolean {
  if (!items?.length) return false;
  return !!findInReactTree(
    items,
    (x: any) =>
      x?.props?.onSelected && x.props.onSelected.toString().includes("launchSource"),
  );
}

function dropDuplicate(items: any[]) {
  const i = items.findIndex((x: any) => x?.key === MENU_KEY);
  if (i !== -1) items.splice(i, 1);
}

function patchItems(menuItems: any[], appid: number) {
  let id = appid;
  // The appid handed in is sometimes cached from a previously opened menu.
  const owner = menuItems.find(
    (x: any) =>
      x?._owner?.pendingProps?.overview?.appid &&
      x._owner.pendingProps.overview.appid !== appid,
  );
  if (owner) {
    id = owner._owner.pendingProps.overview.appid;
  } else {
    const found = findInTree(menuItems, (x: any) => x?.app?.appid, {
      walkable: ["props", "children"],
    });
    if (found) id = found.app.appid;
  }
  insertItem(menuItems, id);
}

export function patchContextMenu(LibraryContextMenu: any) {
  const patches: { outer?: Patch; inner?: Patch; unpatch: () => void } = {
    unpatch: () => undefined,
  };

  patches.outer = afterPatch(
    LibraryContextMenu.prototype,
    "render",
    (_: any, component: any) => {
      let appid = 0;
      if (component._owner?.pendingProps?.overview?.appid) {
        appid = component._owner.pendingProps.overview.appid;
      } else {
        const found = findInTree(component.props.children, (x: any) => x?.app?.appid, {
          walkable: ["props", "children"],
        });
        if (found) appid = found.app.appid;
      }

      if (!patches.inner) {
        patches.inner = afterPatch(component, "type", (_a: any, ret: any) => {
          afterPatch(ret.type.prototype, "render", (_b: any, ret2: any) => {
            const items = ret2.props.children[0];
            if (!isAppContextMenu(items)) return ret2;
            try {
              dropDuplicate(items);
              patchItems(items, appid);
            } catch {
              /* leave the menu untouched rather than break it */
            }
            return ret2;
          });

          afterPatch(
            ret.type.prototype,
            "shouldComponentUpdate",
            ([nextProps]: any, shouldUpdate: any) => {
              try {
                dropDuplicate(nextProps.children);
                if (shouldUpdate === true) patchItems(nextProps.children, appid);
              } catch {
                return shouldUpdate;
              }
              return shouldUpdate;
            },
          );
          return ret;
        });
      } else {
        try {
          insertItem(component.props.children, appid);
        } catch {
          /* ignore */
        }
      }
      return component;
    },
  );

  patches.unpatch = () => {
    patches.outer?.unpatch();
    patches.inner?.unpatch();
  };
  return patches;
}

/**
 * Steam's game context menu component.
 *
 * The module export is a function component that *returns* the menu; the class
 * whose prototype we patch only exists once it has been rendered. Skipping
 * fakeRenderComponent hands back something with no `prototype.render`, so the
 * patch attaches to nothing and the entry never appears — which is exactly what
 * happened the first time round.
 */
export function findLibraryContextMenu(): any {
  const mod = findModuleByExport(
    (e: any) => e?.toString && e.toString().includes("().LibraryContextMenu"),
  );
  if (!mod) {
    console.warn("[ROM Sync] LibraryContextMenu module not found");
    return null;
  }
  const sibling = Object.values(mod).find(
    (x: any) => x?.toString && x.toString().includes("navigator:"),
  );
  if (!sibling) {
    console.warn("[ROM Sync] LibraryContextMenu sibling not found");
    return null;
  }
  try {
    const rendered = fakeRenderComponent(sibling as any);
    const type = rendered?.type;
    if (!type?.prototype?.render) {
      console.warn("[ROM Sync] LibraryContextMenu has no prototype.render", type);
      return null;
    }
    return type;
  } catch (e) {
    console.warn("[ROM Sync] couldn't render LibraryContextMenu", e);
    return null;
  }
}
