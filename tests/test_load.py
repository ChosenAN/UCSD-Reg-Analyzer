"""Tests for CSV parsing, schema detection, and tagging. No network access."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ucsd_enroll_analyzer import load as load_mod
from ucsd_enroll_analyzer.load import load_course, parse_csv

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_normal_dtypes_and_tags():
    df = parse_csv(FIXTURES / "normal.csv", "2024Fall", "BILD 4")
    assert len(df) == 4
    assert pd.api.types.is_datetime64_any_dtype(df["time"])
    assert str(df["enrolled"].dtype) == "Int64"
    assert (df["term"] == "2024Fall").all()
    assert (df["course"] == "BILD 4").all()
    assert df.attrs["degraded"] is False
    assert df["time"].is_monotonic_increasing


def test_parse_spring2022_degraded():
    df = parse_csv(FIXTURES / "spring2022.csv", "2022Spring", "BILD 4")
    assert df.attrs["degraded"] is True
    assert df["enrolled"].isna().all()
    assert str(df["enrolled"].dtype) == "Int64"
    assert df["available"].tolist() == [40, 10]


def test_parse_allzero_loads_without_error():
    df = parse_csv(FIXTURES / "allzero.csv", "2024Fall", "MATH 20A")
    assert len(df) == 2
    assert (df["total"] == 0).all()
    assert df.attrs["degraded"] is False


def test_parse_empty_file():
    df = parse_csv(FIXTURES / "empty.csv", "2024Fall", "GONE 1")
    assert df.empty
    assert list(df.columns) == [
        "time", "enrolled", "available", "waitlisted", "total",
        "term", "course", "section",
    ]


def test_load_course_returns_none_when_not_offered(monkeypatch):
    monkeypatch.setattr(load_mod, "fetch_csv", lambda *a, **k: None)
    assert load_course("2024Fall", "GHOST 1") is None


def test_load_course_parses_when_present(monkeypatch):
    src = FIXTURES / "normal.csv"
    monkeypatch.setattr(load_mod, "fetch_csv", lambda *a, **k: src)
    df = load_course("2024Fall", "BILD 4")
    assert df is not None
    assert len(df) == 4
