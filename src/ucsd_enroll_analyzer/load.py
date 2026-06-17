"""Load raw CSVs into tidy, typed pandas DataFrames with schema detection."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import pandas as pd

from .constants import DEFAULT_CACHE_DIR
from .fetch import fetch_csv

logger = logging.getLogger(__name__)

# Count columns and their target dtype. `enrolled` may be absent (Spring 2022).
COUNT_COLUMNS = ["enrolled", "available", "waitlisted", "total"]
TAG_COLUMNS = ["term", "course", "section"]


def _empty_frame() -> pd.DataFrame:
    """An empty frame with the full expected schema (degraded=False)."""
    cols = ["time", *COUNT_COLUMNS, *TAG_COLUMNS]
    df = pd.DataFrame({c: pd.Series(dtype="object") for c in cols})
    df["time"] = pd.to_datetime(df["time"])
    for c in COUNT_COLUMNS:
        df[c] = df[c].astype("Int64")
    df.attrs["degraded"] = False
    return df


def parse_csv(
    path: Path,
    term: str,
    course: str,
    section: str | None = None,
) -> pd.DataFrame:
    """Parse one cached CSV into a tidy, typed, tagged DataFrame.

    Sets ``df.attrs["degraded"] = True`` and fills ``enrolled`` with NA when the
    source lacks the ``enrolled`` column (the Spring 2022 schema variant).
    """
    try:
        raw = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return _empty_frame()

    degraded = "enrolled" not in raw.columns
    if degraded:
        logger.warning(
            "Degraded schema (no 'enrolled' column): %s %s -- enrolled set to NA.",
            term,
            course,
        )

    df = pd.DataFrame()
    df["time"] = pd.to_datetime(raw["time"], errors="coerce")
    for col in COUNT_COLUMNS:
        if col in raw.columns:
            df[col] = pd.to_numeric(raw[col], errors="coerce").astype("Int64")
        else:
            df[col] = pd.Series([pd.NA] * len(raw), dtype="Int64")

    df["term"] = term
    df["course"] = course
    df["section"] = section if section is not None else pd.NA
    df = df.sort_values("time").reset_index(drop=True)
    df.attrs["degraded"] = degraded
    return df


def load_course(
    term: str,
    course: str,
    section: str | None = None,
    *,
    refresh: bool = False,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> pd.DataFrame | None:
    """Fetch + parse a single course/section. ``None`` if not offered (404)."""
    path = fetch_csv(term, course, section, refresh=refresh, cache_dir=cache_dir)
    if path is None:
        return None
    return parse_csv(path, term, course, section)


def load_many(
    specs: Iterable[tuple[str, str, str | None]],
    *,
    refresh: bool = False,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> pd.DataFrame:
    """Load multiple (term, course, section) specs into one long frame.

    Missing combos (404 -> None) are skipped. Returns an empty frame if none load.
    """
    frames: list[pd.DataFrame] = []
    for term, course, section in specs:
        df = load_course(term, course, section, refresh=refresh, cache_dir=cache_dir)
        if df is not None and not df.empty:
            frames.append(df)
    if not frames:
        return _empty_frame()
    return pd.concat(frames, ignore_index=True)
