"""Tests for the pure analysis functions, using small synthetic frames."""

from __future__ import annotations

import pandas as pd
import pytest

from ucsd_enroll_analyzer import analysis as A


def make(rows: list[dict], term: str = "2024Fall", degraded: bool = False) -> pd.DataFrame:
    """Build a tidy frame from a list of row dicts (hour offsets as ``h``)."""
    base = pd.Timestamp("2024-08-27T00:00:00")
    df = pd.DataFrame(rows)
    df["time"] = [base + pd.Timedelta(hours=int(h)) for h in df.pop("h")]
    for c in ["enrolled", "available", "waitlisted", "total"]:
        if c not in df:
            df[c] = pd.NA
        df[c] = df[c].astype("Int64")
    df["term"] = term
    df["course"] = "BILD 4"
    df["section"] = pd.NA
    df = df[["time", "enrolled", "available", "waitlisted", "total", "term", "course", "section"]]
    df.attrs["degraded"] = degraded
    return df


def test_fill_curve_uses_per_row_total():
    df = make([
        {"h": 0, "enrolled": 50, "available": 50, "waitlisted": 0, "total": 100},
        {"h": 1, "enrolled": 150, "available": 50, "waitlisted": 0, "total": 200},
    ])
    out = A.fill_curve(df)
    assert out["pct_full"].tolist() == pytest.approx([0.5, 0.75])


def test_first_full_times_detects_reopen():
    df = make([
        {"h": 0, "available": 5, "total": 10},
        {"h": 1, "available": 0, "total": 10},
        {"h": 2, "available": 3, "total": 10},
        {"h": 3, "available": 0, "total": 10},
    ])
    times = A.first_full_times(df)
    assert len(times) == 2


def test_capacity_changes_lists_each_change():
    df = make([
        {"h": 0, "total": 150},
        {"h": 1, "total": 150},
        {"h": 2, "total": 160},
        {"h": 3, "total": 160},
    ])
    changes = A.capacity_changes(df)
    assert len(changes) == 1
    assert int(changes.iloc[0]["delta"]) == 10


def test_first_seat_release_jump_and_fallback():
    jumped = make([
        {"h": 0, "total": 0},
        {"h": 1, "total": 0},
        {"h": 2, "total": 30},
    ])
    assert A.first_seat_release(jumped, min_jump=10) == jumped["time"].iloc[2]

    no_jump = make([{"h": 0, "total": 5}, {"h": 1, "total": 5}])
    assert A.first_seat_release(no_jump, min_jump=10) == no_jump["time"].iloc[0]


def test_velocity_steepest_and_spike():
    df = make([
        {"h": 0, "enrolled": 0, "available": 100, "total": 100},
        {"h": 1, "enrolled": 1, "available": 99, "total": 100},
        {"h": 2, "enrolled": 2, "available": 98, "total": 100},
        {"h": 3, "enrolled": 50, "available": 50, "total": 100},
    ])
    sw = A.steepest_window(df)
    assert sw is not None
    assert sw["rate"] == pytest.approx(48.0)

    spikes = A.spike_windows(df, k=3)
    assert len(spikes) == 1
    assert spikes.iloc[0]["enrolled_per_hour"] == pytest.approx(48.0)


def test_time_to_capacity_measures_duration():
    df = make([
        {"h": 0, "enrolled": 0, "available": 0, "total": 0},
        {"h": 1, "enrolled": 20, "available": 80, "total": 100},
        {"h": 2, "enrolled": 60, "available": 40, "total": 100},
        {"h": 3, "enrolled": 100, "available": 0, "total": 100},
    ])
    ttc = A.time_to_capacity(df, min_jump=10)
    assert ttc == pd.Timedelta(hours=2)


def test_degraded_velocity_raises():
    df = make([
        {"h": 0, "available": 40, "total": 40},
        {"h": 1, "available": 10, "total": 40},
    ], degraded=True)
    with pytest.raises(ValueError):
        A.velocity(df)


def test_risk_score_structure_and_disclaimer():
    df = make([
        {"h": 0, "enrolled": 0, "available": 0, "waitlisted": 0, "total": 0},
        {"h": 1, "enrolled": 50, "available": 50, "waitlisted": 0, "total": 100},
        {"h": 2, "enrolled": 100, "available": 0, "waitlisted": 30, "total": 100},
        {"h": 3, "enrolled": 110, "available": 0, "waitlisted": 40, "total": 100},
    ])
    result = A.risk_score(df)
    assert set(result) == {"score", "label", "weights", "components", "inputs", "disclaimer"}
    assert result["label"] in {"Low", "Medium", "High"}
    assert "guarantee" in result["disclaimer"].lower()
    assert result["inputs"]["overenrolled"] is True  # 110 > 100
    assert 0.0 <= result["score"] <= 100.0


def test_align_for_compare_aligns_to_release():
    f1 = make([
        {"h": 0, "enrolled": 0, "available": 0, "total": 0},
        {"h": 1, "enrolled": 50, "available": 50, "total": 100},
    ], term="2023Fall")
    f2 = make([
        {"h": 0, "enrolled": 0, "available": 0, "total": 0},
        {"h": 2, "enrolled": 50, "available": 50, "total": 100},
    ], term="2024Fall")
    aligned = A.align_for_compare([f1, f2])
    assert set(aligned["term"].unique()) == {"2023Fall", "2024Fall"}
    assert aligned["days_since_release"].min() == pytest.approx(0.0)
