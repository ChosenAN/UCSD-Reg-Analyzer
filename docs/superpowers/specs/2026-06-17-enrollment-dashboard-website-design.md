# Enrollment Dashboard Website — Design

**Date:** 2026-06-17
**Status:** Approved design, pending spec review
**Builds on:** the existing `ucsd_enroll_analyzer` Python package (fetch → load → analysis → render/plot + CLI).

## Goal

A public, free-to-host **website** that lets anyone browse, search, rank, and
compare historical UCSD course enrollment — surfacing how fast seats drop when
registration opens. It reuses the existing, tested Python analysis as a
precompute engine; the site itself is a static frontend with no backend server.

## Why this architecture (Approach A: precomputed static)

The source data is one CSV per course across ~23 term repos (tens of thousands of
files). Ranking/searching all courses requires their metrics precomputed — it
cannot be done live per request. Therefore:

- A **Python ingest step** computes per-course summary metrics once and writes
  compact JSON.
- A **static frontend** loads that JSON for instant client-side search/sort/rank.
- **Course charts fetch the raw CSV directly** from `raw.githubusercontent.com`
  in the browser, on demand — so we never store bulky time-series ourselves.

Result: free static hosting (GitHub Pages), no server to run or pay for, no
rewrite of analysis logic in JavaScript, and fast page loads. Data is as fresh as
the last rebuild, which is fine because completed terms never change.

Rejected alternatives: a live FastAPI backend (needs hosting that sleeps/costs,
slow first loads, still needs precompute to rank all courses); a hybrid
serverless API (more complexity, little benefit here).

## Components

### 1. Configurable coverage — `web_build/terms.txt`

- Plain text, one term repo name per line (e.g. `2024Fall`), seeded with all 23
  `KNOWN_TERMS`.
- Lines starting with `#` and blank lines are ignored, so coverage is edited by
  commenting/deleting/adding lines — no code changes.
- Each line is validated with the existing `terms.parse_term`; invalid names are
  skipped with a logged warning.
- A `--terms 2024Fall,2025Winter` CLI flag overrides the file for one-off builds.

### 2. Ingest — `src/ucsd_enroll_analyzer/ingest.py` + CLI `build-web`

- New module `ingest.py`, exposed as a Click subcommand `build-web` on the
  existing CLI group.
- Inputs: the term list (file or `--terms`), an output dir
  (default `web/public/data`), and the existing `--refresh`/`cache_dir` options.
- For each term:
  1. Fetch that term's `all_courses.txt` (via `fetch`, cached) and parse the
     course list. If unavailable, skip the term with a warning.
  2. For each course: `load_course(term, course)` (cache + retries + polite
     delay already handled by `fetch.py`); skip `None`/empty (not offered).
  3. Compute summary metrics via `analysis.py` (see fields below). Degraded
     (Spring 2022, no `enrolled`) frames: velocity/risk fields are `null`, not a
     crash.
  4. Write `web/public/data/<term>.json`.
- After all terms: write `web/public/data/index.json` with the term list, per-term
  course counts, and an ISO `built_at` timestamp.
- Resumable: re-runs reuse the on-disk cache, so they are cheap. Progress is
  logged per term.

**Per-course summary fields** (`<term>.json` is an array of these):

| field | source |
|-------|--------|
| `course` | course code (e.g. `"BILD 4"`) |
| `nominal_capacity` | `risk_inputs` |
| `hours_to_full` | `time_to_capacity` (null if never fills) |
| `peak_enrolled_per_hour` | `steepest_window.rate` (null if degraded) |
| `peak_waitlist` | `risk_inputs` |
| `final_pct_full` | last non-NA `fill_curve.pct_full` |
| `risk_score` | `risk_score.score` (null if degraded) |
| `risk_label` | `risk_score.label` |
| `snapshots` | row count |
| `degraded` | `df.attrs["degraded"]` |

`index.json`: `{ "built_at": ISO8601, "terms": [{ "term": str, "courses": int }] }`.

### 3. Frontend — `web/` (Vite + React + TypeScript)

- **Stack:** Vite + React + TypeScript; Recharts for charts; client-side
  search/sort/filter (no server, no state library needed beyond React state).
- **Views:**
  - **Dashboard** (`/`): pick a term, search by course code, sortable/rankable
    table of the summary fields (e.g. sort by fastest-filling, highest risk).
    Loads `<term>.json` on demand.
  - **Course detail** (`/course/:term/:code`): fetches that course's raw CSV from
    `raw.githubusercontent.com` (URL built the same way as `fetch.build_url`:
    `RAW_BASE/<term>/main/overall/<urlencoded course>.csv`), parses client-side,
    and charts enrolled/available/waitlisted over time. Shows risk score + the
    standard disclaimer, plus the precomputed summary numbers.
  - **Compare** (`/compare`): pick a course + multiple terms; overlay fill curves
    aligned to each term's seat release (mirrors `align_for_compare`), using the
    summary rows plus on-demand CSV fetches.
- **Staleness:** a visible "data last built: <built_at>" banner from `index.json`.
- **Caveats:** the heuristic disclaimer is shown on detail/risk views.

### 4. Deploy — GitHub Pages via GitHub Actions

- A workflow builds the Vite app and publishes `web/dist` to GitHub Pages.
- Data JSON under `web/public/data` is committed to the repo (the ingest output)
  and shipped as static assets. Rebuilds are a manual run of `build-web` followed
  by a commit, or a manual workflow dispatch.

## Data flow

```
terms.txt / --terms
        │  (validate via parse_term)
        ▼
  build-web (ingest.py)
        │  fetch all_courses.txt + per-course CSVs (cached)
        │  load_course → analysis.* → summary rows
        ▼
web/public/data/{index.json, <term>.json}   ← committed
        │
        ▼
  Static frontend (Vite/React)  ──on detail──▶ raw.githubusercontent CSV (live, in browser)
        │
        ▼
  GitHub Pages (free static hosting)
```

## Error handling

- Term repo or `all_courses.txt` missing → skip term, warn, continue.
- Course not offered (404 → `None`) → skip course.
- Degraded schema → emit row with null velocity/risk fields; never crash.
- Frontend CSV fetch failure (course detail) → inline error state, dashboard
  still works from precomputed JSON.
- Invalid term in `terms.txt`/`--terms` → skipped with warning.

## Testing

- **Ingest:** unit-test the summary-row builder against the existing in-memory
  fixtures (normal, degraded, allzero, empty) — assert field values and null
  handling. Test `terms.txt` parsing (comments/blanks/invalid skipped) and
  `--terms` override. No network in unit tests (monkeypatch `load_course`).
- **Frontend:** component tests for the dashboard table (sort/filter) and the raw
  CSV parser/URL builder against a small fixture CSV. Charts smoke-rendered.
- **Integration (opt-in, network):** `build-web --terms 2024Fall` over a tiny
  course subset produces valid `index.json` + `<term>.json`.

## Phasing

Build incrementally; each phase is usable and a natural stopping point.

- **P1 — Ingest + data contract:** `ingest.py`, `build-web` command, `terms.txt`
  (file + `--terms`), JSON output, unit tests. Validate on a couple terms.
- **P2 — Dashboard:** Vite/React scaffold + sortable/searchable/rankable term
  table over `<term>.json`.
- **P3 — Course detail:** live raw-CSV fetch + Recharts time-series + risk panel.
- **P4 — Compare view:** multi-term overlay aligned to seat release.
- **P5 — Deploy:** GitHub Pages Actions workflow + staleness banner + README
  updates.

## Constraints & non-goals

- No backend server, no database, no auth.
- No live/real-time data — historical, rebuilt on demand.
- Full 23-term ingest is a long first run; expected and acceptable (cached,
  resumable). Coverage is user-controlled via `terms.txt`.
- Frontend re-derives only the *chart* series and compare-alignment from raw CSVs;
  all ranking metrics come from the Python precompute (single source of truth).
