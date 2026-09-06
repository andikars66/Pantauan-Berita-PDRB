from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

WITA = ZoneInfo("Asia/Makassar")

_MONTHS = {
    "jan": 1, "januari": 1, "january": 1,
    "feb": 2, "februari": 2, "february": 2,
    "mar": 3, "maret": 3, "march": 3,
    "apr": 4, "april": 4,
    "mei": 5, "may": 5,
    "jun": 6, "juni": 6, "june": 6,
    "jul": 7, "juli": 7, "july": 7,
    "agu": 8, "agustus": 8, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "okt": 10, "oktober": 10, "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "des": 12, "desember": 12, "dec": 12, "december": 12,
}


def today_wita() -> date:
    return datetime.now(WITA).date()


def year_options(today: date | None = None) -> list[int]:
    today = today or today_wita()
    return [today.year - 1, today.year]


def quarter_for_date(value: date) -> int:
    return (value.month - 1) // 3 + 1


def available_quarters(year: int, today: date | None = None) -> list[int]:
    today = today or today_wita()
    if year == today.year - 1:
        return [1, 2, 3, 4]
    if year == today.year:
        return list(range(1, quarter_for_date(today) + 1))
    return []


def quarter_bounds(year: int, quarter: int, today: date | None = None) -> tuple[date, date]:
    today = today or today_wita()
    if year not in year_options(today):
        raise ValueError("Tahun harus tahun berjalan atau satu tahun sebelumnya.")
    if quarter not in available_quarters(year, today):
        raise ValueError("Triwulan yang dipilih belum tersedia.")
    start_month = (quarter - 1) * 3 + 1
    start = date(year, start_month, 1)
    if quarter == 4:
        end = date(year, 12, 31)
    else:
        end = date(year, start_month + 3, 1) - timedelta(days=1)
    return start, min(end, today)


def _clean(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().lower().replace("–", "-")


def parse_news_date(value: object, run_date: date | None = None) -> date | None:
    """Parse deterministic Indonesian/English absolute and relative news dates."""
    run_date = run_date or today_wita()
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean(str(value))
    if not text:
        return None

    # ISO values, including timestamps and a trailing timezone marker.
    iso_candidate = text.replace("z", "+00:00")
    try:
        return datetime.fromisoformat(iso_candidate).date()
    except ValueError:
        pass

    if text in {"hari ini", "today"}:
        return run_date
    if text in {"kemarin", "yesterday"}:
        return run_date - timedelta(days=1)

    relative = re.search(
        r"\b(\d+)\s*(menit|minute|minutes|jam|hour|hours|hari|day|days|minggu|week|weeks|bulan|month|months|tahun|year|years)\s*(?:yang\s+lalu|lalu|ago)?\b",
        text,
    )
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        if unit in {"menit", "minute", "minutes", "jam", "hour", "hours"}:
            return run_date
        days = amount
        if unit in {"minggu", "week", "weeks"}:
            days = amount * 7
        elif unit in {"bulan", "month", "months"}:
            days = amount * 30
        elif unit in {"tahun", "year", "years"}:
            days = amount * 365
        return run_date - timedelta(days=days)

    # Common numeric formats are interpreted day-first, as used by the portals.
    numeric = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", text)
    if numeric:
        day, month, year = map(int, numeric.groups())
        year = year + 2000 if year < 100 else year
        try:
            return date(year, month, day)
        except ValueError:
            return None

    named = re.search(r"\b(\d{1,2})\s+([a-z]+)\s+(\d{4})\b", text)
    if named:
        day, month_name, year = named.groups()
        month = _MONTHS.get(month_name.rstrip("."))
        if month:
            try:
                return date(int(year), month, int(day))
            except ValueError:
                return None

    named_us = re.search(r"\b([a-z]+)\s+(\d{1,2}),?\s+(\d{4})\b", text)
    if named_us:
        month_name, day, year = named_us.groups()
        month = _MONTHS.get(month_name.rstrip("."))
        if month:
            try:
                return date(int(year), month, int(day))
            except ValueError:
                return None
    return None


def in_period(value: date | None, start: date, end: date) -> bool:
    return value is not None and start <= value <= end


def filter_available_years(values: Iterable[int], today: date | None = None) -> list[int]:
    allowed = set(year_options(today))
    return [value for value in values if value in allowed]
