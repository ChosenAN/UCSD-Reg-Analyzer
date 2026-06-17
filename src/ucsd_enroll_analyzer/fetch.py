"""Fetch raw enrollment CSVs from GitHub with on-disk caching and retries."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .constants import DEFAULT_CACHE_DIR, RAW_BASE

logger = logging.getLogger(__name__)

# Polite delay between live network requests (seconds).
REQUEST_DELAY = 0.5


def build_url(term: str, course: str, section: str | None = None) -> str:
    """Build the raw.githubusercontent.com URL, URL-encoding spaces internally."""
    if section is None:
        leaf = f"overall/{quote(course)}.csv"
    else:
        leaf = f"section/{quote(course)}_{quote(section)}.csv"
    return f"{RAW_BASE}/{term}/main/{leaf}"


def cache_path(
    term: str,
    course: str,
    section: str | None = None,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> Path:
    """Compute the on-disk cache path for a (term, course[, section])."""
    if section is None:
        return Path(cache_dir) / term / "overall" / f"{course}.csv"
    return Path(cache_dir) / term / "section" / f"{course}_{section}.csv"


def get_session() -> requests.Session:
    """A requests Session with retry/backoff on rate-limit and server errors."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_csv(
    term: str,
    course: str,
    section: str | None = None,
    *,
    refresh: bool = False,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    session: requests.Session | None = None,
    delay: float = REQUEST_DELAY,
) -> Path | None:
    """Return the cached path for a CSV, fetching it if needed.

    Returns ``None`` (with a logged warning) on a 404 -- i.e. the course/section
    was not offered that term. Never raises on a missing file.
    """
    dest = cache_path(term, course, section, cache_dir)
    if dest.exists() and not refresh:
        return dest

    url = build_url(term, course, section)
    sess = session or get_session()
    response = sess.get(url, timeout=30)
    if delay:
        time.sleep(delay)

    if response.status_code == 404:
        logger.warning(
            "Not offered (404): %s %s%s",
            term,
            course,
            f" [{section}]" if section else "",
        )
        return None
    response.raise_for_status()

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(response.content)
    return dest
