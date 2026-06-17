"""Tests for plotting. The positive path needs matplotlib (the [plot] extra)."""

from __future__ import annotations

import builtins

import pandas as pd
import pytest

from ucsd_enroll_analyzer import plot as P

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")  # headless backend for tests


def _frame() -> pd.DataFrame:
    base = pd.Timestamp("2024-08-27T00:00:00")
    return pd.DataFrame(
        {
            "time": [base + pd.Timedelta(hours=h) for h in range(4)],
            "enrolled": pd.array([0, 20, 60, 100], dtype="Int64"),
            "available": pd.array([100, 80, 40, 0], dtype="Int64"),
            "waitlisted": pd.array([0, 0, 5, 30], dtype="Int64"),
            "total": pd.array([100, 100, 100, 100], dtype="Int64"),
        }
    )


def test_plot_course_writes_png(tmp_path):
    out = tmp_path / "chart.png"
    result = P.plot_course(_frame(), out=out)
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 0


def test_plot_course_draws_capacity_lines(tmp_path):
    df = _frame()
    caps = pd.DataFrame({"time": [df["time"].iloc[1]], "delta": [50]})
    out = tmp_path / "chart2.png"
    P.plot_course(df, out=out, capacity_changes=caps)
    assert out.stat().st_size > 0


def test_missing_matplotlib_raises_with_install_hint(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "matplotlib" or name.startswith("matplotlib."):
            raise ImportError("no matplotlib")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(P.PlotDependencyError) as exc:
        P.plot_course(_frame(), out="ignored.png")
    assert "[plot]" in str(exc.value)
