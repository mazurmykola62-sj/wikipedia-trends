"""
Common utilities shared by every script in this skill:
- a requests.Session configured the way the Wikimedia API wants to be talked to
  (descriptive User-Agent, retries, gentle rate limiting)
- an on-disk cache so re-running or refining a request doesn't re-hit the network
- small date helpers to move between YYYY-MM-DD and the API's YYYYMMDD format

Every script that talks to Wikipedia/Wikimedia should go through get_json() below
instead of calling requests directly, so caching and rate limiting stay consistent.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional

import requests

# Wikimedia asks every client to identify itself with a descriptive User-Agent
# that includes contact info. Replace the contact string below with a real one
# (an email or a project URL) before heavy/production use -- see references/api_reference.md.
USER_AGENT = "wikipedia-trends-skill/1.0 (https://github.com/anthropics/skills; contact: set-a-real-contact@example.com)"

SKILL_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = SKILL_ROOT / "cache"
DATA_START = date(2015, 7, 1)  # Wikimedia pageviews data does not exist before this date

_session: Optional[requests.Session] = None
_last_request_ts = 0.0
MIN_REQUEST_INTERVAL = 0.2  # be polite: max ~5 req/s to any Wikimedia host


def get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return _session


def _cache_path(url: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{key}.json"


def get_json(url: str, *, use_cache: bool = True, timeout: int = 20, max_retries: int = 3) -> Any:
    """GET a URL and return parsed JSON, transparently cached on disk.

    Raises RuntimeError with a readable message on persistent failure (never
    raises a raw requests exception, so callers/agents get an actionable string).
    """
    cache_file = _cache_path(url)
    if use_cache and cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    global _last_request_ts
    session = get_session()
    last_err = None
    for attempt in range(max_retries):
        elapsed = time.time() - _last_request_ts
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        try:
            resp = session.get(url, timeout=timeout)
            _last_request_ts = time.time()
            if resp.status_code == 404:
                raise RuntimeError(
                    f"404 Not Found for {url}\n"
                    "This usually means the article title or project code doesn't exist, "
                    "or there is no data for the requested range. "
                    "Try scripts/resolve_topic.py to find the correct title first."
                )
            if resp.status_code == 429:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            if use_cache:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f)
            return data
        except requests.RequestException as e:
            last_err = e
            time.sleep(1 + attempt)
    raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts: {last_err}")


def parse_date(s: str) -> date:
    """Accepts YYYY-MM-DD or YYYYMMDD."""
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse date '{s}'. Use YYYY-MM-DD.")


def to_api_date(d: date, end_of_day: bool = False) -> str:
    """Pageviews API wants YYYYMMDD00 (start) / YYYYMMDDHH is accepted too; we always use hour 00."""
    return d.strftime("%Y%m%d") + "00"


def clamp_to_data_availability(d: date) -> date:
    return d if d >= DATA_START else DATA_START


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def print_summary(obj: dict) -> None:
    """Print a compact one-line JSON summary to stdout.

    Scripts should print ONLY this to stdout (full data goes to files) so an
    agent reading tool output doesn't burn context on large payloads.
    """
    print(json.dumps(obj, ensure_ascii=False))


def ensure_parent(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
