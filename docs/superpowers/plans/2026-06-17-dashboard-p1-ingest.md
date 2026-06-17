# Dashboard Phase 1 — Ingest / Data Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python ingest step (`build-web` CLI command) that, for a user-configurable list of terms, computes per-course enrollment summary metrics and writes compact JSON the static frontend will consume.

**Architecture:** New `ingest.py` module reusing the tested `load`/`analysis`/`fetch` layers. A `web_build/terms.txt` controls coverage. Output is `web/public/data/index.json` + one `web/public/data/<term>.json` per term. Pure functions are unit-tested without network; the term loop is tested with monkeypatched `load_course`.

**Tech Stack:** Python 3.10+, pandas, click, requests (all already deps). No new dependencies.

## Global Constraints

- Reuse existing modules; do not reimplement analysis. Consume `load.load_course`, `analysis.*`, `fetch.get_session`/`fetch.build_url`-style URL logic, `terms.parse_term`, `constants.KNOWN_TERMS`/`RAW_BASE`/`DEFAULT_CACHE_DIR`.
- Tests must not hit the network except those marked `@pytest.mark.network`.
- Degraded (Spring 2022, no `enrolled`) frames must yield a row with null velocity/risk fields, never a crash.
- Course not offered (`load_course` → `None`) → skipped, never a crash.
- JSON must be valid and use the field names defined here verbatim.
- Run tests with `.venv/Scripts/python.exe -m pytest` (uv is not on PATH in this environment); mypy via `.venv/Scripts/python.exe -m mypy src`.

---

### Task 1: `web_build/terms.txt` + `load_terms`

**Files:**
- Create: `web_build/terms.txt`
- Create: `src/ucsd_enroll_analyzer/ingest.py`
- Create: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `terms.parse_term`, `constants.KNOWN_TERMS`.
- Produces: `load_terms(path: Path | None = None, override: str | None = None) -> list[str]` — returns validated term names. `override` (comma-separated) wins over the file. Lines that are blank or start with `#` are ignored; names failing `parse_term` are skipped with a logged warning.

- [ ] **Step 1: Write `web_build/terms.txt`** seeded with all 23 known terms, with a header comment.

```
# Terms the dashboard build covers. One term repo name per line.
# Comment out (with #) or delete lines to shrink coverage; add lines to extend.
# Names are validated; invalid ones are skipped with a warning.
2022Spring
2022SpringDrop
2022Summer1
2022Summer1Drop
2022Summer2
2022Summer2Drop
2022Summer3
2022Fall
2022FallGrad
2023Winter
2023WinterGrad
2023Spring
2023Summer1
2023Summer2
2023Fall
2024Winter
2024Spring
2024Summer1
2024Summer2
2024Summer3
2024Fall
2025Winter
2025Spring
```

- [ ] **Step 2: Write the failing test** in `tests/test_ingest.py`.

```python
"""Tests for the web ingest pipeline (no network in unit tests)."""

from __future__ import annotations

from ucsd_enroll_analyzer import ingest


def test_load_terms_skips_comments_blanks_and_invalid(tmp_path, caplog):
    f = tmp_path / "terms.txt"
    f.write_text("# header\n\n2024Fall\nNotATerm\n2025Winter\n")
    terms = ingest.load_terms(path=f)
    assert terms == ["2024Fall", "2025Winter"]


def test_load_terms_override_wins(tmp_path):
    f = tmp_path / "terms.txt"
    f.write_text("2024Fall\n")
    terms = ingest.load_terms(path=f, override="2023Fall, 2025Spring")
    assert terms == ["2023Fall", "2025Spring"]
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ingest.py -q`
Expected: FAIL (cannot import `ingest`).

- [ ] **Step 4: Implement `load_terms`** at the top of `src/ucsd_enroll_analyzer/ingest.py`.

```python
"""Build the static-dashboard dataset: per-course summary metrics as JSON.

Reuses the tested load/analysis layers; only the term loop and JSON shaping are
new here.
"""

from __future__ import annotations

import logging
from pathlib import Path

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
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ingest.py -q`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add web_build/terms.txt src/ucsd_enroll_analyzer/ingest.py tests/test_ingest.py
git commit -m "feat(ingest): configurable terms.txt + load_terms"
```

---

### Task 2: `summarize_course(df) -> dict`

**Files:**
- Modify: `src/ucsd_enroll_analyzer/ingest.py`
- Modify: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `analysis.fill_curve`, `analysis.time_to_capacity`, `analysis.steepest_window`, `analysis.risk_inputs`, `analysis.risk_score`.
- Produces: `summarize_course(df: pd.DataFrame) -> dict` — one row of summary fields. Velocity/risk fields are `None` on degraded frames. Fields: `course`, `nominal_capacity`, `hours_to_full`, `peak_enrolled_per_hour`, `peak_waitlist`, `final_pct_full`, `risk_score`, `risk_label`, `snapshots`, `degraded`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_ingest.py`). Reuse the `make` helper pattern from `tests/test_analysis.py`.

```python
import pandas as pd
import pytest


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ingest.py -q`
Expected: FAIL (`summarize_course` not defined).

- [ ] **Step 3: Implement `summarize_course`** (add to `ingest.py`; add `import pandas as pd` and `from . import analysis` at top).

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ingest.py -q`
Expected: PASS (4 tests total).

- [ ] **Step 5: Commit**

```bash
git add src/ucsd_enroll_analyzer/ingest.py tests/test_ingest.py
git commit -m "feat(ingest): per-course summary row builder"
```

---

### Task 3: course-list fetch + `ingest_term`

**Files:**
- Modify: `src/ucsd_enroll_analyzer/ingest.py`
- Modify: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `constants.RAW_BASE`, `constants.DEFAULT_CACHE_DIR`, `fetch.get_session`, `load.load_course`.
- Produces:
  - `fetch_course_list(term, *, session=None, cache_dir=DEFAULT_CACHE_DIR) -> list[str]` — fetch and parse that term's `all_courses.txt` (one code per line, blanks stripped). `[]` on 404/error (logged).
  - `ingest_term(term, *, refresh=False, cache_dir=DEFAULT_CACHE_DIR) -> list[dict]` — summary rows for every offered course in the term (skips `None`).

- [ ] **Step 1: Write the failing test** (append). Monkeypatch `fetch_course_list` and `load_course` so no network is used.

```python
def test_ingest_term_summarizes_offered_courses(monkeypatch):
    monkeypatch.setattr(ingest, "fetch_course_list", lambda *a, **k: ["BILD 4", "MATH 20A", "GONE 1"])

    def fake_load(term, course, section=None, **kwargs):
        if course == "GONE 1":
            return None  # not offered
        return _make([
            {"h": 0, "enrolled": 0, "available": 0, "total": 0},
            {"h": 1, "enrolled": 50, "available": 50, "total": 100},
        ], course=course)

    monkeypatch.setattr(ingest, "load_course", fake_load)
    rows = ingest.ingest_term("2024Fall")
    assert [r["course"] for r in rows] == ["BILD 4", "MATH 20A"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ingest.py::test_ingest_term_summarizes_offered_courses -q`
Expected: FAIL (`ingest_term` not defined).

- [ ] **Step 3: Implement** (add to `ingest.py`; add imports `from .constants import RAW_BASE, DEFAULT_CACHE_DIR`, `from .fetch import get_session`, `from .load import load_course`).

```python
def fetch_course_list(
    term: str, *, session=None, cache_dir: Path = DEFAULT_CACHE_DIR
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
    """Summary rows for every offered course in ``term``."""
    courses = fetch_course_list(term, cache_dir=cache_dir)
    rows: list[dict] = []
    for course in courses:
        df = load_course(term, course, refresh=refresh, cache_dir=cache_dir)
        if df is None or df.empty:
            continue
        rows.append(summarize_course(df))
    logger.info("Ingested %s: %d/%d courses had data.", term, len(rows), len(courses))
    return rows
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ingest.py -q`
Expected: PASS (5 tests total).

- [ ] **Step 5: Commit**

```bash
git add src/ucsd_enroll_analyzer/ingest.py tests/test_ingest.py
git commit -m "feat(ingest): course-list fetch + per-term ingest"
```

---

### Task 4: `build_web` writer + CLI `build-web` command

**Files:**
- Modify: `src/ucsd_enroll_analyzer/ingest.py`
- Modify: `src/ucsd_enroll_analyzer/cli.py`
- Modify: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `load_terms`, `ingest_term`.
- Produces:
  - `build_web(terms, out_dir, *, refresh=False, cache_dir=DEFAULT_CACHE_DIR) -> Path` — writes `<out_dir>/<term>.json` (array of rows) per term and `<out_dir>/index.json` (`{built_at, terms:[{term,courses}]}`). Returns `out_dir`.
  - CLI: `build-web` subcommand on the existing group, options `--terms TEXT`, `--terms-file PATH`, `--out PATH` (default `web/public/data`), plus the group's `--refresh`.

- [ ] **Step 1: Write the failing tests** (append). Monkeypatch `ingest_term` so no network/cache is used.

```python
import json
from click.testing import CliRunner
from ucsd_enroll_analyzer import cli


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ingest.py -q`
Expected: FAIL (`build_web` / `build-web` not defined).

- [ ] **Step 3: Implement `build_web`** in `ingest.py` (add `import json`, `from datetime import datetime, timezone`).

```python
def build_web(
    terms: list[str],
    out_dir: Path,
    *,
    refresh: bool = False,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> Path:
    """Ingest each term and write <term>.json plus an index.json."""
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
```

- [ ] **Step 4: Add the CLI command** to `src/ucsd_enroll_analyzer/cli.py`. Add `from . import ingest` to the existing imports, then append this command before the `if __name__` block.

```python
@main.command(name="build-web")
@click.option("--terms", "terms_override", default=None,
              help="Comma-separated terms to build (overrides --terms-file).")
@click.option("--terms-file", type=click.Path(), default=None,
              help="Path to terms.txt (default: web_build/terms.txt).")
@click.option("--out", type=click.Path(), default="web/public/data",
              help="Output directory for the JSON dataset.")
@click.pass_context
def build_web_cmd(ctx, terms_override, terms_file, out):
    """Build the static-dashboard JSON dataset from configured terms."""
    from pathlib import Path as _Path
    chosen = ingest.load_terms(
        path=_Path(terms_file) if terms_file else None, override=terms_override
    )
    if not chosen:
        raise click.ClickException("No valid terms to build (check terms.txt/--terms).")
    out_dir = ingest.build_web(chosen, _Path(out), refresh=ctx.obj["refresh"])
    click.echo(f"Built {len(chosen)} term(s) into {out_dir}")
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ingest.py -q`
Expected: PASS (7 tests total).

- [ ] **Step 6: Full suite + mypy**

Run: `.venv/Scripts/python.exe -m pytest -m "not network" -q && .venv/Scripts/python.exe -m mypy src`
Expected: all pass; mypy clean.

- [ ] **Step 7: Commit**

```bash
git add src/ucsd_enroll_analyzer/ingest.py src/ucsd_enroll_analyzer/cli.py tests/test_ingest.py
git commit -m "feat(ingest): build-web writes index.json + per-term JSON dataset"
```

---

### Task 5: smoke-build a real term (network, opt-in)

**Files:**
- Modify: `tests/test_integration.py`

**Interfaces:** none new.

- [ ] **Step 1: Add an opt-in network test** that builds a single term to a temp dir and checks the dataset shape. (Will only run with `-m network`.)

```python
@pytest.mark.network
def test_build_web_one_term(tmp_path):
    from ucsd_enroll_analyzer import ingest
    out = ingest.build_web(["2025Spring"], tmp_path / "data", cache_dir=tmp_path / "cache")
    import json
    index = json.loads((out / "index.json").read_text())
    assert index["terms"][0]["term"] == "2025Spring"
    assert index["terms"][0]["courses"] > 0
    rows = json.loads((out / "2025Spring.json").read_text())
    assert {"course", "risk_label", "snapshots"} <= set(rows[0])
```

- [ ] **Step 2: Commit**

```bash
git add tests/test_integration.py
git commit -m "test(ingest): opt-in network smoke build of one term"
```

---

## Self-Review

- **Spec coverage (P1 scope):** configurable `terms.txt` + `--terms` override (T1); per-course summary fields exactly as specified incl. degraded nulls (T2); per-term ingest skipping not-offered courses (T3); `index.json` + `<term>.json` writer and `build-web` CLI (T4); opt-in network smoke (T5). Frontend (P2–P4) and deploy (P5) are out of scope for this plan and get their own plans.
- **Placeholder scan:** none — every step has concrete code/commands.
- **Type consistency:** `load_terms`, `summarize_course`, `fetch_course_list`, `ingest_term`, `build_web` signatures and the summary field names are used consistently across T1–T5 and match the spec's field table.
- **Roadmap (future plans):** P2 dashboard table; P3 course detail + live CSV chart; P4 compare; P5 GitHub Pages deploy.
