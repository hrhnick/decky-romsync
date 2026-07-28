import {
  ButtonItem,
  ConfirmModal,
  DialogButton,
  Focusable,
  Navigation,
  PanelSection,
  PanelSectionRow,
  Toggle,
  showModal,
  staticClasses,
} from "@decky/ui";
import { definePlugin, routerHook } from "@decky/api";
import { useEffect, useState } from "react";
import { FaCog, FaGamepad } from "react-icons/fa";
import {
  createLibrary,
  getSettings,
  installCores,
  installRetroArch,
  setSettings,
  withTimeout,
} from "./api";
import { findLibraryContextMenu, MANAGE_ROUTE, patchContextMenu } from "./contextMenu";
import { Progress, ui, wrapText } from "./PageShell";
import { ManageRom } from "./ManageRom";
import { refreshManaged } from "./managed";
import { Settings, SETTINGS_ROUTE } from "./Settings";
import { cancel, dismissSummary, runSync, SyncOptions, useSyncState } from "./syncStore";

function RomSync() {
  const sync = useSyncState();
  const [settings, setLocal] = useState<any>(null);
  const [installing, setInstalling] = useState("");
  const [loadError, setLoadError] = useState("");
  const [setupStatus, setSetupStatus] = useState("");

  const load = () => {
    setLoadError("");
    withTimeout(getSettings(), 30000, "Loading settings")
      .then(setLocal)
      .catch((e) => setLoadError(String(e?.message ?? e)));
  };

  useEffect(load, []);

  const pending = [
    settings?.pending_add ? `${settings.pending_add} to add` : "",
    settings?.pending_update ? `${settings.pending_update} to update` : "",
    settings?.pending_remove ? `${settings.pending_remove} to remove` : "",
  ]
    .filter(Boolean)
    .join(", ");

  // Removals are the only destructive step, and now that switching a system
  // off deletes shortcuts they're easy to trigger by accident. Nothing is
  // removed without showing exactly what and why first.
  const confirmRemovals = (removals: any[]) =>
    new Promise<boolean>((resolve) => {
      const names = removals.slice(0, 8).map((r) => `${r.title} — ${r.why}`);
      const more = removals.length - names.length;
      showModal(
        <ConfirmModal
          strTitle={`Remove ${removals.length} shortcut${
            removals.length === 1 ? "" : "s"
          }?`}
          strDescription={
            names.join("\n") +
            (more > 0 ? `\n…and ${more} more.` : "") +
            "\n\nSteam playtime for these is lost and cannot be restored."
          }
          strOKButtonText="Remove them"
          onOK={() => resolve(true)}
          onCancel={() => resolve(false)}
          closeModal={() => resolve(false)}
        />,
        window,
      );
    });

  const startSync = (options: SyncOptions = {}) =>
    runSync({ confirmRemovals, ...options });

  return (
    <>
      <PanelSection title="Library">
        {loadError && (
          <>
            <PanelSectionRow>
              <div style={{ fontSize: "0.8em" }}>
                Can't reach the plugin backend: {loadError}. Check every file
                was copied, then restart plugin_loader.
              </div>
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem layout="below" onClick={load}>
                Retry
              </ButtonItem>
            </PanelSectionRow>
          </>
        )}

        {settings?.roots?.length === 0 && (
          <>
            <PanelSectionRow>
              <div style={{ fontSize: "0.8em" }}>
                No ROM library yet. Create one below, or set an existing path
                from the cog above.
              </div>
            </PanelSectionRow>
            <PanelSectionRow>
              <Focusable
                style={{ display: "flex", gap: "8px", width: "100%", minWidth: 0 }}
              >
                {(settings.library_bases ?? []).map((b: any) => (
                  <DialogButton
                    key={b.path}
                    style={{
                      flex: "1 1 0",
                      minWidth: 0,
                      height: "36px",
                      padding: "0 8px",
                      fontSize: "0.8em",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    disabled={sync.busy || !!setupStatus}
                    onClick={async () => {
                      setSetupStatus("Creating…");
                      const r = await createLibrary(b.path);
                      setSetupStatus(r.message);
                      load();
                    }}
                  >
                    {b.label}
                  </DialogButton>
                ))}
              </Focusable>
            </PanelSectionRow>
          </>
        )}

        {settings?.missing_cores?.length > 0 && (
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={sync.busy || !!setupStatus}
              onClick={async () => {
                setSetupStatus("Downloading cores…");
                const r = await installCores(settings.missing_cores);
                setSetupStatus(r.message);
                load();
              }}
            >
              {`Install ${settings.missing_cores.length} missing core${
                settings.missing_cores.length === 1 ? "" : "s"
              }`}
            </ButtonItem>
          </PanelSectionRow>
        )}

        {setupStatus && (
          <PanelSectionRow>
            <div style={{ fontSize: "0.8em", ...wrapText }}>{setupStatus}</div>
          </PanelSectionRow>
        )}

        {settings && !settings.retroarch_installed && (
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={sync.busy || !!installing}
              onClick={async () => {
                setInstalling("Installing RetroArch");
                const r = await installRetroArch();
                setInstalling("");
                load();
                if (!r.ok) setInstalling(r.message);
              }}
            >
              {installing || "Install RetroArch"}
            </ButtonItem>
          </PanelSectionRow>
        )}

        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={sync.busy}
            onClick={() => startSync()}
          >
            {sync.busy ? "Working…" : "Sync"}
          </ButtonItem>
        </PanelSectionRow>

        {/* Toggling a system does nothing until the next sync, which is
            consistent with every other setting here — and means a mis-tap
            costs nothing, since removal destroys Steam playtime. That only
            works if what is queued is visible somewhere. */}
        {!sync.busy && pending && (
          <PanelSectionRow>
            <div style={{ ...ui.small, opacity: ui.dim, ...wrapText }}>
              {pending}
            </div>
          </PanelSectionRow>
        )}

        {sync.busy && (
          <>
            <PanelSectionRow>
              <Progress progress={sync.progress} status={sync.status} />
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem layout="below" onClick={cancel}>
                Stop
              </ButtonItem>
            </PanelSectionRow>
          </>
        )}

        {sync.phase === "error" && (
          <PanelSectionRow>
            <div style={{ fontSize: "0.8em" }}>Sync stopped: {sync.status}</div>
          </PanelSectionRow>
        )}

        {sync.phase === "done" && (
          <>
            {sync.summary.map((line, i) => (
              <PanelSectionRow key={i}>
                <div style={{ fontSize: "0.8em", ...wrapText }}>{line}</div>
              </PanelSectionRow>
            ))}
            <PanelSectionRow>
              <Focusable style={{ display: "flex", justifyContent: "flex-end" }}>
                <DialogButton
                  style={{
                    width: "90px",
                    minWidth: 0,
                    height: "30px",
                    padding: 0,
                    fontSize: "0.8em",
                  }}
                  onClick={dismissSummary}
                >
                  Dismiss
                </DialogButton>
              </Focusable>
            </PanelSectionRow>
          </>
        )}

      </PanelSection>

      <PanelSection title="Systems">
        {settings?.systems?.length === 0 && (
          <PanelSectionRow>
            <div style={{ fontSize: "0.8em" }}>
              {settings?.empty_folders?.length
                ? `Waiting for ROMs in ${settings.empty_folders.join(", ")}.`
                : "No system folders found yet. Add folders like n64 or snes inside your roms folder."}
            </div>
          </PanelSectionRow>
        )}
        {settings?.systems?.map((s: any) => {
          const disabled: string[] = settings.disabled_systems ?? [];
          const enabled = !disabled.includes(s.key);

          // Name, count, toggle. The per-system sync button that used to live
          // here was the rarest action in the panel holding the most visually
          // prominent spot, and it appeared and disappeared with the toggle,
          // so rows changed shape as you used them. A core that is missing is
          // no longer explained here either — the Install button above is the
          // actionable version of the same fact.
          return (
            <PanelSectionRow key={s.key}>
              <Focusable
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  width: "100%",
                  maxWidth: "100%",
                  minWidth: 0,
                  overflow: "hidden",
                  boxSizing: "border-box",
                  padding: "2px 0",
                }}
              >
                <div
                  style={{
                    flex: "1 1 0",
                    minWidth: 0,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    opacity: s.missing_core || !s.has_command ? 0.45 : 1,
                  }}
                  title={s.label}
                >
                  {s.label}
                </div>
                <div
                  style={{
                    ...ui.small,
                    opacity: ui.faint,
                    flex: "0 0 auto",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {s.games}
                </div>
                <Toggle
                  value={enabled}
                  disabled={sync.busy}
                  onChange={async (on) => {
                    const next = on
                      ? disabled.filter((k: string) => k !== s.key)
                      : [...new Set([...disabled, s.key])];
                    const saved = await setSettings({ disabled_systems: next });
                    setLocal({
                      ...settings,
                      disabled_systems: saved.disabled_systems,
                    });
                    // Refresh the pending counts so the Sync button reflects
                    // the change straight away.
                    load();
                  }}
                />
              </Focusable>
            </PanelSectionRow>
          );
        })}

        {settings?.unknown_folders?.length > 0 && (
          <PanelSectionRow>
            <div style={{ fontSize: "0.72em", opacity: 0.65, ...wrapText }}>
              Not recognised: {settings.unknown_folders.join(", ")}. Add a
              .romsync.txt in each with a system and command line.
            </div>
          </PanelSectionRow>
        )}
        {settings?.systems?.length > 0 && settings?.empty_folders?.length > 0 && (
          <PanelSectionRow>
            <div style={{ fontSize: "0.72em", opacity: 0.65, ...wrapText }}>
              Empty, so not listed: {settings.empty_folders.join(", ")}
            </div>
          </PanelSectionRow>
        )}
      </PanelSection>
    </>
  );
}

/** Panel title with a settings cog, the pattern other Decky plugins use. */
function TitleView() {
  return (
    <div
      className={staticClasses.Title}
      style={{ display: "flex", alignItems: "center", width: "100%" }}
    >
      <div style={{ flex: "1 1 auto" }}>ROM Sync</div>
      <DialogButton
        style={{
          height: "30px",
          width: "40px",
          minWidth: 0,
          padding: "10px 12px",
          flex: "0 0 auto",
          marginLeft: "auto",
        }}
        onClick={() => {
          Navigation.CloseSideMenus();
          Navigation.Navigate(SETTINGS_ROUTE);
        }}
      >
        <FaCog style={{ marginTop: "-4px", display: "block" }} />
      </DialogButton>
    </div>
  );
}

export default definePlugin(() => {
  // A failure patching Steam's own React tree must not take the plugin with
  // it — the menu entry is a convenience, the panel is the product.
  let menuPatch: { unpatch: () => void } | null = null;
  try {
    const LibraryContextMenu = findLibraryContextMenu();
    if (LibraryContextMenu) menuPatch = patchContextMenu(LibraryContextMenu);
  } catch (e) {
    console.error("[ROM Sync] context menu patch failed", e);
  }

  routerHook.addRoute(MANAGE_ROUTE, ManageRom, { exact: true });
  routerHook.addRoute(SETTINGS_ROUTE, Settings, { exact: true });

  // Populate the managed-appid set so the menu entry can filter synchronously.
  refreshManaged();

  return {
    name: "ROM Sync",
    titleView: <TitleView />,
    content: <RomSync />,
    icon: <FaGamepad />,
    onDismount() {
      menuPatch?.unpatch();
      routerHook.removeRoute(MANAGE_ROUTE);
      routerHook.removeRoute(SETTINGS_ROUTE);
    },
  };
});
