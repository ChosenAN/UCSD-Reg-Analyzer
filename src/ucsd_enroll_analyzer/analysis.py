"""Pure analysis functions over a single course's tidy enrollment DataFrame.

Every function expects the tidy schema produced by :mod:`load`: a ``time``
(datetime64) column plus nullable-Int64 ``enrolled``, ``available``,
``waitlisted``, ``total`` columns. Functions never fetch or do I/O.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

import numpy as np
import pandas as pd

RISK_DISCLAIMER = (
    "Heuristic estimate from a few terms of noisy WebReg snapshots -- NOT a "
    "guarantee. Registration appointment times, mid-term capacity changes, and "
    "irregular scrape gaps all add uncertainty."
)


def _sorted(df: pd.DataFrame) -> pd.DataFrame:
    """Return df sorted by time with a fresh index (analysis assumes order)."""
    return df.sort_values("time").reset_index(drop=True)


def _require_enrolled(df: pd.DataFrame) -> None:
    """Raise if there isn't enough ``enrolled`` data to compute velocity."""
    if df["enrolled"].notna().sum() < 2:
        raise ValueError(
            "Not enough 'enrolled' data points -- this is likely the degraded "
            "Spring 2022 schema (no enrolled column) or too few snapshots."
        )


def fill_curve(df: pd.DataFrame) -> pd.DataFrame:
    """Add a ``pct_full`` column = (total - available) / total, per row.

    Uses each row's own ``total`` (capacity changes over the term). ``pct_full``
    is NA where ``total`` is 0 or missing.
    """
    out = _sorted(df).copy()
    total = out["total"].astype("Float64")
    available = out["available"].astype("Float64")
    pct = (total - available) / total
    out["pct_full"] = pct.where(total > 0)
    return out


def first_full_times(df: pd.DataFrame) -> list[pd.Timestamp]:
    """Timestamps where ``available`` first reaches 0 (capacity > 0).

    Each separate fill counts: if seats reopen (a drop) and fill again, both
    "went full" moments are returned.
    """
    d = _sorted(df)
    is_full = ((d["available"] == 0) & (d["total"] > 0)).fillna(False).to_numpy(dtype=bool)
    prev = np.concatenate([[False], is_full[:-1]])
    events = is_full & ~prev
    return list(d.loc[events, "time"])


def capacity_changes(df: pd.DataFrame) -> pd.DataFrame:
    """List every change in ``total`` (registrar resizing the course).

    Columns: ``time``, ``prev_total``, ``total``, ``delta`` (signed).
    """
    d = _sorted(df)
    total = d["total"]
    delta = total.diff()
    changed = (delta.notna() & (delta != 0)).fillna(False)
    out = pd.DataFrame(
        {
            "time": d.loc[changed, "time"],
            "prev_total": total.shift()[changed],
            "total": total[changed],
            "delta": delta[changed],
        }
    )
    return out.reset_index(drop=True)


def first_seat_release(df: pd.DataFrame, min_jump: int = 10) -> pd.Timestamp | None:
    """The first timestamp seats were released.

    Defined as the first positive jump in ``total`` of at least ``min_jump``
    seats. Falls back to the first row with ``total`` > 0 if no such jump exists.
    Returns ``None`` for an empty frame.
    """
    if df.empty:
        return None
    d = _sorted(df)
    total = d["total"].astype("Float64")
    delta = total.diff()
    jump = (delta >= min_jump).fillna(False)
    if jump.any():
        return d.loc[jump, "time"].iloc[0]
    positive = (total > 0).fillna(False)
    if positive.any():
        return d.loc[positive, "time"].iloc[0]
    return None


def velocity(df: pd.DataFrame) -> pd.DataFrame:
    """Per-interval enrollment velocity in seats/hour.

    Columns: ``start``, ``end``, ``hours``, ``d_enrolled``, ``enrolled_per_hour``.
    Raises ``ValueError`` on the degraded (no-enrolled) schema.
    """
    _require_enrolled(df)
    d = _sorted(df).dropna(subset=["enrolled"]).reset_index(drop=True)
    times = d["time"]
    enr = d["enrolled"].astype("float")
    rows = []
    for i in range(1, len(d)):
        hours = (times[i] - times[i - 1]).total_seconds() / 3600.0
        if hours <= 0:
            continue
        d_enr = enr[i] - enr[i - 1]
        rows.append(
            {
                "start": times[i - 1],
                "end": times[i],
                "hours": hours,
                "d_enrolled": d_enr,
                "enrolled_per_hour": d_enr / hours,
            }
        )
    return pd.DataFrame(
        rows, columns=["start", "end", "hours", "d_enrolled", "enrolled_per_hour"]
    )


def spike_windows(df: pd.DataFrame, k: float = 3.0) -> pd.DataFrame:
    """Intervals where enrollment velocity is at least ``k`` x the median rate.

    The median is taken over intervals with positive enrollment (drops ignored),
    so this surfaces appointment-window bursts. Same columns as :func:`velocity`.
    """
    v = velocity(df)
    positive = v[v["enrolled_per_hour"] > 0]
    if positive.empty:
        return v.iloc[0:0]
    median = positive["enrolled_per_hour"].median()
    if not median > 0:
        return v.iloc[0:0]
    threshold = k * median
    return v[v["enrolled_per_hour"] >= threshold].reset_index(drop=True)


def steepest_window(df: pd.DataFrame) -> dict | None:
    """The single fastest-filling interval -- the "registration just opened" signal.

    Returns a dict with ``start``, ``end``, ``hours``, ``seats``, ``rate``
    (seats/hour), or ``None`` if no interval can be computed.
    """
    v = velocity(df)
    if v.empty:
        return None
    row = v.loc[v["enrolled_per_hour"].idxmax()]
    return {
        "start": row["start"],
        "end": row["end"],
        "hours": float(row["hours"]),
        "seats": float(row["d_enrolled"]),
        "rate": float(row["enrolled_per_hour"]),
    }


def time_to_capacity(
    df: pd.DataFrame,
    start: datetime | pd.Timestamp | None = None,
    min_jump: int = 10,
) -> timedelta | None:
    """Time from seat release (or ``start``) until ``available`` first hits 0.

    Uses :func:`first_seat_release` when ``start`` is not given. Returns ``None``
    if there's no start point or the course never fills after it.
    """
    if start is None:
        start = first_seat_release(df, min_jump)
    if start is None:
        return None
    d = _sorted(df)
    sub = d[d["time"] >= start]
    full = ((sub["available"] == 0) & (sub["total"] > 0)).fillna(False)
    if not full.any():
        return None
    full_time = sub.loc[full, "time"].iloc[0]
    return full_time - pd.Timestamp(start)


def risk_inputs(df: pd.DataFrame) -> dict:
    """The raw signals feeding :func:`risk_score`, each individually meaningful."""
    caps = df["total"].dropna()
    nominal_capacity = int(caps.max()) if len(caps) else None
    waits = df["waitlisted"].dropna()
    peak_waitlist = int(waits.max()) if len(waits) else None

    ttc = time_to_capacity(df)
    hours_to_full = round(ttc.total_seconds() / 3600.0, 2) if ttc is not None else None

    if df["enrolled"].notna().any():
        overenrolled = bool(((df["enrolled"] > df["total"]).fillna(False)).any())
    else:
        overenrolled = None

    try:
        sw = steepest_window(df)
        peak_rate = round(sw["rate"], 2) if sw is not None else None
    except ValueError:
        peak_rate = None

    return {
        "nominal_capacity": nominal_capacity,
        "peak_waitlist": peak_waitlist,
        "hours_to_full": hours_to_full,
        "overenrolled": overenrolled,
        "peak_enrolled_per_hour": peak_rate,
    }


def risk_score(
    df: pd.DataFrame, weights: tuple[float, float, float] = (0.5, 0.3, 0.2)
) -> dict:
    """A 0-100 "risk of not getting a seat" heuristic with its inputs exposed.

    Blends (a) how fast the course fills, (b) waitlist depth vs capacity, and
    (c) whether enrollment historically exceeded capacity. Returns the score, a
    Low/Medium/High label, the component values, the raw inputs, and a disclaimer.
    """
    inp = risk_inputs(df)

    htf = inp["hours_to_full"]
    fill_comp = max(0.0, 1.0 - htf / 48.0) if htf is not None else 0.0

    cap = inp["nominal_capacity"]
    pw = inp["peak_waitlist"]
    wait_comp = min(pw / cap, 1.0) if cap and pw is not None else 0.0

    over_comp = 1.0 if inp["overenrolled"] else 0.0

    w = weights
    score = round(100.0 * (w[0] * fill_comp + w[1] * wait_comp + w[2] * over_comp), 1)
    label = "Low" if score < 33 else "Medium" if score < 66 else "High"

    return {
        "score": score,
        "label": label,
        "weights": list(w),
        "components": {
            "fill_speed": round(fill_comp, 3),
            "waitlist": round(wait_comp, 3),
            "overenrollment": over_comp,
        },
        "inputs": inp,
        "disclaimer": RISK_DISCLAIMER,
    }


def align_for_compare(
    frames: Iterable[pd.DataFrame], min_jump: int = 10
) -> pd.DataFrame:
    """Overlay-ready long frame aligning terms by days since their seat release.

    For each input frame, day 0 is that term's :func:`first_seat_release`. Frames
    with no detectable release are skipped. Columns: ``term``, ``time``,
    ``days_since_release``, ``pct_full``.
    """
    cols = ["term", "time", "days_since_release", "pct_full"]
    pieces = []
    for df in frames:
        if df is None or df.empty:
            continue
        release = first_seat_release(df, min_jump)
        if release is None:
            continue
        f = fill_curve(df)
        f = f.copy()
        f["days_since_release"] = (f["time"] - pd.Timestamp(release)).dt.total_seconds() / 86400.0
        f = f[f["days_since_release"] >= 0]
        pieces.append(f[cols])
    if not pieces:
        return pd.DataFrame(columns=cols)
    return pd.concat(pieces, ignore_index=True)
