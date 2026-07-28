"""
romsync core logic.

Deliberately free of any `decky` import so it can be unit-tested off-device.
main.py wraps this in the Decky Plugin class.

Launch configuration lives in each system folder's `.romsync.txt`, not in this
file. The table below only supplies the default written into a new folder; once
that file exists it is authoritative, so a user can point a folder at a
different core, or at a different emulator entirely, by editing one line.
"""

from __future__ import annotations

import arcade
import difflib
import glob
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import threading
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable

# Decky exports DECKY_USER_HOME as the real user's home regardless of how the
# plugin is launched. Path.home() follows $HOME, which is not guaranteed to be
# the same thing, so prefer the explicit one.
HOME = Path(os.environ.get("DECKY_USER_HOME") or Path.home())

FLATPAK_APP_DIRS = [
    HOME / ".local/share/flatpak/app",
    Path("/var/lib/flatpak/app"),
]

RETROARCH_ID = "org.libretro.RetroArch"
FLATPAK_BIN = "/usr/bin/flatpak"

# Where RetroArch's own core downloader puts cores for the Flatpak. Cores we
# install go here too, so the two agree.
CORE_DIR = HOME / ".var/app/org.libretro.RetroArch/config/retroarch/cores"

# Also searched, so a core bundled with the Flatpak or installed system-wide
# is found rather than downloaded again.
CORE_SEARCH_DIRS = [
    CORE_DIR,
    HOME / ".local/share/flatpak/app/org.libretro.RetroArch/current/active/files/lib/retroarch/cores",
    Path("/var/lib/flatpak/app/org.libretro.RetroArch/current/active/files/lib/retroarch/cores"),
]

# RetroArch's own core_updater_buildbot_url.
BUILDBOT_URL = "https://buildbot.libretro.com/nightly/linux/x86_64/latest/"

MOUNT_PREFIXES = ("/run/media", "/media", "/mnt", "/run/mount")
EMULATION_DIR = "emulation"
ROMS_DIR = "roms"
SKIP_DIRS = {"media", "images", "downloaded_images", "manuals", "videos",
             "bios", "gamelists", "tools", "storage", "saves", "states", ".git"}
MAX_DEPTH = 3


# --------------------------------------------------------------------------
# System table
# --------------------------------------------------------------------------
# `cores` lists the libretro cores worth offering for a system, best first.
# The first is what seeds a new folder's .romsync.txt; the rest populate the
# core picker. Systems with nothing worth defaulting to get an empty list:
# their file is written with the command commented out and a note to fill in.
@dataclass
class System:
    key: str
    label: str
    aliases: list[str]
    exts: list[str]
    cores: list[str] = field(default_factory=list)
    #: Games here are folders, not files — seeds `folders = yes`.
    folders: bool = False

    @property
    def core(self) -> str | None:
        """The recommended core, or None."""
        return self.cores[0] if self.cores else None


SYSTEMS: list[System] = [
    System("nes", "Nintendo Entertainment System", ["nes", "famicom", "fc"],
       [".nes", ".fds", ".unf", ".zip", ".7z"], cores=["nestopia", "mesen", "fceumm", "quicknes"]),
    System("snes", "Super Nintendo", ["snes", "sfc", "superfamicom", "super nintendo"],
       [".sfc", ".smc", ".swc", ".fig", ".zip", ".7z"], cores=["bsnes", "snes9x", "bsnes_hd_beta", "mesen-s"]),
    System("n64", "Nintendo 64", ["n64", "nintendo64", "nintendo 64"],
       [".z64", ".n64", ".v64", ".ndd", ".zip", ".7z"], cores=["mupen64plus_next", "parallel_n64"]),
    System("gb", "Game Boy", ["gb", "gameboy", "game boy"],
       [".gb", ".zip", ".7z"], cores=["gambatte", "sameboy", "mgba"]),
    System("gbc", "Game Boy Color", ["gbc", "gameboycolor", "game boy color"],
       [".gbc", ".gb", ".zip", ".7z"], cores=["gambatte", "sameboy", "mgba"]),
    System("gba", "Game Boy Advance", ["gba", "gameboyadvance", "game boy advance"],
       [".gba", ".zip", ".7z"], cores=["mgba", "vbam", "vba_next"]),
    System("nds", "Nintendo DS", ["nds", "ds", "nintendods"],
       [".nds", ".zip", ".7z"], cores=["melondsds", "melonds", "desmume"]),
    System("gc", "GameCube", ["gc", "gamecube", "ngc"],
       [".iso", ".gcm", ".gcz", ".rvz", ".ciso"], cores=["dolphin"]),
    System("wii", "Wii", ["wii"],
       [".iso", ".wbfs", ".rvz", ".wad", ".gcz", ".ciso"], cores=["dolphin"]),
    System("wiiu", "Wii U", ["wiiu", "wii u"],
       [".wud", ".wux", ".wua"], cores=[], folders=True),
    System("switch", "Nintendo Switch", ["switch", "nsw"],
       [".nsp", ".xci"], cores=[]),
    System("genesis", "Sega Genesis", ["genesis", "megadrive", "md", "sega genesis", "mega drive"],
       [".md", ".gen", ".bin", ".smd", ".zip", ".7z"], cores=["genesis_plus_gx", "picodrive", "blastem"]),
    System("mastersystem", "Master System", ["mastersystem", "sms", "master system"],
       [".sms", ".zip", ".7z"], cores=["genesis_plus_gx", "gearsystem", "picodrive", "smsplus"]),
    System("gamegear", "Game Gear", ["gamegear", "gg", "game gear"],
       [".gg", ".zip", ".7z"], cores=["genesis_plus_gx", "gearsystem", "smsplus"]),
    System("segacd", "Sega CD", ["segacd", "megacd", "sega cd", "mega cd"],
       [".cue", ".chd", ".iso", ".m3u"], cores=["genesis_plus_gx", "picodrive"]),
    System("saturn", "Sega Saturn", ["saturn", "sega saturn", "ss"],
       [".cue", ".chd", ".iso", ".m3u"], cores=["kronos", "mednafen_saturn", "beetle_saturn", "yabasanshiro"]),
    System("dreamcast", "Dreamcast", ["dreamcast", "dc"],
       [".gdi", ".cdi", ".chd", ".cue", ".m3u"], cores=["flycast"]),
    System("psx", "PlayStation", ["psx", "ps1", "playstation", "psone"],
       [".cue", ".chd", ".pbp", ".iso", ".m3u", ".ecm"], cores=["mednafen_psx_hw", "swanstation", "pcsx_rearmed", "beetle_psx_hw"]),
    System("ps2", "PlayStation 2", ["ps2", "playstation2", "playstation 2"],
       [".iso", ".chd", ".bin", ".gz", ".m3u"], cores=[]),
    System("ps3", "PlayStation 3", ["ps3", "playstation3", "playstation 3"],
       [".iso"], cores=[], folders=True),
    System("psp", "PSP", ["psp", "playstationportable"],
       [".iso", ".cso", ".chd", ".pbp"], cores=["ppsspp"]),
    System("tg16", "TurboGrafx-16", ["tg16", "pcengine", "turbografx", "pce"],
       [".pce", ".cue", ".chd", ".sgx", ".zip", ".7z"], cores=["mednafen_pce", "mednafen_pce_fast", "mednafen_supergrafx"]),
    System("neogeo", "Neo Geo", ["neogeo", "neo geo"],
       [".zip", ".7z", ".chd"], cores=["fbneo", "mame2003_plus", "mame", "geolith"]),
    System("arcade", "Arcade", ["arcade", "mame", "fbneo", "fba"],
       [".zip", ".7z", ".chd"], cores=["fbneo", "mame2003_plus", "mame", "mame2010"]),
    System("atari2600", "Atari 2600", ["atari2600", "2600", "a2600"],
       [".a26", ".bin", ".zip", ".7z"], cores=["stella", "stella2014"]),
    System("3do", "3DO", ["3do"],
       [".iso", ".chd", ".cue"], cores=["opera"]),
    System("c64", "Commodore 64", ["c64", "commodore64"],
       [".d64", ".t64", ".prg", ".crt", ".tap", ".zip"], cores=["vice_x64sc", "vice_x64"]),
    System("msx", "MSX", ["msx", "msx2"],
       [".rom", ".dsk", ".cas", ".mx1", ".mx2", ".zip"], cores=["bluemsx", "fmsx"]),
    System("dos", "MS-DOS", ["dos", "msdos", "pc"],
       [".zip", ".dosz", ".conf", ".iso", ".cue"],
       cores=["dosbox_pure", "dosbox_core", "dosbox_svn"]),
    # ScummVM games are folders, launched via a small .scummvm or .svm stub
    # file naming the game — which is what the core reads, so the stub is the
    # ROM as far as scanning is concerned.
    System("scummvm", "ScummVM", ["scummvm", "scumm"],
       [".scummvm", ".svm"], cores=["scummvm"]),
    # The game is the directory: lair.daphne/ holds the video and data files.
    System("daphne", "Daphne", ["daphne", "laserdisc", "singe"],
       [".daphne", ".singe"], cores=[]),
]

SYSTEM_BY_ALIAS: dict[str, System] = {}
for _sys in SYSTEMS:
    for _alias in _sys.aliases:
        SYSTEM_BY_ALIAS[_alias.casefold()] = _sys
    SYSTEM_BY_ALIAS[_sys.key.casefold()] = _sys

# Folders seeded into a freshly created library.
EXAMPLE_SYSTEMS = ["nes", "gba", "psx", "arcade"]


# --------------------------------------------------------------------------
# Cores
# --------------------------------------------------------------------------
def tmp_path(path: Path) -> Path:
    """Temp path unique to this thread. get_settings and build_plan run on
    separate threads and both seed missing folder configs, so a temp name
    derived only from the target can be written by two writers at once."""
    return path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")


def core_filename(core: str) -> str:
    return f"{core}_libretro.so"


def find_core(core_or_path: str) -> str | None:
    """Absolute path to a core, or None.

    Accepts either a bare core name or a full path. A full path that no longer
    exists is retried by filename across the known core directories: a Flatpak
    update or a switch between user and system install moves cores, and a
    hand-written command in .romsync.txt should keep working rather than
    silently launching nothing.
    """
    candidate = Path(core_or_path)
    if candidate.is_absolute():
        if candidate.is_file():
            return str(candidate)
        wanted = candidate.name
    else:
        wanted = core_filename(core_or_path) if not core_or_path.endswith(".so") \
            else core_or_path

    for directory in CORE_SEARCH_DIRS:
        hit = directory / wanted
        if hit.is_file():
            return str(hit)
    return None


def installed_cores() -> dict[str, str]:
    """core name -> absolute path"""
    found: dict[str, str] = {}
    for directory in CORE_SEARCH_DIRS:
        if not directory.is_dir():
            continue
        try:
            for so in sorted(directory.glob("*_libretro.so")):
                found.setdefault(so.name[: -len("_libretro.so")], str(so))
        except OSError:
            continue
    return found


def install_cores(names: list[str], timeout: int = 120) -> list[dict]:
    """Fetch cores from RetroArch's own buildbot.

    These are nightlies built against current RetroArch, so one can fail to
    load against an older Flatpak. That is why the UI offers RetroArch's Core
    Downloader as the fallback rather than treating this as the only route.
    """
    results = []
    for name in names:
        target = CORE_DIR / core_filename(name)
        url = f"{BUILDBOT_URL}{core_filename(name)}.zip"
        try:
            CORE_DIR.mkdir(parents=True, exist_ok=True)
            tmp_zip = CORE_DIR / f".{name}.zip.part"
            request = urllib.request.Request(
                url, headers={"User-Agent": "ROMSync/0.1 (Decky plugin)"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                tmp_zip.write_bytes(response.read())
            with zipfile.ZipFile(tmp_zip) as archive:
                member = next(
                    (m for m in archive.namelist() if m.endswith(".so")), None)
                if member is None:
                    raise ValueError("archive contained no core")
                with archive.open(member) as src:
                    tmp_so = CORE_DIR / f".{name}.so.part"
                    tmp_so.write_bytes(src.read())
            os.replace(tmp_so, target)
            tmp_zip.unlink(missing_ok=True)
            results.append({"core": name, "ok": True, "path": str(target)})
        except Exception as e:  # noqa: BLE001 - report, never raise
            results.append({"core": name, "ok": False, "error": str(e)})
    return results


# --------------------------------------------------------------------------
# Launch commands
# --------------------------------------------------------------------------
# {rom} is replaced with the ROM's absolute path. Splitting happens before
# substitution so a path containing spaces stays one argument.
ROM_TOKEN = "{rom}"


def retroarch_command(core_path: str) -> str:
    return (f'{FLATPAK_BIN} run {RETROARCH_ID} '
            f'-L "{core_path}" "{ROM_TOKEN}"')


def default_command(system: System) -> tuple[str, str | None]:
    """(command, missing core name). The command is written even when the core
    is absent, so installing it later makes the folder work with no edit."""
    if not system.core:
        return "", None
    resolved = find_core(system.core)
    if resolved:
        return retroarch_command(resolved), None
    return retroarch_command(str(CORE_DIR / core_filename(system.core))), system.core


def split_command(command: str, rom_path: str) -> tuple[str, str] | None:
    """(exe, launch options) for a Steam shortcut, or None if unusable."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    if not parts:
        return None
    parts = [p.replace(ROM_TOKEN, rom_path) for p in parts]
    exe = parts[0]
    args = " ".join(shlex.quote(p) for p in parts[1:])
    return exe, args


def command_core(command: str) -> str | None:
    """The -L argument of a command, if it has one."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    for i, part in enumerate(parts):
        if part == "-L" and i + 1 < len(parts):
            return parts[i + 1]
    return None


# --------------------------------------------------------------------------
# Per-folder configuration: .romsync.txt
# --------------------------------------------------------------------------
# One hidden plain-text file per system folder, holding both how the system
# launches and any per-ROM corrections. It travels with the ROMs, and it is the
# authority: the table above only seeds it.
#
#   system  = the Steam category these games appear under
#   command = how each ROM launches, {rom} replaced with the file path
#
# A folder with a valid header is a system even if its name matches nothing in
# the table, which is how an unsupported console gets added — make a folder,
# write two lines, point the command at any emulator.
OVERRIDE_FILENAME = ".romsync.txt"
LEGACY_OVERRIDE_FILENAME = ".romsync.json"

_TRUTHY = {"yes", "true", "on", "1"}
FIELDS = ("sgdb_id", "title", "exclude")


@dataclass
class FolderConfig:
    system: str = ""
    command: str = ""
    extensions: list[str] = field(default_factory=list)
    #: Each immediate subdirectory is one game, for systems that store a game
    #: as a folder rather than a file.
    folders: bool = False
    games: dict[str, dict] = field(default_factory=dict)


def override_path(system_dir: Path) -> Path:
    return Path(system_dir) / OVERRIDE_FILENAME


def parse_folder_config(text: str) -> FolderConfig:
    config = FolderConfig()
    current: str | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().casefold()
        value = value.strip()

        if key == "file":
            current = value.casefold()
            config.games.setdefault(current, {"_name": value})
            continue
        if current is None:
            # Header fields, before the first per-ROM block.
            if key == "system":
                config.system = value
            elif key == "command":
                config.command = value
            elif key == "folders":
                config.folders = value.casefold() in _TRUTHY
            elif key == "extensions":
                config.extensions = [
                    e if e.startswith(".") else f".{e}"
                    for e in re.split(r"[,\s]+", value.casefold()) if e
                ]
            continue
        if key not in FIELDS:
            continue
        entry = config.games[current]
        if key == "sgdb_id":
            try:
                entry["sgdb_id"] = int(value)
            except ValueError:
                pass
        elif key == "exclude":
            if value.casefold() in _TRUTHY:
                entry["exclude"] = True
        elif value:
            entry[key] = value
    return config


def format_folder_config(config: FolderConfig, note: str = "") -> str:
    lines = [
        f"# ROM Sync - {config.system or 'system'}",
        "#",
        "#   system     = the Steam category these games appear under",
        "#   command    = how each ROM launches; {rom} becomes the file path",
        "#   extensions = which files in this folder count as games",
        "#   folders    = yes, if each game here is a folder rather than a file",
        "#",
        "# Point command at any emulator you like. This file wins over the",
        "# plugin's defaults, and travels with the ROMs.",
        "#",
    ]
    if note:
        lines += [f"# {line}" for line in note.splitlines()] + ["#"]
    lines.append("")
    lines.append(f"system = {config.system}")
    if config.command:
        lines.append(f"command = {config.command}")
    else:
        lines += [
            "# No RetroArch core ships for this system. Fill in a command, e.g.",
            '# command = /usr/bin/flatpak run org.some.Emulator "{rom}"',
            "# command =",
        ]
    if config.folders:
        lines.append("folders = yes")
    else:
        lines.append(f"extensions = {' '.join(config.extensions)}"
                     if config.extensions else
                     "# extensions = .ext .ext   which files here are games")
        lines.append("# folders = yes   if each game here is a folder, not a file")

    lines += [
        "",
        "# Per-ROM corrections below. One block each:",
        "#   file = Some Game (USA).ext",
        "#   sgdb_id = 1234      pin artwork",
        "#   title = Nicer Name  rename in Steam",
        "#   exclude = yes       keep out of Steam",
        "",
    ]
    for entry in config.games.values():
        name = entry.get("_name")
        if not name:
            continue
        block = [f"file = {name}"]
        if entry.get("sgdb_id"):
            block.append(f"sgdb_id = {entry['sgdb_id']}")
        if entry.get("title"):
            block.append(f"title = {entry['title']}")
        if entry.get("exclude"):
            block.append("exclude = yes")
        if len(block) > 1:
            lines.append("\n".join(block))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _load_legacy_games(system_dir: Path) -> dict[str, dict]:
    try:
        raw = json.loads(
            (Path(system_dir) / LEGACY_OVERRIDE_FILENAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    games = raw.get("games") if isinstance(raw, dict) else None
    if not isinstance(games, dict):
        return {}
    return {k.casefold(): dict(v, _name=k)
            for k, v in games.items() if isinstance(v, dict)}


def load_folder_config(system_dir: Path) -> FolderConfig:
    try:
        return parse_folder_config(
            override_path(system_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return FolderConfig(games=_load_legacy_games(system_dir))


def load_overrides(system_dir: Path) -> dict[str, dict]:
    return load_folder_config(system_dir).games


def write_folder_config(system_dir: Path, config: FolderConfig,
                        note: str = "") -> tuple[bool, str]:
    path = override_path(system_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = tmp_path(path)
        tmp.write_text(format_folder_config(config, note), encoding="utf-8")
        os.replace(tmp, path)
        return True, str(path)
    except OSError as e:
        return False, f"Can't write {path}: {e}"


def save_override(system_dir: Path, filename: str, sgdb_id=None,
                  title=None, exclude=None) -> tuple[bool, str]:
    """Merge one game's correction into the folder's file, leaving the header
    and every other block untouched."""
    config = load_folder_config(system_dir)
    key = filename.casefold()
    entry = config.games.get(key) or {"_name": filename}
    entry["_name"] = entry.get("_name") or filename

    for field_name, value in (("sgdb_id", sgdb_id), ("title", title),
                              ("exclude", exclude)):
        if value is None:
            continue
        if value:
            entry[field_name] = int(value) if field_name == "sgdb_id" else value
        else:
            entry.pop(field_name, None)

    if any(entry.get(f) for f in FIELDS):
        config.games[key] = entry
    else:
        config.games.pop(key, None)
    return write_folder_config(system_dir, config)


def ensure_folder_config(system_dir: Path, system: System | None
                         ) -> tuple[FolderConfig, str | None]:
    """Read a folder's config, creating it from the defaults if absent.

    Returns (config, missing core name). A folder with neither a config nor a
    recognised name yields an empty system, and the caller skips it.
    """
    config = load_folder_config(system_dir)

    if not config.system or not config.command:
        if system is None:
            return config, None
        command, absent = default_command(system)
        config.system = config.system or system.label
        config.command = config.command or command
        config.extensions = config.extensions or list(system.exts)
        config.folders = config.folders or system.folders
        note = ("The core for this system is not installed yet. Install it "
                "from the plugin, or from RetroArch's own Core Downloader."
                ) if absent else ""
        write_folder_config(system_dir, config, note)
    elif system is not None and not config.extensions:
        # Backfill: files written before extensions were listed still work off
        # the built-in table, but writing them in keeps every folder's file
        # looking the same and makes the list editable. One-time.
        config.extensions = list(system.exts)
        write_folder_config(system_dir, config)

    # Computed from the final command in every branch. Deriving it inside the
    # branches meant a folder being backfilled reported no missing core on that
    # one run, which self-corrected next time and was confusing until it did.
    missing = None
    if config.command:
        core = command_core(config.command)
        if core and not find_core(core):
            missing = Path(core).name.replace("_libretro.so", "")
    return config, missing


# --------------------------------------------------------------------------
# Config, library location, API key  (unchanged behaviour)
# --------------------------------------------------------------------------
CONFIG_DIR = HOME / ".config" / "romsync"
# Nothing in the config folder is hidden — the folder itself already is, and a
# dotfile inside a dotfolder is just harder to find. The dotted spellings stay
# readable so files written by earlier versions still work.
KEY_FILENAMES = ("steamgriddb_key.txt", ".steamgriddb_key")

# Reading is matched by pattern, not by that exact list. This file gets written
# by hand across several machines, and every plausible spelling —
# steamgriddb_key.txt, .steamgriddb_key, .steamgriddb_key.txt, sgdb-key.txt —
# obviously means the same thing. Enumerating them guarantees missing one.
_KEY_FILE_HINT = re.compile(r"^\.?(steamgriddb|sgdb)[-_ ]?key(\.txt)?$",
                            re.IGNORECASE)


def looks_like_key_file(name: str) -> bool:
    return bool(_KEY_FILE_HINT.match(name.strip()))


def key_files_in(directory: Path) -> list[Path]:
    """Every plausible key file in a folder, canonical spellings first."""
    try:
        found = [f for f in directory.iterdir()
                 if f.is_file() and looks_like_key_file(f.name)]
    except (OSError, PermissionError):
        return []
    order = {name.casefold(): i for i, name in enumerate(KEY_FILENAMES)}
    found.sort(key=lambda f: (order.get(f.name.casefold(), len(order)), f.name))
    return found

LIBRARY_FILENAMES = ("library_path.txt", ".library_path.txt")
LIBRARY_PATH_FILE = CONFIG_DIR / LIBRARY_FILENAMES[0]

LIBRARY_FILE_HEADER = (
    "# ROM Sync library folders, one per line.\n"
    "# Point at your Emulation folder or directly at its roms folder.\n"
    "# Lines starting with # are ignored. Delete this file to re-detect.\n"
)


def _ci_child(parent: Path, name: str) -> Path | None:
    try:
        for child in parent.iterdir():
            if child.name.casefold() == name and child.is_dir():
                return child
    except (OSError, PermissionError):
        return None
    return None


def _candidate_bases() -> list[Path]:
    bases: list[Path] = [HOME]
    try:
        with open("/proc/mounts", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                mount = parts[1].replace("\\040", " ")
                if mount.startswith(MOUNT_PREFIXES):
                    bases.append(Path(mount))
    except OSError:
        pass
    for pattern in ("/run/media/*", "/run/media/*/*", "/media/*", "/media/*/*"):
        for hit in glob.glob(pattern):
            bases.append(Path(hit))
    return bases


def library_file() -> Path:
    """The library file in use, preferring the visible name."""
    for name in LIBRARY_FILENAMES:
        candidate = CONFIG_DIR / name
        if candidate.is_file():
            return candidate
    return LIBRARY_PATH_FILE


def read_library_paths() -> list[str]:
    try:
        text = library_file().read_text(encoding="utf-8")
    except (OSError, ValueError):
        return []
    return [ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def save_library_paths(paths: list[str]) -> tuple[bool, str]:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        body = LIBRARY_FILE_HEADER + "".join(f"{p}\n" for p in paths)
        tmp = tmp_path(LIBRARY_PATH_FILE)
        tmp.write_text(body, encoding="utf-8")
        os.replace(tmp, LIBRARY_PATH_FILE)
        invalidate_roots()
        # Retire the hidden spelling so there is only ever one file to edit.
        legacy = CONFIG_DIR / LIBRARY_FILENAMES[1]
        if legacy.is_file():
            try:
                legacy.unlink()
            except OSError:
                pass
        return True, str(LIBRARY_PATH_FILE)
    except OSError as e:
        return False, f"Can't write {LIBRARY_PATH_FILE}: {e}"


def resolve_library_path(raw: str) -> str | None:
    path = Path(os.path.expanduser(raw.strip()))
    if not path.is_dir():
        return None
    roms = _ci_child(path, ROMS_DIR)
    if roms is not None:
        return os.path.realpath(roms)
    emulation = _ci_child(path, EMULATION_DIR)
    if emulation is not None:
        return os.path.realpath(_ci_child(emulation, ROMS_DIR) or emulation)
    return os.path.realpath(path)


def emulation_dir_for(root: str) -> Path:
    root_path = Path(root)
    if root_path.parent.name.casefold() == EMULATION_DIR:
        return root_path.parent
    return root_path


def autodetect_roots() -> list[str]:
    roots: list[str] = []
    for base in _candidate_bases():
        emulation = _ci_child(base, EMULATION_DIR)
        if emulation is None:
            continue
        target = _ci_child(emulation, ROMS_DIR) or emulation
        real = os.path.realpath(target)
        if real not in roots:
            roots.append(real)
    return roots


# discover_roots reads the library file and stats every configured path, and
# it sits under find_local_art and system_dir_for — both of which run per game,
# per artwork slot. A 200-game prefetch was calling it roughly 1,600 times, each
# one a file read plus directory iteration, much of it against an SD card.
#
# A short TTL rather than a permanent cache: a sync finishes well inside it, and
# a card plugged in mid-session is picked up a few seconds later. Anything that
# deliberately changes the library invalidates it outright.
_ROOTS_TTL = 5.0
_roots_cache: tuple[float, list[str]] | None = None


def invalidate_roots() -> None:
    global _roots_cache
    _roots_cache = None


def discover_roots() -> list[str]:
    """`.library_path.txt` is authoritative once it exists; auto-detection only
    seeds it. Entries that no longer resolve are skipped, not rewritten out, so
    unplugging a card doesn't discard a configured path."""
    global _roots_cache
    if _roots_cache is not None and time.monotonic() - _roots_cache[0] < _ROOTS_TTL:
        return _roots_cache[1]
    roots = _discover_roots_uncached()
    _roots_cache = (time.monotonic(), roots)
    return roots


def _discover_roots_uncached() -> list[str]:
    configured = read_library_paths()
    if configured:
        roots: list[str] = []
        for raw in configured:
            resolved = resolve_library_path(raw)
            if resolved and resolved not in roots:
                roots.append(resolved)
        if roots:
            return roots

    detected = autodetect_roots()
    if detected and not library_file().exists():
        save_library_paths(detected)
    return detected


def removable_bases() -> list[dict]:
    """Mounted volumes a library could be created on, for the setup prompt."""
    out = [{"label": "Home folder", "path": str(HOME)}]
    seen = {str(HOME)}
    for base in _candidate_bases():
        p = str(base)
        if p in seen or not base.is_dir() or p == str(HOME):
            continue
        if not p.startswith(MOUNT_PREFIXES):
            continue
        if not os.access(p, os.W_OK):
            continue
        seen.add(p)
        out.append({"label": base.name or p, "path": p})
    return out


def create_library(base: str) -> tuple[bool, str, list[str]]:
    """Make <base>/Emulation/roms with a few example systems, each already
    carrying a .romsync.txt so the format is discoverable by looking."""
    try:
        root = Path(os.path.expanduser(base.strip()))
        if not root.is_dir():
            return False, f"No folder at {root}.", []
        roms = root / "Emulation" / "roms"
        roms.mkdir(parents=True, exist_ok=True)

        created = []
        for key in EXAMPLE_SYSTEMS:
            system = SYSTEM_BY_ALIAS.get(key)
            if system is None:
                continue
            folder = roms / system.key
            folder.mkdir(exist_ok=True)
            ensure_folder_config(folder, system)
            created.append(folder.name)

        save_library_paths([str(roms)])
        return True, str(roms), created
    except OSError as e:
        return False, f"Couldn't create the library: {e}", []


def _first_key_line(path: Path) -> str | None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    except (OSError, ValueError):
        return None
    return None


def key_file_target() -> Path:
    return CONFIG_DIR / KEY_FILENAMES[0]


def save_key_file(key: str) -> tuple[bool, str]:
    target = key_file_target()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(key.strip() + "\n", encoding="utf-8")
        os.chmod(target, 0o600)
        return True, str(target)
    except OSError as e:
        return False, f"Can't write {target}: {e}"


def key_search_paths() -> list[Path]:
    """Folders checked for a library key, for reporting when none is found."""
    out = []
    for root in discover_roots():
        emulation = emulation_dir_for(root)
        for directory in (emulation, Path(root)):
            if directory not in out:
                out.append(directory)
    return out


def import_library_key(force: bool = False) -> tuple[str, str] | None:
    """Adopt a key sitting beside the library, leaving the original in place —
    a library synced across devices carries its key with it and every device
    imports from that same file.

    Normally only runs when config has no key. `force` re-imports regardless,
    which is what the Reload button needs: without it there is no way to pick
    up a corrected file once anything at all has been saved.
    """
    if not force and find_key_file():
        return None
    for directory in key_search_paths():
        for source in key_files_in(directory):
            key = _first_key_line(source)
            if not key:
                continue
            ok, _ = save_key_file(key)
            return (key, str(source)) if ok else None
    return None


def find_key_file() -> tuple[str, str] | None:
    for source in key_files_in(CONFIG_DIR):
        key = _first_key_line(source)
        if key:
            return key, str(source)
    return None


# --------------------------------------------------------------------------
# Title cleaning and candidate ranking
# --------------------------------------------------------------------------
_PAREN = re.compile(r"\([^)]*\)")
_BRACKET = re.compile(r"\[[^\]]*\]")
_WS = re.compile(r"\s+")
_ARTICLE = re.compile(
    r"^(.*?),\s*(The|A|An|Le|La|Les|Los|Der|Die|Das|El)(\s*(?:[-–—:]\s*.*)?)$",
    re.IGNORECASE,
)


def clean_title(filename: str) -> str:
    """'Super Mario 64 (USA) [!].z64' -> 'Super Mario 64'"""
    return tidy_title(Path(filename).stem)


def tidy_title(s: str) -> str:
    """Tidy an already-extensionless title.

    Separate from clean_title because Path().stem must not touch a title that
    never was a filename: it reads 'Galaga (Namco rev. B)' as having a '.B)'
    extension and truncates it.
    """
    s = _PAREN.sub(" ", s)
    s = _BRACKET.sub(" ", s)
    s = s.replace("_", " ")
    if " " not in s and s.count(".") >= 2:
        s = s.replace(".", " ")
    s = _WS.sub(" ", s).strip(" -–—,._")
    m = _ARTICLE.match(s)
    if m:
        s = _WS.sub(" ", f"{m.group(2)} {m.group(1)}{m.group(3)}").strip()
    return s


# SteamGridDB has no console-platform filter — its "platform" means the store a
# game came from — so candidates are ranked here rather than taking the first.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_LEADING_ARTICLE = re.compile(r"^(the|a|an)\s+")


def normalize_for_match(s: str) -> str:
    s = _NON_ALNUM.sub(" ", s.casefold()).strip()
    return _LEADING_ARTICLE.sub("", s)


def score_match(query: str, candidate: str) -> float:
    q, c = normalize_for_match(query), normalize_for_match(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    ratio = difflib.SequenceMatcher(None, q, c).ratio()
    if c.startswith(q + " ") or q.startswith(c + " "):
        ratio = max(ratio, 0.9)
    return ratio


def rank_candidates(query: str, candidates: list[dict]) -> list[dict]:
    scored = [dict(c, score=round(score_match(query, c.get("name", "")), 3))
              for c in candidates]
    scored.sort(key=lambda c: -c["score"])
    return scored


def pick_best(query: str, candidates: list[dict], threshold: float = 0.6):
    """Returning None is deliberate: a blank cover beats confidently wrong art."""
    ranked = rank_candidates(query, candidates)
    if ranked and ranked[0]["score"] >= threshold:
        return ranked[0]
    return None


# --------------------------------------------------------------------------
# Scanning
# --------------------------------------------------------------------------
_PAREN_GROUP = re.compile(r"\([^)]*\)")


def _tags(filename: str) -> list[str]:
    """The parenthetical groups in a filename, in order: ['(USA)', '(Rev 1)']."""
    return _PAREN_GROUP.findall(Path(filename).stem)


def _disambiguate(members: list[dict]) -> None:
    """Give colliding titles back the tags that tell them apart.

    Region and revision tags are stripped from titles because they are noise —
    right up until two files clean to the same name, at which point they are
    the only thing distinguishing a USA release from a Japanese one. Dropping
    one silently loses a game; keeping both with identical names is unusable.
    Only the tags that actually differ are added back, so a collision between
    (USA) and (Japan) does not also drag in (Rev 1) that they share.
    """
    tag_sets = [set(_tags(m["filename"])) for m in members]
    common = set.intersection(*tag_sets) if tag_sets else set()

    for member, tags in zip(members, tag_sets):
        distinct = [t for t in _tags(member["filename"]) if t not in common]
        if distinct:
            member["title"] = f"{member['title']} {' '.join(distinct)}".strip()

    # Still colliding — nothing in the names separates them, so fall back to
    # the filename itself rather than dropping anything.
    seen: dict[str, int] = {}
    for member in members:
        key = member["title"].casefold()
        seen[key] = seen.get(key, 0) + 1
    for member in members:
        if seen[member["title"].casefold()] > 1:
            member["title"] = Path(member["filename"]).stem

@dataclass
class RomEntry:
    rom_path: str
    system_key: str
    system_label: str
    title: str
    root: str
    system_dir: str = ""
    filename: str = ""
    sgdb_id: int | None = None
    exe: str = FLATPAK_BIN
    launch_options: str = ""
    emulator: str = ""
    resolved: bool = False
    reason: str = ""

    @property
    def uid(self) -> str:
        return uid_for(self.rom_path)


# Artwork placed beside the ROMs in per-asset subfolders overrides everything
# else. This is the familiar shape (ES-DE and friends do the same) and the
# easiest to work with: drop a replacement PNG in and it wins on the next sync,
# with no plugin involvement and no SteamGridDB id to hunt down.
#
#   <system>/media/grid/<rom name>.png
#   <system>/media/hero/<rom name>.png
#
MEDIA_DIR = "media"
MEDIA_EXTS = (".png", ".jpg", ".jpeg")


def media_dir_for(system_dir: str, asset: str) -> Path:
    return Path(system_dir) / MEDIA_DIR / asset


def media_path_for(system_dir: str, asset: str, rom_path: str,
                   ext: str = ".png") -> Path:
    return media_dir_for(system_dir, asset) / (Path(rom_path).stem + ext)


def find_local_art(rom_path: str, system_key: str, asset: str,
                   system_dir: str | None = None) -> str | None:
    """Existing artwork for one slot, newest layout first.

    The per-asset layout is checked before the older flat ones: it is the one
    a user is most likely to be curating by hand, so it should win over
    anything left from an earlier convention.
    """
    rom = Path(rom_path)
    directory = system_dir or system_dir_for(rom_path)

    candidates: list[Path] = []
    for ext in MEDIA_EXTS:
        candidates.append(media_path_for(directory, asset, rom_path, ext))
    for ext in MEDIA_EXTS:
        candidates.append(rom.parent / MEDIA_DIR / f"{rom.stem}.{asset}{ext}")
    for root in discover_roots():
        for ext in MEDIA_EXTS:
            candidates.append(Path(root) / "art" / system_key /
                              f"{rom.stem}.{asset}{ext}")

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def set_system_core(system_dir: Path, core: str) -> tuple[bool, str]:
    """Point a system at a different libretro core.

    Edits the raw file line by line and replaces only the `-L` argument,
    rather than regenerating the file from parsed values. Two things survive
    that would otherwise be lost: any flags someone added to the command by
    hand — a custom config path, fullscreen, a different runtime — and any
    comments they wrote around it. The file stays theirs; this only changes
    the one token the picker is about.
    """
    path = override_path(system_dir)
    try:
        original = path.read_text(encoding="utf-8")
    except OSError as e:
        return False, f"Can't read {path}: {e}"

    resolved = find_core(core) or str(CORE_DIR / core_filename(core))
    lines = original.splitlines(keepends=True)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.strip().casefold() != "command":
            continue

        old = command_core(value.strip())
        if not old:
            return False, ("This system doesn't launch through RetroArch, so "
                           "there is no core to change. Edit the command in "
                           f"{OVERRIDE_FILENAME} instead.")
        if old == resolved:
            return True, str(path)

        lines[i] = line.replace(old, resolved)
        try:
            tmp = tmp_path(path)
            tmp.write_text("".join(lines), encoding="utf-8")
            os.replace(tmp, path)
            return True, str(path)
        except OSError as e:
            return False, f"Can't write {path}: {e}"

    return False, f"No command line found in {path}."


def system_dir_for(rom_path: str, roots: list[str] | None = None) -> str:
    """The system folder a ROM belongs to — the direct child of a scan root.

    Derived rather than remembered. A ROM's parent directory is the wrong
    answer whenever games live in subfolders (ScummVM keeps each game in its
    own folder), and deriving it also fixes manifest entries written before the
    system folder was recorded, without needing a migration.
    """
    real = os.path.realpath(rom_path)
    for root in (roots if roots is not None else discover_roots()):
        root_real = os.path.realpath(root)
        try:
            relative = Path(real).relative_to(root_real)
        except ValueError:
            continue
        if relative.parts:
            return str(Path(root_real) / relative.parts[0])
    return str(Path(real).parent)


def uid_for(rom_path: str) -> str:
    return hashlib.sha1(os.path.realpath(rom_path).encode("utf-8")).hexdigest()[:16]


def _iter_files(base: Path, depth: int = 0) -> Iterable[Path]:
    if depth > MAX_DEPTH:
        return
    try:
        children = list(base.iterdir())
    except (PermissionError, OSError):
        return
    for child in children:
        if child.is_dir():
            if child.name.casefold() in SKIP_DIRS:
                continue
            yield from _iter_files(child, depth + 1)
        elif child.is_file():
            yield child


def collect_m3u_members(system_dir: Path) -> set[str]:
    """Absolute realpaths of every file referenced by an .m3u under this system."""
    members: set[str] = set()
    for f in _iter_files(system_dir):
        if f.suffix.casefold() != ".m3u":
            continue
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            target = (f.parent / line) if not os.path.isabs(line) else Path(line)
            members.add(os.path.realpath(target))
    return members


def iter_games(system_dir: Path, extensions: Iterable[str],
               folders: bool = False) -> Iterable[Path]:
    """Every game in a system folder, file or directory.

    Not every system stores a game as a single file. Daphne names the game
    directory itself (`lair.daphne/`); DOS, PS3 and Wii U keep a folder per
    game with the launchable file buried inside, where matching on extension
    finds SETUP.EXE and EBOOT.BIN rather than the game. Two forms cover both:

    - a directory whose name ends in a configured extension is a game
    - `folders = yes` in .romsync.txt makes every immediate subdirectory one
      game, named after the folder

    Both hand the directory itself to the emulator, which is what the ones
    that work this way expect.
    """
    exts = {e.casefold() for e in extensions}
    system_dir = Path(system_dir)

    if folders:
        try:
            for child in sorted(system_dir.iterdir()):
                if child.is_dir() and child.name.casefold() not in SKIP_DIRS:
                    yield child
        except OSError:
            return
        return

    # Directories named like a ROM, e.g. lair.daphne
    try:
        for child in sorted(system_dir.iterdir()):
            if child.is_dir() and child.suffix.casefold() in exts:
                yield child
    except OSError:
        pass

    if not exts:
        return
    skip = collect_m3u_members(system_dir)
    for f in _iter_files(system_dir):
        suffix = f.suffix.casefold()
        if suffix not in exts and suffix != ".m3u":
            continue
        if os.path.realpath(f) in skip:
            continue
        yield f


def count_roms(system_dir: Path, extensions: Iterable[str],
               folders: bool = False) -> int:
    """How many games are in a folder."""
    return sum(1 for _ in iter_games(system_dir, extensions, folders))


def detect_systems(roots: list[str] | None = None,
                   include_empty: bool = False) -> list[dict]:
    """Systems present on disk, including folders defined purely by their own
    .romsync.txt.

    Empty folders are excluded by default: a freshly created library, or a
    folder kept for later, is not something to toggle or to nag about a
    missing core for.
    """
    roots = roots if roots is not None else discover_roots()
    # Globs three directories; hoisted because it does not vary per system.
    installed = set(installed_cores())
    seen: dict[str, dict] = {}
    for root in roots:
        try:
            children = sorted(p for p in Path(root).iterdir() if p.is_dir())
        except OSError:
            continue
        for child in children:
            if child.name.casefold() in SKIP_DIRS:
                continue
            system = SYSTEM_BY_ALIAS.get(child.name.casefold())
            config, missing = ensure_folder_config(child, system)
            if not config.system or not config.command:
                if system is None:
                    continue
            key = system.key if system else child.name.casefold()
            if key in seen:
                continue
            exts = config.extensions or (system.exts if system else [])
            games = count_roms(child, exts, config.folders)
            if games == 0 and not include_empty:
                continue
            # What this system actually launches with, for the emulator
            # readout: a core name when the command runs RetroArch, otherwise
            # the program itself, which is how a custom command shows up.
            core = command_core(config.command) if config.command else None
            if core:
                emulator = Path(core).name.replace("_libretro.so", "")
                kind = "core"
            elif config.command:
                try:
                    parts = shlex.split(config.command)
                except ValueError:
                    parts = []
                emulator = next(
                    (p for p in parts[1:] if "." in p and "/" not in p),
                    Path(parts[0]).name if parts else "")
                kind = "emulator"
            else:
                emulator, kind = "", ""

            # Cores worth offering for this system, each flagged with whether
            # it is actually present. Uninstalled ones are still offered: on a
            # fresh setup only one core exists, so an installed-only list would
            # leave nothing to choose between. Picking a missing one flags it,
            # and the Install button on the same page then fetches it.
            options = []
            if system and kind == "core":
                current = emulator
                for name in system.cores:
                    options.append({"core": name, "installed": name in installed})
                if current and current not in system.cores:
                    options.insert(0, {"core": current,
                                       "installed": current in installed})

            seen[key] = {
                "key": key,
                "label": config.system or (system.label if system else child.name),
                "core_options": options,
                "folder": str(child),
                "games": games,
                "missing_core": missing,
                "has_command": bool(config.command),
                "emulator": emulator,
                # The command as written, plus where it lives. "Why won't this
                # launch" is answered by reading the line far more often than
                # by rewriting it, and the path says where to go if it isn't.
                "command": config.command,
                "config_file": str(override_path(child)),
            }
    return sorted(seen.values(), key=lambda s_: s_["label"].casefold())


def survey(roots: list[str] | None = None) -> dict:
    """Everything the panel needs about the library, from one pass.

    detect_systems walks every file in every folder, so calling it once per
    question meant five walks — and fifteen count_roms calls for three folders
    — every time the panel opened.
    """
    roots = roots if roots is not None else discover_roots()
    everything = detect_systems(roots, include_empty=True)
    with_games = [d for d in everything if d["games"] > 0]
    return {
        "roots": roots,
        "systems": with_games,
        "empty_folders": [d["label"] for d in everything if d["games"] == 0],
        "missing_cores": sorted({d["missing_core"] for d in with_games
                                 if d.get("missing_core")}),
        "unknown_folders": unrecognised_folders(roots, everything),
    }


def unrecognised_folders(roots: list[str] | None = None,
                         known_systems: list[dict] | None = None) -> list[str]:
    """Folders holding files that the plugin can't place.

    Silently skipping these is the wrong behaviour: from outside it looks like
    the plugin lost your games. Naming them points at the fix — either the
    folder name isn't one we know, or it needs its own .romsync.txt.
    """
    roots = roots if roots is not None else discover_roots()
    known = {d["key"] for d in (known_systems
                                if known_systems is not None
                                else detect_systems(roots, include_empty=True))}
    out: list[str] = []
    for root in roots:
        try:
            children = sorted(p for p in Path(root).iterdir() if p.is_dir())
        except OSError:
            continue
        for child in children:
            if child.name.casefold() in SKIP_DIRS:
                continue
            if SYSTEM_BY_ALIAS.get(child.name.casefold()):
                continue
            if child.name.casefold() in known:
                continue
            config = load_folder_config(child)
            if config.system and config.command:
                continue
            if any(True for _ in _iter_files(child)):
                out.append(child.name)
    return out


def scan(roots: list[str] | None = None,
         arcade_names: "arcade.ArcadeNames | None" = None
         ) -> tuple[list[RomEntry], list[str], set[str]]:
    """Returns (entries, notes, excluded_uids)."""
    roots = roots if roots is not None else discover_roots()
    notes: list[str] = []
    entries: list[RomEntry] = []
    excluded: set[str] = set()
    candidates: list[dict] = []

    for root in roots:
        root_path = Path(root)
        try:
            sysdirs = sorted(p for p in root_path.iterdir() if p.is_dir())
        except OSError as e:
            notes.append(f"Can't read {root}: {e}")
            continue

        for sysdir in sysdirs:
            if sysdir.name.casefold() in SKIP_DIRS:
                continue
            system = SYSTEM_BY_ALIAS.get(sysdir.name.casefold())
            config, _missing = ensure_folder_config(sysdir, system)

            if not config.system:
                notes.append(f"Skipped {sysdir.name}: no system name in "
                             f"{OVERRIDE_FILENAME}.")
                continue

            system_key = system.key if system else sysdir.name.casefold()
            exts = config.extensions or (system.exts if system else [])
            if not exts and not config.folders:
                notes.append(f"Skipped {config.system}: no file extensions "
                             f"known. Add an 'extensions' line to "
                             f"{OVERRIDE_FILENAME}.")
                continue

            for f in sorted(iter_games(sysdir, exts, config.folders)):
                real = os.path.realpath(f)
                ov = config.games.get(f.name.casefold(), {})
                if ov.get("exclude"):
                    excluded.add(uid_for(real))
                    continue

                title = str(ov.get("title") or "").strip()
                if not title and arcade_names is not None \
                        and system_key in arcade.ARCADE_SYSTEMS:
                    dat_title = arcade_names.lookup(f.name)
                    if dat_title:
                        title = tidy_title(dat_title)
                if not title:
                    title = clean_title(f.name)
                if not title:
                    continue

                sgdb_id = ov.get("sgdb_id")
                candidates.append({
                    "title": title,
                    "filename": f.name,
                    "rom_path": real,
                    "system_key": system_key,
                    "system_label": config.system,
                    "root": root,
                    "system_dir": str(sysdir),
                    "sgdb_id": int(sgdb_id) if sgdb_id else None,
                    "config": config,
                })

    for member in _resolve_collisions(candidates, notes):
        config = member.pop("config")
        entry = RomEntry(
            rom_path=member["rom_path"],
            system_key=member["system_key"],
            system_label=member["system_label"],
            title=member["title"],
            root=member["root"],
            system_dir=member["system_dir"],
            filename=member["filename"],
            sgdb_id=member["sgdb_id"],
        )
        _apply_command(entry, config, notes)
        entries.append(entry)
    return entries, notes, excluded


def _resolve_collisions(candidates: list[dict], notes: list[str]) -> list[dict]:
    """Separate genuine duplicates from same-named different games.

    The same filename under two roots is one game on two drives — internal
    wins, as before. Different filenames that merely clean to the same title
    are different games, and get their distinguishing tags back.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for member in candidates:
        groups.setdefault(
            (member["system_key"], member["title"].casefold()), []).append(member)

    kept: list[dict] = []
    for group in groups.values():
        if len(group) == 1:
            kept.extend(group)
            continue

        by_filename: dict[str, list[dict]] = {}
        for member in group:
            by_filename.setdefault(member["filename"].casefold(), []).append(member)

        unique: list[dict] = []
        for same_name in by_filename.values():
            unique.append(same_name[0])
            for extra in same_name[1:]:
                notes.append(
                    f"Duplicate skipped: {extra['title']} "
                    f"({extra['system_label']}) also at {extra['rom_path']}")

        if len(unique) > 1:
            _disambiguate(unique)
            notes.append(
                f"Same name in {unique[0]['system_label']}: kept "
                + ", ".join(m["title"] for m in unique))
        kept.extend(unique)
    return kept


def _executable_exists(exe: str) -> bool:
    """Whether a command's program is actually present.

    Absolute paths are checked directly; a bare name is looked up on PATH,
    since a hand-written command may reasonably use one.
    """
    if not exe:
        return False
    if os.path.isabs(exe):
        return os.path.isfile(exe) and os.access(exe, os.X_OK)
    return shutil.which(exe) is not None


def _apply_command(entry: RomEntry, config: FolderConfig,
                   notes: list[str]) -> None:
    """Turn the folder's command line into a Steam shortcut's exe and args."""
    if not config.command:
        entry.reason = (f"No launch command for {config.system}. Add one to "
                        f"{OVERRIDE_FILENAME} in that folder.")
        return

    # A command with no {rom} builds the same shortcut for every file in the
    # folder, launching the emulator with nothing loaded. It is never what
    # someone meant, and it fails silently at launch rather than at sync, so
    # catch it here.
    if ROM_TOKEN not in config.command:
        entry.reason = (f"The command for {config.system} has no {ROM_TOKEN} "
                        f"in it, so no ROM would be passed. Add it in "
                        f"{OVERRIDE_FILENAME}.")
        return

    command = config.command
    core = command_core(command)
    if core:
        found = find_core(core)
        if not found:
            entry.reason = (f"Core {Path(core).name} is not installed.")
            return
        if found != core:
            # Self-healing: the file names a path that moved. Use the core we
            # found without rewriting the file, so a hand edit is never lost.
            command = command.replace(core, found)
            note = f"{config.system}: core moved, using {found}"
            if note not in notes:
                notes.append(note)

    split = split_command(command, entry.rom_path)
    if split is None:
        entry.reason = f"Couldn't read the command for {config.system}."
        return

    # A core that is missing gets reported; a plain emulator that is missing
    # used to sync fine and fail on launch. Same failure, so same treatment.
    exe = split[0]
    if not core and not _executable_exists(exe):
        entry.reason = (f"{exe} isn't installed, so {config.system} can't "
                        f"launch. Install it, or point the command in "
                        f"{OVERRIDE_FILENAME} somewhere else.")
        return

    entry.exe, entry.launch_options = split
    entry.emulator = Path(core).name if core else Path(entry.exe).name
    entry.resolved = True




# --------------------------------------------------------------------------
# Flatpak detection
# --------------------------------------------------------------------------
def _run(cmd: list[str], timeout: int = 20) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.SubprocessError) as e:
        return 1, "", str(e)


def _flatpak_bin() -> str | None:
    which = shutil.which("flatpak")
    if which:
        return which
    for cand in (FLATPAK_BIN, "/bin/flatpak",
                 "/var/lib/flatpak/exports/bin/flatpak"):
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def installed_flatpaks() -> set[str]:
    """Filesystem first, `flatpak list` second. The plugin runs with a minimal
    environment where flatpak may not be on PATH at all, and a failed subprocess
    is indistinguishable from nothing being installed."""
    found: set[str] = set()
    for base in FLATPAK_APP_DIRS:
        try:
            for entry in base.iterdir():
                if entry.is_dir() and "." in entry.name:
                    found.add(entry.name)
        except (OSError, PermissionError):
            continue
    exe = _flatpak_bin()
    if exe:
        rc, out, _ = _run([exe, "list", "--app", "--columns=application"])
        if rc == 0:
            found.update(l.strip() for l in out.splitlines() if l.strip())
    return found


def install_retroarch() -> tuple[bool, str]:
    """User scope deliberately: a system-scope install won't survive a SteamOS
    update, and user scope needs no password."""
    exe = _flatpak_bin()
    if not exe:
        return False, "Can't find the flatpak command."
    rc, out, err = _run(
        [exe, "install", "--user", "--noninteractive", "--assumeyes",
         "flathub", RETROARCH_ID],
        timeout=1800,
    )
    if rc == 0:
        return True, "RetroArch installed."
    return False, (err or out or "flatpak install failed").strip()


# --------------------------------------------------------------------------
# Manifest — records only shortcuts we created, so mirror sync never touches
# a shortcut the user added by hand.
# --------------------------------------------------------------------------
class Manifest:
    """What this plugin created, so mirror sync never touches anything else.

    Reached from the event loop (commit) and from worker threads (build_plan's
    scan), so mutation is guarded. Without the lock, a reload on one thread
    could rebind `data` between another's mutation and its save, silently
    reverting the write — unreachable through the current UI, but only by
    accident of call ordering.
    """

    ART_SLOTS = ("grid", "hero", "logo", "wide", "icon")

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data: dict[str, dict] = {}
        self._lock = threading.RLock()
        self.load()

    def load(self) -> None:
        with self._lock:
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.data = {}

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = tmp_path(self.path)
            tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)

    def update(self, changes: dict[str, dict], removed: Iterable[str]) -> int:
        """Apply a batch and persist it, without another caller reloading in
        between. The only way manifest state should ever be written."""
        with self._lock:
            self.load()
            self.data.update(changes)
            for uid in removed:
                self.data.pop(uid, None)
            self.save()
            return len(self.data)

    def plan(self, entries: list[RomEntry], excluded: set[str] | None = None,
             disabled_systems: set[str] | None = None) -> dict:
        """Diff desired state against what we created last run."""
        excluded = excluded or set()
        disabled_systems = disabled_systems or set()
        desired = {e.uid: e for e in entries if e.resolved}
        add, update, remove, artwork = [], [], [], []

        for uid, e in desired.items():
            prev = self.data.get(uid)
            if prev is None:
                add.append(asdict(e) | {"uid": uid})
                continue
            if (prev.get("launch_options") != e.launch_options
                    or prev.get("title") != e.title
                    or prev.get("exe") != e.exe):
                update.append(asdict(e) | {"uid": uid, "appid": prev.get("appid")})
            # Artwork is recorded per slot, so a library synced before the key
            # worked can be filled in without touching anything else. Only the
            # missing slots are fetched.
            have = set(prev.get("art") or [])
            if not have and prev.get("appid"):
                artwork.append(asdict(e) | {
                    "uid": uid, "appid": prev.get("appid"), "have": sorted(have)})

        for uid, prev in self.data.items():
            if uid in desired:
                continue
            # Three reasons to remove: the file is gone, the user excluded it,
            # or its system was switched off. A ROM that merely failed to
            # resolve is left alone — a missing core shouldn't nuke a library.
            gone = not os.path.exists(prev.get("rom_path", ""))
            off = prev.get("system_key") in disabled_systems
            if gone or uid in excluded or off:
                why = ("file missing" if gone
                       else "excluded" if uid in excluded
                       else "system turned off")
                remove.append(prev | {"uid": uid, "why": why})

        return {"add": add, "update": update, "remove": remove,
                "artwork": artwork}
