"""Matplotlib charting of a course's enrollment over time (optional extra).

matplotlib is imported lazily inside :func:`plot_course` so the package works
without the ``[plot]`` extra; a missing install raises :class:`PlotDependencyError`
with an install hint instead of a bare ``ImportError``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class PlotDependencyError(RuntimeError):
    """Raised when plotting is requested but matplotlib isn't installed."""


def plot_course(
    df: pd.DataFrame,
    out: str | Path | None = None,
    capacity_changes: pd.DataFrame | None = None,
) -> Path | None:
    """Plot enrolled/available/waitlisted vs time for one course.

    Draws a vertical dashed line at each capacity change. Saves to ``out`` and
    returns its path, or shows the figure interactively and returns ``None`` when
    ``out`` is omitted. Raises :class:`PlotDependencyError` if matplotlib is missing.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise PlotDependencyError(
            "Plotting needs matplotlib. Install the extra: "
            "pip install ucsd-enroll-analyzer[plot]"
        ) from exc

    d = df.sort_values("time")
    fig, ax = plt.subplots(figsize=(10, 6))
    for col in ("enrolled", "available", "waitlisted"):
        if col in d.columns and d[col].notna().any():
            ax.plot(d["time"], d[col].astype("Float64"), label=col, marker=".")

    if capacity_changes is not None and not capacity_changes.empty:
        for t in capacity_changes["time"]:
            ax.axvline(t, color="gray", linestyle="--", alpha=0.6)

    term = d["term"].iloc[0] if "term" in d.columns and len(d) else ""
    course = d["course"].iloc[0] if "course" in d.columns and len(d) else ""
    ax.set_title(f"{course} {term}".strip() or "Enrollment over time")
    ax.set_xlabel("time (America/Los_Angeles)")
    ax.set_ylabel("students")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()

    if out is not None:
        out_path = Path(out)
        fig.savefig(out_path, dpi=100)
        plt.close(fig)
        return out_path
    plt.show()
    plt.close(fig)
    return None
