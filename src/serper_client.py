from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
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


def fetch_serper_credits(api_keys: list[str]) -> dict[str, Any]:
    """Read account balances; never use search responses' per-request credits as balance."""
    keys = list(dict.fromkeys(key.strip() for key in api_keys if key and key.strip()))

    def balance(key: str) -> int | None:
        try:
            with requests.Session() as session:
                response = session.get(
                    "https://google.serper.dev/account", headers={"X-API-KEY": key},
                    timeout=(5, 10), allow_redirects=False,
                )
                response.raise_for_status()
                data = response.json()
                value = data.get("balance") if isinstance(data, dict) else None
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    return value
        except (requests.RequestException, ValueError):
            pass  # No raw response, request headers, or secret-bearing exceptions in logs/UI.
        return None

    with ThreadPoolExecutor(max_workers=3) as executor:
        balances = list(executor.map(balance, keys))
    checked = sum(value is not None for value in balances)
    return {
        "total": sum(balances) if checked == len(keys) else None,
        "checked_keys": checked, "configured_keys": len(keys),
    }


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
    serper_keywords: pd.DataFrame,
    start_date: date,
    end_date: date,
    terms_per_pack: int = 10,
) -> list[QueryPlanItem]:
    plans: list[QueryPlanItem] = []
    for code in query_targets(selected, taxonomy):
        rules = serper_keywords[
            (serper_keywords["taxonomy_code"] == code) & serper_keywords["active"]
        ].sort_values("priority", kind="stable")
        terms = rules["keyword"].drop_duplicates().tolist()
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
        for pack_start in range(0, len(terms), terms_per_pack):
            pack = terms[pack_start:pack_start + terms_per_pack]
            economic = " OR ".join(f'"{term}"' for term in pack)
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
        self.session = session
        self._lock = Lock()
        self._unavailable_keys: set[int] = set()
        self.timeout = timeout
        self.max_retries = max_retries
        self.diagnostics = {
            "requests": 0, "results": 0, "retries": 0,
            "key_failovers": 0, "key_errors": 0, "malformed": 0,
            "failed_queries": 0, "completed_queries": 0,
        }

    def _increment(self, name: str) -> None:
        with self._lock:
            self.diagnostics[name] += 1

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Each query owns its HTTP session; no mutable Session is shared by workers.
        if self.session is not None:
            return self._request_with_session(payload, self.session)
        with requests.Session() as session:
            return self._request_with_session(payload, session)

    def _request_with_session(self, payload: dict[str, Any], session: requests.Session) -> dict[str, Any]:
        if not self.api_keys:
            raise SerperPoolExhausted("Serper API key belum dikonfigurasi.")
        for key_index, key in enumerate(self.api_keys):
            with self._lock:
                if key_index in self._unavailable_keys:
                    continue
            for attempt in range(self.max_retries + 1):
                self._increment("requests")
                try:
                    response = session.post(
                        SERPER_URL, json=payload,
                        headers={"X-API-KEY": key, "Content-Type": "application/json"},
                        timeout=self.timeout,
                    )
                except (requests.Timeout, requests.ConnectionError):
                    if attempt < self.max_retries:
                        self._increment("retries")
                        continue
                    # Network failure does not invalidate a key or exhaust the pool.
                    raise SerperError("Koneksi Serper gagal setelah retry.") from None
                try:
                    data = response.json()
                except ValueError:
                    data = None
                if _key_error(response.status_code, data):
                    with self._lock:
                        self.diagnostics["key_errors"] += 1
                        if key_index not in self._unavailable_keys:
                            self._unavailable_keys.add(key_index)
                            if key_index < len(self.api_keys) - 1:
                                self.diagnostics["key_failovers"] += 1
                    break
                if 500 <= response.status_code < 600 and attempt < self.max_retries:
                    self._increment("retries")
                    continue
                if not response.ok:
                    raise SerperError(f"Serper request gagal (HTTP {response.status_code}).")
                if not isinstance(data, dict):
                    self._increment("malformed")
                    raise SerperError("Respons Serper tidak valid.")
                return data
        raise SerperPoolExhausted("Serper menolak semua API key atau kuotanya habis.")

    def collect(
        self,
        plan: list[QueryPlanItem],
        progress: Callable[[str], None] | None = None,
        results_per_query: int = 10,
        max_workers: int = 3,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        workers = max(1, min(max_workers, 3))
        # Small batches bound in-flight requests and stop dispatch after pool exhaustion.
        def request_item(item: QueryPlanItem):
            try:
                return self._request({"q": item.query, "gl": "id", "hl": "id", "num": results_per_query})
            except SerperError as exc:
                return exc

        outcomes = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for offset in range(0, len(plan), workers):
                batch = plan[offset:offset + workers]
                results = list(executor.map(request_item, batch))
                outcomes.extend(zip(batch, results))
                if progress:
                    progress(f"Serper — query {offset + len(batch)}/{len(plan)}")
                if any(isinstance(result, SerperPoolExhausted) for result in results):
                    self.diagnostics["failed_queries"] += len(plan) - offset - len(batch)
                    break
        first_error = None
        for item, data in outcomes:
            if isinstance(data, SerperError):
                self.diagnostics["failed_queries"] += 1
                first_error = first_error or data
                continue
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
        if first_error is not None and self.diagnostics["completed_queries"] == 0:
            raise first_error
        return records
