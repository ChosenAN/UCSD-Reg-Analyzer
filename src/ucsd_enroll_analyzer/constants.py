"""Project-wide constants: canonical term list, base URL, cache location."""

from __future__ import annotations

from pathlib import Path

# Root for raw file fetches. Each term is its own repo under this org.
RAW_BASE = "https://raw.githubusercontent.com/UCSD-Historical-Enrollment-Data"

# Default on-disk cache directory (relative to the current working dir).
DEFAULT_CACHE_DIR = Path("data_cache")

# Canonical, verified list of available term repos. Users may extend this.
KNOWN_TERMS: list[str] = [
    "2022Spring",
    "2022SpringDrop",
    "2022Summer1",
    "2022Summer1Drop",
    "2022Summer2",
    "2022Summer2Drop",
    "2022Summer3",
    "2022Fall",
    "2022FallGrad",
    "2023Winter",
    "2023WinterGrad",
    "2023Spring",
    "2023Summer1",
    "2023Summer2",
    "2023Fall",
    "2024Winter",
    "2024Spring",
    "2024Summer1",
    "2024Summer2",
    "2024Summer3",
    "2024Fall",
    "2025Winter",
    "2025Spring",
]

# Terms known to use the degraded Spring-2022 schema (no `enrolled` column).
SPRING_2022_TERMS: frozenset[str] = frozenset({"2022Spring", "2022SpringDrop"})
