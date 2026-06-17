"""Command-line interface wiring fetch -> load -> analysis -> render/plot.

Commands: ``fetch``, ``analyze``, ``compare``, ``risk``, ``plot``. Global flags
``--json``, ``--csv PATH``, and ``--refresh`` live on the group and apply to any
subcommand. Tests monkeypatch :func:`load_course`/:func:`load_many`, so command
bodies reference them as module globals (not deep imports).
"""

from __future__ import annotations

from typing import Any

import click
import pandas as pd

from . import analysis, plot, render
from .constants import KNOWN_TERMS
from .load import load_course, load_many
from .terms import parse_term


def _check_term(term: str) -> None:
    """Abort with a friendly message if ``term`` isn't a valid repo name."""
    try:
        parse_term(term)
    except ValueError:
        sample = ", ".join(KNOWN_TERMS[-5:])
        raise click.ClickException(
            f"Unknown term {term!r}. Terms look like '2024Fall' or '2023WinterGrad'. "
            f"Recent known terms: {sample}. See KNOWN_TERMS for the full list."
        )


def _not_offered(term: str, course: str) -> click.ClickException:
    """The 'no data' error, pointing users at that term's all_courses.txt."""
    return click.ClickException(
        f"No data for {course!r} in {term} (not offered, or wrong code). "
        f"Check the course code against all_courses.txt for that term."
    )


def _load(ctx: click.Context, term: str, course: str, section: str | None) -> pd.DataFrame:
    """Validate the term, load the frame, or abort with a friendly error."""
    _check_term(term)
    df = load_course(term, course, section, refresh=ctx.obj["refresh"])
    if df is None or df.empty:
        raise _not_offered(term, course)
    return df


def _emit(ctx: click.Context, payload: Any, df: pd.DataFrame | None, table_text: str) -> None:
    """Honor --csv (dump frame) and --json (machine output) vs plain table."""
    if ctx.obj.get("csv_path") and df is not None:
        render.dump_csv(df, ctx.obj["csv_path"])
        click.echo(f"Wrote CSV to {ctx.obj['csv_path']}", err=True)
    if ctx.obj["as_json"]:
        click.echo(render.to_json(payload))
    else:
        click.echo(table_text)


@click.group()
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
@click.option("--csv", "csv_path", type=click.Path(), default=None,
              help="Also dump the underlying frame to this CSV path.")
@click.option("--refresh", is_flag=True, help="Bypass cache and re-fetch.")
@click.pass_context
def main(ctx: click.Context, as_json: bool, csv_path: str | None, refresh: bool) -> None:
    """Analyze historical UCSD enrollment data."""
    ctx.ensure_object(dict)
    ctx.obj.update(as_json=as_json, csv_path=csv_path, refresh=refresh)


@main.command()
@click.argument("term")
@click.argument("course")
@click.option("--section", default=None, help="Section ID, e.g. 'A'.")
@click.pass_context
def fetch(ctx: click.Context, term: str, course: str, section: str | None) -> None:
    """Fetch + cache one course's CSV and report how many snapshots it has."""
    df = _load(ctx, term, course, section)
    _emit(
        ctx,
        {"term": term, "course": course, "section": section, "snapshots": int(len(df))},
        df,
        f"{course} {term}: {len(df)} snapshots cached.",
    )


@main.command()
@click.argument("term")
@click.argument("course")
@click.option("--section", default=None, help="Section ID, e.g. 'A'.")
@click.pass_context
def analyze(ctx: click.Context, term: str, course: str, section: str | None) -> None:
    """Summarize how a course filled: full-times, steepest window, time-to-full."""
    df = _load(ctx, term, course, section)
    fc = analysis.fill_curve(df)
    full_times = analysis.first_full_times(df)
    try:
        steepest = analysis.steepest_window(df)
    except ValueError:
        steepest = None
    ttc = analysis.time_to_capacity(df)
    final_pct = (
        round(float(fc["pct_full"].dropna().iloc[-1]), 3)
        if fc["pct_full"].notna().any()
        else None
    )

    payload = {
        "term": term,
        "course": course,
        "snapshots": int(len(df)),
        "final_pct_full": final_pct,
        "first_full_times": full_times,
        "time_to_capacity_hours": (
            round(ttc.total_seconds() / 3600.0, 2) if ttc is not None else None
        ),
        "steepest_window": steepest,
    }

    rows: list[list[Any]] = [
        ["snapshots", payload["snapshots"]],
        ["final % full", "n/a" if final_pct is None else f"{final_pct:.0%}"],
        ["times went full", len(full_times)],
        ["hours to full", payload["time_to_capacity_hours"]],
    ]
    if steepest is not None:
        rows.append(
            ["steepest fill window",
             f"{steepest['seats']:.0f} seats in {steepest['hours']:.1f}h "
             f"({steepest['rate']:.1f}/h)"]
        )
    else:
        rows.append(["steepest fill window", "n/a (no enrolled data)"])
    table_text = render.table(rows, ["metric", "value"], title=f"{course} {term}")
    _emit(ctx, payload, df, table_text)


@main.command()
@click.argument("term")
@click.argument("course")
@click.option("--section", default=None, help="Section ID, e.g. 'A'.")
@click.pass_context
def risk(ctx: click.Context, term: str, course: str, section: str | None) -> None:
    """Heuristic 'will I get a seat?' risk score with its inputs and disclaimer."""
    df = _load(ctx, term, course, section)
    result = analysis.risk_score(df)
    inp = result["inputs"]
    rows = [
        ["risk score", f"{result['score']} ({result['label']})"],
        ["hours to full", inp["hours_to_full"]],
        ["peak waitlist", inp["peak_waitlist"]],
        ["over-enrolled", inp["overenrolled"]],
    ]
    table_text = render.table(rows, ["metric", "value"], title=f"Risk: {course} {term}")
    table_text += f"\n\n{result['disclaimer']}"
    _emit(ctx, result, df, table_text)


@main.command()
@click.argument("course")
@click.argument("terms", nargs=-1, required=True)
@click.option("--section", default=None, help="Section ID, e.g. 'A'.")
@click.pass_context
def compare(ctx: click.Context, course: str, terms: tuple[str, ...], section: str | None) -> None:
    """Overlay how a course fills across terms, aligned to each seat release."""
    frames = []
    for term in terms:
        _check_term(term)
        df = load_course(term, course, section, refresh=ctx.obj["refresh"])
        if df is not None and not df.empty:
            frames.append(df)
    if not frames:
        raise _not_offered(", ".join(terms), course)

    aligned = analysis.align_for_compare(frames)
    rows = []
    for term, grp in aligned.groupby("term", sort=False):
        valid = grp.dropna(subset=["pct_full"])
        peak = float(valid["pct_full"].max()) if not valid.empty else None
        days_to_peak = (
            float(valid.loc[valid["pct_full"].idxmax(), "days_since_release"])
            if not valid.empty
            else None
        )
        rows.append([
            term,
            "n/a" if peak is None else f"{peak:.0%}",
            "n/a" if days_to_peak is None else f"{days_to_peak:.2f}",
        ])

    payload = {
        "course": course,
        "terms": list(terms),
        "rows": [
            {"term": r[0], "peak_pct_full": r[1], "days_to_peak": r[2]} for r in rows
        ],
    }
    table_text = render.table(
        rows, ["term", "peak % full", "days to peak"], title=f"Compare: {course}"
    )
    _emit(ctx, payload, aligned, table_text)


@main.command(name="plot")
@click.argument("term")
@click.argument("course")
@click.option("--section", default=None, help="Section ID, e.g. 'A'.")
@click.option("--out", type=click.Path(), default=None, help="PNG output path.")
@click.pass_context
def plot_cmd(ctx: click.Context, term: str, course: str, section: str | None, out: str | None) -> None:
    """Plot enrolled/available/waitlisted over time (needs the [plot] extra)."""
    df = _load(ctx, term, course, section)
    caps = analysis.capacity_changes(df)
    try:
        path = plot.plot_course(df, out=out, capacity_changes=caps)
    except plot.PlotDependencyError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"Saved chart to {path}" if path is not None else "Displayed chart.")


if __name__ == "__main__":  # pragma: no cover
    main()
