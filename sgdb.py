"""
SteamGridDB client with throttling, retry and a disk cache.

Free of any `decky` import so it can be unit-tested off-device. All methods are
synchronous by design: main.py calls them through asyncio.to_thread, and the
throttle lock only has to be correct for plain threads, not for a mix of
threads and coroutines.

Cache layout (keyed so a re-sync or a reset-then-resync is nearly free):

    <cache_dir>/search/<sha1(title)>.json     search result, incl. misses
    <cache_dir>/art/<game_id>/<asset>.png     the chosen image bytes
    <cache_dir>/art/<game_id>/<asset>.miss    SGDB has no image of this type

Negative caching matters as much as positive: a library with obscure ROMs would
otherwise re-ask SGDB the same unanswerable questions on every sync. Misses
expire after MISS_TTL so newly uploaded art does eventually appear.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import ssl
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger("romsync.sgdb")

BASE = "https://www.steamgriddb.com/api/v2"

# SteamGridDB sits behind Cloudflare, which answers urllib's default
# "Python-urllib/3.x" User-Agent with a 403 before the request ever reaches the
# API. That looks exactly like a rejected key, so send a real identifier.
USER_AGENT = "ROMSync/0.1 (Decky plugin; libretro ROM library sync)"
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}

# Sustained requests per second shared across all workers, with a small burst
# allowance. A fixed sleep between requests can't be shared, so concurrency
# would multiply the real rate; a token bucket keeps the budget global no
# matter how many threads are pulling from it.
RATE_PER_SEC = 8.0
BURST = 16
MAX_RETRIES = 2
BACKOFF_BASE = 2.0        # 429/5xx waits: 2s, 4s (or Retry-After if given)
BACKOFF_CAP = 10.0
REQUEST_TIMEOUT = 15      # a stalled socket must not hold up a whole batch
MISS_TTL = 7 * 24 * 3600  # a week

ASSET_ENDPOINTS = {
    "grid": "/grids/game/{id}?dimensions=600x900",
    "wide": "/grids/game/{id}?dimensions=920x430",
    "hero": "/heroes/game/{id}",
    "logo": "/logos/game/{id}",
    "icon": "/icons/game/{id}",
}


# --------------------------------------------------------------------------
# TLS
# --------------------------------------------------------------------------
# Decky runs plugins with a trimmed environment, and Python's default
# verification can end up with no CA bundle at all — every HTTPS request then
# fails with CERTIFICATE_VERIFY_FAILED. Locate a bundle explicitly instead of
# assuming the default works.
CA_BUNDLE_PATHS = (
    "/etc/ssl/certs/ca-certificates.crt",     # Arch / SteamOS, Debian
    "/etc/pki/tls/certs/ca-bundle.crt",       # Fedora / RHEL
    "/etc/ssl/ca-bundle.pem",                 # SUSE
    "/etc/ssl/cert.pem",                      # BSD / macOS
    "/etc/ssl/certs/ca-bundle.crt",
)

_ssl_ctx = None


def ssl_context() -> ssl.SSLContext:
    global _ssl_ctx
    if _ssl_ctx is not None:
        return _ssl_ctx

    for env in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        candidate = os.environ.get(env)
        if candidate and os.path.isfile(candidate):
            _ssl_ctx = ssl.create_default_context(cafile=candidate)
            return _ssl_ctx

    try:
        import certifi
        _ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        return _ssl_ctx
    except Exception:  # noqa: BLE001 - certifi is optional
        pass

    for path in CA_BUNDLE_PATHS:
        if os.path.isfile(path):
            _ssl_ctx = ssl.create_default_context(cafile=path)
            return _ssl_ctx

    if os.path.isdir("/etc/ssl/certs"):
        ctx = ssl.create_default_context()
        try:
            ctx.load_verify_locations(capath="/etc/ssl/certs")
            _ssl_ctx = ctx
            return _ssl_ctx
        except OSError:
            pass

    _ssl_ctx = ssl.create_default_context()
    return _ssl_ctx


def describe_tls() -> str:
    """Where the trust store came from, for diagnostics."""
    for env in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        v = os.environ.get(env)
        if v and os.path.isfile(v):
            return f"{env}={v}"
    try:
        import certifi
        return f"certifi at {certifi.where()}"
    except Exception:  # noqa: BLE001
        pass
    for path in CA_BUNDLE_PATHS:
        if os.path.isfile(path):
            return path
    if os.path.isdir("/etc/ssl/certs"):
        return "/etc/ssl/certs (directory)"
    return "no CA bundle found"


class RateLimited(Exception):
    """Raised only after retries are exhausted."""


def _peek(e, limit: int = 160) -> str:
    """A short, single-line excerpt of an error response body."""
    try:
        raw = e.read()
    except Exception:  # noqa: BLE001
        return ""
    text = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(text)
        for key in ("errors", "message", "error"):
            if key in data:
                return str(data[key])[:limit]
    except ValueError:
        pass
    return " ".join(text.split())[:limit]


def _looks_like_cloudflare(body: str) -> bool:
    lowered = body.lower()
    return any(marker in lowered for marker in
               ("cloudflare", "attention required", "cf-ray", "just a moment"))


class AuthFailed(Exception):
    """SteamGridDB rejected the API key."""


class Unavailable(Exception):
    """Request failed for a reason that is not a genuine empty result.

    Kept distinct from an empty response on purpose: treating a failure as
    "this game has no artwork" is both a wrong message to the user and, once
    cached, a wrong answer that persists long after the cause is fixed.
    """


class TokenBucket:
    def __init__(self, rate: float, burst: int):
        self.rate = rate
        self.capacity = float(burst)
        self.tokens = float(burst)
        self.updated = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(
                    self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait = (1.0 - self.tokens) / self.rate
            time.sleep(wait)


class SgdbClient:
    def __init__(self, cache_dir: Path, key_getter):
        """key_getter: callable returning the current API key, so a key changed
        in settings takes effect without rebuilding the client."""
        self.cache_dir = Path(cache_dir)
        self._key_getter = key_getter
        self._bucket = TokenBucket(RATE_PER_SEC, BURST)

    # -- public -------------------------------------------------------------

    def search(self, title: str) -> list[dict]:
        """Ranked-input candidates [{id, name}], from cache when possible."""
        cache = self.cache_dir / "search" / (_sha1(title.casefold()) + ".json")
        cached = _read_cache_json(cache)
        if cached is not None:
            return cached["items"]

        # Anything that isn't a real answer raises out of here rather than
        # degrading to []. Only genuine responses are cached.
        data = self._request_json(
            f"/search/autocomplete/{urllib.parse.quote(title)}")
        items = [{"id": i["id"], "name": i.get("name", "")}
                 for i in ((data or {}).get("data") or [])]
        _write_cache_json(cache, {"items": items, "at": time.time()})
        return items

    def game_details(self, game_id: int) -> dict:
        """Name and release year for one game.

        The autocomplete endpoint returns only id, name, types and verified —
        no date — so a year costs one extra request per candidate. Cached like
        everything else, so it is paid once per game ever.
        """
        cache = self.cache_dir / "games" / f"{int(game_id)}.json"
        cached = _read_cache_json(cache)
        if cached is not None:
            return cached.get("game") or {}

        data = self._request_json(f"/games/id/{int(game_id)}")
        game = (data or {}).get("data") or {}
        if isinstance(game, list):
            game = game[0] if game else {}
        out = {"name": game.get("name", "")}
        released = game.get("release_date")
        if isinstance(released, (int, float)) and released > 0:
            try:
                out["year"] = time.gmtime(released).tm_year
            except (ValueError, OSError):
                pass
        _write_cache_json(cache, {"game": out, "items": [out]})
        return out

    def get_asset(self, game_id: int, asset: str) -> bytes | None:
        """Image bytes for one slot, or None if SGDB has nothing. Cached."""
        art_dir = self.cache_dir / "art" / str(int(game_id))
        hit = art_dir / f"{asset}.png"
        miss = art_dir / f"{asset}.miss"

        if hit.is_file():
            try:
                return hit.read_bytes()
            except OSError:
                pass
        if miss.is_file() and not _expired(miss, MISS_TTL):
            return None

        data = self._request_json(ASSET_ENDPOINTS[asset].format(id=int(game_id)))
        items = (data or {}).get("data") or []
        url = items[0].get("url") if items else None
        if not url:
            _touch(miss)   # a real "SteamGridDB has none of these"
            return None

        try:
            blob = self._request_bytes(url)
        except (Unavailable, AuthFailed):
            return None    # transient: cache nothing so the next sync retries
        if blob is None:
            return None
        _write_bytes(hit, blob)
        _unlink(miss)
        return blob

    def check_key(self) -> tuple[bool, str]:
        """Round-trip a known-good search so key problems are reported as key
        problems rather than as every game missing."""
        try:
            items = self.search("Chrono Trigger")
        except AuthFailed as e:
            return False, str(e)
        except RateLimited as e:
            return False, str(e)
        except Unavailable as e:
            return False, str(e)
        if not items:
            return False, "SteamGridDB replied, but returned no results at all."
        return True, f"Key works — test search returned {len(items)} results."

    def get_thumb(self, game_id: int) -> bytes | None:
        """Small preview of a game's cover, for confirming a match by eye.

        Uses the thumbnail the grids endpoint already returns rather than the
        full image — a preview is 20-50KB against several hundred.
        """
        cache = self.cache_dir / "thumbs" / f"{int(game_id)}.png"
        if cache.is_file():
            try:
                return cache.read_bytes()
            except OSError:
                pass
        data = self._request_json(
            f"/grids/game/{int(game_id)}?dimensions=600x900")
        items = (data or {}).get("data") or []
        url = (items[0].get("thumb") or items[0].get("url")) if items else None
        if not url:
            return None
        try:
            blob = self._request_bytes(url)
        except (Unavailable, AuthFailed):
            return None
        if blob:
            _write_bytes(cache, blob)
        return blob

    def purge_search_cache(self) -> int:
        n = 0
        d = self.cache_dir / "search"
        if d.is_dir():
            for f in d.glob("*.json"):
                try:
                    f.unlink()
                    n += 1
                except OSError:
                    pass
        return n

    def purge_cache(self) -> int:
        """Delete everything cached. Returns number of files removed."""
        n = 0
        if self.cache_dir.is_dir():
            for p in sorted(self.cache_dir.rglob("*"), reverse=True):
                try:
                    if p.is_file():
                        p.unlink()
                        n += 1
                    else:
                        p.rmdir()
                except OSError:
                    pass
        return n

    # -- transport ----------------------------------------------------------

    def _throttle(self):
        self._bucket.acquire()

    def _attempt(self, url: str, headers: dict) -> bytes:
        """One network attempt. Separated from _do so tests can fake the
        transport while exercising the real retry/backoff logic."""
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(
                req, timeout=REQUEST_TIMEOUT, context=ssl_context()) as r:
            return r.read()

    def _do(self, url: str, with_auth: bool):
        headers = dict(DEFAULT_HEADERS)
        if with_auth:
            key = self._key_getter() or ""
            headers["Authorization"] = f"Bearer {key}"

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            try:
                return self._attempt(url, headers)
            except urllib.error.HTTPError as e:
                if e.code == 429 or 500 <= e.code < 600:
                    retry_after = _retry_after_seconds(e) or (
                        BACKOFF_BASE * (2 ** attempt))
                    logger.warning("sgdb %s -> %s, retry in %.1fs",
                                   url, e.code, retry_after)
                    last_exc = e
                    time.sleep(min(retry_after, BACKOFF_CAP))
                    continue
                if e.code in (401, 403):
                    body = _peek(e)
                    # A 403 whose body is a Cloudflare challenge is a blocked
                    # request, not a bad key — different problem, different fix.
                    if e.code == 403 and _looks_like_cloudflare(body):
                        raise Unavailable(
                            "Cloudflare blocked the request before it reached "
                            "SteamGridDB. This is not a key problem."
                        ) from e
                    raise AuthFailed(
                        f"SteamGridDB rejected the key (HTTP {e.code})."
                        + (f" {body}" if body else "")) from e
                if e.code == 404:
                    return None   # genuinely nothing there
                logger.warning("sgdb %s -> %s", url, e.code)
                raise Unavailable(f"SteamGridDB returned {e.code}.") from e
            except ssl.SSLError as e:
                raise Unavailable(
                    f"TLS verification failed ({e}). Trust store: "
                    f"{describe_tls()}. Check the system clock is correct."
                ) from e
            except OSError as e:
                last_exc = e
                logger.warning("sgdb %s: %s", url, e)
                time.sleep(min(BACKOFF_BASE * (2 ** attempt), BACKOFF_CAP))
                continue

        if isinstance(last_exc, urllib.error.HTTPError) and last_exc.code == 429:
            raise RateLimited(
                "SteamGridDB is rate limiting us. Artwork will finish on a "
                "later sync — everything fetched so far is cached.")
        raise Unavailable(f"Couldn't reach SteamGridDB: {last_exc}")

    def _request_json(self, path: str):
        raw = self._do(BASE + path, with_auth=True)
        if raw is None:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError as e:
            raise Unavailable("SteamGridDB sent a malformed response.") from e

    def _request_bytes(self, url: str) -> bytes | None:
        # Image CDN, no auth header — don't leak the API key to a third host.
        return self._do(url, with_auth=False)


# -- cache helpers -----------------------------------------------------------

def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _expired(path: Path, ttl: float) -> bool:
    try:
        return (time.time() - path.stat().st_mtime) > ttl
    except OSError:
        return True


def _read_cache_json(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not data.get("items") and _expired(path, MISS_TTL):
        return None
    return data


def _tmp_for(path: Path) -> Path:
    """A temp path unique to this thread.

    Deriving it from the target alone races: the prefetch runs eight threads,
    and two games can resolve to the same SteamGridDB id — region variants of
    one game routinely do — so both would write the same `.tmp` and os.replace
    could publish a half-written image into a permanent cache.
    """
    return path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")


def _write_cache_json(path: Path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = _tmp_for(path)
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass  # cache is an optimization; never let it break the fetch


def _write_bytes(path: Path, blob: bytes):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = _tmp_for(path)
        tmp.write_bytes(blob)
        os.replace(tmp, path)
    except OSError:
        pass


def _touch(path: Path):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
    except OSError:
        pass


def _unlink(path: Path):
    try:
        path.unlink()
    except OSError:
        pass


def _retry_after_seconds(e) -> float | None:
    try:
        v = e.headers.get("Retry-After")
        return float(v) if v else None
    except (TypeError, ValueError):
        return None
