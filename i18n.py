"""Translations for messages the backend hands to the UI.

The frontend owns the interface copy; this module owns the sentences the Python
side formats and returns — status lines, errors and the reasons shown in a sync
summary. It has no `decky` import so `romsync.py` and friends still run
off-device.

Language is set once per session by the frontend (`set_language`) and persisted
in settings.json, because restarting plugin_loader reloads the backend without
reloading the frontend.
"""

from __future__ import annotations

_LANG = "en"

_EN: dict[str, str] = {
    # -- library / settings ------------------------------------------------
    "main.enterFolder": "Enter a folder path.",
    "main.noFolder": "No folder at {path}.",
    "main.libraryUsing.one": "Using {path} — {count} system found.",
    "main.libraryUsing.other": "Using {path} — {count} systems found.",
    "main.libraryEmpty":
        "Using {path}, but no system folders are in it yet.",
    "main.libraryCreated":
        "Created {path} with folders: {folders}. Drop ROMs into those.",
    "main.coreUsing": "Now using {core}.",
    "main.coreUsingMissing":
        "Now using {core}, but that core isn't installed yet.",
    "main.coresInstalled": "Installed {cores}.",
    "main.coresFailed":
        "Couldn't fetch {cores} — install them from RetroArch's Core Downloader "
        "instead (Main Menu, Online Updater, Core Downloader).",
    "main.foundRoots": "Found {count}: {roots}",
    "main.noEmulationFolder":
        "No Emulation folder found on any mounted volume.",
    "main.homeFolder": "Home folder",
    "main.arcadeNames": "Arcade names: {message}",

    # -- artwork / key -----------------------------------------------------
    "main.warningNoKey":
        "Add a SteamGridDB key in settings to fill missing artwork.",
    "main.noSgdbMatch": "No SteamGridDB match for {title}.",
    "main.noSgdbArt": "SteamGridDB has no artwork for {title}.",
    "main.noKeyPrefetch":
        "No SteamGridDB key set — no artwork will be fetched.",
    "main.keyImported": "Imported key from {path}.",
    "main.noKeyFile":
        "No key file found. Looked in: {paths}. The file should be named "
        "steamgriddb_key.txt and contain just the key.",
    "main.noKeyFileNowhere": "nowhere — no library set",
    "main.noKey": "No SteamGridDB key set. Add one above.",

    # -- library / config writers -----------------------------------------
    "rom.writeError": "Can't write {path}: {error}",
    "rom.libraryWriteError": "Can't write {file}: {error}",
    "rom.createError": "Couldn't create the library: {error}",
    "rom.readError": "Can't read {path}: {error}",
    "rom.notRetroarch":
        "This system doesn't launch through RetroArch, so there is no core to "
        "change. Edit the command in {file} instead.",
    "rom.noCommandLine": "No command line found in {path}.",

    # -- launcher detection ------------------------------------------------
    "rom.launcherUnreadable": "can't be read ({error})",
    "rom.launcherNoFile": "has no {exts} file in it",
    "rom.launcherAmbiguous":
        "has {count} launchers ({names}) and none is named after the folder — "
        "rename the right one to \"{target}\"",

    # -- scan notes --------------------------------------------------------
    "rom.scanReadError": "Can't read {root}: {error}",
    "rom.skippedNoSystem":
        "Skipped {folder}: no system name in {file}.",
    "rom.skippedNoExts":
        "Skipped {system}: no file extensions known. Add an 'extensions' line "
        "to {file}.",
    "rom.gameProblem": "{system}: \"{folder}\" {why}.",
    "rom.duplicateSkipped":
        "Duplicate skipped: {title} ({system}) also at {path}",
    "rom.sameNameKept":
        "Same name in {system}: kept {titles}",
    "rom.coreMoved": "{system}: core moved, using {path}",

    # -- launch resolution --------------------------------------------------
    "rom.noLaunchCommand":
        "No launch command for {system}. Add one to {file} in that folder.",
    "rom.commandNoRomToken":
        "The command for {system} has no {token} in it, so no ROM would be "
        "passed. Add it in {file}.",
    "rom.coreNotInstalled": "Core {core} is not installed.",
    "rom.commandUnreadable": "Couldn't read the command for {system}.",
    "rom.exeMissing":
        "{exe} isn't installed, so {system} can't launch. Install it, or point "
        "the command in {file} somewhere else.",

    # -- removal reasons ----------------------------------------------------
    "rom.planFileMissing": "file missing",
    "rom.planExcluded": "excluded",
    "rom.planSystemOff": "system turned off",

    # -- retroarch ----------------------------------------------------------
    "rom.flatpakMissing": "Can't find the flatpak command.",
    "rom.retroarchInstalled": "RetroArch installed.",
    "rom.flatpakFailed": "flatpak install failed",

    # -- arcade name list ---------------------------------------------------
    "arcade.downloadError":
        "Couldn't download the arcade name list: {error}",
    "arcade.empty":
        "Arcade name list downloaded but contained no entries.",
    "arcade.saveError": "Couldn't save the arcade name list: {error}",
    "arcade.available": "{count} arcade titles available.",

    # -- steamgriddb --------------------------------------------------------
    "sgdb.cloudflare":
        "Cloudflare blocked the request before it reached SteamGridDB. This "
        "is not a key problem.",
    "sgdb.rejectedKey": "SteamGridDB rejected the key (HTTP {code}).",
    "sgdb.httpError": "SteamGridDB returned {code}.",
    "sgdb.tlsError":
        "TLS verification failed ({error}). Trust store: {store}. Check the "
        "system clock is correct.",
    "sgdb.tlsDirectory": "/etc/ssl/certs (directory)",
    "sgdb.noCaBundle": "no CA bundle found",
    "sgdb.rateLimited":
        "SteamGridDB is rate limiting us. Artwork will finish on a later sync "
        "— everything fetched so far is cached.",
    "sgdb.unreachable": "Couldn't reach SteamGridDB: {error}",
    "sgdb.malformed": "SteamGridDB sent a malformed response.",
    "sgdb.noResults":
        "SteamGridDB replied, but returned no results at all.",
    "sgdb.keyWorks.one":
        "Key works — test search returned {count} result.",
    "sgdb.keyWorks.other":
        "Key works — test search returned {count} results.",
}

_FR: dict[str, str] = {
    "main.enterFolder": "Saisissez un chemin de dossier.",
    "main.noFolder": "Aucun dossier à {path}.",
    "main.libraryUsing.one": "Utilisation de {path} — {count} système trouvé.",
    "main.libraryUsing.other":
        "Utilisation de {path} — {count} systèmes trouvés.",
    "main.libraryEmpty":
        "Utilisation de {path}, mais aucun dossier de système ne s'y trouve "
        "encore.",
    "main.libraryCreated":
        "Bibliothèque créée dans {path} avec les dossiers : {folders}. "
        "Déposez-y vos ROMs.",
    "main.coreUsing": "Utilisation de {core} désormais.",
    "main.coreUsingMissing":
        "Utilisation de {core}, mais ce cœur n'est pas encore installé.",
    "main.coresInstalled": "Cœurs installés : {cores}.",
    "main.coresFailed":
        "Impossible de récupérer {cores} — installez-les plutôt depuis le "
        "téléchargeur de cœurs de RetroArch (Menu principal, Mise à jour en "
        "ligne, Téléchargeur de cœurs).",
    "main.foundRoots": "Trouvés : {count} — {roots}",
    "main.noEmulationFolder":
        "Aucun dossier Emulation trouvé sur les volumes montés.",
    "main.homeFolder": "Dossier personnel",
    "main.arcadeNames": "Noms arcade : {message}",

    "main.warningNoKey":
        "Ajoutez une clé SteamGridDB dans les paramètres pour compléter les "
        "illustrations manquantes.",
    "main.noSgdbMatch": "Aucune correspondance SteamGridDB pour {title}.",
    "main.noSgdbArt": "SteamGridDB n'a pas d'illustration pour {title}.",
    "main.noKeyPrefetch":
        "Aucune clé SteamGridDB définie — aucune illustration ne sera "
        "récupérée.",
    "main.keyImported": "Clé importée depuis {path}.",
    "main.noKeyFile":
        "Aucun fichier de clé trouvé. Emplacements vérifiés : {paths}. Le "
        "fichier doit s'appeler steamgriddb_key.txt et contenir uniquement la "
        "clé.",
    "main.noKeyFileNowhere": "nulle part — aucune bibliothèque définie",
    "main.noKey": "Aucune clé SteamGridDB définie. Ajoutez-en une ci-dessus.",

    "rom.writeError": "Impossible d'écrire {path} : {error}",
    "rom.libraryWriteError": "Impossible d'écrire {file} : {error}",
    "rom.createError": "Impossible de créer la bibliothèque : {error}",
    "rom.readError": "Impossible de lire {path} : {error}",
    "rom.notRetroarch":
        "Ce système ne se lance pas via RetroArch : il n'y a donc aucun cœur "
        "à changer. Modifiez plutôt la commande dans {file}.",
    "rom.noCommandLine": "Aucune ligne de commande trouvée dans {path}.",

    "rom.launcherUnreadable": "illisible ({error})",
    "rom.launcherNoFile": "ne contient aucun fichier {exts}",
    "rom.launcherAmbiguous":
        "contient {count} lanceurs ({names}) et aucun ne porte le nom du "
        "dossier — renommez le bon en « {target} »",

    "rom.scanReadError": "Impossible de lire {root} : {error}",
    "rom.skippedNoSystem":
        "Dossier {folder} ignoré : aucun nom de système dans {file}.",
    "rom.skippedNoExts":
        "{system} ignoré : aucune extension de fichier connue. Ajoutez une "
        "ligne 'extensions' dans {file}.",
    "rom.gameProblem": "{system} : « {folder} » {why}.",
    "rom.duplicateSkipped":
        "Doublon ignoré : {title} ({system}) également dans {path}",
    "rom.sameNameKept": "Même nom dans {system} : conservé {titles}",
    "rom.coreMoved": "{system} : cœur déplacé, utilisation de {path}",

    "rom.noLaunchCommand":
        "Aucune commande de lancement pour {system}. Ajoutez-en une dans "
        "{file}, dans ce dossier.",
    "rom.commandNoRomToken":
        "La commande de {system} ne contient pas {token} : aucune ROM ne "
        "serait transmise. Ajoutez-le dans {file}.",
    "rom.coreNotInstalled": "Le cœur {core} n'est pas installé.",
    "rom.commandUnreadable": "Impossible de lire la commande de {system}.",
    "rom.exeMissing":
        "{exe} n'est pas installé, donc {system} ne peut pas se lancer. "
        "Installez-le ou modifiez la commande dans {file}.",

    "rom.planFileMissing": "fichier manquant",
    "rom.planExcluded": "exclu",
    "rom.planSystemOff": "système désactivé",

    "rom.flatpakMissing": "Impossible de trouver la commande flatpak.",
    "rom.retroarchInstalled": "RetroArch installé.",
    "rom.flatpakFailed": "échec de l'installation par flatpak",

    "arcade.downloadError":
        "Impossible de télécharger la liste des noms arcade : {error}",
    "arcade.empty":
        "La liste des noms arcade a été téléchargée mais ne contient aucune "
        "entrée.",
    "arcade.saveError":
        "Impossible d'enregistrer la liste des noms arcade : {error}",
    "arcade.available": "{count} titres arcade disponibles.",

    "sgdb.cloudflare":
        "Cloudflare a bloqué la requête avant qu'elle n'atteigne SteamGridDB. "
        "Le problème ne vient pas de la clé.",
    "sgdb.rejectedKey": "SteamGridDB a refusé la clé (HTTP {code}).",
    "sgdb.httpError": "SteamGridDB a renvoyé {code}.",
    "sgdb.tlsError":
        "La vérification TLS a échoué ({error}). Magasin de confiance : "
        "{store}. Vérifiez que l'horloge du système est correcte.",
    "sgdb.tlsDirectory": "/etc/ssl/certs (dossier)",
    "sgdb.noCaBundle": "aucun fichier de certificats CA trouvé",
    "sgdb.rateLimited":
        "SteamGridDB limite le débit. Les illustrations seront terminées lors "
        "d'une prochaine synchronisation — tout ce qui a été récupéré est en "
        "cache.",
    "sgdb.unreachable": "Impossible de joindre SteamGridDB : {error}",
    "sgdb.malformed": "SteamGridDB a envoyé une réponse malformée.",
    "sgdb.noResults":
        "SteamGridDB a répondu, mais n'a renvoyé aucun résultat.",
    "sgdb.keyWorks.one":
        "La clé fonctionne — la recherche de test a renvoyé {count} résultat.",
    "sgdb.keyWorks.other":
        "La clé fonctionne — la recherche de test a renvoyé {count} résultats.",
}


def set_language(lang: str | None) -> str:
    """Store the session language and return the one actually selected."""
    global _LANG
    _LANG = "fr" if str(lang or "").lower().startswith("fr") else "en"
    return _LANG


def language() -> str:
    return _LANG


def t(key: str, **params) -> str:
    """Look a message up and interpolate its named placeholders."""
    catalog = _FR if _LANG == "fr" else _EN
    text = catalog.get(key) or _EN.get(key) or key
    return text.format(**params) if params else text


def tn(key: str, count: int, **params) -> str:
    """Plural lookup. French uses the singular for 0 and 1, English only for 1."""
    singular = count <= 1 if _LANG == "fr" else count == 1
    return t(f"{key}.{'one' if singular else 'other'}", count=count, **params)
