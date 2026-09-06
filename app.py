from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config_loader import AppConfig, ConfigError, load_config
from src.date_utils import available_quarters, today_wita, year_options
from src.exporter import build_main_excel, build_raw_excel
from src.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
PROJECT_ROOT = Path(__file__).resolve().parent


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


def taxonomy_label(code: str, config: AppConfig) -> str:
    row = config.taxonomy.set_index("taxonomy_code").loc[code]
    display_code = code.split(".", 1)[1]
    return f'{"　" * int(row["level"])}{display_code}. {row["label"]}'


def set_dimension_selection(dimension: str, config: AppConfig, select_all: bool) -> None:
    key = f"selection_{dimension}"
    st.session_state[key] = (
        config.taxonomy.loc[
            (config.taxonomy["dimension"] == dimension) & config.taxonomy["selectable"],
            "taxonomy_code",
        ].tolist()
        if select_all else []
    )


def render_selector(dimension: str, title: str, config: AppConfig) -> list[str]:
    st.subheader(title)
    left, right = st.columns(2)
    left.button(
        "Pilih Semua", key=f"all_{dimension}", use_container_width=True,
        on_click=set_dimension_selection, args=(dimension, config, True),
    )
    right.button(
        "Hapus Semua", key=f"clear_{dimension}", use_container_width=True,
        on_click=set_dimension_selection, args=(dimension, config, False),
    )
    options = config.taxonomy.loc[
        (config.taxonomy["dimension"] == dimension) & config.taxonomy["selectable"],
        "taxonomy_code",
    ].tolist()
    key = f"selection_{dimension}"
    st.session_state.setdefault(key, [])
    return st.multiselect(
        "Sektor/subsektor", options, key=key,
        format_func=lambda code: taxonomy_label(code, config),
        placeholder="Pilih parent atau child…",
        label_visibility="collapsed",
    )


def main_table(result: dict) -> pd.DataFrame:
    frame = result["selected_df"].copy()
    if frame.empty:
        return pd.DataFrame(columns=["Sektor/Subsektor", "Judul Berita", "Tanggal", "Pengaruh", "Tautan", "Sumber"])
    frame["sector_display"] = frame.apply(
        lambda row: f'{row["dimension"]} — {row["taxonomy_code"].split(".", 1)[1]}. {row["label"]}', axis=1,
    )
    st.subheader("Hasil utama")
    search = st.text_input("Cari judul, sektor, atau sumber", key="main_search")
    f1, f2, f3 = st.columns(3)
    dimensions = f1.multiselect("Dimensi", sorted(frame["dimension"].unique()), key="filter_dimension")
    sectors = f2.multiselect(
        "Sektor/subsektor", frame["sector_display"].drop_duplicates().tolist(), key="filter_sector",
    )
    impacts = f3.multiselect("Pengaruh", ["Positif", "Negatif", "Netral"], key="filter_impact")
    f4, f5 = st.columns(2)
    sources = f4.multiselect("Sumber", sorted(frame["source"].unique()), key="filter_source")
    dates = f5.date_input(
        "Rentang tanggal", value=(result["metadata"]["start_date"], result["metadata"]["end_date"]),
        min_value=result["metadata"]["start_date"], max_value=result["metadata"]["end_date"],
        key="filter_dates",
    )
    if search:
        mask = (
            frame["title"].str.contains(search, case=False, na=False, regex=False)
            | frame["sector_display"].str.contains(search, case=False, na=False, regex=False)
            | frame["source"].str.contains(search, case=False, na=False, regex=False)
        )
        frame = frame[mask]
    if dimensions:
        frame = frame[frame["dimension"].isin(dimensions)]
    if sectors:
        frame = frame[frame["sector_display"].isin(sectors)]
    if impacts:
        frame = frame[frame["impact"].isin(impacts)]
    if sources:
        frame = frame[frame["source"].isin(sources)]
    if isinstance(dates, (tuple, list)) and len(dates) == 2:
        frame = frame[(frame["date"] >= dates[0]) & (frame["date"] <= dates[1])]
    return frame.rename(columns={
        "sector_display": "Sektor/Subsektor", "title": "Judul Berita", "date": "Tanggal",
        "impact": "Pengaruh", "url": "Tautan", "source": "Sumber",
    })[["Sektor/Subsektor", "Judul Berita", "Tanggal", "Pengaruh", "Tautan", "Sumber"]]


def render_results(result: dict) -> None:
    status = result["metadata"]["status"]
    if status == "Selesai":
        st.success(status)
    elif status == "Selesai dengan peringatan":
        st.warning(status)
    else:
        st.error(status)

    metric_names = list(result["summary"])
    for group in (metric_names[:4], metric_names[4:]):
        columns = st.columns(len(group))
        for column, name in zip(columns, group):
            column.metric(name, result["summary"][name])
    st.caption("Raw Records menghitung record scraping; Classification Rows menghitung pasangan artikel × klasifikasi.")

    st.subheader("Ringkasan taxonomy")
    st.dataframe(result["taxonomy_summary"], hide_index=True, use_container_width=True)
    chart_data = result["taxonomy_summary"].set_index("Kode")["Jumlah Berita"]
    st.bar_chart(chart_data)
    impact_counts = result["selected_df"]["impact"].value_counts().reindex(["Positif", "Negatif", "Netral"], fill_value=0)
    st.bar_chart(impact_counts)

    display = main_table(result)
    st.dataframe(
        display, hide_index=True, use_container_width=True,
        column_config={"Tautan": st.column_config.LinkColumn("Tautan", display_text="Buka")},
    )

    st.subheader("Unduh Excel")
    main_bytes = build_main_excel(result)
    raw_bytes = build_raw_excel(result)
    a, b = st.columns(2)
    a.download_button(
        "Unduh hasil utama", main_bytes,
        file_name=f'berita_pdrb_{result["metadata"]["year"]}_T{result["metadata"]["quarter"]}.xlsx',
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    b.download_button(
        "Unduh raw result", raw_bytes,
        file_name=f'raw_berita_pdrb_{result["metadata"]["year"]}_T{result["metadata"]["quarter"]}.xlsx',
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    with st.expander("Lihat seluruh hasil scraping (raw)", expanded=False):
        raw = result["raw_df"].rename(columns={
            "classifications": "Sektor/Subsektor", "title": "Judul Berita", "date": "Tanggal",
            "impacts": "Pengaruh", "url": "Tautan", "source": "Sumber",
        })
        visible = raw[["Sektor/Subsektor", "Judul Berita", "Tanggal", "Pengaruh", "Tautan", "Sumber"]]
        st.dataframe(
            visible, hide_index=True, use_container_width=True,
            column_config={"Tautan": st.column_config.LinkColumn("Tautan", display_text="Buka")},
        )
    with st.expander("Status sumber dan diagnostics", expanded=False):
        st.dataframe(result["source_statuses"], hide_index=True, use_container_width=True)
        diagnostics = result["query_diagnostics"]
        st.caption(
            f'Serper: {diagnostics["planned_queries"]} query direncanakan; '
            f'{diagnostics["requests"]} request; {diagnostics["results"]} hasil; '
            f'{diagnostics["retries"]} retry; {diagnostics["key_failovers"]} failover key.'
        )


def app() -> None:
    st.set_page_config(page_title="Pantauan Berita PDRB Lombok Tengah", layout="wide")
    st.title("Pantauan Berita PDRB Lombok Tengah")
    st.caption("Mengumpulkan dan mengklasifikasikan berita ekonomi berdasarkan Lapangan Usaha dan Pengeluaran.")
    try:
        config = get_config()
    except ConfigError as exc:
        st.error(f"Konfigurasi tidak valid: {exc}")
        st.stop()

    today = today_wita()
    years = year_options(today)
    first, second = st.columns(2)
    year = first.selectbox("Tahun", years, index=len(years) - 1)
    quarters = available_quarters(year, today)
    quarter = second.selectbox("Triwulan", quarters, index=len(quarters) - 1, format_func=lambda value: f"T{value}")
    left, right = st.columns(2)
    with left:
        lu = render_selector("LU", "Lapangan Usaha", config)
    with right:
        exp = render_selector("EXP", "Pengeluaran", config)
    selected = lu + exp

    started = st.button(
        "Mulai", type="primary", disabled=not selected,
        use_container_width=True,
    )
    if started:
        st.session_state.pop("run_result", None)
        for key in (
            "main_search", "filter_dimension", "filter_sector", "filter_impact",
            "filter_source", "filter_dates",
        ):
            st.session_state.pop(key, None)
        progress_bar = st.progress(0)
        status_text = st.empty()

        def progress(value: int, label: str) -> None:
            progress_bar.progress(value)
            status_text.text(label)

        try:
            st.session_state["run_result"] = run_pipeline(
                year, quarter, selected, config, get_serper_keys(), today, progress,
            )
        except Exception:
            logging.getLogger(__name__).exception("Fatal pipeline error")
            st.error("Proses gagal karena kesalahan internal. Periksa konfigurasi atau log aplikasi.")
        finally:
            status_text.empty()
            progress_bar.empty()

    if "run_result" in st.session_state:
        render_results(st.session_state["run_result"])


if __name__ == "__main__":
    app()
