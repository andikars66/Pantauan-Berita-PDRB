from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable
from urllib.parse import urlparse
from uuid import uuid4

import pandas as pd
import requests

from .config_loader import query_targets

LOGGER = logging.getLogger(__name__)
SERPER_URL = "https://google.serper.dev/news"


class SerperError(RuntimeError):
    pass


class SerperPoolExhausted(SerperError):
    pass


@dataclass(frozen=True)
class QueryPlanItem:
    taxonomy_code: str
    scope: str
    query: str


def generate_query_plan(
    selected: list[str],
    taxonomy: pd.DataFrame,
    keywords: pd.DataFrame,
    start_date: date,
    end_date: date,
    terms_per_pack: int = 4,
) -> list[QueryPlanItem]:
    plans: list[QueryPlanItem] = []
    taxonomy_index = taxonomy.set_index("taxonomy_code")
    for code in query_targets(selected, taxonomy):
        rules = keywords[
            (keywords["taxonomy_code"] == code)
            & (keywords["keyword_type"] == "include")
            & keywords["serper_query"]
        ].sort_values("weight", ascending=False, kind="stable")
        terms = rules["keyword"].drop_duplicates().head(terms_per_pack).tolist()
        if not terms:
            terms = [str(taxonomy_index.loc[code, "label"])]
        economic = " OR ".join(f'"{term}"' for term in terms)
        # Google date operators are exclusive at their boundaries. Broaden by one
        # day, then apply the authoritative inclusive date filter in the pipeline.
        date_filter = (
            f"after:{(start_date - timedelta(days=1)).isoformat()} "
            f"before:{(end_date + timedelta(days=1)).isoformat()}"
        )
        scopes = {
            "local": '("Lombok Tengah" OR "Loteng" OR "Mandalika")',
            "province": '("Nusa Tenggara Barat" OR "NTB")',
        }
        for scope, geography in scopes.items():
            plans.append(QueryPlanItem(code, scope, f"{geography} ({economic}) {date_filter}"))
    return plans


def _key_error(status_code: int, payload: Any) -> bool:
    if status_code in {401, 403, 429}:
        return True
    message = str(payload).casefold()
    return status_code in {400, 402} and any(
        marker in message for marker in ("quota", "credit", "api key", "unauthor", "rate limit")
    )


class SerperClient:
    def __init__(
        self,
        api_keys: list[str],
        session: requests.Session | None = None,
        timeout: tuple[float, float] = (5.0, 20.0),
        max_retries: int = 2,
    ) -> None:
        self.api_keys = [key.strip() for key in api_keys if key and key.strip()]
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.diagnostics = {
            "requests": 0, "results": 0, "retries": 0,
            "key_failovers": 0, "key_errors": 0, "malformed": 0,
            "failed_queries": 0, "completed_queries": 0,
        }

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_keys:
            raise SerperPoolExhausted("Serper API key belum dikonfigurasi.")
        last_message = "Semua Serper API key tidak dapat digunakan."
        for key_index, key in enumerate(self.api_keys):
            for attempt in range(self.max_retries + 1):
                self.diagnostics["requests"] += 1
                try:
                    response = self.session.post(
                        SERPER_URL,
                        json=payload,
                        headers={"X-API-KEY": key, "Content-Type": "application/json"},
                        timeout=self.timeout,
                    )
                except (requests.Timeout, requests.ConnectionError) as exc:
                    LOGGER.warning("Serper network error on attempt %s: %s", attempt + 1, type(exc).__name__)
                    if attempt < self.max_retries:
                        self.diagnostics["retries"] += 1
                        continue
                    last_message = "Koneksi Serper gagal setelah retry."
                    break
                try:
                    data = response.json()
                except ValueError:
                    data = {"error": "invalid-json"}
                if _key_error(response.status_code, data):
                    self.diagnostics["key_errors"] += 1
                    last_message = "Serper menolak API key atau kuotanya habis."
                    break
                if 500 <= response.status_code < 600 and attempt < self.max_retries:
                    self.diagnostics["retries"] += 1
                    continue
                if not response.ok:
                    raise SerperError(f"Serper request gagal (HTTP {response.status_code}).")
                if not isinstance(data, dict):
                    self.diagnostics["malformed"] += 1
                    raise SerperError("Respons Serper tidak valid.")
                return data
            if key_index < len(self.api_keys) - 1:
                self.diagnostics["key_failovers"] += 1
        raise SerperPoolExhausted(last_message)

    def collect(
        self,
        plan: list[QueryPlanItem],
        progress: Callable[[str], None] | None = None,
        results_per_query: int = 10,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for index, item in enumerate(plan, start=1):
            if progress:
                progress(f"Serper — query {index}/{len(plan)}")
            try:
                data = self._request({"q": item.query, "gl": "id", "hl": "id", "num": results_per_query})
            except SerperError:
                self.diagnostics["failed_queries"] += 1
                if self.diagnostics["completed_queries"] == 0:
                    raise
                break
            self.diagnostics["completed_queries"] += 1
            items = data.get("news", data.get("organic", []))
            if not isinstance(items, list):
                self.diagnostics["malformed"] += 1
                continue
            self.diagnostics["results"] += len(items)
            for result in items:
                if not isinstance(result, dict):
                    continue
                url = str(result.get("link") or "")
                source = result.get("source") or urlparse(url).netloc or "Google/Serper"
                records.append({
                    "record_id": str(uuid4()),
                    "source_type": "serper",
                    "source": str(source),
                    "title": str(result.get("title") or "").strip(),
                    "date_raw": result.get("date"),
                    "url": url,
                    "snippet": str(result.get("snippet") or "").strip(),
                    "article_text": "",
                    "source_context_local": False,
                    "query_taxonomy": item.taxonomy_code,
                    "query_scope": item.scope,
                })
        return records
