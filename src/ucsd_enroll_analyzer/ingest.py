"""Build the static-dashboard dataset: per-course summary metrics as JSON.

Reuses the tested load/analysis layers; only the term loop and JSON shaping are
new here. The output is one ``<term>.json`` (array of summary rows) per term plus
an ``index.json`` describing the build.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from . import analysis
from .constants import DEFAULT_CACHE_DIR, RAW_BASE
from .fetch import get_session
from .load import load_course
from .terms import parse_term

logger = logging.getLogger(__name__)

# Default coverage file, relative to the repo root / current working dir.
DEFAULT_TERMS_FILE = Path("web_build/terms.txt")


def _validate(names: list[str]) -> list[str]:
    """Keep only names that parse as real term repos; warn on the rest."""
    valid: list[str] = []
    for name in names:
        try:
            parse_term(name)
        except ValueError:
            logger.warning("Skipping unrecognized term: %s", name)
            continue
        valid.append(name)
    return valid


def load_terms(path: Path | None = None, override: str | None = None) -> list[str]:
    """Resolve which terms to build. ``override`` (comma list) beats the file."""
    if override is not None:
        names = [n.strip() for n in override.split(",") if n.strip()]
        return _validate(names)
    src = Path(path) if path is not None else DEFAULT_TERMS_FILE
    lines = src.read_text().splitlines()
    names = [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
    return _validate(names)


def summarize_course(df: pd.DataFrame) -> dict:
    """Compute one dashboard summary row for a course's tidy frame."""
    course = str(df["course"].iloc[0]) if len(df) else None
    degraded = bool(df.attrs.get("degraded", False))

    inp = analysis.risk_inputs(df)
    fc = analysis.fill_curve(df)
    final_pct = (
        round(float(fc["pct_full"].dropna().iloc[-1]), 4)
        if fc["pct_full"].notna().any()
        else None
    )

    if degraded:
        peak_rate = None
        score = None
        label = None
    else:
        risk = analysis.risk_score(df)
        score = risk["score"]
        label = risk["label"]
        peak_rate = inp["peak_enrolled_per_hour"]

    return {
        "course": course,
        "nominal_capacity": inp["nominal_capacity"],
        "hours_to_full": inp["hours_to_full"],
        "peak_enrolled_per_hour": peak_rate,
        "peak_waitlist": inp["peak_waitlist"],
        "final_pct_full": final_pct,
        "risk_score": score,
        "risk_label": label,
        "snapshots": int(len(df)),
        "degraded": degraded,
    }


def fetch_course_list(
    term: str,
    *,
    session: requests.Session | None = None,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> list[str]:
    """Fetch + cache a term's all_courses.txt; return course codes (one per line)."""
    dest = Path(cache_dir) / term / "all_courses.txt"
    if dest.exists():
        text = dest.read_text()
    else:
        url = f"{RAW_BASE}/{term}/main/all_courses.txt"
        sess = session or get_session()
        resp = sess.get(url, timeout=30)
        if resp.status_code == 404:
            logger.warning("No all_courses.txt for %s (404).", term)
            return []
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(resp.text)
        text = resp.text
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def ingest_term(
    term: str, *, refresh: bool = False, cache_dir: Path = DEFAULT_CACHE_DIR
) -> list[dict]:
    """Summary rows for every offered course in ``term`` (skips not-offered)."""
    courses = fetch_course_list(term, cache_dir=cache_dir)
    rows: list[dict] = []
    for course in courses:
        df = load_course(term, course, refresh=refresh, cache_dir=cache_dir)
        if df is None or df.empty:
            continue
        rows.append(summarize_course(df))
    logger.info("Ingested %s: %d/%d courses had data.", term, len(rows), len(courses))
    return rows


def build_web(
    terms: list[str],
    out_dir: Path,
    *,
    refresh: bool = False,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> Path:
    """Ingest each term and write <term>.json plus an index.json. Returns out_dir."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    index_terms: list[dict] = []
    for term in terms:
        rows = ingest_term(term, refresh=refresh, cache_dir=cache_dir)
        (out / f"{term}.json").write_text(json.dumps(rows, indent=2))
        index_terms.append({"term": term, "courses": len(rows)})
    index = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "terms": index_terms,
    }
    (out / "index.json").write_text(json.dumps(index, indent=2))
    return out
