"""Parse term repo names like ``2024Fall`` into structured, sortable data."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Chronological order of quarters within a calendar year.
QUARTER_ORDER: dict[str, int] = {
    "Winter": 0,
    "Spring": 1,
    "Summer1": 2,
    "Summer2": 3,
    "Summer3": 4,
    "Fall": 5,
}

_TERM_RE = re.compile(r"^(\d{4})(Winter|Spring|Summer[123]|Fall)(Grad)?(Drop)?$")


@dataclass(frozen=True)
class ParsedTerm:
    """Structured form of a term repo name."""

    raw: str
    year: int
    quarter: str
    is_grad: bool
    is_drop: bool

    @property
    def sort_key(self) -> tuple[int, int]:
        """Chronological sort key: (year, quarter index)."""
        return (self.year, QUARTER_ORDER[self.quarter])


def parse_term(term: str) -> ParsedTerm:
    """Parse a term repo name. Raises ``ValueError`` on an unrecognized name."""
    match = _TERM_RE.match(term)
    if match is None:
        raise ValueError(
            f"Unrecognized term name: {term!r}. "
            "Expected forms like '2024Fall', '2023WinterGrad', '2022SpringDrop'."
        )
    year, quarter, grad, drop = match.groups()
    return ParsedTerm(
        raw=term,
        year=int(year),
        quarter=quarter,
        is_grad=grad is not None,
        is_drop=drop is not None,
    )
