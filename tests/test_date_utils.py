from datetime import date

import pytest

from src.date_utils import available_quarters, parse_news_date, quarter_bounds, year_options


def test_year_and_quarter_availability():
    today = date(2026, 9, 6)
    assert year_options(today) == [2025, 2026]
    assert available_quarters(2025, today) == [1, 2, 3, 4]
    assert available_quarters(2026, today) == [1, 2, 3]
    assert available_quarters(2024, today) == []


@pytest.mark.parametrize(
    ("quarter", "expected"),
    [
        (1, (date(2026, 1, 1), date(2026, 3, 31))),
        (2, (date(2026, 4, 1), date(2026, 6, 30))),
        (3, (date(2026, 7, 1), date(2026, 9, 6))),
        (4, (date(2025, 10, 1), date(2025, 12, 31))),
    ],
)
def test_quarter_boundaries(quarter, expected):
    year = 2025 if quarter == 4 else 2026
    assert quarter_bounds(year, quarter, date(2026, 9, 6)) == expected


def test_future_quarter_rejected():
    with pytest.raises(ValueError, match="belum tersedia"):
        quarter_bounds(2026, 4, date(2026, 9, 6))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("6 September 2026", date(2026, 9, 6)),
        ("September 6, 2026", date(2026, 9, 6)),
        ("06/09/2026", date(2026, 9, 6)),
        ("2026-09-06T07:30:00+08:00", date(2026, 9, 6)),
        ("2 days ago", date(2026, 9, 4)),
        ("3 jam lalu", date(2026, 9, 6)),
    ],
)
def test_date_parser(raw, expected):
    assert parse_news_date(raw, date(2026, 9, 6)) == expected


def test_unverifiable_date_is_none():
    assert parse_news_date("tanggal tidak diketahui", date(2026, 9, 6)) is None
