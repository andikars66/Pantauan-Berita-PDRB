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
