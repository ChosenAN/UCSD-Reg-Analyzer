"""Tests for term-name parsing."""

from __future__ import annotations

import pytest

from ucsd_enroll_analyzer.terms import parse_term


def test_basic_term():
    p = parse_term("2024Fall")
    assert p.year == 2024
    assert p.quarter == "Fall"
    assert p.is_grad is False
    assert p.is_drop is False


def test_grad_flag():
    assert parse_term("2023WinterGrad").is_grad is True


def test_drop_flag():
    p = parse_term("2022SpringDrop")
    assert p.is_drop is True
    assert p.quarter == "Spring"


def test_chronological_sort_key():
    assert parse_term("2023Fall").sort_key < parse_term("2024Winter").sort_key
    assert parse_term("2024Summer1").sort_key < parse_term("2024Summer2").sort_key


def test_invalid_term_raises():
    with pytest.raises(ValueError):
        parse_term("NotATerm")
