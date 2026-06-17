# UCSD Enrollment Analyzer — Design

Date: 2026-06-16
Status: Approved (pending written-spec review)

## Purpose

A Python package + CLI (`ucsd-enroll-analyzer`) that fetches, caches, parses, and
analyzes historical UCSD course-enrollment data scraped from the
[UCSD-Historical-Enrollment-Data](https://github.com/UCSD-Historical-Enrollment-Data)
GitHub org (docs/attribution: [ewang2002/UCSDHistEnrollData](https://github.com/ewang2002/UCSDHistEnrollData)).

**Primary user goal:** A freshman wants to see *how fast seats drop the moment
registration opens* for a course — i.e. detect the cohort-release / appointment-window
moment and quantify the drop (seats/hour, hours-until-full).

## Tooling decisions

- **Packaging/env:** `uv` (`pyproject.toml` + `uv.lock`).
- **CLI framework:** `click`.
- **Plotting:** `matplotlib` as an optional `[plot]` extra (imported lazily; `plot`
  command errors with a clear install hint if missing).
- **Tables:** `rich` as a light core dependency, with a plain-text fallback if import fails.
- **Python:** target 3.10+.

## Data source (ground truth)

- Each term is its own repo (`2024Fall`, `2023Spring`, ...), default branch `main`.
- Raw files via `https://raw.githubusercontent.com/UCSD-Historical-Enrollment-Data/<TERM>/main/<path>`.
- Per-term layout: `all_courses.txt`, `all_sections.txt`, `overall/<COURSE>.csv`,
  `section/<COURSE>_<SECTION>.csv`. (`raw/`, `cleaned/` ignored.)
- Course/section names with spaces must be URL-encoded (`BILD 4` → `BILD%204`).
- CSV schema: `time,enrolled,available,waitlisted,total` — `time` is ISO 8601, no tz,
  always America/Los_Angeles wall-clock. `total` (capacity) changes over the term.

### Known data-quality issues (handled, not silenced)

1. Irregular scrape intervals — never assume fixed frequency; normalize velocity per hour.
2. `total` changes mid-term — any "percent full" uses that row's `total`.
3. Spring 2022 (`2022Spring`, `2022SpringDrop`) has a **different schema** (no `enrolled`).
   Detect via missing column → mark frame `degraded`, log warning, skip analyses that
   need `enrolled` rather than crash.
4. 404 on fetch = "not offered this term" → return `None` + warning, never crash a batch.
5. Empty / all-zero early rows are real data (registrar hadn't opened seats), not bugs.

## Architecture

Layered, network-free core so load+analysis are fully unit-testable.

```
src/ucsd_enroll_analyzer/
├── constants.py   # KNOWN_TERMS, RAW_BASE_URL, default cache dir
├── fetch.py       # Session+retries, URL-encode, on-disk cache, 404→None
├── load.py        # CSV→tidy DataFrame, dtype coercion, schema detection, term tagging
├── terms.py       # parse "2024Fall"→(year, quarter, sort key) for cross-term alignment
├── analysis.py    # pure functions: fill curve, time-to-capacity, capacity changes,
│                  #   spikes, compare, risk
├── render.py      # rich tables / plain-text fallback / JSON serialization
├── plot.py        # matplotlib (lazy import; only on `plot`)
└── cli.py         # click group + 5 subcommands
tests/
├── fixtures/      # tiny synthetic CSVs (normal + Spring2022 variant + all-zero)
├── test_load.py, test_analysis.py, test_terms.py   # no network
└── test_integration.py   # @pytest.mark.network, one real small file
```

**Layer boundaries:** `fetch` knows only URLs/cache/bytes. `load` owns bytes→DataFrame
and schema detection. `analysis` is pure functions over DataFrames (no I/O). `render`/`plot`
are output-only. `cli` wires them.

## Data layer

- **`fetch.fetch_csv(term, course, section=None, refresh=False) -> Path | None`**
  - `requests.Session` + `urllib3.Retry` (backoff on 429/5xx) + small inter-request sleep.
  - URL built with `urllib.parse.quote` (handles spaces internally).
  - Cache: `./data_cache/<term>/<overall|section>/<file>.csv`; cache hit skips network;
    `refresh=True` bypasses.
  - 404 → `None` + logged warning.
- **`load.load_course(...) -> pd.DataFrame | None`**
  - `time` → `datetime64[ns]` (naive = Pacific, documented); counts → nullable ints.
  - Tags rows with `term`/`course`/`section` → tidy long format, concatenatable.
  - Schema detection: missing `enrolled` → frame marked `degraded=True` + warning.
  - Empty/all-zero files load normally.

## Analysis API (pure functions)

| Function | Approach | Default (overridable) |
|---|---|---|
| `fill_curve` | `(total - available)/total` per row; first/all timestamps `available==0`, plus reopens | — |
| `capacity_changes` | every row where `total != prev total`, with timestamps | — |
| `time_to_capacity` | from start time to first `available==0` | start = first `total` jump **≥ 10 seats**, or user-supplied time |
| `spike_detection` | per-hour enrollment velocity between snapshots; flag windows above `k × term median rate` | **k = 3** |
| `steepest_window` | the single fastest-velocity window — the "registration just opened" signal, surfaced prominently by `analyze` | — |
| `risk_score` | heuristic blend → 0–100 + Low/Med/High; prints every input | weights **fill-speed 50% / waitlist-depth 30% / overenroll-frequency 20%** |
| `compare` | align terms by "days since first seat release"; overlay fill curves | reuses the first-release detector |

`risk_score` output explicitly states it is a heuristic on a few terms of noisy WebReg
scrapes, not a guarantee.

## CLI

- `fetch <term> <course> [--section X]` — pull + cache, print summary stats.
- `analyze <term> <course>` — fill-curve summary, time-to-full, capacity-change log,
  and the steepest-drop window highlighted.
- `compare <course> --terms 2023Fall,2024Fall` — cross-term overlay.
- `risk <term> <course>` — heuristic with all inputs spelled out.
- `plot <term> <course> [--section X] [--out path.png]` — enrolled/available/waitlisted
  over time with vertical lines at detected capacity changes.
- All accept course names with spaces (quoted or not), URL-encoded internally.
- Global flags: `--json`, `--csv PATH`, `--refresh`.
- Unknown term/course → friendly message suggesting that term's `all_courses.txt` +
  the known-terms list, never a raw traceback.

## Error handling

- Network/404 isolated in `fetch`; batch runs never crash on one missing combo.
- Degraded (Spring 2022) frames flow through but skip `enrolled`-dependent analyses
  with a clear message.
- CLI catches known error types → friendly messages; unexpected errors still surface.

## Testing & quality

- Unit tests over synthetic fixtures (no network) for load/analysis/terms, incl. the
  Spring 2022 variant and all-zero early data.
- One `@pytest.mark.network` integration test hitting a real small file to confirm the
  live schema still matches.
- Type hints throughout; `pyproject.toml` configured for `mypy`.
- README: setup, examples, honest heuristic caveats, MIT attribution + links to
  `ewang2002/UCSDHistEnrollData` and its `docs/csv_info.md`.

## Build order

1. Data layer (fetch + cache + load) solid and tested. **Check in with user.**
2. Analysis functions on top.
3. CLI + render + plot last.
