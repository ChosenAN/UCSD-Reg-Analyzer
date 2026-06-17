"""Output rendering: rich (or plain-text) tables, JSON, and CSV dumps.

``rich`` is a core dependency, but :func:`table` falls back to aligned plain
text if it ever fails to import, so no render path hard-depends on it.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

import pandas as pd


def _json_default(obj: Any) -> Any:
    """Serialize values the stdlib ``json`` module can't handle on its own."""
    if obj is pd.NA or obj is None:
        return None
    if isinstance(obj, timedelta):  # pd.Timedelta subclasses timedelta
        return obj.total_seconds()
    if isinstance(obj, datetime):  # pd.Timestamp subclasses datetime
        return obj.isoformat()
    if hasattr(obj, "item"):  # numpy / pandas scalar
        value = obj.item()
        return None if pd.isna(value) else value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def to_json(obj: Any) -> str:
    """Dump ``obj`` to indented JSON, serializing Timestamps and timedeltas.

    Timestamps become ISO-8601 strings, timedeltas become float seconds, and
    ``pd.NA`` / NaN become ``null``.
    """
    return json.dumps(obj, default=_json_default, indent=2)


def _plain_table(
    rows: Sequence[Sequence[Any]], headers: Sequence[Any], title: str | None
) -> str:
    """Aligned plain-text table used when ``rich`` is unavailable."""
    str_rows = [[str(c) for c in row] for row in rows]
    widths = [len(str(h)) for h in headers]
    for row in str_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    lines: list[str] = []
    if title:
        lines.append(str(title))
    lines.append("  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers)))
    lines.append("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in str_rows:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


def table(
    rows: Sequence[Sequence[Any]],
    headers: Sequence[Any],
    title: str | None = None,
) -> str:
    """Render ``rows`` as a string table, preferring ``rich`` when importable."""
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        return _plain_table(rows, headers, title)

    t = Table(title=title)
    for h in headers:
        t.add_column(str(h))
    for row in rows:
        t.add_row(*[str(c) for c in row])
    console = Console(file=io.StringIO(), width=120)
    console.print(t)
    return console.file.getvalue()  # type: ignore[attr-defined]


def dump_csv(df: pd.DataFrame, path: str | Path) -> Path:
    """Write ``df`` to ``path`` as CSV (no index). Returns the path."""
    out = Path(path)
    df.to_csv(out, index=False)
    return out
