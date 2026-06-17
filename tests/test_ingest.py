"""Tests for the web ingest pipeline (no network in unit tests)."""

from __future__ import annotations

import json

import pandas as pd
import pytest
from click.testing import CliRunner

from ucsd_enroll_analyzer import cli, ingest


def _make(rows, course="BILD 4", degraded=False):
    base = pd.Timestamp("2024-08-27T00:00:00")
    df = pd.DataFrame(rows)
    df["time"] = [base + pd.Timedelta(hours=int(h)) for h in df.pop("h")]
    for c in ["enrolled", "available", "waitlisted", "total"]:
        if c not in df:
            df[c] = pd.NA
        df[c] = df[c].astype("Int64")
    df["term"] = "2024Fall"
    df["course"] = course
    df["section"] = pd.NA
    df = df[["time", "enrolled", "available", "waitlisted", "total", "term", "course", "section"]]
    df.attrs["degraded"] = degraded
    return df


def test_load_terms_skips_comments_blanks_and_invalid(tmp_path):
    f = tmp_path / "terms.txt"
    f.write_text("# header\n\n2024Fall\nNotATerm\n2025Winter\n")
    assert ingest.load_terms(path=f) == ["2024Fall", "2025Winter"]


def test_load_terms_override_wins(tmp_path):
    f = tmp_path / "terms.txt"
    f.write_text("2024Fall\n")
    assert ingest.load_terms(path=f, override="2023Fall, 2025Spring") == ["2023Fall", "2025Spring"]


def test_summarize_course_normal():
    df = _make([
        {"h": 0, "enrolled": 0, "available": 0, "waitlisted": 0, "total": 0},
        {"h": 1, "enrolled": 50, "available": 50, "waitlisted": 0, "total": 100},
        {"h": 2, "enrolled": 100, "available": 0, "waitlisted": 30, "total": 100},
    ])
    row = ingest.summarize_course(df)
    assert row["course"] == "BILD 4"
    assert row["nominal_capacity"] == 100
    assert row["peak_waitlist"] == 30
    assert row["snapshots"] == 3
    assert row["degraded"] is False
    assert row["risk_label"] in {"Low", "Medium", "High"}
    assert row["final_pct_full"] == pytest.approx(1.0)


def test_summarize_course_degraded_nulls_velocity_and_risk():
    df = _make([
        {"h": 0, "available": 40, "total": 40},
        {"h": 1, "available": 10, "total": 40},
    ], degraded=True)
    row = ingest.summarize_course(df)
    assert row["degraded"] is True
    assert row["peak_enrolled_per_hour"] is None
    assert row["risk_score"] is None
    assert row["risk_label"] is None


def test_ingest_term_summarizes_offered_courses(monkeypatch):
    monkeypatch.setattr(ingest, "fetch_course_list", lambda *a, **k: ["BILD 4", "MATH 20A", "GONE 1"])

    def fake_load(term, course, section=None, **kwargs):
        if course == "GONE 1":
            return None
        return _make([
            {"h": 0, "enrolled": 0, "available": 0, "total": 0},
            {"h": 1, "enrolled": 50, "available": 50, "total": 100},
        ], course=course)

    monkeypatch.setattr(ingest, "load_course", fake_load)
    rows = ingest.ingest_term("2024Fall")
    assert [r["course"] for r in rows] == ["BILD 4", "MATH 20A"]


def test_build_web_writes_index_and_term_files(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ingest, "ingest_term",
        lambda term, **k: [{"course": "BILD 4", "risk_label": "High", "snapshots": 3}],
    )
    out = tmp_path / "data"
    ingest.build_web(["2024Fall"], out)
    index = json.loads((out / "index.json").read_text())
    assert index["terms"] == [{"term": "2024Fall", "courses": 1}]
    assert "built_at" in index
    term_rows = json.loads((out / "2024Fall.json").read_text())
    assert term_rows[0]["course"] == "BILD 4"


def test_build_web_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ingest, "ingest_term",
        lambda term, **k: [{"course": "BILD 4", "snapshots": 3}],
    )
    out = tmp_path / "data"
    result = CliRunner().invoke(
        cli.main, ["build-web", "--terms", "2024Fall", "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert (out / "index.json").exists()
