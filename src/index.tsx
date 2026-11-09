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
  setLanguage,
  setSettings,
  withTimeout,
} from "./api";
import { findLibraryContextMenu, MANAGE_ROUTE, patchContextMenu } from "./contextMenu";
import { Progress, ui, wrapText } from "./PageShell";
import { ManageRom } from "./ManageRom";
import { refreshManaged } from "./managed";
import { Settings, SETTINGS_ROUTE } from "./Settings";
import { cancel, dismissSummary, runSync, SyncOptions, useSyncState } from "./syncStore";
import { lang, t, tp } from "./i18n";

function RomSync() {
  const sync = useSyncState();
  const [settings, setLocal] = useState<any>(null);
  const [installing, setInstalling] = useState("");
  const [loadError, setLoadError] = useState("");
  const [setupStatus, setSetupStatus] = useState("");

  const load = () => {
    setLoadError("");
    withTimeout(getSettings(), 30000, t("common.loadingSettings"))
      .then(setLocal)
      .catch((e) => setLoadError(String(e?.message ?? e)));
  };

  useEffect(load, []);

  const pending = [
    settings?.pending_add ? t("panel.pendingAdd", { count: settings.pending_add }) : "",
    settings?.pending_update
      ? t("panel.pendingUpdate", { count: settings.pending_update })
      : "",
    settings?.pending_remove
      ? t("panel.pendingRemove", { count: settings.pending_remove })
      : "",
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
          strTitle={tp("panel.removeShortcutsTitle", removals.length)}
          strDescription={
            names.join("\n") +
            (more > 0 ? `\n${t("panel.removeMore", { count: more })}` : "") +
            `\n\n${t("panel.removeWarning")}`
          }
          strOKButtonText={t("common.removeThem")}
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
      <PanelSection title={t("common.library")}>
        {loadError && (
          <>
            <PanelSectionRow>
              <div style={{ fontSize: "0.8em" }}>
                {t("panel.backendError", { error: loadError })}
              </div>
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem layout="below" onClick={load}>
                {t("common.retry")}
              </ButtonItem>
            </PanelSectionRow>
          </>
        )}

        {settings?.roots?.length === 0 && (
          <>
            <PanelSectionRow>
              <div style={{ fontSize: "0.8em" }}>{t("panel.noLibrary")}</div>
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
                      setSetupStatus(t("panel.creating"));
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
                setSetupStatus(t("panel.downloadingCores"));
                const r = await installCores(settings.missing_cores);
                setSetupStatus(r.message);
                load();
              }}
            >
              {tp("panel.installMissingCores", settings.missing_cores.length)}
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
                setInstalling(t("panel.installingRetroArch"));
                const r = await installRetroArch();
                setInstalling("");
                load();
                if (!r.ok) setInstalling(r.message);
              }}
            >
              {installing || t("panel.installRetroArch")}
            </ButtonItem>
          </PanelSectionRow>
        )}

        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={sync.busy}
            onClick={() => startSync()}
          >
            {sync.busy ? t("common.working") : t("common.sync")}
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
                {t("common.stop")}
              </ButtonItem>
            </PanelSectionRow>
          </>
        )}

        {sync.phase === "error" && (
          <PanelSectionRow>
            <div style={{ fontSize: "0.8em" }}>
              {t("panel.syncStopped", { status: sync.status })}
            </div>
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
                  {t("common.dismiss")}
                </DialogButton>
              </Focusable>
            </PanelSectionRow>
          </>
        )}

      </PanelSection>

      <PanelSection title={t("panel.systems")}>
        {settings?.systems?.length === 0 && (
          <PanelSectionRow>
            <div style={{ fontSize: "0.8em" }}>
              {settings?.empty_folders?.length
                ? t("panel.waitingForRoms", {
                    folders: settings.empty_folders.join(", "),
                  })
                : t("panel.noSystems")}
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
              {t("panel.notRecognised", {
                folders: settings.unknown_folders.join(", "),
              })}
            </div>
          </PanelSectionRow>
        )}
        {settings?.systems?.length > 0 && settings?.empty_folders?.length > 0 && (
          <PanelSectionRow>
            <div style={{ fontSize: "0.72em", opacity: 0.65, ...wrapText }}>
              {t("panel.emptyNotListed", {
                folders: settings.empty_folders.join(", "),
              })}
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
  // The Python backend formats the messages it returns, so it needs the same
  // language as this UI. A failure here only leaves those messages in English.
  setLanguage(lang).catch(() => undefined);

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
