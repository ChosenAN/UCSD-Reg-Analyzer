# UCSD Enrollment Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `uv`-managed Python package + `click` CLI that fetches, caches, parses, and analyzes historical UCSD enrollment CSVs, with a focus on showing how fast seats drop when registration opens.

**Architecture:** Layered, network-free core. `fetch` (URLs/cache/bytes) → `load` (bytes→tidy DataFrame + schema detection) → `analysis` (pure functions) → `render`/`plot` (output) → `cli` (wiring). Load+analysis are fully unit-testable without network.

**Tech Stack:** Python 3.10+, uv, pandas, requests, click, rich (core); matplotlib (optional `[plot]` extra); pytest, mypy.

## Global Constraints

- Python 3.10+; manage env/deps with `uv`; `pyproject.toml` + `uv.lock`.
- Package name `ucsd-enroll-analyzer`; import package `ucsd_enroll_analyzer` under `src/`.
- `matplotlib` only in optional `[plot]` extra, imported lazily inside `plot.py`.
- `rich` is a core dep but every render path must have a plain-text fallback.
- Course/section names with spaces are URL-encoded internally (`urllib.parse.quote`); users never encode manually.
- `time` parsed as naive `datetime64[ns]`, documented as America/Los_Angeles wall-clock.
- 404 → `None` + logged warning, never an exception that crashes a batch.
- Spring 2022 schema (no `enrolled`) → frame marked degraded + warning, not a crash.
- Tests must not require network except those marked `@pytest.mark.network`.
- License MIT; README attributes `ewang2002/UCSDHistEnrollData` + `docs/csv_info.md`.

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `LICENSE`, `src/ucsd_enroll_analyzer/__init__.py`, `tests/__init__.py`
- Init: git repo

**Interfaces:**
- Produces: installable package skeleton; `[project.scripts] ucsd-enroll-analyzer = "ucsd_enroll_analyzer.cli:main"`; `[project.optional-dependencies] plot = ["matplotlib"]`; pytest config with `network` marker; mypy config.

- [ ] `git init`; write `.gitignore` (`.venv/`, `__pycache__/`, `data_cache/`, `*.egg-info`, `.pytest_cache/`, `.mypy_cache/`).
- [ ] Write `pyproject.toml`: build backend (hatchling), deps `pandas`, `requests`, `click`, `rich`; optional `plot`; dev group `pytest`, `mypy`; `[tool.pytest.ini_options] markers = ["network: hits live GitHub"]`; `[tool.mypy]` basic strictness.
- [ ] `uv sync` to create env + lock.
- [ ] Verify `uv run python -c "import ucsd_enroll_analyzer"` succeeds.
- [ ] Commit.

---

### Task 2: `constants.py` + `terms.py`

**Files:**
- Create: `src/ucsd_enroll_analyzer/constants.py`, `src/ucsd_enroll_analyzer/terms.py`, `tests/test_terms.py`

**Interfaces:**
- Produces:
  - `KNOWN_TERMS: list[str]` (the 23 canonical term repo names).
  - `RAW_BASE = "https://raw.githubusercontent.com/UCSD-Historical-Enrollment-Data"`.
  - `DEFAULT_CACHE_DIR: Path` (`./data_cache`).
  - `parse_term(term: str) -> ParsedTerm` where `ParsedTerm` is a dataclass `(raw, year:int, quarter:str, is_grad:bool, is_drop:bool, sort_key:tuple)`.
  - `quarter_order: dict[str,int]` so terms sort chronologically (Winter<Spring<Summer1<Summer2<Summer3<Fall).

- [ ] Write `test_terms.py`: `parse_term("2024Fall")` → year 2024, quarter "Fall"; `"2023WinterGrad"` → is_grad True; `"2022SpringDrop"` → is_drop True; sort_key orders `2023Fall` before `2024Winter`.
- [ ] Run tests → fail.
- [ ] Implement `constants.py` (KNOWN_TERMS verbatim from spec) and `terms.parse_term` (regex `^(\d{4})(Winter|Spring|Summer[123]|Fall)(Grad)?(Drop)?$`).
- [ ] Run tests → pass. Commit.

---

### Task 3: `fetch.py` — URL building + cache (no real network in tests)

**Files:**
- Create: `src/ucsd_enroll_analyzer/fetch.py`, `tests/test_fetch.py`

**Interfaces:**
- Consumes: `RAW_BASE`, `DEFAULT_CACHE_DIR`.
- Produces:
  - `build_url(term, course, section=None) -> str` (URL-encoded path: `overall/BILD%204.csv` or `section/BILD%204_A.csv`).
  - `cache_path(term, course, section=None, cache_dir=DEFAULT_CACHE_DIR) -> Path`.
  - `fetch_csv(term, course, section=None, *, refresh=False, cache_dir=DEFAULT_CACHE_DIR, session=None) -> Path | None` — returns cached path, fetches on miss, `None` on 404.
  - `get_session() -> requests.Session` with `urllib3.Retry` (total=3, backoff_factor, status_forcelist=[429,500,502,503,504]).

- [ ] Test `build_url`: spaces → `%20`; section path format. (pure, no network)
- [ ] Test `cache_path` directory layout.
- [ ] Test `fetch_csv` cache-hit path returns existing file without calling session (inject a mock session; assert not called).
- [ ] Test `fetch_csv` 404 → `None` + warning logged (mock session returning 404).
- [ ] Run → fail. Implement. Run → pass. Commit.

---

### Task 4: `load.py` — CSV → tidy DataFrame + schema detection

**Files:**
- Create: `src/ucsd_enroll_analyzer/load.py`, `tests/test_load.py`, fixtures under `tests/fixtures/` (`normal.csv`, `spring2022.csv` (no `enrolled`), `allzero.csv`, `empty.csv`).

**Interfaces:**
- Consumes: `fetch.fetch_csv`, `terms.parse_term`.
- Produces:
  - `parse_csv(path, term, course, section=None) -> pd.DataFrame` — columns `time`(datetime64), `enrolled`/`available`/`waitlisted`/`total`(nullable Int64), plus tag cols `term`,`course`,`section`. Sets `df.attrs["degraded"]=True` when `enrolled` missing (adds `enrolled` as all-NA).
  - `load_course(term, course, section=None, *, refresh=False, cache_dir=...) -> pd.DataFrame | None` — fetch then parse; `None` if not offered.
  - `load_many(specs) -> pd.DataFrame` — concat of multiple, skipping `None`s.

- [ ] Tests: normal fixture → correct dtypes, tag columns, row count; spring2022 fixture → `attrs["degraded"]` True + `enrolled` all NA; allzero → loads, no error; empty → empty frame, no crash; `load_course` returns `None` when `fetch_csv` returns `None`.
- [ ] Run → fail. Implement. Run → pass. Commit.

**CHECK IN WITH USER after Task 4 — data layer working.**

---

### Task 5: `analysis.py` part 1 — fill curve, capacity changes, first release

**Files:**
- Create: `src/ucsd_enroll_analyzer/analysis.py`, `tests/test_analysis.py`

**Interfaces:**
- Consumes: tidy DataFrame from `load`.
- Produces (all pure, operate on one course's frame sorted by `time`):
  - `fill_curve(df) -> pd.DataFrame` adds `pct_full = (total-available)/total` (NA where total 0/NA).
  - `first_full_times(df) -> list[Timestamp]` timestamps where `available` first hits 0, including reopen→refill cycles.
  - `capacity_changes(df) -> pd.DataFrame` rows where `total != prev`, with `delta`, `time`.
  - `first_seat_release(df, min_jump=10) -> Timestamp | None` first `total` positive jump ≥ `min_jump` (fallback: first row with total>0).

- [ ] Tests with small in-memory DataFrames covering: pct uses per-row total; reopen cycle yields two full-times; capacity_changes lists each change with correct delta; first_seat_release picks the ≥10 jump and the fallback.
- [ ] Run → fail. Implement. Run → pass. Commit.

---

### Task 6: `analysis.py` part 2 — velocity, spikes, steepest window, time-to-capacity

**Files:**
- Modify: `src/ucsd_enroll_analyzer/analysis.py`; extend `tests/test_analysis.py`

**Interfaces:**
- Consumes: frame + `first_seat_release`.
- Produces:
  - `velocity(df) -> pd.DataFrame` per-interval `enrolled_per_hour` (Δenrolled / Δhours), skipping degraded frames (raise/clear message if no `enrolled`).
  - `spike_windows(df, k=3) -> pd.DataFrame` intervals where rate ≥ `k × median rate`.
  - `steepest_window(df) -> dict` the single max-rate interval (start, end, rate, seats) — the "registration just opened" signal.
  - `time_to_capacity(df, start=None, min_jump=10) -> timedelta | None` from start (or `first_seat_release`) to first `available==0` after start.

- [ ] Tests: synthetic frame with one obvious burst → `steepest_window` finds it; `spike_windows` flags it at k=3; `time_to_capacity` measures correct duration; degraded frame → velocity raises clear error.
- [ ] Run → fail. Implement. Run → pass. Commit.

---

### Task 7: `analysis.py` part 3 — risk score + cross-term compare

**Files:**
- Modify: `src/ucsd_enroll_analyzer/analysis.py`; extend `tests/test_analysis.py`

**Interfaces:**
- Produces:
  - `risk_inputs(df) -> dict` — fill speed (hrs to full or seats/hr), peak waitlist, overenroll flag (`enrolled > total`), each as named fields.
  - `risk_score(df, weights=(0.5,0.3,0.2)) -> dict` — normalized 0–100 score, Low/Med/High label, the input dict, and a `disclaimer` string ("heuristic on noisy historical scrapes, not a guarantee").
  - `align_for_compare(frames, min_jump=10) -> pd.DataFrame` — long frame with `days_since_release` (from each term's `first_seat_release`) and `pct_full`, tagged `term`, for overlay.

- [ ] Tests: risk_inputs computes peak waitlist + overenroll flag; risk_score returns label thresholds + includes disclaimer + inputs; align_for_compare aligns two synthetic terms to day-0 at their releases.
- [ ] Run → fail. Implement. Run → pass. Commit.

---

### Task 8: `render.py` — tables / JSON / CSV dump

**Files:**
- Create: `src/ucsd_enroll_analyzer/render.py`, `tests/test_render.py`

**Interfaces:**
- Produces:
  - `table(rows, headers, title=None) -> str` rich table if import OK else aligned plain text.
  - `to_json(obj) -> str` JSON with Timestamps/timedeltas serialized to ISO/seconds.
  - `dump_csv(df, path)`.

- [ ] Tests: `to_json` serializes a dict containing Timestamp + timedelta without error; `table` returns a string containing the headers (works regardless of rich presence).
- [ ] Run → fail. Implement. Run → pass. Commit.

---

### Task 9: `plot.py` — matplotlib chart (lazy import)

**Files:**
- Create: `src/ucsd_enroll_analyzer/plot.py`, `tests/test_plot.py`

**Interfaces:**
- Produces: `plot_course(df, out=None, capacity_changes=None) -> Path | None` — plots enrolled/available/waitlisted vs time with vertical lines at capacity changes; saves to `out` or shows; raises `PlotDependencyError` (clear install hint) if matplotlib missing.

- [ ] Test: with matplotlib installed (dev env has it via `[plot]`), `plot_course(df, out=tmp.png)` writes a non-empty PNG; if import fails, error message mentions `pip install ucsd-enroll-analyzer[plot]`. Use `Agg` backend in test.
- [ ] Run → fail. Implement. Run → pass. Commit.

---

### Task 10: `cli.py` — wire up all commands

**Files:**
- Create: `src/ucsd_enroll_analyzer/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `main()` click group with `fetch`, `analyze`, `compare`, `risk`, `plot`; global `--json`, `--csv PATH`, `--refresh`; friendly unknown-term/course messages referencing `all_courses.txt` + KNOWN_TERMS.

- [ ] Tests via `click.testing.CliRunner` with monkeypatched `load_course`/`load_many` (no network): `analyze` prints fill summary + steepest window; `--json` emits valid JSON; unknown term → friendly message + exit nonzero; `risk` prints disclaimer.
- [ ] Run → fail. Implement. Run → pass. Commit.

---

### Task 11: Integration test (network) + README

**Files:**
- Create: `tests/test_integration.py`, `README.md`

**Interfaces:** none new.

- [ ] `@pytest.mark.network` test: `load_course("2024Fall", "BILD 4")` returns a frame whose columns match the coded schema (asserts the live schema still matches). Skipped by default unless `-m network`.
- [ ] README: what it is, `uv sync` setup, install `[plot]` extra, example commands for all 5 commands, honest heuristic caveats (few terms of noisy WebReg scrapes, not official registrar data), MIT attribution + links to `ewang2002/UCSDHistEnrollData` and `docs/csv_info.md`.
- [ ] Run full unit suite (`uv run pytest -m "not network"`) → pass; `uv run mypy src` → clean. Commit.

---

## Self-Review

- **Spec coverage:** fetch+cache (T3), loader+schema detection+404 (T4), fill curve (T5), time-to-capacity (T6), capacity changes (T5), spikes+steepest window (T6), cross-term compare (T7), risk (T7), all 5 CLI commands + flags (T10), rich/plain/JSON/CSV output (T8/T10), plot (T9), unit + network tests (T4–T11), type hints + mypy (T1/T11), README + attribution (T11). All covered.
- **Placeholder scan:** none.
- **Type consistency:** `first_seat_release`/`min_jump` reused consistently T5–T7; `load_course`/`load_many` names consistent T4/T10; `risk_score` returns dict-with-disclaimer consistent T7/T10.
