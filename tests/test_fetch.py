"""Tests for URL building and caching. No real network access."""

from __future__ import annotations

from ucsd_enroll_analyzer.fetch import build_url, cache_path, fetch_csv


def test_build_url_encodes_spaces():
    url = build_url("2024Fall", "BILD 4")
    assert url.endswith("/2024Fall/main/overall/BILD%204.csv")


def test_build_url_section():
    url = build_url("2024Fall", "BILD 4", "A")
    assert url.endswith("/2024Fall/main/section/BILD%204_A.csv")


def test_cache_path_layout(tmp_path):
    p = cache_path("2024Fall", "BILD 4", cache_dir=tmp_path)
    assert p == tmp_path / "2024Fall" / "overall" / "BILD 4.csv"
    s = cache_path("2024Fall", "BILD 4", "A", cache_dir=tmp_path)
    assert s == tmp_path / "2024Fall" / "section" / "BILD 4_A.csv"


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes = b""):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError("raise_for_status should not be reached in test")


class _FakeSession:
    def __init__(self, response: _FakeResponse):
        self.response = response
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        return self.response


def test_cache_hit_skips_network(tmp_path):
    dest = cache_path("2024Fall", "BILD 4", cache_dir=tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("cached")
    session = _FakeSession(_FakeResponse(200, b"new"))
    result = fetch_csv("2024Fall", "BILD 4", cache_dir=tmp_path, session=session, delay=0)
    assert result == dest
    assert session.calls == 0  # served from cache, no network


def test_404_returns_none(tmp_path):
    session = _FakeSession(_FakeResponse(404))
    result = fetch_csv("2024Fall", "NOPE 999", cache_dir=tmp_path, session=session, delay=0)
    assert result is None
    assert session.calls == 1


def test_successful_fetch_writes_cache(tmp_path):
    session = _FakeSession(_FakeResponse(200, b"time,enrolled\n2024-01-01T00:00:00,1\n"))
    result = fetch_csv("2024Fall", "BILD 4", cache_dir=tmp_path, session=session, delay=0)
    assert result is not None
    assert result.exists()
    assert result.read_bytes().startswith(b"time,enrolled")
