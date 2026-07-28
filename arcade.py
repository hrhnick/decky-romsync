"""
Arcade ROM name resolution.

Arcade ROMs are named by MAME set short-name — `sf2ce.zip`, `mslug.zip`,
`10yard.zip` — so there is nothing in the filename to clean up. The real title
only exists in a DAT file, which maps a zip back to the game it belongs to.

Source is libretro-database's consolidated MAME DAT (clrmamepro format). Note
the mapping runs the opposite way to what the field names suggest:

    game (
        name "10-Yard Fight (World, set 1)"     <- the title
        rom ( name 10yard.zip ... )             <- the file on disk
    )

Downloaded once and reduced to a compact JSON map. No decky import, so this is
testable off-device.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request

from sgdb import DEFAULT_HEADERS, ssl_context
from pathlib import Path

DAT_URL = (
    "https://raw.githubusercontent.com/libretro/libretro-database/master/"
    "metadat/mame/MAME.dat"
)

# Systems whose filenames are set names rather than titles.
ARCADE_SYSTEMS = {"arcade", "neogeo"}

_NAME_LINE = re.compile(r'^\s*name\s+"(.+)"\s*$')
_ROM_LINE = re.compile(r'^\s*rom\s*\(\s*name\s+(\S+?\.zip)\b', re.IGNORECASE)


def parse_dat(text: str) -> dict[str, str]:
    """{set name without extension (casefolded): full title}"""
    mapping: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("game ("):
            current = None
            continue
        m = _NAME_LINE.match(line)
        if m and current is None:
            current = m.group(1)
            continue
        m = _ROM_LINE.match(line)
        if m and current:
            stem = Path(m.group(1)).stem.casefold()
            # First title wins; later duplicates are usually clones sharing a
            # parent's ROM entries.
            mapping.setdefault(stem, current)
    return mapping


class ArcadeNames:
    """Lazy, cached lookup. Absent data degrades to the raw filename."""

    def __init__(self, cache_dir: Path):
        self.path = Path(cache_dir) / "arcade-names.json"
        self._map: dict[str, str] | None = None

    def _ensure(self) -> dict[str, str]:
        if self._map is None:
            try:
                self._map = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._map = {}
        return self._map

    @property
    def available(self) -> bool:
        return bool(self._ensure())

    def lookup(self, filename: str) -> str | None:
        stem = Path(filename).stem.casefold()
        return self._ensure().get(stem)

    def refresh(self, timeout: int = 60) -> tuple[bool, str]:
        """Download and reduce the DAT. Returns (ok, message)."""
        try:
            request = urllib.request.Request(DAT_URL, headers=DEFAULT_HEADERS)
            with urllib.request.urlopen(
                    request, timeout=timeout, context=ssl_context()) as r:
                text = r.read().decode("utf-8", errors="replace")
        except OSError as e:
            return False, f"Couldn't download the arcade name list: {e}"

        mapping = parse_dat(text)
        if not mapping:
            return False, "Arcade name list downloaded but contained no entries."

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(f".{os.getpid()}.tmp")
            tmp.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as e:
            return False, f"Couldn't save the arcade name list: {e}"

        self._map = mapping
        return True, f"{len(mapping)} arcade titles available."
