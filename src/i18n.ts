/**
 * Translation for the plugin UI.
 *
 * Decky has no i18n API of its own, so this is deliberately small: two flat
 * dictionaries, one lookup function and a plural helper. The English side is
 * the source language — every key must exist in both dictionaries, which the
 * `Record<Key, string>` annotation enforces at build time.
 *
 * Language comes from the Steam client's CEF locale through `navigator`, which
 * follows the client language setting. Anything that is not French falls back
 * to English rather than to an untranslated screen.
 */

export type Lang = "en" | "fr";

type Params = Record<string, string | number>;

const EN = {
  // -- shared -------------------------------------------------------------
  "common.library": "Library",
  "common.save": "Save",
  "common.removeThem": "Remove them",
  "common.retry": "Retry",
  "common.dismiss": "Dismiss",
  "common.stop": "Stop",
  "common.sync": "Sync",
  "common.working": "Working…",
  "common.syncing": "Syncing…",
  "common.syncNow": "Sync now",
  "common.dangerZone": "Danger zone",
  "common.loadingSettings": "Loading settings",

  // -- panel --------------------------------------------------------------
  "panel.systems": "Systems",
  "panel.pendingAdd": "{count} to add",
  "panel.pendingUpdate": "{count} to update",
  "panel.pendingRemove": "{count} to remove",
  "panel.removeShortcutsTitle.one": "Remove {count} shortcut?",
  "panel.removeShortcutsTitle.other": "Remove {count} shortcuts?",
  "panel.removeMore": "…and {count} more.",
  "panel.removeWarning":
    "Steam playtime for these is lost and cannot be restored.",
  "panel.backendError":
    "Can't reach the plugin backend: {error}. Check every file was copied, " +
    "then restart plugin_loader.",
  "panel.noLibrary":
    "No ROM library yet. Create one below, or set an existing path from the " +
    "cog above.",
  "panel.creating": "Creating…",
  "panel.downloadingCores": "Downloading cores…",
  "panel.installMissingCores.one": "Install {count} missing core",
  "panel.installMissingCores.other": "Install {count} missing cores",
  "panel.installRetroArch": "Install RetroArch",
  "panel.installingRetroArch": "Installing RetroArch",
  "panel.syncStopped": "Sync stopped: {status}",
  "panel.waitingForRoms": "Waiting for ROMs in {folders}.",
  "panel.noSystems":
    "No system folders found yet. Add folders like n64 or snes inside your " +
    "roms folder.",
  "panel.notRecognised":
    "Not recognised: {folders}. Add a .romsync.txt in each with a system " +
    "and command line.",
  "panel.emptyNotListed": "Empty, so not listed: {folders}",

  // -- game context menu --------------------------------------------------
  "menu.manageRom": "Manage ROM...",

  // -- settings -----------------------------------------------------------
  "settings.removeAllTitle": "Remove all synced games?",
  "settings.removeAllBody":
    "This removes every shortcut ROM Sync created. Shortcuts it adopted " +
    "from another tool are left in place and simply forgotten. Your ROMs, " +
    "collections and .romsync.txt files are not touched.",
  "settings.noEmulationFolder":
    "No Emulation folder found. Enter the path below, or press Re-detect " +
    "after plugging in your card.",
  "settings.scanning": "Scanning: {folders}",
  "settings.pathLabel": "Path",
  "settings.pathDescription": "Your Emulation folder, or the roms folder inside it.",
  "settings.checking": "Checking…",
  "settings.useThisFolder": "Use this folder",
  "settings.scanningAction": "Scanning…",
  "settings.redetect": "Re-detect",
  "settings.savedIn": "Saved in {file} — editable by hand.",
  "settings.apiKey": "API key",
  "settings.testing": "Testing…",
  "settings.saveAndTest": "Save & test",
  "settings.lookingForKeyFile": "Looking for a key file…",
  "settings.importFile": "Import file",
  "settings.clearing": "Clearing…",
  "settings.clearCache": "Clear cache",
  "settings.cacheCleared":
    "Cleared {count} cached files. The next sync re-downloads artwork for " +
    "games that are missing it.",
  "settings.importHelp":
    "Import file picks up a key saved next to your library — any of " +
    "steamgriddb_key.txt, .steamgriddb_key or .steamgriddb_key.txt. " +
    "Clear cache first if you want fresh images from SteamGridDB. " +
    "Artwork you place in a system's media folder always overrides both.",
  "settings.keyImported":
    "Imported your key from {path}. That file is left in place so other " +
    "devices sharing this library can use it too.",
  "settings.storedIn": "Stored in {path}",
  "settings.savedTo": "Saved to {target}.",
  "settings.configFolder": "the config folder",
  "settings.artworkWins":
    "Artwork next to a ROM in a media folder always wins over SteamGridDB.",
  "settings.emulators": "Emulators",
  "settings.retroarchInstalled": "RetroArch installed · {count} cores available",
  "settings.retroarchMissing": "RetroArch is not installed.",
  "settings.installingRetroArch": "Installing RetroArch…",
  "settings.showCommands": "Show launch commands",
  "settings.showCommandsDesc":
    "What each system runs, and which file it lives in.",
  "settings.coreNotInstalled": "{core} · not installed",
  "settings.noCommandSet": "no command set",
  "settings.noSystemsWithGames": "No systems with games yet.",
  "settings.coreChangeNote":
    "Changing a core here rewrites one argument in that system's " +
    ".romsync.txt and leaves the rest of the command, and any comments, " +
    "exactly as written. Games pick it up on the next sync.",
  "settings.removeAllButton": "Remove all synced games",

  // -- manage ROM ---------------------------------------------------------
  "manage.manageRom": "Manage ROM",
  "manage.loading": "Loading",
  "manage.notManaged": "ROM Sync doesn't manage this game.",
  "manage.idMustBeNumber": "SteamGridDB ID must be a number.",
  "manage.saving": "Saving",
  "manage.overrideWriteError": "Couldn't write the override file.",
  "manage.lookingUpArt": "Looking up artwork",
  "manage.clearingOldArt": "Clearing old artwork",
  "manage.applying": "Applying {label}",
  "manage.applyingIcon": "Applying icon",
  "manage.saved": "Saved.",
  "manage.about": "About",
  "manage.artwork": "Artwork",
  "manage.system": "System",
  "manage.emulator": "Emulator",
  "manage.romFile": "ROM file",
  "manage.launchesWith": "Launches with",
  "manage.mediaNote":
    "Artwork you place in {grid} overrides SteamGridDB for this game. The " +
    "launch command comes from {path}.",
  "manage.mediaFolderDefault": "the system's media folder",
  "manage.romsyncDefault": "the system's .romsync.txt",
  "manage.searching": "Searching SteamGridDB…",
  "manage.noMatches":
    "No SteamGridDB matches. Enter an ID below if you know it.",
  "manage.noCover": "No cover",
  "manage.pickGame": "Pick a game",
  "manage.sgdbIdLabel": "SteamGridDB ID",
  "manage.sgdbIdDesc": "Leave empty to match by name.",
  "manage.titleLabel": "Title",
  "manage.titleDesc": "Leave empty to use the name from the filename.",
  "manage.excludeLabel": "Exclude from Steam",
  "manage.excludeDesc":
    "Removes the shortcut on the next sync and keeps it out.",
  "manage.excludeNote":
    "To hide a game temporarily, use Steam's own Manage › Hide instead — it " +
    "is reversible from the library. Excluding is for keeping a game out " +
    "for good: the plugin will not add it back, and only editing {path} " +
    "will undo it. Either way the ROM file itself is never deleted.",
  "manage.queued":
    "Queued. The shortcut goes on the next sync, or remove it now.",
  "manage.slotCapsule": "capsule",
  "manage.slotHero": "hero",
  "manage.slotLogo": "logo",
  "manage.slotHeader": "header",

  // -- sync / reset -------------------------------------------------------
  "sync.scanLabel": "Scan",
  "sync.artFetchLabel": "Artwork fetch",
  "sync.artLabel": "Artwork",
  "sync.saveLabel": "Save",
  "sync.lookingForRoms": "Looking for ROMs",
  "sync.waitingConfirmation": "Waiting for confirmation",
  "sync.cancelled": "Cancelled. Nothing was changed.",
  "sync.nothingToDo.one": "Nothing to do. {count} game already in sync.",
  "sync.nothingToDo.other": "Nothing to do. {count} games already in sync.",
  "sync.checkingShortcuts": "Checking existing shortcuts",
  "sync.fetchingArt": "Fetching artwork {from}–{to} of {total}",
  "sync.artSummary": "Artwork: {found} found, {missing} without.",
  "sync.rateLimited":
    "Hit the SteamGridDB rate limit — rerun Sync later to fill gaps.",
  "sync.adopting": "Adopting {step}/{total} · {title}",
  "sync.adding": "Adding {step}/{total} · {title}",
  "sync.artworkStep": "Artwork {step}/{total} · {title}",
  "sync.updating": "Updating {step}/{total} · {title}",
  "sync.removing": "Removing {step}/{total} · {title}",
  "sync.filingInto": "Filing into {label}",
  "sync.tidying": "Tidying categories",
  "sync.stoppedEarly": "Stopped early. Everything done so far was kept.",
  "sync.totals":
    "Added {added}, adopted {adopted}, updated {updated}, removed {removed}.",
  "sync.prunedCategories": "Removed empty categories: {list}.",
  "sync.artApplied": "Artwork applied to {applied} of {attempted}.",
  "sync.moreNotes": "…and {count} more notes.",
  "sync.excluded": "{count} excluded by .romsync.txt.",
  "sync.skippedNoEmulator": "{count} skipped — no emulator:",
  "sync.readingLibrary": "Reading library",
  "sync.removedShortcuts": "Removed {count} shortcuts.",
  "sync.leftAdopted":
    "Left {count} adopted shortcuts alone, just stopped tracking them.",
  "sync.filesUntouched":
    "Collections and .romsync.txt files were not touched.",
  "sync.stopped":
    "Stopped. Anything already added was kept — run Sync again to continue.",
  "sync.stopping":
    "Finishing the current game, then stopping. Press again to force stop.",

  // -- requests -----------------------------------------------------------
  "api.timeout": "{label} did not respond after {seconds}s",
} as const;

type Key = keyof typeof EN;

const FR: Record<Key, string> = {
  "common.library": "Bibliothèque",
  "common.save": "Enregistrer",
  "common.removeThem": "Les retirer",
  "common.retry": "Réessayer",
  "common.dismiss": "Fermer",
  "common.stop": "Arrêter",
  "common.sync": "Synchroniser",
  "common.working": "En cours…",
  "common.syncing": "Synchronisation…",
  "common.syncNow": "Synchroniser maintenant",
  "common.dangerZone": "Zone de danger",
  "common.loadingSettings": "Chargement des paramètres",

  "panel.systems": "Systèmes",
  "panel.pendingAdd": "{count} à ajouter",
  "panel.pendingUpdate": "{count} à mettre à jour",
  "panel.pendingRemove": "{count} à retirer",
  "panel.removeShortcutsTitle.one": "Retirer {count} raccourci ?",
  "panel.removeShortcutsTitle.other": "Retirer {count} raccourcis ?",
  "panel.removeMore": "…et {count} de plus.",
  "panel.removeWarning":
    "Le temps de jeu Steam associé sera perdu et ne pourra pas être restauré.",
  "panel.backendError":
    "Impossible de joindre le backend du plugin : {error}. Vérifiez que tous " +
    "les fichiers ont été copiés, puis redémarrez plugin_loader.",
  "panel.noLibrary":
    "Aucune bibliothèque de ROMs pour l'instant. Créez-en une ci-dessous ou " +
    "indiquez un chemin existant depuis l'engrenage ci-dessus.",
  "panel.creating": "Création…",
  "panel.downloadingCores": "Téléchargement des cœurs…",
  "panel.installMissingCores.one": "Installer {count} cœur manquant",
  "panel.installMissingCores.other": "Installer {count} cœurs manquants",
  "panel.installRetroArch": "Installer RetroArch",
  "panel.installingRetroArch": "Installation de RetroArch",
  "panel.syncStopped": "Synchronisation arrêtée : {status}",
  "panel.waitingForRoms": "En attente de ROMs dans {folders}.",
  "panel.noSystems":
    "Aucun dossier de système trouvé pour l'instant. Ajoutez des dossiers " +
    "comme n64 ou snes dans votre dossier roms.",
  "panel.notRecognised":
    "Non reconnus : {folders}. Ajoutez un .romsync.txt dans chacun, avec un " +
    "système et une ligne de commande.",
  "panel.emptyNotListed": "Vides, donc non listés : {folders}",

  "menu.manageRom": "Gérer la ROM…",

  "settings.removeAllTitle": "Retirer tous les jeux synchronisés ?",
  "settings.removeAllBody":
    "Cela retire tous les raccourcis créés par ROM Sync. Les raccourcis " +
    "adoptés depuis un autre outil sont laissés en place et simplement " +
    "oubliés. Vos ROMs, collections et fichiers .romsync.txt ne sont pas " +
    "modifiés.",
  "settings.noEmulationFolder":
    "Aucun dossier Emulation trouvé. Saisissez le chemin ci-dessous ou " +
    "appuyez sur Détecter à nouveau après avoir branché votre carte.",
  "settings.scanning": "Analyse : {folders}",
  "settings.pathLabel": "Chemin",
  "settings.pathDescription":
    "Votre dossier Emulation, ou le dossier roms qu'il contient.",
  "settings.checking": "Vérification…",
  "settings.useThisFolder": "Utiliser ce dossier",
  "settings.scanningAction": "Analyse…",
  "settings.redetect": "Détecter à nouveau",
  "settings.savedIn": "Enregistré dans {file} — modifiable à la main.",
  "settings.apiKey": "Clé API",
  "settings.testing": "Test en cours…",
  "settings.saveAndTest": "Enregistrer et tester",
  "settings.lookingForKeyFile": "Recherche d'un fichier de clé…",
  "settings.importFile": "Importer un fichier",
  "settings.clearing": "Nettoyage…",
  "settings.clearCache": "Vider le cache",
  "settings.cacheCleared":
    "{count} fichiers en cache ont été supprimés. La prochaine " +
    "synchronisation retéléchargera les illustrations des jeux qui en " +
    "manquent.",
  "settings.importHelp":
    "Importer un fichier récupère une clé enregistrée à côté de votre " +
    "bibliothèque — steamgriddb_key.txt, .steamgriddb_key ou " +
    ".steamgriddb_key.txt. Videz d'abord le cache si vous voulez des images " +
    "fraîches depuis SteamGridDB. Les illustrations placées dans le dossier " +
    "media d'un système ont toujours la priorité sur les deux.",
  "settings.keyImported":
    "Clé importée depuis {path}. Ce fichier est laissé en place afin que " +
    "les autres appareils partageant cette bibliothèque puissent aussi " +
    "l'utiliser.",
  "settings.storedIn": "Stocké dans {path}",
  "settings.savedTo": "Enregistré dans {target}.",
  "settings.configFolder": "le dossier de configuration",
  "settings.artworkWins":
    "Une illustration placée à côté d'une ROM dans un dossier media a " +
    "toujours la priorité sur SteamGridDB.",
  "settings.emulators": "Émulateurs",
  "settings.retroarchInstalled":
    "RetroArch installé · {count} cœurs disponibles",
  "settings.retroarchMissing": "RetroArch n'est pas installé.",
  "settings.installingRetroArch": "Installation de RetroArch…",
  "settings.showCommands": "Afficher les commandes de lancement",
  "settings.showCommandsDesc":
    "Ce que lance chaque système, et dans quel fichier cela se trouve.",
  "settings.coreNotInstalled": "{core} · non installé",
  "settings.noCommandSet": "aucune commande définie",
  "settings.noSystemsWithGames": "Aucun système avec des jeux pour l'instant.",
  "settings.coreChangeNote":
    "Changer de cœur ici réécrit un argument dans le .romsync.txt de ce " +
    "système et laisse le reste de la commande, ainsi que les commentaires, " +
    "exactement tels quels. Les jeux en tiendront compte à la prochaine " +
    "synchronisation.",
  "settings.removeAllButton": "Retirer tous les jeux synchronisés",

  "manage.manageRom": "Gérer la ROM",
  "manage.loading": "Chargement",
  "manage.notManaged": "ROM Sync ne gère pas ce jeu.",
  "manage.idMustBeNumber": "L'ID SteamGridDB doit être un nombre.",
  "manage.saving": "Enregistrement",
  "manage.overrideWriteError": "Impossible d'écrire le fichier de réglages.",
  "manage.lookingUpArt": "Recherche des illustrations",
  "manage.clearingOldArt": "Suppression des anciennes illustrations",
  "manage.applying": "Application : {label}",
  "manage.applyingIcon": "Application de l'icône",
  "manage.saved": "Enregistré.",
  "manage.about": "À propos",
  "manage.artwork": "Illustrations",
  "manage.system": "Système",
  "manage.emulator": "Émulateur",
  "manage.romFile": "Fichier ROM",
  "manage.launchesWith": "Se lance avec",
  "manage.mediaNote":
    "Une illustration placée dans {grid} a la priorité sur SteamGridDB pour " +
    "ce jeu. La commande de lancement provient de {path}.",
  "manage.mediaFolderDefault": "le dossier media du système",
  "manage.romsyncDefault": "le .romsync.txt du système",
  "manage.searching": "Recherche sur SteamGridDB…",
  "manage.noMatches":
    "Aucun résultat SteamGridDB. Saisissez un ID ci-dessous si vous le " +
    "connaissez.",
  "manage.noCover": "Aucune jaquette",
  "manage.pickGame": "Choisissez un jeu",
  "manage.sgdbIdLabel": "ID SteamGridDB",
  "manage.sgdbIdDesc": "Laissez vide pour faire correspondre par nom.",
  "manage.titleLabel": "Titre",
  "manage.titleDesc": "Laissez vide pour utiliser le nom du fichier.",
  "manage.excludeLabel": "Exclure de Steam",
  "manage.excludeDesc":
    "Retire le raccourci à la prochaine synchronisation et l'empêche de " +
    "revenir.",
  "manage.excludeNote":
    "Pour masquer un jeu temporairement, utilisez plutôt Gérer › Masquer de " +
    "Steam — c'est réversible depuis la bibliothèque. L'exclusion sert à " +
    "écarter définitivement un jeu : le plugin ne le rajoutera pas, et seul " +
    "le fichier {path} permet de revenir en arrière. Dans tous les cas, le " +
    "fichier ROM n'est jamais supprimé.",
  "manage.queued":
    "En attente. Le raccourci sera retiré à la prochaine synchronisation, ou " +
    "retirez-le maintenant.",
  "manage.slotCapsule": "capsule",
  "manage.slotHero": "hero",
  "manage.slotLogo": "logo",
  "manage.slotHeader": "bannière",

  "sync.scanLabel": "Analyse",
  "sync.artFetchLabel": "Récupération des illustrations",
  "sync.artLabel": "Illustrations",
  "sync.saveLabel": "Enregistrement",
  "sync.lookingForRoms": "Recherche des ROMs",
  "sync.waitingConfirmation": "En attente de confirmation",
  "sync.cancelled": "Annulé. Rien n'a été modifié.",
  "sync.nothingToDo.one": "Rien à faire. {count} jeu déjà synchronisé.",
  "sync.nothingToDo.other": "Rien à faire. {count} jeux déjà synchronisés.",
  "sync.checkingShortcuts": "Vérification des raccourcis existants",
  "sync.fetchingArt": "Récupération des illustrations {from}–{to} sur {total}",
  "sync.artSummary": "Illustrations : {found} trouvées, {missing} manquantes.",
  "sync.rateLimited":
    "Limite de débit SteamGridDB atteinte — relancez la synchronisation plus " +
    "tard pour compléter.",
  "sync.adopting": "Adoption {step}/{total} · {title}",
  "sync.adding": "Ajout {step}/{total} · {title}",
  "sync.artworkStep": "Illustration {step}/{total} · {title}",
  "sync.updating": "Mise à jour {step}/{total} · {title}",
  "sync.removing": "Retrait {step}/{total} · {title}",
  "sync.filingInto": "Classement dans {label}",
  "sync.tidying": "Nettoyage des catégories",
  "sync.stoppedEarly": "Arrêté avant la fin. Tout ce qui a été fait est conservé.",
  "sync.totals":
    "Ajoutés : {added}, adoptés : {adopted}, mis à jour : {updated}, " +
    "retirés : {removed}.",
  "sync.prunedCategories": "Catégories vides supprimées : {list}.",
  "sync.artApplied": "Illustrations appliquées : {applied} sur {attempted}.",
  "sync.moreNotes": "…et {count} autres notes.",
  "sync.excluded": "{count} exclus par .romsync.txt.",
  "sync.skippedNoEmulator": "{count} ignorés — aucun émulateur :",
  "sync.readingLibrary": "Lecture de la bibliothèque",
  "sync.removedShortcuts": "{count} raccourcis retirés.",
  "sync.leftAdopted":
    "{count} raccourcis adoptés laissés en place, simplement retirés du suivi.",
  "sync.filesUntouched":
    "Les collections et les fichiers .romsync.txt n'ont pas été modifiés.",
  "sync.stopped":
    "Arrêté. Tout ce qui a déjà été ajouté est conservé — relancez la " +
    "synchronisation pour continuer.",
  "sync.stopping":
    "Fin du jeu en cours, puis arrêt. Appuyez à nouveau pour forcer l'arrêt.",

  "api.timeout": "{label} n'a pas répondu après {seconds} s",
};

function detectLanguage(): Lang {
  try {
    const locales =
      navigator.languages && navigator.languages.length
        ? navigator.languages
        : [navigator.language];
    const first = locales.find((l) => !!l) ?? "en";
    return first.toLowerCase().startsWith("fr") ? "fr" : "en";
  } catch {
    return "en";
  }
}

/** Resolved once per session; changing Steam's language needs a restart too. */
export const lang: Lang = detectLanguage();

function interpolate(text: string, params?: Params): string {
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  );
}

const dictionary: Record<Key, string> = lang === "fr" ? FR : EN;

export function t(key: Key, params?: Params): string {
  return interpolate(dictionary[key] ?? EN[key], params);
}

/**
 * Plural lookup. English singular is exactly 1; French uses the singular for
 * 0 and 1, so the rule cannot be shared between the two dictionaries.
 */
export function tp(key: string, count: number, params?: Params): string {
  const singular = lang === "fr" ? count <= 1 : count === 1;
  return t(
    `${key}.${singular ? "one" : "other"}` as Key,
    { count, ...params },
  );
}
