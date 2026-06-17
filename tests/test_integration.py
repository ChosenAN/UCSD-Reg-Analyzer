"""Live-network integration test. Skipped unless run with ``-m network``.

Guards against the upstream CSV schema drifting away from what :mod:`load`
codes for. Hits raw.githubusercontent.com, so it is opt-in only.
"""

from __future__ import annotations

import pytest

from ucsd_enroll_analyzer.load import load_course

EXPECTED_COLUMNS = [
    "time",
    "enrolled",
    "available",
    "waitlisted",
    "total",
    "term",
    "course",
    "section",
]


@pytest.mark.network
def test_live_load_course_matches_coded_schema(tmp_path):
    df = load_course("2024Fall", "BILD 4", cache_dir=tmp_path)
    assert df is not None, "expected BILD 4 to have been offered in 2024Fall"
    assert list(df.columns) == EXPECTED_COLUMNS
    assert len(df) > 0
    assert df.attrs.get("degraded") is False


@pytest.mark.network
def test_build_web_one_term(tmp_path):
    import json

    from ucsd_enroll_analyzer import ingest

    out = ingest.build_web(["2025Spring"], tmp_path / "data", cache_dir=tmp_path / "cache")
    index = json.loads((out / "index.json").read_text())
    assert index["terms"][0]["term"] == "2025Spring"
    assert index["terms"][0]["courses"] > 0
    rows = json.loads((out / "2025Spring.json").read_text())
    assert {"course", "risk_label", "snapshots"} <= set(rows[0])
