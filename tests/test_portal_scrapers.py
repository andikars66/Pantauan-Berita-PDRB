from datetime import date
from html import escape
import json

from src.portal_scrapers import crawl_portal, parse_inside_lombok, parse_lombok_post


HTML = """
<html><body><main>
<article class="post"><h2><a href="/category">Lombok Tengah</a></h2>
<h3 class="entry-title"><a href="/berita-a">Produksi padi meningkat</a></h3>
<time datetime="2026-08-10T08:00:00+08:00">10 Agustus 2026</time><p>Cuplikan</p></article>
</main></body></html>
"""


def test_both_parsers_extract_required_archive_fields():
    for parser in (parse_inside_lombok, parse_lombok_post):
        item = parser(HTML, "https://example.com/")[0]
        assert item["title"] == "Produksi padi meningkat"
        assert item["date_raw"].startswith("2026-08-10")
        assert item["url"] == "https://example.com/berita-a"


def test_lombok_post_current_inertia_payload():
    payload = {
        "props": {"news": {"data": [{
            "title": "Hotel baru di Mandalika", "slug": "hotel-baru-di-mandalika",
            "description": "Cuplikan ekonomi", "date": "2026-09-05 12:06:03",
            "timestamp": "2026-09-05T12:06:03+08:00", "article_id": "2609050001",
            "category": {"slug": "praya"},
        }]}}
    }
    html = f'<div id="app" data-page="{escape(json.dumps(payload), quote=True)}"></div>'
    item = parse_lombok_post(html, "https://lombokpost.jawapos.com/tag/lombok-tengah")[0]
    assert item["snippet"] == "Cuplikan ekonomi"
    assert item["url"] == "https://lombokpost.jawapos.com/praya/2609050001/hotel-baru-di-mandalika"


class Response:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class Session:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.urls = []

    def get(self, url, timeout):
        self.urls.append(url)
        return Response(next(self.pages))


def test_pagination_stops_when_page_is_older_than_period():
    old = HTML.replace("2026-08-10T08:00:00+08:00", "2026-06-10T08:00:00+08:00")
    session = Session([HTML, old])
    records, status = crawl_portal(
        "inside_lombok", "Inside Lombok", "https://example.com/category/", date(2026, 7, 1),
        date(2026, 9, 6), date(2026, 9, 6), session=session, max_pages=10,
    )
    assert len(records) == 1
    assert len(session.urls) == 2
    assert status["Lolos Periode"] == 1


import pytest
from pathlib import Path
from src.portal_scrapers import PORTAL_PARSERS, PortalScrapingError, _page_url


@pytest.mark.parametrize("portal,count", [("radar_mandalika", 2), ("radar_lombok", 2), ("suara_ntb", 3), ("pemkab_loteng", 2)])
def test_new_portals_with_live_structure_fixtures(portal, count):
    html = (Path(__file__).parent / "fixtures" / f"{portal}.html").read_text(encoding="utf-8")
    records = PORTAL_PARSERS[portal](html, "https://example.com/category/")
    assert len(records) == count
    assert all(item["title"] and item["url"].startswith("https://") and item["date_raw"] for item in records)


def test_featured_grid_does_not_repeat_on_later_pages():
    html = (Path(__file__).parent / "fixtures/suara_ntb.html").read_text(encoding="utf-8")
    assert len(PORTAL_PARSERS["suara_ntb"](html, "https://example.com/category/page/2/")) == 1


@pytest.mark.parametrize("portal,expected", [
    ("radar_mandalika", "https://example.com/category/page/2/"),
    ("radar_lombok", "https://example.com/category/page/2"),
    ("suara_ntb", "https://example.com/category/page/2/"),
    ("pemkab_loteng", "https://example.com/category/15"),
])
def test_new_portal_pagination(portal, expected):
    assert _page_url(portal, "https://example.com/category/", 2) == expected


def test_unrecognized_later_page_keeps_partial_records_with_warning():
    records, status = crawl_portal(
        "inside_lombok", "Inside Lombok", "https://example.com/", date(2026, 7, 1),
        date(2026, 9, 11), date(2026, 9, 11), session=Session([HTML, "<html>Bot verification</html>"]),
    )
    assert len(records) == 1
    assert status["Status"] == "Warning"


def test_network_failure_on_later_page_keeps_records():
    import requests
    class FailingSession(Session):
        def get(self, url, timeout):
            if self.urls:
                raise requests.Timeout()
            return super().get(url, timeout)
    records, status = crawl_portal(
        "inside_lombok", "Inside Lombok", "https://example.com/", date(2026, 7, 1),
        date(2026, 9, 11), date(2026, 9, 11), session=FailingSession([HTML]),
    )
    assert len(records) == 1 and status["Status"] == "Warning"


def test_missing_archive_date_is_counted():
    html = HTML.replace('<time datetime="2026-08-10T08:00:00+08:00">10 Agustus 2026</time>', '')
    records, status = crawl_portal(
        "inside_lombok", "Inside Lombok", "https://example.com/", date(2026, 7, 1),
        date(2026, 9, 11), date(2026, 9, 11), session=Session([html]), max_pages=1,
    )
    assert not records and status["Gagal Parse Tanggal"] == 1


def test_pemkab_title_detail_and_period_guard():
    archive = '<article><div class="entry-content-2"><h5 class="post-title"><a href="/berita/a">Produksi...</a></h5><span class="post-on">11 September 2026</span></div></article>'
    detail = '<div class="single-header"><h2>Produksi padi meningkat di Lombok Tengah</h2></div>'
    session = Session([archive, detail])
    records, _ = crawl_portal("pemkab_loteng", "Pemkab", "https://example.com/berita/",
                             date(2026, 7, 1), date(2026, 9, 11), date(2026, 9, 11), session=session, max_pages=1)
    assert records[0]["title"] == "Produksi padi meningkat di Lombok Tengah"
    assert len(session.urls) == 2
    session = Session([archive])
    records, _ = crawl_portal("pemkab_loteng", "Pemkab", "https://example.com/berita/",
                             date(2026, 1, 1), date(2026, 3, 31), date(2026, 9, 11), session=session, max_pages=1)
    assert not records and len(session.urls) == 1


def test_radar_featured_date_uses_article_metadata():
    archive = '<div class="td-big-grid-post"><h3 class="entry-title"><a href="/a">Hotel dibangun</a></h3></div>'
    detail = '<meta property="article:published_time" content="2026-09-09T06:05:02+00:00">'
    records, status = crawl_portal("radar_lombok", "Radar Lombok", "https://example.com/daerah/lombok-tengah",
                                  date(2026, 7, 1), date(2026, 9, 11), date(2026, 9, 11),
                                  session=Session([archive, detail]), max_pages=1)
    assert records[0]["date"] == date(2026, 9, 9)
    assert status["Gagal Parse Tanggal"] == 0
