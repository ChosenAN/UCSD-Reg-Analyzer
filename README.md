# UCSD Enrollment Analyzer

**🌐 Live dashboard: https://chosenan.github.io/UCSD-Reg-Analyzer/**

A small Python CLI that fetches, caches, and analyzes **historical UCSD course
enrollment data** — with a focus on the question every student actually cares
about: *how fast do seats disappear the moment registration opens?*

It pulls per-course enrollment snapshots from the
[UCSD-Historical-Enrollment-Data](https://github.com/UCSD-Historical-Enrollment-Data)
GitHub org (scraped from WebReg by [`ewang2002/UCSDHistEnrollData`](https://github.com/ewang2002/UCSDHistEnrollData)),
turns them into tidy tables, and computes fill curves, the steepest fill window,
time-to-capacity, a rough risk score, and cross-term comparisons.

## What it does

- **Fetch + cache** raw CSVs locally (`data_cache/`), so repeat analysis is offline.
- **Detect schema drift** — the Spring 2022 terms have no `enrolled` column; those
  frames are flagged *degraded* instead of crashing.
- **Analyze** a single course: fill %, when it first hit 0 seats (including reopen
  → refill cycles), capacity changes, the single fastest-filling interval, and how
  long it took to fill after seats were released.
- **Compare** the same course across multiple terms, aligned to day 0 = each term's
  seat release.
- **Score risk** (Low / Medium / High) of not getting a seat — a heuristic, with the
  inputs and a disclaimer shown.
- **Plot** enrolled / available / waitlisted over time (optional, needs `[plot]`).

## Setup

Requires Python 3.10+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync                 # core install (fetch / load / analyze / risk / compare)
uv sync --extra plot    # also install matplotlib for the `plot` command
```

Run the CLI through uv:

```bash
uv run ucsd-enroll-analyzer --help
```

## Commands

Terms are repo names like `2024Fall`, `2023WinterGrad`, `2022SpringDrop`. Course
codes carry their space (`"BILD 4"`); the tool URL-encodes them for you. Use a term's
`all_courses.txt` (in its repo) to confirm a course code.

```bash
# How many snapshots are cached for a course
uv run ucsd-enroll-analyzer fetch 2024Fall "BILD 4"

# Fill summary + the steepest "registration just opened" window
uv run ucsd-enroll-analyzer analyze 2024Fall "BILD 4"

# Risk of not getting a seat (with disclaimer)
uv run ucsd-enroll-analyzer risk 2024Fall "BILD 4"

# Overlay the same course across terms, aligned to seat release
uv run ucsd-enroll-analyzer compare "BILD 4" 2023Fall 2024Fall

# Chart it (requires `uv sync --extra plot`)
uv run ucsd-enroll-analyzer plot 2024Fall "BILD 4" --out bild4.png
```

Global flags (place before the subcommand):

- `--json` — machine-readable JSON instead of a table.
- `--csv PATH` — also dump the underlying frame to a CSV file.
- `--refresh` — bypass the cache and re-fetch.

```bash
uv run ucsd-enroll-analyzer --json analyze 2024Fall "BILD 4"
```

## Website (static dashboard)

**Live site: https://chosenan.github.io/UCSD-Reg-Analyzer/**

A precomputed static site (`web/`, Vite + React) lets anyone browse, search,
rank, and compare courses in the browser — no backend. The Python CLI is the
precompute engine; the site just renders its output.

```bash
# 1. Precompute per-course summaries into the site's data folder.
#    Coverage is controlled by web_build/terms.txt; --terms overrides it.
uv run ucsd-enroll-analyzer build-web --terms 2024Fall   # writes web/public/data/

# 2. Run the site locally.
cd web
npm install
npm run dev        # http://localhost:5173/UCSD-Reg-Analyzer/
npm test           # frontend unit tests
npm run build      # production build into web/dist
```

- **Dashboard** ranks/sorts/searches a term's courses from the precomputed JSON.
- **Course detail** fetches that course's raw CSV from `raw.githubusercontent.com`
  on demand and charts enrolled/available/waitlisted over time.
- **Compare** overlays a course across terms, aligned to each term's seat release.

**Deploy:** committing `web/**` to `main` triggers `.github/workflows/deploy-pages.yml`,
which builds the site and publishes to GitHub Pages. Enable Pages → "GitHub
Actions" once in repo settings. Refresh data by re-running `build-web` and
committing `web/public/data`.

## Caveats — please read

This is built on **a handful of terms of noisy WebReg scrapes**, not official
registrar data. Snapshots are irregular, capacity changes mid-term, and graduate
appointment windows differ. The risk score is a **heuristic on noisy historical
data, not a guarantee** of what will happen next term. Treat outputs as rough
signal, not fact.

## Development

```bash
uv run pytest -m "not network"   # fast unit suite (no network)
uv run pytest -m network         # opt-in: hits live GitHub to check schema drift
uv run mypy src                  # type-check
```

## Attribution & License

- Data: [UCSD-Historical-Enrollment-Data](https://github.com/UCSD-Historical-Enrollment-Data),
  scraped by [`ewang2002/UCSDHistEnrollData`](https://github.com/ewang2002/UCSDHistEnrollData).
- Column meanings follow that project's `docs/csv_info.md`.
- This tool is licensed under the [MIT License](LICENSE). It is not affiliated with
  or endorsed by UC San Diego.
