"""CLI tests via Click's CliRunner, with load_course monkeypatched (no network)."""

from __future__ import annotations

import json

import pandas as pd
from click.testing import CliRunner

from ucsd_enroll_analyzer import cli


def _frame(term: str = "2024Fall") -> pd.DataFrame:
    base = pd.Timestamp("2024-08-27T00:00:00")
    df = pd.DataFrame(
        {
            "time": [base + pd.Timedelta(hours=h) for h in range(4)],
            "enrolled": pd.array([0, 20, 60, 100], dtype="Int64"),
            "available": pd.array([100, 80, 40, 0], dtype="Int64"),
            "waitlisted": pd.array([0, 0, 5, 30], dtype="Int64"),
            "total": pd.array([100, 100, 100, 100], dtype="Int64"),
            "term": term,
            "course": "BILD 4",
            "section": pd.NA,
        }
    )
    df.attrs["degraded"] = False
    return df


def test_analyze_prints_fill_and_steepest(monkeypatch):
    monkeypatch.setattr(cli, "load_course", lambda *a, **k: _frame())
    result = CliRunner().invoke(cli.main, ["analyze", "2024Fall", "BILD 4"])
    assert result.exit_code == 0, result.output
    assert "steepest" in result.output.lower()


def test_analyze_json_is_valid(monkeypatch):
    monkeypatch.setattr(cli, "load_course", lambda *a, **k: _frame())
    result = CliRunner().invoke(cli.main, ["--json", "analyze", "2024Fall", "BILD 4"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)  # must parse
    assert payload["course"] == "BILD 4"


def test_unknown_term_is_friendly_and_nonzero(monkeypatch):
    monkeypatch.setattr(cli, "load_course", lambda *a, **k: _frame())
    result = CliRunner().invoke(cli.main, ["analyze", "Fall2024", "BILD 4"])
    assert result.exit_code != 0
    assert "term" in result.output.lower()


def test_not_offered_references_all_courses(monkeypatch):
    monkeypatch.setattr(cli, "load_course", lambda *a, **k: None)
    result = CliRunner().invoke(cli.main, ["analyze", "2024Fall", "NOPE 999"])
    assert result.exit_code != 0
    assert "all_courses.txt" in result.output


def test_risk_prints_disclaimer(monkeypatch):
    monkeypatch.setattr(cli, "load_course", lambda *a, **k: _frame())
    result = CliRunner().invoke(cli.main, ["risk", "2024Fall", "BILD 4"])
    assert result.exit_code == 0, result.output
    assert "guarantee" in result.output.lower()


def test_compare_aligns_terms(monkeypatch):
    frames = {"2023Fall": _frame("2023Fall"), "2024Fall": _frame("2024Fall")}
    monkeypatch.setattr(cli, "load_course", lambda term, *a, **k: frames[term])
    result = CliRunner().invoke(
        cli.main, ["compare", "BILD 4", "2023Fall", "2024Fall"]
    )
    assert result.exit_code == 0, result.output
    assert "2023Fall" in result.output
    assert "2024Fall" in result.output
