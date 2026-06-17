"""Tests for output rendering: tables, JSON, CSV dump."""

from __future__ import annotations

import json

import pandas as pd

from ucsd_enroll_analyzer import render as R


def test_to_json_serializes_timestamp_and_timedelta():
    obj = {
        "when": pd.Timestamp("2024-08-27T08:00:00"),
        "took": pd.Timedelta(hours=2, minutes=30),
        "nested": {"label": "High", "score": 81.0},
    }
    text = R.to_json(obj)
    back = json.loads(text)  # must be valid JSON
    assert back["when"] == "2024-08-27T08:00:00"
    assert back["took"] == 9000.0  # seconds
    assert back["nested"]["label"] == "High"


def test_to_json_handles_na_and_numpy():
    df = pd.DataFrame({"x": pd.array([1, 2], dtype="Int64")})
    obj = {"missing": pd.NA, "count": df["x"].max()}
    back = json.loads(R.to_json(obj))
    assert back["missing"] is None
    assert back["count"] == 2


def test_table_contains_headers():
    out = R.table(
        rows=[["BILD 4", "High"], ["MATH 20A", "Low"]],
        headers=["course", "risk"],
        title="Risk summary",
    )
    assert isinstance(out, str)
    assert "course" in out
    assert "risk" in out
    assert "BILD 4" in out


def test_dump_csv_writes_file(tmp_path):
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    path = tmp_path / "out.csv"
    R.dump_csv(df, path)
    assert path.exists()
    assert "a,b" in path.read_text()
