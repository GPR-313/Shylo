"""Shared plumbing for ARGUS data sources.

Every source client subclasses `Source`. The base handles the three things that
otherwise get reimplemented badly in each module: polite rate limiting, retry
with backoff, and an on-disk cache so a re-run of the morning brief during
development does not hammer a free API and get the key banned.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import requests

CACHE_DIR = Path(os.getenv("ARGUS_CACHE_DIR", ".cache"))
DEFAULT_TTL = int(os.getenv("ARGUS_CACHE_TTL", "3600"))  # seconds

# SEC and several government APIs require a descriptive UA with contact info.
USER_AGENT = os.getenv("ARGUS_USER_AGENT", "ARGUS/0.1 (research; set ARGUS_USER_AGENT)")


class SourceError(RuntimeError):
    """Raised when a source cannot be reached or returns something unusable."""


class Source:
    """Base class for a data source.

    Subclasses set `name`, `base_url`, and optionally `min_interval` (seconds
    between requests) and `ttl` (cache lifetime).
    """

    name: str = "source"
    base_url: str = ""
    min_interval: float = 0.2
    ttl: int = DEFAULT_TTL
    requires_key: str | None = None  # env var name, if the source needs one

    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._last_call = 0.0
        if self.requires_key and not os.getenv(self.requires_key):
            raise SourceError(
                f"{self.name} needs {self.requires_key} in the environment; "
                "copy .env.example to .env and fill it in"
            )

    # -- caching -----------------------------------------------------------

    def _cache_path(self, url: str, params: dict[str, Any] | None) -> Path:
        key = hashlib.sha256(
            (url + json.dumps(params or {}, sort_keys=True)).encode()
        ).hexdigest()[:20]
        return CACHE_DIR / self.name / f"{key}.json"

    def _read_cache(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        if self.ttl and time.time() - path.stat().st_mtime > self.ttl:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _write_cache(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass  # cache failures are never fatal

    # -- fetching ----------------------------------------------------------

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        use_cache: bool = True,
        retries: int = 3,
        headers: dict[str, str] | None = None,
    ) -> Any:
        # An empty path means "hit base_url itself" (GDELT's DOC API takes all
        # of its arguments as query params). Joining a "" would append a
        # trailing slash, which some endpoints answer with a 404.
        if path.startswith("http"):
            url = path
        elif path:
            url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        else:
            url = self.base_url
        cache_path = self._cache_path(url, params)

        if use_cache:
            cached = self._read_cache(cache_path)
            if cached is not None:
                return cached

        last_exc: Exception | None = None
        for attempt in range(retries):
            elapsed = time.time() - self._last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=30)
                self._last_call = time.time()
                if resp.status_code == 429:
                    time.sleep(2 ** attempt * 2)
                    continue
                resp.raise_for_status()
                payload = resp.json()
                if use_cache:
                    self._write_cache(cache_path, payload)
                return payload
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                time.sleep(2 ** attempt)

        # Serve stale cache rather than failing a scheduled run outright.
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        raise SourceError(f"{self.name}: {url} failed after {retries} tries: {last_exc}")
