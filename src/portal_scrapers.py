from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from uuid import uuid4

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .date_utils import parse_news_date

LOGGER = logging.getLogger(__name__)


class PortalScrapingError(RuntimeError):
    pass


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2, connect=2, read=2, status=2,
        backoff_factor=0.35,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.6",
    })
    return session


def _first_text(node: Any, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        found = node.select_one(selector)
        if found:
            value = found.get("datetime") or found.get("content") or found.get_text(" ", strip=True)
            if value:
                return str(value).strip()
    return ""


def _parse_cards(html: str, base_url: str, card_selectors: tuple[str, ...]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    cards: list[Any] = []
    for selector in card_selectors:
        cards = soup.select(selector)
        if cards:
            break
    results: list[dict[str, str]] = []
    seen_nodes: set[tuple[str, str]] = set()
    for card in cards:
        title_node = None
        for selector in (
            ".entry-title a", "h3.td-module-title a", ".post-title a", "a.post-title",
            "a.latest__link", "h1 a", "h2 a", "h3 a", "h4 a", "a",
        ):
            title_node = card.select_one(selector)
            if title_node:
                break
        if not title_node:
            continue
        title = title_node.get("title") or title_node.get_text(" ", strip=True)
        href = title_node.get("href") or ""
        date_raw = _first_text(card, (
            "time[datetime]", "time", ".jeg_meta_date", ".entry-date", ".post-date",
            ".latest__date", ".post-on", ".date", "span[class*='date']", "div[class*='date']",
        ))
        snippet = _first_text(card, (
            ".jeg_post_excerpt", ".entry-summary", ".post-excerpt", ".latest__desc",
            ".td-excerpt", ".description", "p",
        ))
        if not title or not href:
            continue
        key = (title.strip(), urljoin(base_url, href))
        if key in seen_nodes:
            continue
        seen_nodes.add(key)
        results.append({
            "title": title.strip(), "url": key[1], "date_raw": date_raw, "snippet": snippet,
        })
    return results


def _parse_json_ld(html: str, base_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or "")
        except (TypeError, json.JSONDecodeError):
            continue
        stack = payload if isinstance(payload, list) else [payload]
        for item in stack:
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            candidates = graph if isinstance(graph, list) else [item]
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                type_name = candidate.get("@type", "")
                if type_name not in {"NewsArticle", "Article", "BlogPosting"}:
                    continue
                title = candidate.get("headline") or candidate.get("name")
                url = candidate.get("url") or candidate.get("mainEntityOfPage")
                if isinstance(url, dict):
                    url = url.get("@id")
                date_raw = candidate.get("datePublished")
                if title and url and date_raw:
                    results.append({
                        "title": str(title), "url": urljoin(base_url, str(url)),
                        "date_raw": str(date_raw),
                        "snippet": str(candidate.get("description") or ""),
                    })
    return results


def parse_inside_lombok(html: str, base_url: str) -> list[dict[str, str]]:
    items = _parse_cards(html, base_url, (
        ".tdb_module_loop.td-cpt-post", "article.jeg_post", ".jeg_posts article",
        "article.post", ".post-listing article", "article",
    ))
    return items or _parse_json_ld(html, base_url)


def parse_lombok_post(html: str, base_url: str) -> list[dict[str, str]]:
    # The current Lombok Post is an Inertia/Vue app. Archive data is embedded in
    # #app[data-page], so parsing it avoids browser automation and extra API calls.
    soup = BeautifulSoup(html, "html.parser")
    app = soup.select_one("#app[data-page]")
    if app:
        try:
            page = json.loads(app.get("data-page", ""))
            props = page.get("props", {})
            collection = props.get("news", {}).get("data")
            if not isinstance(collection, list):
                collection = props.get("tag", {}).get("articles", {}).get("data", [])
            embedded: list[dict[str, str]] = []
            for item in collection if isinstance(collection, list) else []:
                if not isinstance(item, dict):
                    continue
                title, slug = item.get("title"), item.get("slug")
                date_raw = item.get("timestamp") or item.get("date")
                article_id = item.get("article_id")
                category = item.get("category") or {}
                category_slug = category.get("slug") if isinstance(category, dict) else None
                if not all((title, slug, date_raw, article_id, category_slug)):
                    continue
                embedded.append({
                    "title": str(title),
                    "url": urljoin(base_url, f"/{category_slug}/{article_id}/{slug}"),
                    "date_raw": str(date_raw),
                    "snippet": str(item.get("description") or ""),
                })
            if embedded:
                return embedded
        except (TypeError, json.JSONDecodeError, AttributeError):
            LOGGER.warning("Lombok Post data-page could not be decoded")
    items = _parse_cards(html, base_url, (
        ".latest__item", ".list-content__item", ".post-list article", "article", ".item-content",
    ))
    return items or _parse_json_ld(html, base_url)


def parse_radar_mandalika(html: str, base_url: str) -> list[dict[str, str]]:
    return _parse_cards(html, base_url, ("article.small",))


def parse_radar_lombok(html: str, base_url: str) -> list[dict[str, str]]:
    selector = ".td-ss-main-content .td_module_wrap"
    if "/page/" not in urlsplit(base_url).path:
        selector = ".td-big-grid-post, " + selector
    return _parse_cards(html, base_url, (selector,))


def parse_suara_ntb(html: str, base_url: str) -> list[dict[str, str]]:
    # Include the category's leading grid and archive loop, but exclude the sidebar.
    selector = ".tdb-category-loop-posts .tdb_module_loop"
    if "/page/" not in urlsplit(base_url).path:
        selector = ".td-big-grid-flex-post, " + selector
    items = _parse_cards(html, base_url, (selector,))
    for item in items:
        if not item["date_raw"]:
            match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", item["url"])
            if match:
                item["date_raw"] = "-".join(match.groups())
    return items


def parse_pemkab_loteng(html: str, base_url: str) -> list[dict[str, str]]:
    return _parse_cards(html, base_url, ("article:has(.entry-content-2)",))


PORTAL_PARSERS = {
    "inside_lombok": parse_inside_lombok, "lombok_post": parse_lombok_post,
    "radar_mandalika": parse_radar_mandalika, "radar_lombok": parse_radar_lombok,
    "suara_ntb": parse_suara_ntb, "pemkab_loteng": parse_pemkab_loteng,
}


def _page_url(portal_id: str, base_url: str, page: int) -> str:
    if page == 1:
        return base_url
    if portal_id == "radar_lombok":
        return urljoin(base_url.rstrip("/") + "/", f"page/{page}")
    if portal_id == "pemkab_loteng":
        return urljoin(base_url.rstrip("/") + "/", str((page - 1) * 15))
    if portal_id in {"inside_lombok", "radar_mandalika", "radar_lombok", "suara_ntb"}:
        return urljoin(base_url.rstrip("/") + "/", f"page/{page}/")
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["page"] = str(page)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def crawl_portal(
    portal_id: str,
    name: str,
    base_url: str,
    start_date: date,
    end_date: date,
    run_date: date,
    session: requests.Session | None = None,
    max_pages: int = 50,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parsers = PORTAL_PARSERS
    if portal_id not in parsers:
        raise PortalScrapingError(f"Portal tidak didukung: {portal_id}")
    if session is None:
        with build_session() as owned_session:
            return crawl_portal(portal_id, name, base_url, start_date, end_date, run_date,
                                owned_session, max_pages, progress)
    records: list[dict[str, Any]] = []
    status = {
        "Sumber": name, "Status": "Berhasil", "Ditemukan": 0,
        "Lolos Periode": 0, "Gagal Parse Tanggal": 0, "Warning/Error": "",
    }
    visited: set[str] = set()
    page_fingerprints: set[tuple[str, ...]] = set()
    for page in range(1, max_pages + 1):
        url = _page_url(portal_id, base_url, page)
        if url in visited:
            status["Warning/Error"] = "Pagination berulang; crawl dihentikan."
            status["Status"] = "Warning"
            break
        visited.add(url)
        if progress:
            progress(f"{name} — halaman {page} — {len(records)} artikel periode")
        try:
            response = session.get(url, timeout=(5, 20))
            response.raise_for_status()
        except requests.RequestException as exc:
            message = f"Request gagal pada halaman {page}: {type(exc).__name__}"
            if page == 1:
                raise PortalScrapingError(message) from None
            status.update({"Status": "Warning", "Warning/Error": message})
            break
        response.encoding = "utf-8"
        items = parsers[portal_id](response.text, url)
        # Unrecognized responses must never masquerade as successful empty archives.
        if not items:
            if page == 1:
                raise PortalScrapingError("Struktur daftar artikel tidak dikenali pada halaman pertama.")
            status.update({"Status": "Warning", "Warning/Error":
                           f"Struktur daftar artikel tidak dikenali pada halaman {page}."})
            break
        fingerprint = tuple(item["url"] for item in items)
        if fingerprint in page_fingerprints:
            status["Status"] = "Warning"
            status["Warning/Error"] = "Konten pagination berulang; crawl dihentikan."
            break
        page_fingerprints.add(fingerprint)
        status["Ditemukan"] += len(items)
        parsed_dates: list[date] = []
        for item in items:
            if portal_id == "radar_lombok" and not item.get("date_raw"):
                try:
                    detail = session.get(item["url"], timeout=(5, 20))
                    detail.raise_for_status()
                    detail.encoding = "utf-8"
                    soup = BeautifulSoup(detail.text, "html.parser")
                    item["date_raw"] = _first_text(soup, (
                        'meta[property="article:published_time"]', 'time[datetime]',
                    ))
                except requests.RequestException:
                    pass  # Count the missing date explicitly below; never infer today's date.
            parsed = parse_news_date(item.get("date_raw"), run_date)
            if parsed is None:
                status["Gagal Parse Tanggal"] += 1
                continue
            parsed_dates.append(parsed)
            if start_date <= parsed <= end_date:
                if portal_id == "pemkab_loteng":
                    # Archive titles are abbreviated; fetch only in-period details,
                    # sequentially on the same session to keep one request per host.
                    try:
                        detail = session.get(item["url"], timeout=(5, 20))
                        detail.raise_for_status()
                        detail.encoding = "utf-8"
                        soup = BeautifulSoup(detail.text, "html.parser")
                        headline = soup.select_one(".single-header h2")
                        if not headline:
                            raise PortalScrapingError("Judul detail tidak dikenali")
                        item["title"] = headline.get_text(" ", strip=True)
                    except (requests.RequestException, PortalScrapingError):
                        status.update({"Status": "Warning", "Warning/Error":
                                       "Sebagian detail gagal; menggunakan judul ringkas arsip."})
                records.append({
                    "record_id": str(uuid4()), "source_type": "portal", "source": name,
                    "title": item["title"], "date_raw": item["date_raw"], "date": parsed,
                    "url": item["url"], "snippet": item.get("snippet", ""),
                    "article_text": "", "source_context_local": True,
                })
        status["Lolos Periode"] = len(records)
        if parsed_dates and max(parsed_dates) < start_date:
            break
    else:
        status["Status"] = "Warning"
        status["Warning/Error"] = f"Mencapai batas {max_pages} halaman."
    if status["Gagal Parse Tanggal"] and status["Status"] == "Berhasil":
        status["Status"] = "Warning"
        status["Warning/Error"] = f'{status["Gagal Parse Tanggal"]} tanggal tidak dapat diparse.'
    return records, status
