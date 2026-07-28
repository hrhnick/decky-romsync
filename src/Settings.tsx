import {
  ConfirmModal,
  DialogButton,
  Focusable,
  Dropdown,
  Navigation,
  SidebarNavigation,
  TextField,
  ToggleField,
  showModal,
} from "@decky/ui";
import { useEffect, useState } from "react";
import {
  getSettings,
  installCores,
  setCore,
  installRetroArch,
  purgeArtCache,
  redetectLibrary,
  reimportKey,
  setLibraryPath,
  setSettings,
  testKey,
  withTimeout,
} from "./api";
import { ActionRow, compactButton, PageBody, PageShell, Row, wrapText } from "./PageShell";
import { runReset, useSyncState } from "./syncStore";

export const SETTINGS_ROUTE = "/romsync-settings";

/**
 * Reached from the cog in the panel title. Setup and destructive actions live
 * here rather than in the panel: they are touched once, and keeping them out of
 * the main view leaves Sync as the obvious thing to press. A route rather than
 * a modal because a modal raised from the panel renders behind the quick access
 * menu.
 */
export function Settings() {
  const sync = useSyncState();
  const [settings, setLocal] = useState<any>(null);
  const [key, setKey] = useState("");
  const [keyStatus, setKeyStatus] = useState("");
  const [libPath, setLibPath] = useState("");
  const [libStatus, setLibStatus] = useState("");
  const [loadError, setLoadError] = useState("");
  const [coreStatus, setCoreStatus] = useState("");
  const [coreBusy, setCoreBusy] = useState(false);
  const [showCommands, setShowCommands] = useState(false);

  const load = () => {
    setLoadError("");
    withTimeout(getSettings(), 30000, "Loading settings")
      .then((s) => {
        setLocal(s);
        setKey(s.sgdb_key ?? "");
        setLibPath(s.library_paths?.[0] ?? "");
      })
      .catch((e) => setLoadError(String(e?.message ?? e)));
  };

  useEffect(load, []);

  const confirmReset = () =>
    showModal(
      <ConfirmModal
        strTitle="Remove all synced games?"
        strDescription={
          "This removes every shortcut ROM Sync created. Shortcuts it adopted " +
          "from another tool are left in place and simply forgotten. Your ROMs, " +
          "collections and .romsync.txt files are not touched."
        }
        strOKButtonText="Remove them"
        onOK={() => {
          runReset();
          Navigation.NavigateBack();
        }}
      />,
      window,
    );

  // SidebarNavigation rather than a hand-rolled scroll container: it is
  // Steam's own settings component, so gamepad navigation and scrolling are
  // its problem rather than something to reimplement. It also suits a settings
  // screen better than one long column.
  return (
    <PageShell>
      <SidebarNavigation
        title="ROM Sync"
        showTitle
        pages={[
          {
            title: "Library",
            content: (
              <PageBody>
                {settings?.roots?.length === 0 && (
                  <Row>
                    <div style={{ fontSize: "0.8em" }}>
                      No Emulation folder found. Enter the path below, or press
                      Re-detect after plugging in your card.
                    </div>
                  </Row>
                )}
                {settings?.roots?.length > 0 && (
                  <Row>
                    <div style={{ fontSize: "0.72em", opacity: 0.65, ...wrapText }}>
                      Scanning: {settings.roots.join(", ")}
                    </div>
                  </Row>
                )}
                <Row>
                  <Focusable>
                    <TextField
                      label="Path"
                      description="Your Emulation folder, or the roms folder inside it."
                      value={libPath}
                      onChange={(e) => setLibPath(e.target.value)}
                    />
                  </Focusable>
                </Row>
                <Row>
                  <ActionRow>
                      <DialogButton
                        style={compactButton}
                        disabled={sync.busy}
                        onClick={async () => {
                          setLibStatus("Checking…");
                          const r = await setLibraryPath(libPath);
                          setLibStatus(r.message);
                          if (r.ok) load();
                        }}
                      >
                        Use this folder
                      </DialogButton>
                      <DialogButton
                        style={compactButton}
                        disabled={sync.busy}
                        onClick={async () => {
                          setLibStatus("Scanning…");
                          const r = await redetectLibrary();
                          setLibStatus(r.message);
                          load();
                        }}
                      >
                        Re-detect
                      </DialogButton>
                  </ActionRow>
                </Row>
                {libStatus && (
                  <Row>
                    <div style={{ fontSize: "0.8em", ...wrapText }}>{libStatus}</div>
                  </Row>
                )}
                {settings?.library_file && (
                  <Row>
                    <div style={{ fontSize: "0.72em", opacity: 0.65, ...wrapText }}>
                      Saved in {settings.library_file} — editable by hand.
                    </div>
                  </Row>
                )}
              </PageBody>
            ),
          },
          {
            title: "SteamGridDB",
            content: (
              <PageBody>
                <Row>
                  <Focusable>
                    <TextField
                      label="API key"
                      value={key}
                      bIsPassword
                      onChange={(e) => setKey(e.target.value)}
                      onBlur={() => setSettings({ sgdb_key: key })}
                    />
                  </Focusable>
                </Row>
                <Row>
                  <ActionRow>
                      <DialogButton
                        style={compactButton}
                        disabled={sync.busy}
                        onClick={async () => {
                          await setSettings({ sgdb_key: key });
                          setKeyStatus("Testing…");
                          const r = await testKey();
                          setKeyStatus(r.message);
                          load();
                        }}
                      >
                        Save &amp; test
                      </DialogButton>
                      <DialogButton
                        style={compactButton}
                        disabled={sync.busy}
                        onClick={async () => {
                          setKeyStatus("Looking for a key file…");
                          const r = await reimportKey();
                          setKeyStatus(r.message);
                          load();
                        }}
                      >
                        Import file
                      </DialogButton>
                      <DialogButton
                        style={compactButton}
                        disabled={sync.busy}
                        onClick={async () => {
                          setKeyStatus("Clearing…");
                          const r = await purgeArtCache();
                          setKeyStatus(
                            `Cleared ${r.removed} cached files. The next sync re-downloads ` +
                              "artwork for games that are missing it.",
                          );
                        }}
                      >
                        Clear cache
                      </DialogButton>
                  </ActionRow>
                </Row>
                {keyStatus && (
                  <Row>
                    <div style={{ fontSize: "0.8em", ...wrapText }}>{keyStatus}</div>
                  </Row>
                )}
                <Row>
                  <div style={{ fontSize: "0.72em", opacity: 0.65 }}>
                    Import file picks up a key saved next to your library — any of
                    steamgriddb_key.txt, .steamgriddb_key or .steamgriddb_key.txt.
                    Clear cache first if you want fresh images from SteamGridDB.
                    Artwork you place in a system's media folder always overrides both.
                  </div>
                </Row>
                {settings?.imported_from && (
                  <Row>
                    <div style={{ fontSize: "0.72em", opacity: 0.65 }}>
                      Imported your key from {settings.imported_from}. That file is left
                      in place so other devices sharing this library can use it too.
                    </div>
                  </Row>
                )}
                <Row>
                  <div style={{ fontSize: "0.72em", opacity: 0.65 }}>
                    {settings?.key_file_path
                      ? `Stored in ${settings.key_file_path}`
                      : `Saved to ${settings?.key_save_target ?? "the config folder"}.`}
                    {" Artwork next to a ROM in a media folder always wins over SteamGridDB."}
                  </div>
                </Row>
              </PageBody>
            ),
          },
          {
            title: "Emulators",
            content: (
              <PageBody>
                <Row>
                  <div style={{ fontSize: "0.8em", ...wrapText }}>
                    {settings?.retroarch_installed
                      ? `RetroArch installed · ${settings?.cores?.length ?? 0} cores available`
                      : "RetroArch is not installed."}
                  </div>
                </Row>

                {settings && !settings.retroarch_installed && (
                  <Row>
                    <ActionRow>
                      <DialogButton
                        style={compactButton}
                        disabled={coreBusy}
                        onClick={async () => {
                          setCoreBusy(true);
                          setCoreStatus("Installing RetroArch…");
                          const r = await installRetroArch();
                          setCoreStatus(r.message);
                          setCoreBusy(false);
                          load();
                        }}
                      >
                        Install RetroArch
                      </DialogButton>
                    </ActionRow>
                  </Row>
                )}

                {/* One line per system: what it launches with, and whether
                    that is actually present. This is the question people
                    actually have — "will my SNES games run?" — and it was
                    previously only answerable by reading a truncated note in
                    the panel. */}
                <Row>
                  <ToggleField
                    label="Show launch commands"
                    description="What each system runs, and which file it lives in."
                    checked={showCommands}
                    onChange={setShowCommands}
                  />
                </Row>

                {/* One row per system. A RetroArch system gets a picker; a
                    system pointed at anything else gets read-only text,
                    because there is no core to swap and the picker must never
                    overwrite a hand-written command. */}
                {(settings?.systems ?? []).map((sys: any) => {
                  const options: any[] = sys.core_options ?? [];
                  return (
                    <Row key={sys.key}>
                      <Focusable
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "12px",
                          width: "100%",
                          minWidth: 0,
                        }}
                      >
                        <div
                          style={{
                            flex: "1 1 0",
                            minWidth: 0,
                            fontSize: "0.8em",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                            opacity: sys.missing_core ? 0.9 : 1,
                          }}
                          title={sys.label}
                        >
                          {sys.label}
                        </div>

                        {/* Every row gets the same control, so a system with
                            one core doesn't sit in a differently shaped box
                            next to one with four. Re-picking the current core
                            is already a no-op, so a single-option picker is
                            harmless. A system running something other than
                            RetroArch has no core to pick at all, so its box is
                            inert — the same shape, honest about the
                            difference, and it can't write a flatpak id into a
                            -L argument. */}
                        <div style={{ flex: "0 0 230px", minWidth: 0 }}>
                          <Dropdown
                            disabled={coreBusy || sync.busy || options.length === 0}
                            selectedOption={options.length ? sys.emulator : "custom"}
                            rgOptions={
                              options.length
                                ? options.map((o) => ({
                                    data: o.core,
                                    label: o.installed
                                      ? o.core
                                      : `${o.core} · not installed`,
                                  }))
                                : [{
                                    data: "custom",
                                    label: sys.emulator || "no command set",
                                  }]
                            }
                            onChange={async (opt) => {
                              if (!options.length) return;
                              setCoreBusy(true);
                              const r = await setCore(sys.folder, opt.data);
                              setCoreStatus(r.message);
                              setCoreBusy(false);
                              load();
                            }}
                          />
                        </div>
                      </Focusable>

                      {/* Read-only, and off by default: the page stays clean
                          for everyone else, and one toggle beats an expander
                          per row that would triple the focus stops on this
                          page for something read once a year. */}
                      {showCommands && (
                        <div style={{ marginTop: "4px", paddingLeft: "2px" }}>
                          <div
                            style={{
                              fontSize: "0.68em",
                              opacity: 0.55,
                              lineHeight: 1.5,
                              ...wrapText,
                            }}
                          >
                            {sys.command || "no command set"}
                          </div>
                          <div
                            style={{
                              fontSize: "0.68em",
                              opacity: 0.35,
                              marginTop: "2px",
                              ...wrapText,
                            }}
                          >
                            {sys.config_file}
                          </div>
                        </div>
                      )}
                    </Row>
                  );
                })}

                {settings?.systems?.length === 0 && (
                  <Row>
                    <div style={{ fontSize: "0.8em", opacity: 0.65 }}>
                      No systems with games yet.
                    </div>
                  </Row>
                )}

                {coreStatus && (
                  <Row>
                    <div style={{ fontSize: "0.8em", ...wrapText }}>{coreStatus}</div>
                  </Row>
                )}

                {settings?.missing_cores?.length > 0 && (
                  <Row>
                    <ActionRow>
                      <DialogButton
                        style={compactButton}
                        disabled={coreBusy || sync.busy}
                        onClick={async () => {
                          setCoreBusy(true);
                          setCoreStatus("Downloading cores…");
                          const r = await installCores(settings.missing_cores);
                          setCoreStatus(r.message);
                          setCoreBusy(false);
                          load();
                        }}
                      >
                        {`Install ${settings.missing_cores.length} missing core${
                          settings.missing_cores.length === 1 ? "" : "s"
                        }`}
                      </DialogButton>
                    </ActionRow>
                  </Row>
                )}

                <Row>
                  <div style={{ fontSize: "0.72em", opacity: 0.65, ...wrapText }}>
                    Changing a core here rewrites one argument in that
                    system's .romsync.txt and leaves the rest of the command,
                    and any comments, exactly as written. Games pick it up on
                    the next sync.
                  </div>
                </Row>
              </PageBody>
            ),
          },
          {
            title: "Danger zone",
            content: (
              <PageBody>
                <Row>
                  <ActionRow>
                    <DialogButton
                      style={compactButton}
                      disabled={sync.busy}
                      onClick={confirmReset}
                    >
                      Remove all synced games
                    </DialogButton>
                  </ActionRow>
                </Row>
              </PageBody>
            ),
          },
        ]}
      />
    </PageShell>
  );
}
