from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Callable

import pandas as pd

from .classifier import classify_text
from .config_loader import AppConfig, expand_selection
from .date_utils import WITA, in_period, parse_news_date, quarter_bounds, today_wita
from .geography import geographic_relevance
from .portal_scrapers import PortalScrapingError, crawl_portal
from .serper_client import SerperClient, SerperError, generate_query_plan

LOGGER = logging.getLogger(__name__)

RAW_COLUMNS = [
    "record_id", "source_type", "source", "title", "date", "url", "snippet",
    "article_text", "source_context_local", "period_valid", "geo_relevant",
    "classification_count", "classifications", "impacts",
]
CLASS_COLUMNS = [
    "record_id", "dimension", "taxonomy_code", "label", "sort_order", "title",
    "date", "impact", "url", "source", "include_score", "positive_score", "negative_score",
]


def _source_status(name: str, status: str, message: str = "") -> dict[str, Any]:
    return {
        "Sumber": name, "Status": status, "Ditemukan": 0, "Lolos Periode": 0,
        "Gagal Parse Tanggal": 0, "Warning/Error": message,
    }


def _normalize_and_classify(
    records: list[dict[str, Any]], config: AppConfig, start: date, end: date, run_date: date,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, int]]]:
    raw_rows: list[dict[str, Any]] = []
    class_rows: list[dict[str, Any]] = []
    diagnostics: dict[str, dict[str, int]] = {}
    for record in records:
        source = record["source"]
        diagnostic = diagnostics.setdefault(source, {"period": 0, "date_failed": 0, "geo": 0})
        parsed = record.get("date") or parse_news_date(record.get("date_raw"), run_date)
        if parsed is None:
            diagnostic["date_failed"] += 1
            continue
        if not in_period(parsed, start, end):
            continue
        diagnostic["period"] += 1
        classification_text = " ".join(filter(None, [
            str(record.get("title", "")), str(record.get("snippet", "")),
            "" if record.get("source_type") == "serper" else str(record.get("article_text", "")),
        ]))
        geo_ok, _ = geographic_relevance(
            classification_text, config.geography, bool(record.get("source_context_local")),
        )
        if not geo_ok:
            continue
        diagnostic["geo"] += 1
        classifications = classify_text(classification_text, config.taxonomy, config.keywords)
        labels = "; ".join(f"{item.taxonomy_code} — {item.label}" for item in classifications)
        impacts = "; ".join(f"{item.taxonomy_code}={item.impact}" for item in classifications)
        raw_rows.append({
            "record_id": record["record_id"], "source_type": record["source_type"],
            "source": source, "title": record.get("title", ""), "date": parsed,
            "url": record.get("url", ""), "snippet": record.get("snippet", ""),
            "article_text": record.get("article_text", ""),
            "source_context_local": bool(record.get("source_context_local")),
            "period_valid": True, "geo_relevant": True,
            "classification_count": len(classifications), "classifications": labels, "impacts": impacts,
        })
        for item in classifications:
            class_rows.append({
                "record_id": record["record_id"], "dimension": item.dimension,
                "taxonomy_code": item.taxonomy_code, "label": item.label,
                "sort_order": item.sort_order, "title": record.get("title", ""),
                "date": parsed, "impact": item.impact, "url": record.get("url", ""),
                "source": source, "include_score": item.include_score,
                "positive_score": item.positive_score, "negative_score": item.negative_score,
            })
    return (
        pd.DataFrame(raw_rows, columns=RAW_COLUMNS),
        pd.DataFrame(class_rows, columns=CLASS_COLUMNS),
        diagnostics,
    )


def _taxonomy_summary(selected: list[str], taxonomy: pd.DataFrame, selected_rows: pd.DataFrame) -> pd.DataFrame:
    chosen = taxonomy[taxonomy["taxonomy_code"].isin(selected)].copy()
    counts = selected_rows["taxonomy_code"].value_counts() if not selected_rows.empty else pd.Series(dtype=int)
    chosen["Jumlah Berita"] = chosen["taxonomy_code"].map(counts).fillna(0).astype(int)
    chosen["Dimensi"] = chosen["dimension"].map({"LU": "Lapangan Usaha", "EXP": "Pengeluaran"})
    chosen["Kode"] = chosen["taxonomy_code"].str.replace(r"^(LU|EXP)\.", "", regex=True)
    chosen["Sektor/Subsektor"] = chosen["label"]
    return chosen.sort_values("sort_order")[["Dimensi", "Kode", "Sektor/Subsektor", "Jumlah Berita"]]


def run_pipeline(
    year: int,
    quarter: int,
    selected: list[str],
    config: AppConfig,
    serper_keys: list[str] | None = None,
    run_date: date | None = None,
    progress: Callable[[int, str], None] | None = None,
    portal_max_pages: int | None = None,
) -> dict[str, Any]:
    run_date = run_date or today_wita()
    if not selected:
        raise ValueError("Pilih minimal satu taxonomy sebelum memulai.")
    start, end = quarter_bounds(year, quarter, run_date)
    expanded = expand_selection(selected, config.taxonomy)
    emit = progress or (lambda _value, _label: None)
    records: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []

    emit(5, "Persiapan")
    plan = generate_query_plan(selected, config.taxonomy, config.keywords, start, end)
    emit(15, "Serper")
    serper = SerperClient(serper_keys or [])
    try:
        serper_records = serper.collect(plan, lambda message: emit(25, message))
        records.extend(serper_records)
        statuses.append(_source_status("Serper", "Berhasil"))
        statuses[-1]["Ditemukan"] = len(serper_records)
        if serper.diagnostics["failed_queries"] or serper.diagnostics["malformed"]:
            statuses[-1]["Status"] = "Warning"
            statuses[-1]["Warning/Error"] = (
                f'{serper.diagnostics["failed_queries"]} query gagal; '
                f'{serper.diagnostics["malformed"]} respons malformed.'
            )
    except SerperError as exc:
        LOGGER.warning("Serper source failed: %s", type(exc).__name__)
        statuses.append(_source_status("Serper", "Gagal", str(exc)))
    except Exception as exc:
        LOGGER.exception("Unexpected Serper failure")
        statuses.append(_source_status("Serper", "Gagal", f"Kesalahan Serper: {type(exc).__name__}"))

    portal_rows = config.portals[config.portals["active"]]
    stages = {"inside_lombok": (38, "Inside Lombok"), "lombok_post": (52, "Lombok Post")}
    for portal in portal_rows.itertuples():
        value, label = stages[portal.id]
        emit(value, label)
        try:
            found, source_status = crawl_portal(
                portal.id, portal.name, portal.url, start, end, run_date,
                max_pages=(
                    portal_max_pages
                    if portal_max_pages is not None
                    else int(getattr(portal, "max_pages", 200))
                ),
                progress=lambda message, value=value: emit(value, message),
            )
            records.extend(found)
            statuses.append(source_status)
        except PortalScrapingError as exc:
            LOGGER.warning("Portal %s failed: %s", portal.id, type(exc).__name__)
            statuses.append(_source_status(portal.name, "Gagal", str(exc)))
        except Exception as exc:
            LOGGER.exception("Unexpected portal failure for %s", portal.id)
            statuses.append(_source_status(portal.name, "Gagal", f"Kesalahan parser: {type(exc).__name__}"))

    emit(66, "Normalisasi")
    raw, classifications, record_diagnostics = _normalize_and_classify(records, config, start, end, run_date)
    emit(78, "Klasifikasi")
    status_by_name = {item["Sumber"]: item for item in statuses}
    for source, values in record_diagnostics.items():
        if source not in status_by_name:
            continue
        status = status_by_name[source]
        status["Lolos Periode"] = values["period"]
        status["Gagal Parse Tanggal"] += values["date_failed"]
        if values["date_failed"] and status["Status"] == "Berhasil":
            status["Status"] = "Warning"
            status["Warning/Error"] = f'{values["date_failed"]} tanggal tidak dapat diparse.'

    emit(88, "Penyusunan Hasil")
    selected_rows = classifications[classifications["taxonomy_code"].isin(expanded)].copy()
    if not selected_rows.empty:
        selected_rows = selected_rows.sort_values(
            ["sort_order", "date", "title"], ascending=[True, False, True], kind="stable",
        ).reset_index(drop=True)
    taxonomy_summary = _taxonomy_summary(expanded, config.taxonomy, selected_rows)
    metrics = {
        "Raw Records": len(raw),
        "Raw Records Terklasifikasi": int((raw["classification_count"] > 0).sum()) if not raw.empty else 0,
        "Raw Records Tidak Terklasifikasi": int((raw["classification_count"] == 0).sum()) if not raw.empty else 0,
        "Classification Rows Terpilih": len(selected_rows),
        "Positif": int((selected_rows["impact"] == "Positif").sum()) if not selected_rows.empty else 0,
        "Negatif": int((selected_rows["impact"] == "Negatif").sum()) if not selected_rows.empty else 0,
        "Netral": int((selected_rows["impact"] == "Netral").sum()) if not selected_rows.empty else 0,
    }
    failed = sum(item["Status"] == "Gagal" for item in statuses)
    warnings = sum(item["Status"] == "Warning" for item in statuses)
    if failed == len(statuses) and statuses:
        run_status = "Gagal"
    elif failed or warnings:
        run_status = "Selesai dengan peringatan"
    else:
        run_status = "Selesai"
    emit(100, "Selesai")
    return {
        "metadata": {
            "year": year, "quarter": quarter, "start_date": start, "end_date": end,
            "run_at": datetime.now(WITA), "status": run_status,
            "selected_original": selected, "selected_expanded": expanded,
        },
        "raw_df": raw,
        "classification_df": classifications,
        "selected_df": selected_rows,
        "taxonomy_summary": taxonomy_summary,
        "summary": metrics,
        "source_statuses": pd.DataFrame(statuses),
        "query_diagnostics": {"planned_queries": len(plan), **serper.diagnostics},
    }
