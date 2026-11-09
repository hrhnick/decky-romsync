import {
  DialogButton,
  Focusable,
  SidebarNavigation,
  TextField,
  ToggleField,
} from "@decky/ui";
import { useEffect, useState } from "react";
import {
  artPreview,
  Candidate,
  Game,
  getArt,
  getOverride,
  listGames,
  Override,
  searchSgdb,
  setOverride,
  withTimeout,
} from "./api";
import { getSelectedAppId } from "./contextMenu";
import {
  ActionRow,
  compactButton,
  PageBody,
  PageShell,
  Progress,
  Row,
  ui,
  wrapText,
} from "./PageShell";
import { AssetType, clearArtwork, setArtwork, setShortcutIcon } from "./steam";
import { runSync, useSyncState } from "./syncStore";
import { t } from "./i18n";

/** Label above a read-only value. */
function Fact({ label, value }: { label: string; value: string }) {
  return (
    <Row>
      <div style={{ ...ui.small, opacity: ui.faint, marginBottom: "2px" }}>
        {label}
      </div>
      <div style={{ ...ui.text, ...wrapText }}>{value || "—"}</div>
    </Row>
  );
}

/**
 * Status line and Save, shown on every pane that can change something.
 *
 * Module scope, not defined inside ManageRom: a component declared in a render
 * gets a new function identity each time, so React sees a different type,
 * unmounts the subtree and remounts it. On a gamepad UI that drops focus —
 * every keystroke in a field above would knock the selection off.
 */
function Footer({
  busy,
  progress,
  status,
  disabled,
  onSave,
  label = t("common.save"),
}: {
  busy: boolean;
  progress: number;
  status: string;
  disabled: boolean;
  onSave: () => void;
  label?: string;
}) {
  return (
    <>
      {busy ? (
        <Row>
          <Progress progress={progress} status={status} />
        </Row>
      ) : (
        status && (
          <Row>
            <div style={{ ...ui.text, ...wrapText }}>{status}</div>
          </Row>
        )
      )}
      <Row>
        <ActionRow>
          <DialogButton style={compactButton} disabled={disabled} onClick={onSave}>
            {label}
          </DialogButton>
        </ActionRow>
      </Row>
    </>
  );
}

/**
 * Reached from the game's gear menu via "Manage ROM...". A full route rather
 * than a modal: a modal raised from the Decky panel renders behind the quick
 * access menu, which made this flow unusable.
 *
 * Three panes, mirroring Settings. About is read-only and answers "why won't
 * this launch". Artwork is the common task. Exclusion sits behind its own pane
 * so it cannot be caught by a stray press while adjusting a cover — it is the
 * one action here the plugin cannot walk back.
 */
export function ManageRom() {
  const id = getSelectedAppId();
  const sync = useSyncState();
  const [game, setGame] = useState<Game | null>(null);
  const [ov, setOv] = useState<Override | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [idText, setIdText] = useState("");
  const [title, setTitle] = useState("");
  const [exclude, setExclude] = useState(false);
  const [wasExcluded, setWasExcluded] = useState(false);
  const [status, setStatus] = useState(t("manage.loading"));
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [searching, setSearching] = useState(true);
  const [preview, setPreview] = useState("");

  useEffect(() => {
    listGames()
      .then(async (games) => {
        const match = games.find((g) => g.appid === id) ?? null;
        setGame(match);
        if (!match) {
          setStatus(t("manage.notManaged"));
          setSearching(false);
          return;
        }
        setStatus("");
        const o = await getOverride(match.system_dir, match.filename);
        setOv(o);
        setIdText(o.sgdb_id ? String(o.sgdb_id) : "");
        setTitle(o.title ?? "");
        setExclude(o.exclude);
        setWasExcluded(o.exclude);
        setSearching(true);
        searchSgdb(match.title)
          .then(setCandidates)
          .catch(() => setCandidates([]))
          .finally(() => setSearching(false));
      })
      .catch((e) => {
        setStatus(String(e?.message ?? e));
        setSearching(false);
      });
  }, [id]);

  // Seeing the cover is the fastest way to tell a right match from a wrong
  // one — far quicker than reading names that differ by a subtitle.
  useEffect(() => {
    const parsed = Number(idText.trim());
    if (!idText.trim() || Number.isNaN(parsed)) {
      setPreview("");
      return;
    }
    let live = true;
    artPreview(parsed)
      .then((r) => live && setPreview(r.image))
      .catch(() => live && setPreview(""));
    return () => {
      live = false;
    };
  }, [idText]);

  const save = async (reapply = true) => {
    if (!game || busy) return;
    const parsed = idText.trim() ? Number(idText.trim()) : 0;
    if (idText.trim() && Number.isNaN(parsed)) {
      setStatus(t("manage.idMustBeNumber"));
      return;
    }
    setBusy(true);
    setProgress(5);
    setStatus(t("manage.saving"));
    const res = await setOverride(
      game.system_dir,
      game.filename,
      parsed,
      title.trim(),
      exclude,
    );
    if (!res.ok) {
      setStatus(res.message ?? t("manage.overrideWriteError"));
      setBusy(false);
      return;
    }
    setProgress(20);
    setWasExcluded(exclude);

    // Artwork is pointless on a game that is about to be removed.
    if (reapply && !exclude && game.appid) {
      setStatus(t("manage.lookingUpArt"));
      try {
        const { art, icon_path, warning } = await withTimeout(
          getArt(game.rom_path, title.trim() || game.title, game.system_key, parsed || null),
          60000,
          t("sync.artLabel"),
        );
        const slots: [string, AssetType, string][] = [
          ["grid", AssetType.Capsule, t("manage.slotCapsule")],
          ["hero", AssetType.Hero, t("manage.slotHero")],
          ["logo", AssetType.Logo, t("manage.slotLogo")],
          ["wide", AssetType.Header, t("manage.slotHeader")],
        ];
        const filling = slots.filter(([name]) => art[name]);
        setStatus(t("manage.clearingOldArt"));
        await clearArtwork(game.appid, filling.map(([, type]) => type));

        const steps = filling.length + (icon_path ? 1 : 0) || 1;
        let done = 0;
        for (const [name, type, label] of filling) {
          setStatus(t("manage.applying", { label }));
          await setArtwork(game.appid, art[name], type);
          setProgress(20 + (++done / steps) * 80);
        }
        if (icon_path) {
          setStatus(t("manage.applyingIcon"));
          await setShortcutIcon(game.appid, icon_path);
          setProgress(20 + (++done / steps) * 80);
        }
        if (warning) {
          setStatus(warning);
          setBusy(false);
          return;
        }
      } catch (e: any) {
        setStatus(String(e?.message ?? e));
        setBusy(false);
        return;
      }
    }
    setProgress(100);
    setStatus(t("manage.saved"));
    setBusy(false);
  };

  return (
    <PageShell>
      <SidebarNavigation
        title={game ? game.title : t("manage.manageRom")}
        showTitle
        pages={[
          {
            title: t("manage.about"),
            content: (
              <PageBody>
                <Fact label={t("manage.system")} value={game?.system_label ?? ""} />
                <Fact label={t("manage.emulator")} value={game?.emulator ?? ""} />
                <Fact label={t("manage.romFile")} value={game?.rom_path ?? ""} />
                <Fact
                  label={t("manage.launchesWith")}
                  value={
                    game ? `${game.exe ?? ""} ${game.launch_options ?? ""}`.trim() : ""
                  }
                />
                <Row>
                  <div style={{ ...ui.small, opacity: ui.dim, ...wrapText }}>
                    {t("manage.mediaNote", {
                      grid: game?.system_dir
                        ? `${game.system_dir}/media/grid/`
                        : t("manage.mediaFolderDefault"),
                      path: ov?.path ?? t("manage.romsyncDefault"),
                    })}
                  </div>
                </Row>
              </PageBody>
            ),
          },
          {
            title: t("manage.artwork"),
            content: (
              <PageBody>
                {searching && (
                  <Row>
                    <div style={{ ...ui.text, opacity: ui.dim }}>
                      {t("manage.searching")}
                    </div>
                  </Row>
                )}

                {!searching && candidates.length === 0 && (
                  <Row>
                    <div style={{ ...ui.text, opacity: ui.dim }}>
                      {t("manage.noMatches")}
                    </div>
                  </Row>
                )}

                {candidates.length > 0 && (
                  <Row>
                    <div style={{ display: "flex", gap: "20px", width: "100%" }}>
                      {preview ? (
                        <img
                          src={`data:image/png;base64,${preview}`}
                          alt=""
                          style={{
                            width: "116px",
                            height: "174px",
                            flex: "0 0 auto",
                            objectFit: "cover",
                            borderRadius: "4px",
                            alignSelf: "flex-start",
                          }}
                        />
                      ) : (
                        <div
                          style={{
                            width: "116px",
                            height: "174px",
                            flex: "0 0 auto",
                            borderRadius: "4px",
                            background: "rgba(255,255,255,0.06)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            ...ui.small,
                            opacity: ui.faint,
                            textAlign: "center",
                            padding: "8px",
                            boxSizing: "border-box",
                          }}
                        >
                          {idText ? t("manage.noCover") : t("manage.pickGame")}
                        </div>
                      )}

                      <Focusable
                        flow-children="column"
                        style={{
                          flex: "1 1 0",
                          minWidth: 0,
                          display: "flex",
                          flexDirection: "column",
                          gap: "8px",
                          maxHeight: "174px",
                          overflowY: "scroll",
                          paddingRight: "8px",
                        }}
                      >
                        {candidates.map((c) => {
                          const picked = String(c.id) === idText;
                          return (
                            <DialogButton
                              key={c.id}
                              onClick={() => setIdText(String(c.id))}
                              style={{
                                height: "46px",
                                padding: "0 14px",
                                ...ui.text,
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                gap: "12px",
                                outline: picked ? "2px solid #1a9fff" : "none",
                              }}
                            >
                              <span
                                style={{
                                  flex: "1 1 0",
                                  minWidth: 0,
                                  textAlign: "left",
                                  overflow: "hidden",
                                  textOverflow: "ellipsis",
                                  whiteSpace: "nowrap",
                                }}
                              >
                                {c.name}
                              </span>
                              {c.year && (
                                <span style={{ opacity: ui.faint, flex: "0 0 auto" }}>
                                  {c.year}
                                </span>
                              )}
                            </DialogButton>
                          );
                        })}
                      </Focusable>
                    </div>
                  </Row>
                )}

                <Row>
                  <Focusable>
                    <TextField
                      label={t("manage.sgdbIdLabel")}
                      description={t("manage.sgdbIdDesc")}
                      value={idText}
                      onChange={(e) => setIdText(e.target.value)}
                    />
                  </Focusable>
                </Row>

                <Row>
                  <Focusable>
                    <TextField
                      label={t("manage.titleLabel")}
                      description={t("manage.titleDesc")}
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                    />
                  </Focusable>
                </Row>

                <Footer
                  busy={busy}
                  progress={progress}
                  status={status}
                  disabled={!game || busy}
                  onSave={() => save(true)}
                />
              </PageBody>
            ),
          },
          {
            title: t("common.dangerZone"),
            content: (
              <PageBody>
                <Row>
                  <ToggleField
                    label={t("manage.excludeLabel")}
                    description={t("manage.excludeDesc")}
                    checked={exclude}
                    onChange={setExclude}
                  />
                </Row>

                <Row>
                  <div style={{ ...ui.small, opacity: ui.dim, ...wrapText }}>
                    {t("manage.excludeNote", {
                      path: ov?.path ?? ".romsync.txt",
                    })}
                  </div>
                </Row>

                <Footer
                  busy={busy}
                  progress={progress}
                  status={status}
                  disabled={!game || busy}
                  onSave={() => save(true)}
                />

                {wasExcluded && !busy && (
                  <>
                    <Row>
                      <div style={{ ...ui.small, opacity: ui.dim, ...wrapText }}>
                        {t("manage.queued")}
                      </div>
                    </Row>
                    <Row>
                      <ActionRow>
                        <DialogButton
                          style={compactButton}
                          disabled={sync.busy}
                          onClick={() => runSync()}
                        >
                          {sync.busy ? t("common.syncing") : t("common.syncNow")}
                        </DialogButton>
                      </ActionRow>
                    </Row>
                  </>
                )}
              </PageBody>
            ),
          },
        ]}
      />
    </PageShell>
  );
}
