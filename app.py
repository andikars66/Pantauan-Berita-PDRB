from __future__ import annotations

import logging
import hashlib
from time import monotonic
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config_loader import (
    AppConfig,
    ConfigError,
    load_config,
    update_hierarchical_selection,
)
from src.date_utils import available_quarters, quarter_bounds, today_wita, year_options
from src.exporter import build_main_excel, build_raw_excel
from src.pipeline import run_pipeline
from src.serper_client import fetch_serper_credits

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
PROJECT_ROOT = Path(__file__).resolve().parent
QUARTER_LABELS = {1: "Jan–Mar", 2: "Apr–Jun", 3: "Jul–Sep", 4: "Okt–Des"}


def inject_styles() -> None:
    css = (PROJECT_ROOT / "static" / "styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def get_config() -> AppConfig:
    return load_config(PROJECT_ROOT / "config")


def get_serper_keys() -> list[str]:
    value = None
    try:
        value = st.secrets.get("SERPER_API_KEYS")
    except (FileNotFoundError, KeyError):
        value = None
    if value is None:
        value = os.environ.get("SERPER_API_KEYS", "")
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def get_credit_summary(keys: list[str]) -> dict:
    # Session-local cache stores only a fingerprint and aggregate, never API keys.
    fingerprint = hashlib.sha256("\0".join(sorted(set(keys))).encode()).hexdigest()
    cached = st.session_state.get("serper_credit_summary")
    if cached is None or cached[0] != fingerprint or monotonic() - cached[1] >= 300:
        summary = fetch_serper_credits(keys)
        cached = (fingerprint, monotonic(), summary)
        st.session_state["serper_credit_summary"] = cached
    return cached[2]


def taxonomy_label(code: str, config: AppConfig) -> str:
    row = config.taxonomy.set_index("taxonomy_code").loc[code]
    display_code = code.split(".", 1)[1]
    return f'{"　" * int(row["level"])}{display_code}. {row["label"]}'


def _taxonomy_widget_key(dimension: str, code: str) -> str:
    return f"taxonomy_{dimension}_{code}"


def set_dimension_selection(dimension: str, config: AppConfig, select_all: bool) -> None:
    options = config.taxonomy.loc[
        (config.taxonomy["dimension"] == dimension) & config.taxonomy["selectable"],
        "taxonomy_code",
    ].tolist()
    selected = options if select_all else []
    st.session_state[f"selection_{dimension}"] = selected
    for code in options:
        st.session_state[_taxonomy_widget_key(dimension, code)] = select_all


def toggle_taxonomy_node(dimension: str, code: str, config: AppConfig) -> None:
    selection_key = f"selection_{dimension}"
    checked = bool(st.session_state[_taxonomy_widget_key(dimension, code)])
    selected = update_hierarchical_selection(
        st.session_state.get(selection_key, []), code, checked, config.taxonomy,
    )
    st.session_state[selection_key] = selected
    selected_set = set(selected)
    options = config.taxonomy.loc[
        (config.taxonomy["dimension"] == dimension) & config.taxonomy["selectable"],
        "taxonomy_code",
    ]
    for option in options:
        st.session_state[_taxonomy_widget_key(dimension, option)] = option in selected_set


def render_taxonomy_dropdown(dimension: str, title: str, config: AppConfig) -> list[str]:
    selection_key = f"selection_{dimension}"
    st.session_state.setdefault(selection_key, [])
    selected = st.session_state[selection_key]
    options = config.taxonomy.loc[
        (config.taxonomy["dimension"] == dimension) & config.taxonomy["selectable"],
        "taxonomy_code",
    ].tolist()
    st.markdown(f"**{title}**")
    popover_label = f"{len(selected)} dipilih" if selected else "Pilih kategori"
    with st.popover(popover_label, use_container_width=True):
        st.caption("Centang parent untuk memilih seluruh turunannya.")
        action_left, action_right, _ = st.columns([1, 1, 1.2])
        action_left.button(
            "Pilih semua", key=f"all_{dimension}",
            on_click=set_dimension_selection, args=(dimension, config, True),
        )
        action_right.button(
            "Hapus semua", key=f"clear_{dimension}",
            on_click=set_dimension_selection, args=(dimension, config, False),
        )
        st.divider()
        selected_set = set(st.session_state[selection_key])
        with st.container(height=410, border=False):
            for code in options:
                widget_key = _taxonomy_widget_key(dimension, code)
                if widget_key not in st.session_state:
                    st.session_state[widget_key] = code in selected_set
                st.checkbox(
                    taxonomy_label(code, config),
                    key=widget_key,
                    on_change=toggle_taxonomy_node,
                    args=(dimension, code, config),
                )
    return st.session_state[selection_key]


def _display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=["Sektor/Subsektor", "Judul Berita", "Tanggal", "Pengaruh", "Tautan", "Sumber"],
        )
    prepared = frame.copy()
    prepared["sector_display"] = prepared.apply(
        lambda row: f'{row["taxonomy_code"].split(".", 1)[1]}. {row["label"]}', axis=1,
    )
    return prepared.rename(columns={
        "sector_display": "Sektor/Subsektor", "title": "Judul Berita", "date": "Tanggal",
        "impact": "Pengaruh", "url": "Tautan", "source": "Sumber",
    })[["Sektor/Subsektor", "Judul Berita", "Tanggal", "Pengaruh", "Tautan", "Sumber"]]


def render_dimension_results(result: dict, dimension: str, title: str) -> None:
    frame = result["selected_df"]
    frame = frame[frame["dimension"] == dimension].copy()
    st.markdown(
        f'<div class="section-heading"><h3>{title}</h3><span>{len(frame)} baris hasil</span></div>',
        unsafe_allow_html=True,
    )
    filter_left, filter_right = st.columns(2)
    sector_codes = frame["taxonomy_code"].drop_duplicates().tolist() if not frame.empty else []
    sector_labels = {
        row.taxonomy_code: f'{row.taxonomy_code.split(".", 1)[1]}. {row.label}'
        for row in frame[["taxonomy_code", "label"]].drop_duplicates().itertuples()
    }
    sectors = filter_left.multiselect(
        "Sektor/subsektor", sector_codes, key=f"filter_sector_{dimension}",
        format_func=lambda code: sector_labels.get(code, code),
        placeholder="Semua sektor",
    )
    impacts = filter_right.multiselect(
        "Pengaruh", ["Positif", "Negatif", "Netral"], key=f"filter_impact_{dimension}",
        placeholder="Semua pengaruh",
    )
    if sectors:
        frame = frame[frame["taxonomy_code"].isin(sectors)]
    if impacts:
        frame = frame[frame["impact"].isin(impacts)]
    display = _display_frame(frame)
    if display.empty:
        st.info(f"Belum ada hasil {title.lower()} untuk pilihan dan filter ini.")
    else:
        st.dataframe(
            display, hide_index=True, use_container_width=True,
            column_config={"Tautan": st.column_config.LinkColumn("Tautan", display_text="Buka ↗")},
        )

    dimension_name = "Lapangan Usaha" if dimension == "LU" else "Pengeluaran"
    summary = result["taxonomy_summary"]
    zero_rows = summary[(summary["Dimensi"] == dimension_name) & (summary["Jumlah Berita"] == 0)]
    if not zero_rows.empty:
        with st.expander(f"{len(zero_rows)} sektor terpilih belum memiliki berita", expanded=False):
            st.caption(
                " · ".join(
                    f'{row["Kode"]}. {row["Sektor/Subsektor"]}' for _, row in zero_rows.iterrows()
                )
            )


def render_summary_cards(result: dict) -> None:
    st.markdown('<h2 class="panel-heading">Ringkasan hasil</h2>', unsafe_allow_html=True)
    metric_names = list(result["summary"])
    for group in (metric_names[:4], metric_names[4:]):
        columns = st.columns(len(group))
        for column, name in zip(columns, group):
            column.metric(name, result["summary"][name])
    st.caption("Raw Records menghitung hasil scraping; baris klasifikasi menghitung pasangan artikel × taxonomy.")


def render_results(result: dict) -> None:
    status = result["metadata"]["status"]
    if status == "Selesai":
        st.success("Proses selesai")
    elif status == "Selesai dengan peringatan":
        st.warning("Proses selesai dengan peringatan. Periksa tab Status Sumber.")
    else:
        st.error("Proses gagal. Periksa tab Status Sumber.")

    render_summary_cards(result)
    main_tab, raw_tab, status_tab = st.tabs(["Hasil Utama", "Raw Result", "Status Sumber"])
    with main_tab:
        render_dimension_results(result, "LU", "Lapangan Usaha")
        st.download_button(
            "Download Lapangan Usaha",
            build_main_excel(result, dimension="LU"),
            file_name=f'berita_pdrb_lapangan_usaha_{result["metadata"]["year"]}_T{result["metadata"]["quarter"]}.xlsx',
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.divider()
        render_dimension_results(result, "EXP", "Pengeluaran")
        st.download_button(
            "Download Pengeluaran",
            build_main_excel(result, dimension="EXP"),
            file_name=f'berita_pdrb_pengeluaran_{result["metadata"]["year"]}_T{result["metadata"]["quarter"]}.xlsx',
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with raw_tab:
        raw = result["raw_df"].rename(columns={
            "classifications": "Sektor/Subsektor", "title": "Judul Berita", "date": "Tanggal",
            "impacts": "Pengaruh", "url": "Tautan", "source": "Sumber",
        })
        visible = raw[["Sektor/Subsektor", "Judul Berita", "Tanggal", "Pengaruh", "Tautan", "Sumber"]]
        st.dataframe(
            visible, hide_index=True, use_container_width=True,
            column_config={"Tautan": st.column_config.LinkColumn("Tautan", display_text="Buka ↗")},
        )
        st.download_button(
            "Download Raw Result",
            build_raw_excel(result),
            file_name=f'raw_berita_pdrb_{result["metadata"]["year"]}_T{result["metadata"]["quarter"]}.xlsx',
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with status_tab:
        st.dataframe(result["source_statuses"], hide_index=True, use_container_width=True)
        diagnostics = result["query_diagnostics"]
        st.caption(
            f'Serper: {diagnostics["planned_queries"]} query direncanakan · '
            f'{diagnostics["requests"]} request · {diagnostics["results"]} hasil · '
            f'{diagnostics["retries"]} retry · {diagnostics["key_failovers"]} failover key.'
        )


def app() -> None:
    st.set_page_config(page_title="Tukang Koran", page_icon="📰", layout="centered")
    inject_styles()
    try:
        config = get_config()
    except ConfigError as exc:
        st.error(f"Konfigurasi tidak valid: {exc}")
        st.stop()

    credits = get_credit_summary(get_serper_keys())
    credit_value = f'{credits["total"]:,}' if credits["total"] is not None else "Tidak tersedia"
    key_status = f"Credits left: {credit_value}"
    credit_class = "credit-ok" if credits["total"] else "credit-warning"
    st.markdown(
        f"""
        <header class="product-header">
            <div>
                <h1>Tukang Koran</h1>
                <p>Telusur Kabar Aktivitas Ekonomi Regional — Koleksi, Kategorisasi, dan Analisis PDRB</p>
            </div>
            <div class="credit-badge {credit_class}">{key_status}</div>
        </header>
        """,
        unsafe_allow_html=True,
    )

    if credits["total"] is None:
        st.caption(f'Sisa kredit belum lengkap: {credits["checked_keys"]}/{credits["configured_keys"]} key berhasil diperiksa.')
    elif not credits["configured_keys"]:
        st.caption("API key Serper belum dikonfigurasi.")
    today = today_wita()
    period_options = [
        (year, quarter)
        for year in year_options(today)
        for quarter in available_quarters(year, today)
    ]
    with st.container(border=True, key="parameter_panel"):
        st.markdown('<h2 class="panel-heading">Parameter pencarian</h2>', unsafe_allow_html=True)
        period_column, lu_column, exp_column = st.columns([.82, 1.1, 1.1])
        with period_column:
            st.markdown("**Periode**")
            year, quarter = st.selectbox(
                "Periode", period_options, index=len(period_options) - 1,
                format_func=lambda value: f"T{value[1]} {value[0]} ({QUARTER_LABELS[value[1]]})",
                label_visibility="collapsed",
            )
        with lu_column:
            lu = render_taxonomy_dropdown("LU", "Lapangan Usaha", config)
        with exp_column:
            exp = render_taxonomy_dropdown("EXP", "Pengeluaran", config)

        st.markdown("**Sumber berita**")
        source_options = [("serper", "Serper")] + [
            (row.id, row.name) for row in config.portals[config.portals["active"]].itertuples()
        ]
        source_columns = st.columns(3)
        selected_sources = []
        for index, (source_id, source_name) in enumerate(source_options):
            if source_columns[index % 3].checkbox(source_name, value=True, key=f"source_{source_id}"):
                selected_sources.append(source_id)
        if not selected_sources:
            st.caption("Pilih minimal satu sumber berita untuk memulai.")

        start_date, end_date = quarter_bounds(year, quarter, today)
        selected = lu + exp
        st.markdown(
            f'<div class="period-note">{start_date:%d %b %Y} – {end_date:%d %b %Y} &nbsp;·&nbsp; '
            f'{len(selected)} kategori dipilih</div>',
            unsafe_allow_html=True,
        )
        run_column, _ = st.columns([1, 2])
        with run_column:
            started = st.button(
                "Mulai Pencarian", type="primary", disabled=not selected or not selected_sources,
                use_container_width=True, key="run_button",
            )

    if started:
        st.session_state.pop("run_result", None)
        for key in ("filter_sector_LU", "filter_impact_LU", "filter_sector_EXP", "filter_impact_EXP"):
            st.session_state.pop(key, None)
        progress_bar = st.progress(0)
        status_text = st.empty()

        def progress(value: int, label: str) -> None:
            progress_bar.progress(value)
            status_text.caption(label)

        try:
            st.session_state["run_result"] = run_pipeline(
                year, quarter, selected, config, get_serper_keys(), today, progress,
                selected_sources=selected_sources,
            )
        except Exception:
            logging.getLogger(__name__).exception("Fatal pipeline error")
            st.error("Proses gagal karena kesalahan internal. Periksa konfigurasi atau log aplikasi.")
        finally:
            status_text.empty()
            progress_bar.empty()
        if "serper" in selected_sources:
            st.session_state.pop("serper_credit_summary", None)
            if "run_result" in st.session_state:
                st.rerun()

    if "run_result" in st.session_state:
        render_results(st.session_state["run_result"])
    else:
        st.info("Pilih periode, minimal satu kategori dan sumber berita, lalu mulai pencarian.")


if __name__ == "__main__":
    app()
